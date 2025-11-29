import os
import sys
import asyncio
from database import db, mongodb_version
from config import Config, temp
from platform import python_version
from translation import Translation
from pyrogram import Client, filters, enums, __version__ as pyrogram_version
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaDocument

# ================= MAIN MENU BUTTONS ================= #
main_buttons = [
    [
        InlineKeyboardButton('🙋‍♂️ ʜᴇʟᴘ', callback_data='help'),
        InlineKeyboardButton('💁‍♂️ ᴀʙᴏᴜᴛ ', callback_data='about')
    ],
    [
        InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs ⚙️', callback_data='settings#main')
    ]
]

#=================== START ===================#
@Client.on_message(filters.private & filters.command(['start']))
async def start(client, message):
    user = message.from_user
    if not await db.is_user_exist(user.id):
        await db.add_user(user.id, user.first_name)

    await client.send_message(
        chat_id=message.chat.id,
        reply_markup=InlineKeyboardMarkup(main_buttons),
        text=Translation.START_TXT.format(message.from_user.first_name)
    )

#=================== RESTART ===================#
@Client.on_message(filters.private & filters.command(['restart']) & filters.user(Config.BOT_OWNER_ID))
async def restart(client, message):
    msg = await message.reply_text("<i>Trying to restarting.....</i>")
    await asyncio.sleep(5)
    await msg.edit("<i>Server restarted successfully ✅</i>")
    os.execl(sys.executable, sys.executable, *sys.argv)

#=================== HELP ===================#
@Client.on_callback_query(filters.regex(r'^help'))
async def helpcb(bot, query):
    await query.message.edit_text(
        text=Translation.HELP_TXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton('ʜᴏᴡ ᴛᴏ ᴜsᴇ ❓', callback_data='how_to_use')],
            [
                InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs ', callback_data='settings#main'),
                InlineKeyboardButton('📜 sᴛᴀᴛᴜs ', callback_data='status')
            ],
            [InlineKeyboardButton('↩ ʙᴀᴄᴋ', callback_data='back')]
        ])
    )

@Client.on_callback_query(filters.regex(r'^how_to_use'))
async def how_to_use(bot, query):
    await query.message.edit_text(
        text=Translation.HOW_USE_TXT,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back', callback_data='help')]]),
        disable_web_page_preview=True
    )

@Client.on_callback_query(filters.regex(r'^back'))
async def back(bot, query):
    await query.message.edit_text(
        reply_markup=InlineKeyboardMarkup(main_buttons),
        text=Translation.START_TXT.format(query.from_user.first_name)
    )

#=================== ABOUT ===================#
@Client.on_callback_query(filters.regex(r'^about'))
async def about(bot, query):
    await query.message.edit_text(
        text=Translation.ABOUT_TXT.format(
            my_name='Public Forward',
            python_version=python_version(),
            pyrogram_version=pyrogram_version,
            mongodb_version=await mongodb_version()
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back', callback_data='back')]]),
        disable_web_page_preview=True,
        parse_mode=enums.ParseMode.HTML,
    )

#=================== STATUS ===================#
@Client.on_callback_query(filters.regex(r'^status'))
async def status(bot, query):
    users_count, bots_count = await db.total_users_bots_count()
    total_channels = await db.total_channels()
    await query.message.edit_text(
        text=Translation.STATUS_TXT.format(
            users_count,
            bots_count,
            temp.forwardings,
            total_channels,
            temp.BANNED_USERS
        ),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back', callback_data='help')]]),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True,
    )

#=================== SETTINGS MENU ===================#
@Client.on_callback_query(filters.regex(r'^settings#main'))
async def settings_main(bot, query):
    user_id = query.from_user.id
    configs = await db.get_configs(user_id)
    filters_list = configs.get('filters', {})

    buttons = [
        [InlineKeyboardButton('📝 Add Filter', callback_data='add_filter')],
        [InlineKeyboardButton('❌ Remove Words', callback_data='remove_words')],
        [InlineKeyboardButton('↩ Back', callback_data='back')]
    ]

    await query.message.edit_text(
        text="⚙️ <b>Settings Menu</b>\n\nCurrent Filters:\n" +
             ("\n".join(filters_list.keys()) if filters_list else "None"),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )

#=================== ADD FILTER (INLINE) ===================#
@Client.on_callback_query(filters.regex(r'^add_filter'))
async def add_filter_inline(bot, query):
    # Predefined words for demonstration; you can customize
    word_buttons = [
        [InlineKeyboardButton("spam", callback_data="addword#spam")],
        [InlineKeyboardButton("ad", callback_data="addword#ad")],
        [InlineKeyboardButton("unsubscribe", callback_data="addword#unsubscribe")],
        [InlineKeyboardButton("↩ Back", callback_data="settings#main")]
    ]
    await query.message.edit_text(
        text="Select a word to add to filters:",
        reply_markup=InlineKeyboardMarkup(word_buttons)
    )

@Client.on_callback_query(filters.regex(r'^addword#'))
async def addword_callback(bot, query):
    word = query.data.split("#")[1]
    user_id = query.from_user.id

    configs = await db.get_configs(user_id)
    filters_list = configs.get('filters', {})
    filters_list[word] = True
    await db.update_configs(user_id, 'filters', filters_list)

    await query.answer(f"✅ '{word}' added to filters.", show_alert=True)
    await settings_main(bot, query)

#=================== REMOVE WORDS ===================#
@Client.on_callback_query(filters.regex(r'^remove_words'))
async def remove_words(bot, query):
    user_id = query.from_user.id
    configs = await db.get_configs(user_id)
    filters_list = configs.get('filters', {})

    if not filters_list:
        await query.message.edit_text(
            "❌ You have no words in your filter list.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩ Back', callback_data='settings#main')]])
        )
        return

    buttons = [[InlineKeyboardButton(f"❌ {word}", callback_data=f"del_word#{word}")] for word in filters_list.keys()]
    buttons.append([InlineKeyboardButton('↩ Back', callback_data='settings#main')])

    await query.message.edit_text(
        text="Select words to remove from your filter:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

#=================== DELETE WORD ===================#
@Client.on_callback_query(filters.regex(r'^del_word#'))
async def del_word(bot, query):
    user_id = query.from_user.id
    word = query.data.split("#")[1]

    configs = await db.get_configs(user_id)
    filters_list = configs.get('filters', {})

    if word in filters_list:
        del filters_list[word]
        await db.update_configs(user_id, 'filters', filters_list)
        await query.answer(f"✅ Removed '{word}' from filters.", show_alert=True)
    else:
        await query.answer(f"⚠️ '{word}' not found.", show_alert=True)

    await remove_words(bot, query)
