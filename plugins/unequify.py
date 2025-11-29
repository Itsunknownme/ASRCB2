import re, asyncio
from database import db
from config import temp
from .test import CLIENT, start_clone_bot
from translation import Translation
from pyrogram import Client, filters
# from pyropatch.utils import unpack_new_file_id
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CLIENT = CLIENT()

# Removed support + update buttons
COMPLETED_BTN = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton('Close', callback_data='close_btn')]
    ]
)

CANCEL_BTN = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton('Cancel', callback_data='terminate_frwd')]
    ]
)

@Client.on_message(filters.command("unequify") & filters.private)
async def unequify(client, message):
    user_id = message.from_user.id
    temp.CANCEL[user_id] = False

    if temp.lock.get(user_id) and str(temp.lock.get(user_id)) == "True":
        return await message.reply("**Please wait until previous task completes.**")

    _bot = await db.get_bot(user_id)
    if not _bot or _bot['is_bot']:
        return await message.reply("<b>Userbot required. Please add a userbot using /settings</b>")

    target = await client.ask(
        user_id,
        text="**Forward the last message from target chat or send last message link.**\n/cancel - `cancel process`"
    )

    if target.text.startswith("/"):
        return await message.reply("**Process cancelled!**")

    elif target.text:
        regex = re.compile(
            r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$"
        )
        match = regex.match(target.text.replace("?single", ""))

        if not match:
            return await message.reply('**Invalid link**')

        chat_id = match.group(4)
        last_msg_id = int(match.group(5))

        if chat_id.isnumeric():
            chat_id = int("-100" + chat_id)

    elif target.forward_from_chat and target.forward_from_chat.type in ['channel', 'supergroup']:
        last_msg_id = target.forward_from_message_id
        chat_id = target.forward_from_chat.username or target.forward_from_chat.id

    else:
        return await message.reply_text("**Invalid!**")

    confirm = await client.ask(
        user_id,
        text="**Send /yes to start the process or /no to cancel**"
    )

    if confirm.text.lower() == '/no':
        return await confirm.reply("**Process cancelled!**")

    sts = await confirm.reply("`Processing..`")

    try:
        bot = await start_clone_bot(CLIENT.client(_bot))
    except Exception as e:
        return await sts.edit(e)

    try:
        k = await bot.send_message(chat_id, "testing")
        await k.delete()
    except:
        await sts.edit(
            f"**Please make your userbot admin in target chat with full permissions**"
        )
        return await bot.stop()

    MESSAGES = []
    DUPLICATE = []
    total = deleted = 0
    temp.lock[user_id] = True

    try:
        await sts.edit(
            Translation.DUPLICATE_TEXT.format(total, deleted, "Processing"),
            reply_markup=CANCEL_BTN
        )

        async for msg in bot.search_messages(chat_id=chat_id, filter="document"):

            if temp.CANCEL.get(user_id) == True:
                await sts.edit(
                    Translation.DUPLICATE_TEXT.format(total, deleted, "Cancelled"),
                    reply_markup=COMPLETED_BTN
                )
                return await bot.stop()

            file = msg.document
            file_id = unpack_new_file_id(file.file_id)

            if file_id in MESSAGES:
                DUPLICATE.append(msg.id)
            else:
                MESSAGES.append(file_id)

            total += 1

            if total % 10000 == 0:
                await sts.edit(
                    Translation.DUPLICATE_TEXT.format(total, deleted, "Processing"),
                    reply_markup=CANCEL_BTN
                )

            if len(DUPLICATE) >= 100:
                await bot.delete_messages(chat_id, DUPLICATE)
                deleted += 100
                DUPLICATE = []

                await sts.edit(
                    Translation.DUPLICATE_TEXT.format(total, deleted, "Processing"),
                    reply_markup=CANCEL_BTN
                )

        if DUPLICATE:
            await bot.delete_messages(chat_id, DUPLICATE)
            deleted += len(DUPLICATE)

    except Exception as e:
        temp.lock[user_id] = False
        await sts.edit(f"**ERROR**\n`{e}`")
        return await bot.stop()

    temp.lock[user_id] = False
    await sts.edit(
        Translation.DUPLICATE_TEXT.format(total, deleted, "Completed"),
        reply_markup=COMPLETED_BTN
    )
    await bot.stop()
