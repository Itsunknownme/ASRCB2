import os
import sys
import math
import time
import asyncio
import logging
from .utils import STS, clean_caption # <--- Add clean_caption here
from database import db
from .test import CLIENT, start_clone_bot
from config import Config, temp
from translation import Translation
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CLIENT = CLIENT()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
TEXT = Translation.TEXT


# ───────────────────────────────────────────
# START PUBLIC FORWARDING
# ───────────────────────────────────────────
@Client.on_callback_query(filters.regex(r'^start_public'))
async def start_public(bot, query):
    user_id = query.from_user.id
    temp.CANCEL[user_id] = False

    forward_id = query.data.split("_")[2]

    if temp.lock.get(user_id):
        return await query.answer("Please wait until previous task finishes.", show_alert=True)

    sts = STS(forward_id)
    if not sts.verify():
        await query.answer("This button is no longer active.", show_alert=True)
        return await query.message.delete()

    session = sts.get(full=True)

    # Target chat busy check
    if session.TO in temp.IS_FRWD_CHAT:
        return await query.answer("Target chat is currently busy. Try again later.", show_alert=True)

    msg = await query.message.edit("<code>Checking your data...</code>")
    bot_info, caption, forward_tag, data, protect, buttons = await sts.get_data(user_id)

    if not bot_info:
        return await msg.edit("<code>Please add a bot using /settings first.</code>")

    try:
        client = await start_clone_bot(CLIENT.client(bot_info))
    except Exception as e:
        return await msg.edit(f"<b>Error:</b> <code>{e}</code>")

    # Source access check
    try:
        await client.get_messages(sts.get("FROM"), sts.get("limit"))
    except:
        await msg.edit(
            "**Source chat is restricted. Make your bot an admin or use userbot.**",
            reply_markup=retry_btn(forward_id)
        )
        return await stop(client, user_id)

    # Target access check
    try:
        test_msg = await client.send_message(session.TO, "Checking access…")
        await test_msg.delete()
    except:
        await msg.edit(
            "**Bot/Userbot is not admin in target chat. Please grant admin rights.**",
            reply_markup=retry_btn(forward_id)
        )
        return await stop(client, user_id)

    # Start forwarding
    temp.forwardings += 1
    temp.IS_FRWD_CHAT.append(session.TO)
    temp.lock[user_id] = True
    await db.add_frwd(user_id)

    await send(client, user_id, "<b>🚀 Forwarding Started</b>")
    sts.add(time=True)

    await msg_edit(msg, "<code>Processing…</code>")

    sleep_time = 1 if bot_info["is_bot"] else 10

    # ───────────────────────────────────────────
    # FORWARDING LOOP
    # ───────────────────────────────────────────
    try:
        queued_messages = []
        count = 0

        async for item in client.iter_messages(
            client,
            chat_id=sts.get('FROM'),
            limit=int(sts.get('limit')),
            offset=int(sts.get('skip')) if sts.get('skip') else 0
        ):
            if await is_cancelled(client, user_id, msg, sts):
                return

            if count % 20 == 0:
                await edit_progress(msg, 'Forwarding', 10, sts)
            count += 1

            sts.add('fetched')

            # Filters
            if item in ["DUPLICATE", "FILTERED"]:
                sts.add('filtered')
                continue

            if item.empty or item.service:
                sts.add('deleted')
                continue

            # Forward with tag
            if forward_tag:
                queued_messages.append(item.id)
                remaining = sts.get('total') - sts.get('fetched')

                if len(queued_messages) >= 100 or remaining <= 100:
                    await forward(client, queued_messages, msg, sts, protect)
                    sts.add('total_files', len(queued_messages))
                    queued_messages = []
                    await asyncio.sleep(10)

           # ... (inside start_public) ...

            else:
                # 1. Generate the base caption using the existing custom function
                base_caption = custom_caption(item, caption)
                
                # 2. 🚨 NEW: Clean the caption by removing configured words
                cleaned_caption = await clean_caption(user_id, base_caption)
                
                info = {
                    "msg_id": item.id,
                    "media": media(item),
                    # 3. Use the cleaned caption for forwarding
                    "caption": cleaned_caption, 
                    "button": buttons,
                    "protect": protect,
                }
                await copy_message(client, info, msg, sts)
                sts.add('total_files')
                await asyncio.sleep(sleep_time)

# ...


    except Exception as e:
        await msg_edit(msg, f"<b>Error:</b>\n<code>{e}</code>", wait=True)
        temp.IS_FRWD_CHAT.remove(session.TO)
        return await stop(client, user_id)

    temp.IS_FRWD_CHAT.remove(session.TO)
    await send(client, user_id, "<b>✅ Forwarding Completed Successfully</b>")
    await edit_progress(msg, "Completed", "completed", sts)
    await stop(client, user_id)


# ───────────────────────────────────────────
# HELPER: COPY MESSAGE
# ───────────────────────────────────────────
async def copy_message(client, msg, callback, sts):
    try:
        if msg["media"] and msg["caption"]:
            await client.send_cached_media(
                chat_id=sts.get('TO'),
                file_id=msg["media"],
                caption=msg["caption"],
                reply_markup=msg["button"],
                protect_content=msg["protect"]
            )
        else:
            await client.copy_message(
                chat_id=sts.get('TO'),
                from_chat_id=sts.get('FROM'),
                message_id=msg["msg_id"],
                caption=msg["caption"],
                reply_markup=msg["button"],
                protect_content=msg["protect"]
            )
    except FloodWait as e:
        await edit_progress(callback, "Sleeping", e.value, sts)
        await asyncio.sleep(e.value)
        return await copy_message(client, msg, callback, sts)
    except:
        sts.add('deleted')


# ───────────────────────────────────────────
# HELPER: FORWARD BULK
# ───────────────────────────────────────────
async def forward(client, msg_ids, callback, sts, protect):
    try:
        await client.forward_messages(
            chat_id=sts.get('TO'),
            from_chat_id=sts.get('FROM'),
            message_ids=msg_ids,
            protect_content=protect
        )
    except FloodWait as e:
        await edit_progress(callback, "Sleeping", e.value, sts)
        await asyncio.sleep(e.value)
        await forward(client, msg_ids, callback, sts, protect)


# ───────────────────────────────────────────
# EDIT PROGRESS MESSAGE
# ───────────────────────────────────────────
async def msg_edit(msg, text, button=None, wait=None):
    try:
        return await msg.edit(text, reply_markup=button)
    except MessageNotModified:
        pass
    except FloodWait as e:
        if wait:
            await asyncio.sleep(e.value)
            return await msg_edit(msg, text, button, wait)


async def edit_progress(msg, title, status, sts):
    data = sts.get(full=True)
    percentage = "{:.0f}".format(float(data.fetched) * 100 / float(data.total))

    now = time.time()
    elapsed = now - data.start
    speed = sts.divide(data.fetched, elapsed)
    eta_ms = round(sts.divide(data.total - data.fetched, int(speed)) * 1000)

    progress_bar = "◉" * (int(int(percentage) / 10)) + "◎" * (10 - int(int(percentage) / 10))

    button = [
        [InlineKeyboardButton(title, f'fwrdstatus#{status}#{eta_ms}#{percentage}#{data.id}')]
    ]

    if status in ["completed", "cancelled"]:
        button.append([InlineKeyboardButton("Close", callback_data="close_btn")])
    else:
        button.append([InlineKeyboardButton("Cancel", callback_data="terminate_frwd")])

    text = TEXT.format(
        data.fetched, data.total_files, data.duplicate, data.deleted,
        data.skip, status, percentage, TimeFormatter(eta_ms), progress_bar
    )

    await msg_edit(msg, text, InlineKeyboardMarkup(button))


# ───────────────────────────────────────────
# CANCEL FORWARD
# ───────────────────────────────────────────
@Client.on_callback_query(filters.regex(r'^terminate_frwd$'))
async def terminate_forward(bot, cb):
    user_id = cb.from_user.id
    temp.lock[user_id] = False
    temp.CANCEL[user_id] = True
    await cb.answer("Forwarding cancelled!", show_alert=True)


# ───────────────────────────────────────────
# STATUS POPUP
# ───────────────────────────────────────────
@Client.on_callback_query(filters.regex(r'^fwrdstatus'))
async def status_popup(bot, query):
    _, status, eta_ms, pct, forward_id = query.data.split("#")
    sts = STS(forward_id)

    if not sts.verify():
        fetched = forwarded = remaining = 0
    else:
        fetched = sts.get("fetched")
        forwarded = sts.get("total_files")
        remaining = fetched - forwarded

    eta = TimeFormatter(int(eta_ms))

    text = (
        f"📊 <b>Status:</b> {status}\n"
        f"📈 <b>Progress:</b> {pct}%\n"
        f"📥 <b>Fetched:</b> {fetched}\n"
        f"📤 <b>Forwarded:</b> {forwarded}\n"
        f"⏳ <b>Remaining:</b> {remaining}\n"
        f"⏱️ <b>ETA:</b> {eta}"
    )

    await query.answer(text, show_alert=True)


# ───────────────────────────────────────────
# CLOSE BUTTON
# ───────────────────────────────────────────
@Client.on_callback_query(filters.regex(r'^close_btn$'))
async def close_message(bot, cb):
    await cb.message.delete()


# ───────────────────────────────────────────
# STOP
# ───────────────────────────────────────────
async def stop(client, user):
    try:
        await client.stop()
    except:
        pass

    await db.rmve_frwd(user)
    temp.forwardings -= 1
    temp.lock[user] = False


# ───────────────────────────────────────────
# SMALL HELPERS
# ───────────────────────────────────────────
async def send(bot, user, text):
    try:
        await bot.send_message(user, text=text)
    except:
        pass


def custom_caption(msg, caption):
    if msg.media:
        media = getattr(msg, msg.media.value, None)
        if media:
            file_name = getattr(media, "file_name", "")
            file_size = getattr(media, "file_size", "")
            original_caption = msg.caption.html if msg.caption else ""

            if caption:
                return caption.format(
                    filename=file_name,
                    size=get_size(file_size),
                    caption=original_caption
                )
            return original_caption
    return None


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB"]
    size = float(size)
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"


def media(msg):
    if msg.media:
        media = getattr(msg, msg.media.value, None)
        return getattr(media, "file_id", None)
    return None


def TimeFormatter(ms: int) -> str:
    seconds, ms = divmod(int(ms), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    text = ""
    if days: text += f"{days}d "
    if hours: text += f"{hours}h "
    if minutes: text += f"{minutes}m "
    if seconds: text += f"{seconds}s "

    return text.strip() or "0s"


def retry_btn(frwd_id):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Retry", f"start_public_{frwd_id}")]]
    )
