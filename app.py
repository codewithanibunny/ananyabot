# -*- coding: utf-8 -*-
"""
Ananya - Your Friendly Telegram Bot (Render Version)
Powered by Google Gemini

This version is the FINAL, STABLE build. It includes:
- All Telegram bot features (personalities, memory, vision, TTS, broadcast, force-join).
- All bug fixes (asyncio, NameErrors, ScopeErrors).
- A full, password-protected admin dashboard hosted on the root URL.
- NEW: Fixed critical API key leak in error messages.
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
          
