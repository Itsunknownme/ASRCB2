import os
import sys
import asyncio 
from database import db, mongodb_version
from config import Config, temp
from platform import python_version
from translation import Translation
from pyrogram import Client, filters, enums, __version__ as pyrogram_version
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaDocument

# MAIN MENU BUTTONS (CLEAN – NO CHANNEL/GROUP BUTTON)
main_buttons = [[
        InlineKeyboardButton('🙋‍♂️ ʜᴇʟᴘ', callback_data='help'),
        InlineKeyboardButton('💁‍♂️ ᴀʙᴏᴜᴛ ', callback_data='about')
    ],[
        InlineKeyboardButton('⚙️ sᴇᴛᴛɪɴɢs ⚙️', callback_data='settings#main')
    ]
]

#=================== Start ===================#

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

#=================== Restart ===================#

@Client.on_message(filters.private & filters.command(['restart']) & filters.user(Config.BOT_OWNER_ID))
async def restart(client, message):
    msg = await message.reply_text("<i>Trying to restarting.....</i>")
    await asyncio.sleep(5)
    await msg.edit("<i>Server restarted successfully ✅</i>")
    os.execl(sys.executable, sys.executable, *sys.argv)

# ... (Existing imports and functions above) ...

# ================== NEW: REMOVE WORDS SETTINGS ==================#

# Dictionary to hold user IDs currently setting their words
# Ensure you define 'SETTING_WORDS = {}' in your config.py/temp module if not already done.
if not hasattr(temp, 'SETTING_WORDS'):
    temp.SETTING_WORDS = {}


@Client.on_message(filters.private & filters.command(['setwords']))
async def set_words_prompt(client, message):
    user_id = message.from_user.id
    
    # Check current settings
    current_words = await db.get_remove_words(user_id)
    words_str = ", ".join(current_words) if current_words else "None"

    text = (
        "✍️ **Remove Words Setup**\n\n"
        "Please reply to this message with a **comma-separated list** of words "
        "you want to automatically remove from forwarded captions.\n\n"
        "**Example:** `chatgpt, zydickc, subscribe, promo`\n\n"
        f"**Currently set words:** `{words_str}`\n\n"
        "To clear the list, reply with the word `CLEAR`."
    )
    
    # Store user ID to capture the next message as the word list
    temp.SETTING_WORDS[user_id] = True
    
    await message.reply_text(text)


@Client.on_message(filters.private & filters.text & filters.reply)
async def set_remove_words_handler(client, message):
    user_id = message.from_user.id
    
    # Check if this message is a reply to the /setwords prompt
    if user_id in temp.SETTING_WORDS and message.reply_to_message:
        
        # Check if it's replying to the prompt message (using simple text check)
        if message.reply_to_message.text and "Remove Words Setup" in message.reply_to_message.text:
            
            input_text = message.text.strip().lower()

            if input_text == "clear":
                new_words = []
                response_text = "🗑️ **Success!** The list of words to remove has been **cleared**."
            else:
                # Split the text by comma, clean up spaces, and filter out empty strings
                new_words = [
                    word.strip() for word in input_text.split(',') 
                    if word.strip()
                ]

                # Save the words in the database
                await db.set_remove_words(user_id, new_words)
                
                if new_words:
                    words_str = ", ".join(new_words)
                    response_text = (
                        "✅ **Words to Remove Updated!**\n\n"
                        "The following words will now be removed from forwarded captions:\n"
                        f"`{words_str}`"
                    )
                else:
                    response_text = "⚠️ You didn't provide any valid words. The list remains unchanged."
            
            # Finalize the process
            del temp.SETTING_WORDS[user_id]
            
            await message.reply_text(response_text, reply_to_message_id=message.id)
            return

# ... (Existing functions below) ...


#================== Help ==================#

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

#================== About ==================#

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

#================== Status ==================#

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
