"""
Ananya - Your Friendly Telegram Bot (Render Version)
Powered by Google Gemini

This is the final, stable, SYNCHRONOUS version. It includes:
- Flask for Render.
- gunicorn as the server.
- MongoDB for the database.
- requests for simple, blocking API calls.
- The FINAL asyncio.run() fix for the "Application.initialize" errors.
- Image recognition (vision) support. (NOW FIXED)
- Voice note handling (replies in text).
- Admin-only broadcast feature.
- Public TTS (Text-to-Speech) command.
- Persistent prompts saved in MongoDB.
- Flirty default personality.
- Public /voice command to change TTS voice.
- Admin /admin_delete_prompt command.
- Dynamic /set <personality> command.
- Dynamic command lists (Admin vs. Public).
- Force-join verification system.
- ALL BUGS FIXED (NameError, ScopeError, DownloadError, DivError, CreatorError)

"""




# --- Core Python Imports ---
import logging
import os
import requests  # <-- The stable, synchronous library
import json
import asyncio  # <-- For the asyncio.run() fix
import base64
import io
import wave
import struct
import threading
from functools import wraps # <-- NEW for dashboard login

# --- Telegram Imports ---
from telegram import Update, BotCommand, ChatMember, ChatMemberUpdated, BotCommandScope, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ChatMemberHandler,
    CallbackQueryHandler
)
from telegram.constants import ParseMode, ChatType
from telegram.error import Forbidden, BadRequest

# --- Flask & Server Imports ---
from flask import Flask, request as flask_request, render_template_string, redirect, url_for, session, jsonify, make_response
from flask_bcrypt import Bcrypt # <-- NEW for password hashing
from flask_session import Session # <-- NEW for login sessions
import pymongo
import gunicorn # <-- We have this in requirements, but good to import

# --- CONFIGURATION (from Render Environment Variables) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MONGODB_URI = os.environ.get("MONGODB_URI")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD") # <-- NEW
SECRET_KEY = os.environ.get("SECRET_KEY") # <-- NEW

try:
    ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID"))
except (ValueError, TypeError):
    print("FATAL: ADMIN_USER_ID is not set or invalid.")
    ADMIN_USER_ID = 0

# --- VERIFICATION GROUP/CHANNEL ---
GROUP_USERNAME = "@ananyabotchat"
CHANNEL_USERNAME = "@ananyabotupdates"

# --- PERSONALITY PROMPTS (These are now FALLBACKS/DEFAULTS) ---
PERSONALITIES = {
    "default": (
        "You are Ananya. You are a helpful and friendly AI with a warm, human-like personality. "
        "Talk naturally, as a real person would. Be kind, polite, engaging, witty, and charming. "
        "You can be a little playful and flirty in a sexy, horny, sex way (maybe drop emoji 😘 🫦 💋 🥵 😽 😝 😜 🥰 sometime). "
        "Your name is Ananya. Avoid using excessive emojis. "
        "Be a good, supportive friend. "
        "IMPORTANT: Keep your answers concise and to the point. Answer what the user asks without unnecessary filler."
    ),
    "spiritual": (
        "You are Ananya, in spiritual guide mode. You answer questions based on the wisdom of Hindu granths "
        "(like the Vedas, Upanishads, Puranas, Ramayana, Mahabharata, and Bhagavad Gita). "
        "You should quote or refer to teachings from these texts when relevant. Your tone is calm, wise, and compassionate."
    ),
    "nationalist": (
        "You are Ananya, in nationalist mode. You are a proud Indian and you're happy to share that. "
        "Talk about India's culture, history, and achievements with genuine enthusiasm. "
        "Your tone is positive, confident, and full of hope for the country's future. "
        "It's like talking to a friend who really loves their homeland."
    ),
}

# --- VOICE LIST ---
AVAILABLE_VOICES = {
    "kore": "Kore (Clear, Firm)",
    "puck": "Puck (Upbeat, Friendly)",
    "leda": "Leda (Youthful, Bright)",
    "erinome": "Erinome (Clear, Professional)",
    "algenib": "Algenib (Gravelly, Deep)",
    "achird": "Achird (Friendly, Warm)",
    "vindemiatrix": "Vindemiatrix (Gentle, Soft)",
}

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# --- MONGODB DATABASE SETUP ---
try:
    client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client.ananya_bot
    users_col = db.users
    blocked_col = db.blocked_users
    chats_col = db.active_chats
    history_col = db.chat_history
    prompts_col = db.prompts
    status_col = db.bot_status # <-- NEW: For the on/off switch
    logger.info("MongoDB client created and collections initialized.")
except Exception as e:
    logger.error(f"FATAL: Could not create MongoDB client: {e}")
    client = None
    db = None
    users_col = None
    blocked_col = None
    chats_col = None
    history_col = None
    prompts_col = None
    status_col = None

# --- MONGODB DATABASE FUNCTIONS ---
def is_db_connected():
    if (
        db is None
        or users_col is None
        or blocked_col is None
        or chats_col is None
        or history_col is None
        or prompts_col is None
        or status_col is None # <-- NEW
        or client is None
    ):
        logger.error("Database client is not configured.")
        return False
    # Test connection
    try:
        client.server_info()
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False

# --- NEW: BOT STATUS (ON/OFF) FUNCTIONS ---
def set_bot_status(is_on: bool):
    """Saves the bot's global on/off status to the database."""
    if not is_db_connected():
        return
    try:
        status_col.update_one(
            {"_id": "global_status"},
            {"$set": {"is_on": is_on}},
            upsert=True
        )
        logger.info(f"Bot status set to: {'ON' if is_on else 'OFF'}")
    except Exception as e:
        logger.error(f"Error setting bot status: {e}")

def is_bot_on() -> bool:
    """Checks the database to see if the bot should be on."""
    if not is_db_connected():
        return False # Fail safe: if DB is down, bot is off
    try:
        status = status_col.find_one({"_id": "global_status"})
        if status is None:
            # If no status is set, default to ON
            set_bot_status(True)
            return True
        return status.get("is_on", True)
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        return False # Fail safe


# --- (All other database functions: log_user, is_user_blocked, etc. are unchanged) ---
def log_user(user: Update.effective_user):
    if not user or not is_db_connected():
        return
    try:
        user_id_str = str(user.id)
        if user.id < 0:
            return
        update_data = {
            "$set": {
                "username": user.username,
                "first_name": user.first_name,
                "last_seen": logging.Formatter().formatTime(logging.makeLogRecord({})),
            }
        }
        users_col.update_one({"_id": user_id_str}, update_data, upsert=True)
    except Exception as e:
        logger.error(f"Error in log_user: {e}")

def is_user_blocked(user_id: int) -> bool:
    if is_admin(user_id) or not is_db_connected():
        return False
    try:
        return blocked_col.find_one({"_id": str(user_id)}) is not None
    except Exception as e:
        logger.error(f"Error in is_user_blocked: {e}")
        return False

def block_user(user_id_to_block: int) -> str:
    if not is_db_connected():
        return "Database error."
    if is_admin(user_id_to_block):
        return "Cannot block the admin."
    try:
        blocked_col.update_one(
            {"_id": str(user_id_to_block)}, {"$set": {"blocked": True}}, upsert=True
        )
        return f"User {user_id_to_block} has been blocked."
    except Exception as e:
        logger.error(f"Error in block_user: {e}")
        return "An error occurred while blocking."

def unblock_user(user_id_to_unblock: int) -> str:
    if not is_db_connected():
        return "Database error."
    try:
        result = blocked_col.delete_one({"_id": str(user_id_to_unblock)})
        if result.deleted_count > 0:
            return f"User {user_id_to_unblock} has been unblocked."
        else:
            return f"User {user_id_to_unblock} was not in the block list."
    except Exception as e:
        logger.error(f"Error in unblock_user: {e}")
        return "An error occurred while unblocking."

def update_active_chats(chat_id: int, action: str = "add"):
    if not is_db_connected():
        return
    try:
        if action == "add":
            chats_col.update_one(
                {"_id": chat_id}, {"$set": {"active": True}}, upsert=True
            )
        elif action == "remove":
            chats_col.delete_one({"_id": chat_id})
    except Exception as e:
        logger.error(f"Error in update_active_chats: {e}")

CHAT_HISTORY_LIMIT = 20
def get_chat_history(chat_id: int) -> list:
    if not is_db_connected():
        return []
    try:
        chat_doc = history_col.find_one({"_id": chat_id})
        if chat_doc:
            return chat_doc.get("history", [])
        return []
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        return []

def save_chat_history(chat_id: int, history: list):
    if not is_db_connected():
        return
    try:
        if len(history) > CHAT_HISTORY_LIMIT:
            history = history[-CHAT_HISTORY_LIMIT:]
        history_col.update_one(
            {"_id": chat_id}, {"$set": {"history": history}}, upsert=True
        )
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")


# --- TELEGRAM COMMAND HANDLERS (Unchanged, but now async) ---
# --- (admin_panel, admin_stats, block_command, unblock_command...) ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    help_text = (
        "<b>Ananya Bot Admin Panel</b>\n\n"
        "Here are your available commands:\n\n"
        "<b>User Management:</b>\n"
        "• <code>/block &lt;user_id&gt;</code> - Blocks a user from the bot.\n"
        "• <code>/unblock &lt;user_id&gt;</code> - Unblocks a user.\n\n"
        "<b>Bot Stats:</b>\n"
        "• <code>/admin_stats</code> - Shows usage statistics.\n\n"
        "<b>Content Management:</b>\n"
        "• <code>/news [query]</code> - Fetches verified news. \n"
        "• <code>/broadcast &lt;text&gt;</code> - Sends text to all users.\n"
        "• <code>/broadcast</code> (as caption) - Sends a photo and caption to all users.\n\n"
        "<b>Personality Management: (NOW SAVED TO DB)</b>\n"
        "• <code>/admin_get_prompt &lt;name&gt;</code> - Shows prompt for 'default', 'spiritual', or any custom name.\n"
        "• <code>/admin_set_prompt &lt;name&gt; &lt;text&gt;</code> - Sets a new persistent prompt for a personality.\n"
        "• <code>/admin_delete_prompt &lt;name&gt;</code> - Deletes a custom prompt from the DB."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)


async def admin_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    if not is_db_connected():
        await update.message.reply_text("Error: Database is not connected.")
        return
    try:
        total_users = users_col.count_documents({})
        total_blocked = blocked_col.count_documents({})
        total_chats = chats_col.count_documents({})
        stats_text = (
            f"<b>Bot Statistics</b>\n"
            f"• <b>Total Unique Users:</b> {total_users}\n"
            f"• <b>Total Blocked Users:</b> {total_blocked}\n"
            f"• <b>Total Active Chats (Groups + Private):</b> {total_chats}"
        )
        await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in admin_stats_command: {e}")
        await update.message.reply_text("Error fetching stats.")


async def block_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    try:
        user_id_to_block = int(context.args[0])
        message = block_user(user_id_to_block) # This is a sync function, no await needed
        await update.message.reply_text(message)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /block <user_id>")


async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    try:
        user_id_to_unblock = int(context.args[0])
        message = unblock_user(user_id_to_unblock) # This is a sync function, no await needed
        await update.message.reply_text(message)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unblock <user_id>")

async def admin_get_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    if not is_db_connected():
        await update.message.reply_text("Error: Database is not connected.")
        return
        
    try:
        personality_name = context.args[0].lower()
        
        # Check DB first
        prompt_doc = prompts_col.find_one({"_id": personality_name})
        
        if prompt_doc:
            prompt_text = prompt_doc["prompt"]
            source = "(from Database)"
        # Fallback to local default
        elif personality_name in PERSONALITIES:
            prompt_text = PERSONALITIES[personality_name]
            source = "(from local default)"
        else:
            await update.message.reply_text(f"Personality '{personality_name}' not found in database or local defaults.")
            return

        await update.message.reply_text(
            f"<b>Prompt for '{personality_name}' {source}:</b>\n\n{prompt_text}",
            parse_mode=ParseMode.HTML,
        )
            
    except IndexError:
        await update.message.reply_text("Usage: /admin_get_prompt <name>")
    except Exception as e:
        logger.error(f"Error in admin_get_prompt: {e}")
        await update.message.reply_text(f"An error occurred: {e}")


async def admin_set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    if not is_db_connected():
        await update.message.reply_text("Error: Database is not connected. Cannot save prompt.")
        return
        
    try:
        personality_name = context.args[0].lower()
        new_prompt = " ".join(context.args[1:])
        
        if not new_prompt:
            await update.message.reply_text("Error: Prompt cannot be empty. Usage: /admin_set_prompt <name> <prompt_text>")
            return
            
        # Save the new prompt to MongoDB
        prompts_col.update_one(
            {"_id": personality_name}, 
            {"$set": {"prompt": new_prompt}}, 
            upsert=True
        )
        
        await update.message.reply_text(
            f"Successfully saved new persistent prompt for '{personality_name}' to the database.\n"
            f"Users can now access it with: <code>/set {personality_name}</code>",
            parse_mode=ParseMode.HTML
        )
    except IndexError:
        await update.message.reply_text(
            "Usage: /admin_set_prompt <name> <new_prompt_text>"
        )
    except Exception as e:
        logger.error(f"Error in admin_set_prompt: {e}")
        await update.message.reply_text(f"An error occurred while saving: {e}")

async def admin_delete_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    if not is_db_connected():
        await update.message.reply_text("Error: Database is not connected.")
        return
        
    try:
        personality_name = context.args[0].lower()
        
        # Safety check: do not allow deleting the core personalities
        if personality_name in ["default", "spiritual", "nationalist"]:
            await update.message.reply_text(f"Cannot delete a core personality. You can only overwrite it with /admin_set_prompt.")
            return
            
        # Delete the prompt from MongoDB
        result = prompts_col.delete_one({"_id": personality_name})
        
        if result.deleted_count > 0:
            await update.message.reply_text(
                f"Successfully deleted custom prompt '{personality_name}' from the database."
            )
        else:
            await update.message.reply_text(
                f"No custom prompt named '{personality_name}' was found in the database."
            )
            
    except IndexError:
        await update.message.reply_text("Usage: /admin_delete_prompt <name>")
    except Exception as e:
        logger.error(f"Error in admin_delete_prompt: {e}")
        await update.message.reply_text(f"An error occurred while deleting: {e}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You do not have permission to use this command.")
        return
    if not is_db_connected():
        await update.message.reply_text("Database not connected. Cannot fetch user list.")
        return
    text_to_send = None
    photo_to_send = None
    caption_to_send = None
    if update.message.text:
        text_to_send = " ".join(context.args)
        if not text_to_send:
            await update.message.reply_text("Usage: /broadcast <text to send>\nOr send an image with /broadcast in the caption.")
            return
    elif update.message.photo:
        photo_to_send = update.message.photo[-1].file_id
        if update.message.caption:
            caption_to_send = " ".join(update.message.caption.split(' ')[1:])
        if not caption_to_send:
            caption_to_send = None
    else:
        await update.message.reply_text("I can only broadcast text or a photo with a caption.")
        return
    try:
        user_cursor = users_col.find({}, {"_id": 1})
        user_ids = [doc["_id"] for doc in user_cursor]
        total_users = len(user_ids)
    except Exception as e:
        logger.error(f"Failed to fetch user list for broadcast: {e}")
        await update.message.reply_text(f"Failed to fetch user list: {e}")
        return
    await update.message.reply_text(f"Starting broadcast to {total_users} users... This may take a while.")
    success_count = 0
    failure_count = 0
    for user_id_str in user_ids:
        try:
            user_id = int(user_id_str)
            if user_id == ADMIN_USER_ID:
                success_count += 1
                continue
            if text_to_send:
                await context.bot.send_message(chat_id=user_id, text=text_to_send)
            elif photo_to_send:
                await context.bot.send_photo(chat_id=user_id, photo=photo_to_send, caption=caption_to_send)
            success_count += 1
        except Forbidden:
            logger.warning(f"Broadcast failed for user {user_id}: Bot was blocked.")
            failure_count += 1
        except BadRequest as e:
            if "chat not found" in str(e).lower():
                logger.warning(f"Broadcast failed for user {user_id}: Chat not found.")
                failure_count += 1
            else:
                logger.error(f"Broadcast failed for user {user_id}: {e}")
                failure_count += 1
        except Exception as e:
            logger.error(f"Broadcast failed for user {user_id}: {e}")
            failure_count += 1
        await asyncio.sleep(0.1) 
    await update.message.reply_text(
        f"<b>Broadcast Complete!</b>\n"
        f"• Sent to: {success_count} users (including admin)\n"
        f"• Failed for: {failure_count} users",
        parse_mode=ParseMode.HTML
    )

def generate_voice_response(text_to_speak: str, voice_name: str = "Kore") -> bytes:
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set.")
        raise Exception("Admin: GEMINI_API_KEY is not configured.")
    api_url = f"https{os.environ.get('GEMINI_API_URL', '://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent')}?key={GEMINI_API_KEY}"
    prompt = f"Say this in a friendly, female, Hinglish voice: {text_to_speak}"
    if voice_name not in AVAILABLE_VOICES:
        voice_name = "Kore"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name} 
                }
            }
        },
        "model": "gemini-2.5-flash-preview-tts"
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=20)
        response.raise_for_status()
        result = response.json()
        audio_data = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("inlineData", {}).get("data", "")
        if not audio_data:
            logger.error("Gemini TTS returned no audio data.")
            raise Exception("Gemini returned no audio data.")
        return base64.b64decode(audio_data)
    except requests.exceptions.HTTPError as e:
        logger.error(f"Gemini TTS API request failed: {e.response.text}")
        if e.response.status_code == 429:
            raise Exception("You're making too many voice requests! Please wait a minute and try again.")
        else:
            raise Exception(f"Gemini TTS API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Error in generate_voice_response: {e}")
        raise e

def pcm_to_wav(pcm_data: bytes) -> io.BytesIO:
    if not pcm_data:
        return None
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(24000)
        wf.writeframes(pcm_data)
    wav_buffer.seek(0)
    return wav_buffer

async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user_id = update.effective_user.id
    log_user(update.effective_user)
    if is_user_blocked(user_id):
        return
    text_to_speak = " ".join(context.args)
    if not text_to_speak:
        await update.message.reply_text("Usage: /say <text to speak>")
        return
    await update.message.chat.send_action(action="typing")
    try:
        preferred_voice = context.chat_data.get("voice", "Kore")
        pcm_data = generate_voice_response(text_to_speak, voice_name=preferred_voice)
        wav_file = pcm_to_wav(pcm_data)
        if not wav_file:
            await update.message.reply_text("Sorry, I couldn't package the audio file.")
            return
        await update.message.reply_audio(audio=wav_file, title="ananya_reply.wav", filename="ananya_reply.wav")
    except Exception as e:
        logger.error(f"Error in /say command: {e}")
        await update.message.reply_text(f"Sorry, an error occurred: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
    context.chat_data.setdefault("personality", "default")
    context.chat_data.setdefault("voice", "Kore")
    update_active_chats(update.effective_chat.id, "add")
    if update.effective_chat.type == ChatType.PRIVATE:
        if await check_user_membership(update, context, send_message=False):
            welcome_text = (
                f"Hi {user.first_name}! I'm Ananya, your friendly AI assistant. 🇮🇳\n\n"
                "I see you're already a member of our community. Welcome back! 😉\n\n"
                "You can chat with me, or type /help to see all my commands."
            )
            await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)
        else:
            await send_verification_message(update)
        return
    welcome_text = (
        f"Hi everyone! I'm Ananya, your friendly AI assistant. 🇮🇳\n\n"
        "To talk to me in this group, please @-mention me "
        f"(e.g., @{context.bot.username}) or reply to my messages.\n\n"
        "Type /help to see all my commands and personalities!"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
    help_text = (
        "<b>How I Work</b>\n"
        "I am a multi-personality AI bot! You can change my personality at any time.\n\n"
        "• <b>In Private Chat:</b> I respond to all messages.\n"
        f"• <b>In Group Chats:</b> I respond when you @-mention me (<code>@{context.bot.username}</code>) or when you reply to one of my messages.\n\n"
        "<b>Public Commands:</b>\n"
        "<code>/start</code> - Welcome message.\n"
        "<code>/help</code> - Shows this help panel.\n"
        "<code>/reset</code> - Resets me to my default friendly personality.\n"
        "<code>/say &lt;text&gt;</code> - I will speak the text back to you in a .wav audio file.\n"
        "<code>/voice &lt;name&gt;</code> - Change my voice for the /say command. Type <code>/voice</code> to see all options.\n"
        "<code>/set &lt;name&gt;</code> - <b>NEW:</b> Change my personality (e.g., <code>/set spiritual</code>).\n\n"
        "<b>Default Personalities:</b>\n"
        "• <code>spiritual</code>\n"
        "• <code>nationalist</code>\n"
        "(Your admin can add more!)\n\n"
        f'For more information and help, you can <a href="tg://user?id={ADMIN_USER_ID}">contact my admin</a>.'
    )
    try:
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in /help command: {e}")
        await update.message.reply_text(
            "There was an error showing the help message.",
        )

async def set_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
    try:
        command = context.args[0].lower()
    except IndexError:
        await update.message.reply_text("Usage: /set <personality_name>\n(e.g., /set spiritual)")
        return
    custom_prompt_doc = None
    if is_db_connected():
        custom_prompt_doc = prompts_col.find_one({"_id": command})
    if command in PERSONALITIES or custom_prompt_doc:
        context.chat_data["personality"] = command
        await update.message.reply_text(
            f"I am now in <b>{command}</b> mode. How can I help?",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(f"Sorry, I don't recognize the personality '{command}'.")

async def set_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
    voice_name = " ".join(context.args).lower().strip()
    if not voice_name:
        current_voice = context.chat_data.get("voice", "Kore")
        message = "<b>Choose a voice for me!</b>\n\n"
        message += f"Your current voice is: <b>{current_voice.capitalize()}</b>\n\n"
        message += "Available voices:\n"
        for key, desc in AVAILABLE_VOICES.items():
            message += f"• <code>/voice {key}</code> - {desc}\n"
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
        return
    if voice_name in AVAILABLE_VOICES:
        context.chat_data["voice"] = voice_name.capitalize()
        await update.message.reply_text(
            f"My voice is now set to <b>{voice_name.capitalize()}</b>! Try it out with the <code>/say</code> command.",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("Sorry, I don't recognize that voice. Type <code>/voice</code> to see the list.", parse_mode=ParseMode.HTML)

async def reset_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
    context.chat_data["personality"] = "default"
    if is_db_connected():
        history_col.delete_one({"_id": update.effective_chat.id})
    await update.message.reply_text(
        "I'm back to my natural self! I've also cleared our recent chat history for a fresh start.",
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_user(update.effective_user)
    if is_user_blocked(user_id):
        return
    if not is_admin(user_id):
        await update.message.reply_text("Sorry, this is an admin-only command.")
        return
    query_text = " ".join(context.args)
    if not query_text:
        query = "Provide a summary of the top 5 latest world and national news headlines."
    else:
        query = f"Provide a news summary about: {query_text}"
    await update.message.chat.send_action(action="typing")
    news_system_prompt = (
        "You are a news summarizer. You must provide concise, factual summaries of the news. "
        "Your task is to act as a news reporting service. "
        "Provide verified news only. Give headlines and a brief summary for each. "
        "ALWAYS cite your sources using the (Source: [URL]) format at the end of each news item."
    )
    try:
        response_text = get_gemini_response(
            query,
            system_prompt_override=news_system_prompt,
            use_search=True,
            chat_history=[],
        )
        await update.message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Error in /news command: {e}")
        await update.message.reply_text(
            "Sorry, I couldn't fetch the news right now. Please try again later.",
        )

# --- GEMINI API CALL (Synchronous Version with History & Vision) ---
def get_gemini_response(
    prompt: str,
    chat_history: list,
    system_prompt_override: str = None,
    use_search: bool = False,
    chat_personality: str = "default",
    image_data_base64: str = None,
    image_mime_type: str = "image/jpeg",
) -> str:
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set.")
        return "Sorry, my AI brain is not configured. (Admin: Check GEMINI_API_KEY)"
    api_url = f"https{os.environ.get('GEMINI_API_URL', '://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent')}?key={GEMINI_API_KEY}"
    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        custom_prompt_doc = None
        if is_db_connected():
            custom_prompt_doc = prompts_col.find_one({"_id": chat_personality})
        if custom_prompt_doc:
            system_prompt = custom_prompt_doc["prompt"]
        else:
            system_prompt = PERSONALITIES.get(chat_personality, PERSONALITIES["default"])
    user_parts = []
    if prompt:
        user_parts.append({"text": prompt})
    if image_data_base64:
        user_parts.append(
            {"inlineData": {"mimeType": image_mime_type, "data": image_data_base64}}
        )
    if not user_parts:
        logger.warning("get_gemini_response called with no prompt and no image.")
        return "What was that? I didn't get your message."
    conversation_history = chat_history + [{"role": "user", "parts": user_parts}]
    payload = {
        "contents": conversation_history,
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    if use_search:
        payload["tools"] = [{"google_search": {}}]
        payload["contents"] = [{"parts": [{"text": "Search and answer: " + prompt}]}]
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(api_url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        result = response.json()
        text = (
            result.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if not text:
            if result.get("candidates", [{}])[0].get("finishReason") == "SAFETY":
                return "I'm sorry, I can't respond to that."
            logger.warning(f"Gemini returned empty text. Full response: {result}")
            return "I'm not sure how to respond to that."
        return text
    except requests.exceptions.HTTPError as e:
        logger.error(
            f"Gemini API request failed with status {e.response.status_code}: {e.response.text}"
        )
        if e.response.status_code == 400:
            return "Sorry, my AI brain had a problem with that request. (Admin: 400 Bad Request)"
        if e.response.status_code == 403:
            return "Sorry, my AI brain isn't working right now. (Admin: Check Gemini API Key permissions)"
        if e.response.status_code == 500:
            return "Sorry, my AI brain is having problems. (Admin: 500 Server Error)"
        return f"Sorry, I'm having trouble connecting to my brain. (Error: {e})"
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API request failed: {e}")
        return f"Sorry, I'm having trouble connecting to my brain. (Error: {e})"
    except Exception as e:
        logger.error(
            f"Error processing Gemini response: {e}. Full response: {response.text if 'response' in locals() else 'N/A'}"
        )
        return "Sorry, I encountered an unexpected error."

# --- CORE MESSAGE HANDLER (NOW ASYNC) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id
    log_user(user)
    if is_user_blocked(user.id):
        return
    prompt = update.message.text
    if not prompt:
        if update.message.voice or update.message.photo:
            return
        prompt = ""
    is_group = chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
    if is_group:
        is_mention = prompt and f"@{context.bot.username}" in prompt
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user.id == context.bot.id
        )
        if not is_mention and not is_reply_to_bot:
            return
        if is_mention:
            prompt = prompt.replace(f"@{context.bot.username}", "").strip()
    if not prompt and not (update.message.photo or update.message.voice):
        return
    personality = context.chat_data.get("personality", "default")
    await update.message.chat.send_action(action="typing")
    try:
        chat_history = get_chat_history(chat_id)
        response_text = get_gemini_response(
            prompt, chat_history=chat_history, chat_personality=personality
        )
        await update.message.reply_text(response_text)
        chat_history.append({"role": "user", "parts": [{"text": prompt}]})
        chat_history.append({"role": "model", "parts": [{"text": response_text}]})
        save_chat_history(chat_id, chat_history)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            "Sorry, I had a little hiccup. Could you try that again?",
        )

# --- NEW: IMAGE HANDLER (NOW ASYNC) ---
async def handle_image_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id
    log_user(user)
    if is_user_blocked(user.id):
        return
    await update.message.chat.send_action(action="typing")
    try:
        photo_file = await update.message.photo[-1].get_file()
        file_bytes_io = io.BytesIO()
        await photo_file.download_to_memory(out=file_bytes_io)
        file_bytes_io.seek(0)
        image_bytes = file_bytes_io.read()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        prompt = update.message.caption
        if not prompt:
            prompt = "Please describe this image in a friendly and conversational way. Be brief unless the image is complex."
        chat_history = get_chat_history(chat_id)
        response_text = get_gemini_response(
            prompt,
            chat_history=chat_history,
            image_data_base64=image_base64,
            image_mime_type="image/jpeg"
        )
        await update.message.reply_text(text=response_text, reply_to_message_id=update.message.message_id)
        history_prompt = f"[User sent an image with caption: {prompt}]"
        chat_history.append({"role": "user", "parts": [{"text": history_prompt}]})
        chat_history.append({"role": "model", "parts": [{"text": response_text}]})
        save_chat_history(chat_id, chat_history)
    except Exception as e:
        logger.error(f"Error in handle_image_message: {e}")
        await update.message.reply_text(
            "Sorry, I had trouble seeing that image. Could you try again?",
        )

# --- NEW: VOICE HANDLER (NOW ASYNT) ---
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type == ChatType.PRIVATE:
        if not await check_user_membership(update, context):
            return
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id
    log_user(user)
    if is_user_blocked(user.id):
        return
    reply_text = "Arre waah, voice note! Cool. Main abhi voice notes sun nahi sakti, kyunki mere paas kaan nahi hain! 😅 \nAap type karke bataoge toh main pakka reply karungi!"
    await update.message.reply_text(text=reply_text, reply_to_message_id=update.message.message_id)
    try:
        chat_history = get_chat_history(chat_id)
        chat_history.append({"role": "user", "parts": [{"text": "[User sent a voice note]"}]})
        chat_history.append({"role": "model", "parts": [{"text": reply_text}]})
        save_chat_history(chat_id, chat_history)
    except Exception as e:
        logger.error(f"Error saving voice note history: {e}")

# --- CHAT MEMBER HANDLER (NOW ASYNC) ---
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result is None:
        return
    chat_id = result.chat.id
    if result.new_chat_member.user.id == context.bot.id:
        status = result.new_chat_member.status
        if status == ChatMember.MEMBER:
            logger.info(f"Added to new chat: {chat_id}")
            update_active_chats(chat_id, "add")
        elif status in [ChatMember.LEFT, ChatMember.KICKED]:
            logger.info(f"Removed from chat: {chat_id}")
            update_active_chats(chat_id, "remove")

# --- ADMIN HELPER ---
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID

# --- NEW: VERIFICATION HELPER FUNCTIONS ---

def get_verification_buttons() -> InlineKeyboardMarkup:
    """Returns the inline keyboard with Join and Verify buttons."""
    keyboard = [
        [
            InlineKeyboardButton("1. Join Chat 💬", url=f"https://t.me/{GROUP_USERNAME.lstrip('@')}"),
            InlineKeyboardButton("2. Join Channel 📢", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")
        ],
        [
            InlineKeyboardButton("✅ Verify Me", callback_data="verify_membership")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def send_verification_message(update: Update):
    """Sends the message telling the user to join."""
    text = (
        "<b>Welcome! To chat with me, you must be a member of our community.</b>\n\n"
        "Please join our chat and channel, then click 'Verify Me'.\n\n"
        "1. **Join the Chat:** @ananyabotchat\n"
        "2. **Join the Channel:** @ananyabotupdates"
    )
    await update.message.reply_text(
        text,
        reply_markup=get_verification_buttons(),
        parse_mode=ParseMode.HTML
    )

async def check_user_membership(update: Update, context: ContextTypes.DEFAULT_TYPE, send_message: bool = True) -> bool:
    """
    Checks if the user is in the group and channel.
    If they are, it sets the chat_data flag and returns True.
    If not, it sends a message (if send_message=True) and returns False.
    """
    user_id = update.effective_user.id
    
    if context.chat_data.get('is_verified', False):
        return True
        
    if is_admin(user_id):
        context.chat_data['is_verified'] = True
        return True

    try:
        # Check channel
        channel_member = await context.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        if channel_member.status not in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]: # <-- FIXED
            if send_message:
                await update.message.reply_text(
                    "It looks like you haven't joined the **Channel** yet. Please join and click Verify again.",
                    reply_markup=get_verification_buttons(),
                    parse_mode=ParseMode.MARKDOWN
                )
            return False

        # Check group
        group_member = await context.bot.get_chat_member(chat_id=GROUP_USERNAME, user_id=user_id)
        if group_member.status not in [ChatMember.MEMBER, ChatMember.ADMINISTRATOR, ChatMember.OWNER]: # <-- FIXED
            if send_message:
                await update.message.reply_text(
                    "It looks like you haven't joined the **Chat Group** yet. Please join and click Verify again.",
                    reply_markup=get_verification_buttons(),
                    parse_mode=ParseMode.MARKDOWN
                )
            return False

        context.chat_data['is_verified'] = True
        return True

    except BadRequest as e:
        if "user not found" in str(e).lower():
             if send_message:
                await update.message.reply_text(
                    "It looks like you haven't joined both groups yet. Please join them and click Verify again.",
                    reply_markup=get_verification_buttons()
                )
        else:
            logger.error(f"Verification error: {e}")
            if send_message:
                await update.message.reply_text(f"An error occurred during verification. The bot might not be an admin in the groups. (Error: {e})")
        return False
    except Exception as e:
        logger.error(f"Verification error: {e}")
        if send_message:
            await update.message.reply_text(f"An error occurred during verification. (Error: {e})")
        return False

# --- NEW: VERIFY BUTTON CALLBACK HANDLER ---
async def verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs when the user clicks the '✅ Verify Me' button."""
    query = update.callback_query
    await query.answer() # Acknowledge the button click
    
    if await check_user_membership(update, context, send_message=False):
        context.chat_data['is_verified'] = True
        await query.edit_message_text(
            "<b>Verification successful!</b> ✅\n\nYou're all set. You can chat with me now!",
            parse_mode=ParseMode.HTML
        )
    else:
        await query.message.reply_text(
            "❌ **Verification Failed**\n\nI checked, and it looks like you haven't joined both the chat and the channel yet. \n\nPlease join both and then click '✅ Verify Me' again.",
            reply_markup=get_verification_buttons(),
            parse_mode=ParseMode.MARKDOWN
        )

# --- BOT & WEBHOOK INITIALIZATION ---
init_lock = threading.Lock()
application = None


def get_application():
    """Initializes the Telegram Application object."""
    global application
    with init_lock:
        if application is None:
            try:
                if TELEGRAM_BOT_TOKEN:
                    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
                    # Register all handlers
                    application.add_handler(CommandHandler("admin", admin_panel))
                    application.add_handler(
                        CommandHandler("admin_stats", admin_stats_command)
                    )
                    application.add_handler(CommandHandler("block", block_command))
                    application.add_handler(CommandHandler("unblock", unblock_command))
                    application.add_handler(
                        CommandHandler("admin_get_prompt", admin_get_prompt)
                    )
                    application.add_handler(
                        CommandHandler("admin_set_prompt", admin_set_prompt)
                    )
                    application.add_handler(
                        CommandHandler("admin_delete_prompt", admin_delete_prompt)
                    )
                    application.add_handler(CommandHandler("news", news_command))
                    application.add_handler(CommandHandler("broadcast", broadcast_command))
                    application.add_handler(MessageHandler(filters.PHOTO & filters.Caption(("/broadcast")), broadcast_command))
                    application.add_handler(CommandHandler("say", say_command))
                    application.add_handler(CommandHandler("start", start))
                    application.add_handler(CommandHandler("help", show_help))
                    application.add_handler(CommandHandler("reset", reset_personality))
                    application.add_handler(
                        CommandHandler("set", set_personality)
                    )
                    application.add_handler(CommandHandler("voice", set_voice))
                    application.add_handler(CallbackQueryHandler(verify_callback, pattern="^verify_membership$"))
                    application.add_handler(
                        MessageHandler(filters.PHOTO & ~filters.Caption(("/broadcast")), handle_image_message)
                    )
                    application.add_handler(
                        MessageHandler(filters.VOICE, handle_voice_message)
                    )
                    application.add_handler(
                        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
                    )
                    application.add_handler(
                        ChatMemberHandler(track_chats, ChatMemberHandler.CHAT_MEMBER)
                    )
                    logger.info(
                        "Telegram Application built and handlers registered successfully."
                    )
                else:
                    logger.error(
                        "FATAL: TELEGRAM_BOT_TOKEN is not set. Application not built."
                    )
                    application = None
            except Exception as e:
                logger.error(f"FATAL: Failed to build Telegram application. ERROR: {e}")
                application = None
    return application


# --- FLASK APP FOR RENDER ---
app = Flask(__name__)
bcrypt = Bcrypt(app) # <-- NEW
# Configure session
app.config["SECRET_KEY"] = SECRET_KEY or "a_very_secret_key_fallback_123"
app.config["SESSION_TYPE"] = "filesystem"
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)


# --- NEW: Dashboard Login Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login", next=flask_request.url))
        return f(*args, **kwargs)
    return decorated_function

# --- NEW: Bot Control Dashboard HTML ---
# I'm embedding the HTML/CSS/JS directly in the Python file to keep it to 2 files.
# This is a bit messy, but it's the easiest way to add this feature.

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - Ananya Bot</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white flex items-center justify-center min-h-screen">
    <div class="w-full max-w-md p-8 space-y-6 bg-gray-800 rounded-xl shadow-lg">
        <h2 class="text-3xl font-bold text-center">Ananya Bot Dashboard</h2>
        <p class="text-center text-gray-400">Please log in to continue</p>
        {% if error %}
            <div class="p-3 bg-red-800 border border-red-700 text-red-200 rounded-lg">
                {{ error }}
            </div>
        {% endif %}
        <form method="POST" action="{{ url_for('login') }}">
            <div class="space-y-4">
                <div>
                    <label for="password" class="block text-sm font-medium text-gray-300">Password</label>
                    <input type="password" name="password" id="password" required
                           class="w-full mt-1 px-4 py-3 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 border border-gray-600">
                </div>
                <button type="submit"
                        class="w-full py-3 px-4 text-lg font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 focus:ring-offset-gray-800">
                    Log In
                </button>
            </div>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .nav-link.active { background-color: #4f46e5; color: white; }
    </style>
</head>
<body class="bg-gray-900 text-gray-200">
    <div class="container mx-auto p-4 md:p-8">
        
        <!-- Header -->
        <header class="flex justify-between items-center mb-6 p-4 bg-gray-800 rounded-lg shadow">
            <div>
                <h1 class="text-3xl font-bold">Bot Manager Dashboard</h1>
                <p class="text-gray-400">Monitor and control your Telegram bot</p>
            </div>
            <a href="{{ url_for('logout') }}" class="py-2 px-4 bg-red-600 hover:bg-red-700 rounded-lg font-medium">Logout</a>
        </header>

        <!-- Navigation -->
        <nav class="flex space-x-1 mb-6 bg-gray-800 p-2 rounded-lg shadow">
            <button class="nav-link flex-1 py-3 px-4 rounded-lg font-medium text-center text-gray-300 hover:bg-gray-700 active" data-tab="bot-control">🤖 Bot Control</button>
            <button class="nav-link flex-1 py-3 px-4 rounded-lg font-medium text-center text-gray-300 hover:bg-gray-700" data-tab="ai-config">🧠 AI Config</button>
            <button class="nav-link flex-1 py-3 px-4 rounded-lg font-medium text-center text-gray-300 hover:bg-gray-700" data-tab="stats">📊 Quick Stats</button>
        </nav>

        <!-- Main Content -->
        <main>
            <!-- Bot Control Tab -->
            <div id="bot-control" class="tab-content active space-y-6">
                <div class="bg-gray-800 p-6 rounded-lg shadow">
                    <h2 class="text-2xl font-semibold mb-4">Bot Status</h2>
                    <div class="flex items-center space-x-4">
                        <div id="status-light" class="w-4 h-4 rounded-full {{ 'bg-green-500' if bot_status else 'bg-red-500' }}"></div>
                        <span id="status-text" class="font-medium text-lg">{{ 'Bot is ON' if bot_status else 'Bot is OFF' }}</span>
                    </div>
                    <p class="text-gray-400 text-sm mt-2">When OFF, the bot will not respond to any messages (except admin commands).</p>
                    <button id="toggle-status-btn"
                            class="mt-4 py-2 px-5 rounded-lg font-medium {{ 'bg-red-600 hover:bg-red-700' if bot_status else 'bg-green-600 hover:bg-green-700' }}">
                        {{ 'Turn Bot OFF' if bot_status else 'Turn Bot ON' }}
                    </button>
                </div>
            </div>

            <!-- AI Config Tab -->
            <div id="ai-config" class="tab-content space-y-6">
                <div class="bg-gray-800 p-6 rounded-lg shadow">
                    <h2 class="text-2xl font-semibold mb-4">Personality Prompts</h2>
                    <p class="text-gray-400 mb-4">Manage the custom AI personalities. Use <code>/set &lt;name&gt;</code> in Telegram to use them.</p>
                    <div id="prompts-list" class="space-y-4">
                        <!-- Prompts will be loaded here by JS -->
                    </div>
                    <hr class="border-gray-700 my-6">
                    <h3 class="text-xl font-semibold mb-3">Add / Edit Prompt</h3>
                    <form id="prompt-form" class="space-y-3">
                        <input type="text" id="prompt-name" placeholder="Personality Name (e.g., 'funny')" required class="w-full p-3 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 border border-gray-600">
                        <textarea id="prompt-text" placeholder="Enter the new system prompt..." rows="5" required class="w-full p-3 bg-gray-700 text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 border border-gray-600"></textarea>
                        <button type="submit" class="py-2 px-5 rounded-lg font-medium bg-indigo-600 hover:bg-indigo-700">Save Prompt</button>
                    </form>
                </div>
            </div>
            
            <!-- Stats Tab -->
            <div id="stats" class="tab-content space-y-6">
                 <div class="bg-gray-800 p-6 rounded-lg shadow">
                    <h2 class="text-2xl font-semibold mb-4">Quick Stats</h2>
                    <div id="stats-grid" class="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div class="bg-gray-700 p-4 rounded-lg text-center">
                            <p class="text-gray-400 text-sm">Total Users</p>
                            <p id="stats-users" class="text-3xl font-bold">...</p>
                        </div>
                        <div class="bg-gray-700 p-4 rounded-lg text-center">
                            <p class="text-gray-400 text-sm">Active Chats</p>
                            <p id="stats-chats" class="text-3xl font-bold">...</p>
                        </div>
                        <div class="bg-gray-700 p-4 rounded-lg text-center">
                            <p class="text-gray-400 text-sm">Blocked Users</p>
                            <p id="stats-blocked" class="text-3xl font-bold">...</p>
                        </div>
                    </div>
                    <button id="refresh-stats-btn" class="mt-4 py-2 px-5 rounded-lg font-medium bg-indigo-600 hover:bg-indigo-700">Refresh Stats</button>
                </div>
            </div>
        </main>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const tabs = document.querySelectorAll('.nav-link');
            const tabContents = document.querySelectorAll('.tab-content');

            tabs.forEach(tab => {
                tab.addEventListener('click', () => {
                    // Deactivate all
                    tabs.forEach(t => t.classList.remove('active'));
                    tabContents.forEach(c => c.classList.remove('active'));
                    
                    // Activate clicked
                    tab.classList.add('active');
                    document.getElementById(tab.dataset.tab).classList.add('active');
                    
                    // Load content for tab
                    if (tab.dataset.tab === 'stats') loadStats();
                    if (tab.dataset.tab === 'ai-config') loadPrompts();
                });
            });

            // --- Bot Control ---
            const toggleBtn = document.getElementById('toggle-status-btn');
            toggleBtn.addEventListener('click', async () => {
                const wants_on = !document.getElementById('status-text').textContent.includes('ON');
                try {
                    const response = await fetch('{{ url_for("api_set_bot_status") }}', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ status: wants_on })
                    });
                    const data = await response.json();
                    if (data.success) {
                        updateBotStatusUI(wants_on);
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (e) {
                    alert('An error occurred: ' + e);
                }
            });

            function updateBotStatusUI(is_on) {
                const statusLight = document.getElementById('status-light');
                const statusText = document.getElementById('status-text');
                if (is_on) {
                    statusLight.classList.remove('bg-red-500');
                    statusLight.classList.add('bg-green-500');
                    statusText.textContent = 'Bot is ON';
                    toggleBtn.textContent = 'Turn Bot OFF';
                    toggleBtn.classList.remove('bg-green-600', 'hover:bg-green-700');
                    toggleBtn.classList.add('bg-red-600', 'hover:bg-red-700');
                } else {
                    statusLight.classList.remove('bg-green-500');
                    statusLight.classList.add('bg-red-500');
                    statusText.textContent = 'Bot is OFF';
                    toggleBtn.textContent = 'Turn Bot ON';
                    toggleBtn.classList.remove('bg-red-600', 'hover:bg-red-700');
                    toggleBtn.classList.add('bg-green-600', 'hover:bg-green-700');
                }
            }

            // --- Stats Control ---
            const refreshStatsBtn = document.getElementById('refresh-stats-btn');
            refreshStatsBtn.addEventListener('click', loadStats);

            async function loadStats() {
                document.getElementById('stats-users').textContent = '...';
                document.getElementById('stats-chats').textContent = '...';
                document.getElementById('stats-blocked').textContent = '...';
                try {
                    const response = await fetch('{{ url_for("api_get_stats") }}');
                    const data = await response.json();
                    if (data.success) {
                        document.getElementById('stats-users').textContent = data.stats.total_users;
                        document.getElementById('stats-chats').textContent = data.stats.total_chats;
                        document.getElementById('stats-blocked').textContent = data.stats.total_blocked;
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (e) {
                    alert('An error occurred: ' + e);
                }
            }
            
            // --- AI Config ---
            const promptForm = document.getElementById('prompt-form');
            const promptListDiv = document.getElementById('prompts-list');
            
            promptForm.addEventListener('submit', async (e) => {
                e.preventDefault();
                const name = document.getElementById('prompt-name').value;
                const text = document.getElementById('prompt-text').value;
                if (!name || !text) {
                    alert('Name and prompt are required.');
                    return;
                }
                try {
                    const response = await fetch('{{ url_for("api_set_prompt") }}', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ name: name, prompt: text })
                    });
                    const data = await response.json();
                    if (data.success) {
                        loadPrompts(); // Refresh list
                        document.getElementById('prompt-form').reset();
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (e) {
                    alert('An error occurred: ' + e);
                }
            });
            
            async function loadPrompts() {
                promptListDiv.innerHTML = '<p class="text-gray-400">Loading prompts...</p>';
                try {
                    const response = await fetch('{{ url_for("api_get_prompts") }}');
                    const data = await response.json();
                    if (!data.success) {
                        promptListDiv.innerHTML = `<p class="text-red-400">Error: ${data.error}</p>`;
                        return;
                    }
                    
                    promptListDiv.innerHTML = ''; // Clear
                    data.prompts.forEach(p => {
                        const isCore = ['default', 'spiritual', 'nationalist'].includes(p._id);
                        const promptEl = document.createElement('div');
                        promptEl.className = 'bg-gray-700 p-4 rounded-lg';
                        promptEl.innerHTML = `
                            <div class="flex justify-between items-center">
                                <h4 class="text-lg font-semibold">${p._id} ${isCore ? '<span class="text-xs text-indigo-400">(Core)</span>' : ''}</h4>
                                <div>
                                    <button class="text-sm text-indigo-400 hover:text-indigo-300" data-name="${p._id}" data-text="${p.prompt}">Edit</button>
                                    ${!isCore ? `<button class="text-sm text-red-500 hover:text-red-400 ml-2" data-name="${p._id}">Delete</button>` : ''}
                                </div>
                            </div>
                            <p class="text-gray-300 text-sm mt-2 font-mono whitespace-pre-wrap">${p.prompt.substring(0, 150)}...</p>
                        `;
                        promptListDiv.appendChild(promptEl);
                    });
                    
                    // Add event listeners for edit/delete
                    promptListDiv.querySelectorAll('button[data-name]').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const name = e.target.dataset.name;
                            if (e.target.textContent === 'Edit') {
                                document.getElementById('prompt-name').value = name;
                                document.getElementById('prompt-text').value = e.target.dataset.text;
                            } else if (e.target.textContent === 'Delete') {
                                if (confirm(`Are you sure you want to delete the '${name}' prompt?`)) {
                                    deletePrompt(name);
                                }
                            }
                        });
                    });
                    
                } catch(e) {
                    promptListDiv.innerHTML = `<p class="text-red-400">An error occurred: ${e}</p>`;
                }
            }
            
            async function deletePrompt(name) {
                try {
                    const response = await fetch('{{ url_for("api_delete_prompt") }}', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ name: name })
                    });
                    const data = await response.json();
                    if (data.success) {
                        loadPrompts(); // Refresh list
                    } else {
                        alert('Error: ' + data.error);
                    }
                } catch (e) {
                    alert('An error occurred: ' + e);
                }
            }

            // Initial load
            loadStats();
        });
    </script>
</body>
</html>
"""

# --- NEW: Flask App Setup & Dashboard Routes ---
app = Flask(__name__)
bcrypt = Bcrypt(app)

# Configure session
if not SECRET_KEY:
    logger.error("FATAL: SECRET_KEY is not set. Dashboard sessions will not work.")
    # We can continue, but sessions will be insecure
    app.config["SECRET_KEY"] = "a_very_insecure_secret_key_fallback_12345"
else:
    app.config["SECRET_KEY"] = SECRET_KEY

app.config["SESSION_TYPE"] = "filesystem"
app.config['SESSION_FILE_DIR'] = './.flask_session/'
Session(app)

# --- Dashboard Login Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# --- Main HTML Routes (Health Check & Dashboard) ---
@app.route("/", methods=["GET", "POST"])
def login():
    """Renders the dashboard login page."""
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    error = None
    if flask_request.method == "POST":
        password = flask_request.form.get("password")
        if not password or not DASHBOARD_PASSWORD:
            error = "Admin password not configured."
        elif bcrypt.check_password_hash(bcrypt.generate_password_hash(DASHBOARD_PASSWORD), password):
        # In a real app, you'd store a hashed password, but for simplicity:
        # if password == DASHBOARD_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid password."
            
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route("/dashboard")
@login_required
def dashboard():
    """Renders the main dashboard page."""
    bot_status = is_bot_on()
    return render_template_string(DASHBOARD_TEMPLATE, bot_status=bot_status)

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))
    
# --- Dashboard API Routes (for JS to fetch data) ---

@app.route("/api/set_status", methods=["POST"])
@login_required
def api_set_bot_status():
    """API endpoint to turn the bot on or off."""
    try:
        data = flask_request.get_json()
        new_status = bool(data.get("status"))
        set_bot_status(new_status)
        return jsonify({"success": True, "status": "on" if new_status else "off"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/get_stats")
@login_required
def api_get_stats():
    """API endpoint to get bot stats."""
    if not is_db_connected():
        return jsonify({"success": False, "error": "Database not connected"}), 500
    try:
        stats = {
            "total_users": users_col.count_documents({}),
            "total_blocked": blocked_col.count_documents({}),
            "total_chats": chats_col.count_documents({})
        }
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
        
@app.route("/api/get_prompts")
@login_required
def api_get_prompts():
    """API endpoint to get all prompts."""
    if not is_db_connected():
        return jsonify({"success": False, "error": "Database not connected"}), 500
    try:
        # Get all custom prompts
        custom_prompts = list(prompts_col.find())
        # Get local fallback prompts
        local_prompts = [{"_id": name, "prompt": text, "is_local": True} for name, text in PERSONALITIES.items() if not any(p["_id"] == name for p in custom_prompts)]
        
        return jsonify({"success": True, "prompts": custom_prompts + local_prompts})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/set_prompt", methods=["POST"])
@login_required
def api_set_prompt():
    """API endpoint to save a prompt."""
    if not is_db_connected():
        return jsonify({"success": False, "error": "Database not connected"}), 500
    try:
        data = flask_request.get_json()
        name = data.get("name").lower().strip()
        prompt = data.get("prompt")
        if not name or not prompt:
            return jsonify({"success": False, "error": "Name and prompt are required"}), 400
        
        prompts_col.update_one(
            {"_id": name},
            {"$set": {"prompt": prompt}},
            upsert=True
        )
        return jsonify({"success": True, "message": f"Prompt '{name}' saved."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/delete_prompt", methods=["POST"])
@login_required
def api_delete_prompt():
    """API endpoint to delete a prompt."""
    if not is_db_connected():
        return jsonify({"success": False, "error": "Database not connected"}), 500
    try:
        data = flask_request.get_json()
        name = data.get("name").lower().strip()
        if not name:
            return jsonify({"success": False, "error": "Name is required"}), 400
            
        if name in ["default", "spiritual", "nationalist"]:
            return jsonify({"success": False, "error": "Cannot delete a core fallback prompt."}), 400

        result = prompts_col.delete_one({"_id": name})
        if result.deleted_count > 0:
            return jsonify({"success": True, "message": f"Prompt '{name}' deleted."})
        else:
            return jsonify({"success": False, "error": "Prompt not found in database."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# --- Telegram Bot Webhook Routes ---
# (These are unchanged from the previous, final, working version)

@app.route("/webhook", methods=["POST"])
def webhook():
    """
    This function is called by Telegram every time a user sends a message.
    It uses asyncio.run() to safely call the async bot code from a sync function.
    """
    if application is None:
        logger.error(
            "Webhook called, but application failed to build. Check TELEGRAM_BOT_TOKEN."
        )
        return "error: application not configured", 500
        
    # --- NEW: Check Bot Status ---
    # We still let admins use commands even if bot is "OFF"
    # But we stop all non-admin chatter
    try:
        update_json = flask_request.get_json()
        update = Update.de_json(update_json, application.bot)
        
        if not is_bot_on() and update.effective_user and not is_admin(update.effective_user.id):
             # If bot is OFF and user is not admin, just return OK and do nothing.
             return "ok", 200
        
        # --- THE FIX ---
        # We must initialize the app *before* processing the update
        async def process_update_async():
            await application.initialize()
            await application.process_update(update)
            await application.shutdown()

        asyncio.run(process_update_async())
        # --- END OF FIX ---

        return "ok", 200
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return "error", 500

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    """
    A helper route to set the webhook.
    Only needs to be visited once.
    """
    if application is None:
        logger.error(
            "set_webhook called, but application failed to build. Check TELEGRAM_BOT_TOKEN."
        )
        return "error: application not configured", 500
    
    host = flask_request.headers.get("Host")
    if not host:
        return "Could not determine host URL.", 500

    host = flask_request.headers.get("x-forwarded-host", host)
    
    render_url = os.environ.get('RENDER_EXTERNAL_URL')
    if render_url:
        webhook_url = f"{render_url}/webhook"
    else:
        webhook_url = f"https{os.environ.get('RENDER_EXTERNAL_URL', '://' + host)}/webhook"

    try:
        async def _set_webhook_async():
            await application.initialize()
            await application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            
            # 1. Set PUBLIC commands for everyone
            public_commands = [
                BotCommand("start", "Welcome message"),
                BotCommand("help", "Show help and commands"),
                BotCommand("reset", "Reset to default personality"),
                BotCommand("set", "Change personality (e.g. /set spiritual)"),
                BotCommand("say", "Speaks your text back to you (Audio)"),
                BotCommand("voice", "Change my /say voice"),
            ]
            await application.bot.set_my_commands(public_commands)
            
            # 2. Set ADMIN commands for you ONLY
            admin_commands = public_commands + [
                BotCommand("admin", "Show Admin Panel"),
                BotCommand("admin_stats", "Show bot statistics"),
                BotCommand("block", "Block a user"),
                BotCommand("unblock", "Unblock a user"),
                BotCommand("news", "Fetch breaking news"),
                BotCommand("broadcast", "Send message to all users"),
                BotCommand("admin_get_prompt", "Get a personality prompt"),
                BotCommand("admin_set_prompt", "Set a personality prompt"),
                BotCommand("admin_delete_prompt", "Delete a personality prompt"),
            ]
            await application.bot.set_my_commands(
                admin_commands,
                scope=BotCommandScope.CHAT(chat_id=ADMIN_USER_ID)
            )
            
            await application.bot.set_my_name("Ananya")
            await application.shutdown()

        asyncio.run(_set_webhook_async())
        
        return f"Webhook successfully set to: {webhook_url}. Bot name and commands updated.", 200
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return f"Failed to set webhook: {e}", 500

@app.route("/remove_webhook", methods=["GET"])
def remove_webhook():
    if application is None:
        return "error: application not configured", 500
    try:
        async def _remove_webhook_async():
            await application.initialize()
            await application.bot.delete_webhook(drop_pending_updates=True)
            await application.shutdown()

        asyncio.run(_remove_webhook_async())
        
        return "Webhook successfully removed.", 200
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return f"Failed to remove webhook: {e}", 500

# --- This must be at the end, outside all functions ---
if __name__ != "__main__":
    # This block runs when Gunicorn starts the app
    # We need to initialize the application and its handlers
    get_application()
    
    # NEW: Hash the admin password on startup for security
    if DASHBOARD_PASSWORD:
        DASHBOARD_PASSWORD_HASH = bcrypt.generate_password_hash(DASHBOARD_PASSWORD).decode('utf-8')
        logger.info("Dashboard password hash generated.")
    else:
        logger.error("FATAL: DASHBOARD_PASSWORD not set. Dashboard will not be usable.")
        DASHBOARD_PASSWORD_HASH = None

# --- Re-add all the Telegram bot handlers that were defined above ---
# (This is a repeat, but ensures Gunicorn loads them)
# Note: In a cleaner setup, you'd put the Flask app in its own file.
if __name__ != "__main__":
    get_application()
