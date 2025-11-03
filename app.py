# -*- coding: utf-8 -*-
"""
Ananya - Your Friendly Telegram Bot (Render Version)
Powered by Google Gemini

This version is the final, stable, synchronous version and includes:
- Flask and gunicorn for the web server.
- MongoDB for all persistence.
- httpx for reliable, synchronous API calls.
- *** NEW: MongoDB-backed long-term chat memory ***
"""

import logging
import os
import httpx  # Using synchronous httpx client
import json
from telegram import Update, BotCommand, ChatMember, ChatMemberUpdated
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ChatMemberHandler,
)
from telegram.constants import ParseMode, ChatType

from flask import Flask, request as flask_request
import pymongo

# --- CONFIGURATION (from Render Environment Variables) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MONGODB_URI = os.environ.get("MONGODB_URI")

try:
    ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID"))
except (ValueError, TypeError):
    print("FATAL: ADMIN_USER_ID is not set or invalid.")
    ADMIN_USER_ID = 0

# --- NEW: Chat History Configuration ---
# We will store the last 20 messages (10 user, 10 bot)
CHAT_HISTORY_LENGTH = 20

# --- PERSONALITY PROMPTS ---
PERSONALITIES = {
    "default": (
        "You are Ananya. You are a helpful and friendly AI with a warm, human-like personality. "
        "Talk naturally, as a real person would. Be kind, polite, and engaging. "
        "Your name is Ananya. Avoid using excessive emojis; use them only when a real person naturally would. "
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

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# --- MONGODB DATABASE SETUP ---
try:
    client = pymongo.MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client.ananya_bot
    users_col = db.users
    blocked_col = db.blocked_users
    chats_col = db.active_chats
    # --- NEW: Chat History Collection ---
    chat_history_col = db.chat_history
    
    logger.info("MongoDB client created and all collections initialized.")
except Exception as e:
    logger.error(f"FATAL: Could not create MongoDB client: {e}")
    client = None
    db = None
    users_col = None
    blocked_col = None
    chats_col = None
    chat_history_col = None # <-- NEW

# --- MONGODB DATABASE FUNCTIONS ---
def is_db_connected():
    # --- NEW: Added chat_history_col to the check ---
    if (
        db is None
        or users_col is None
        or blocked_col is None
        or chats_col is None
        or client is None
        or chat_history_col is None
    ):
        logger.error("Database client is not configured.")
        return False
    return True

# --- NEW: Functions to get, update, and reset chat history ---

def get_chat_history(chat_id: int) -> list:
    """Fetches the chat history for a given chat ID from MongoDB."""
    if not is_db_connected():
        return []
    try:
        chat_doc = chat_history_col.find_one({"_id": str(chat_id)})
        if chat_doc and "history" in chat_doc:
            return chat_doc["history"]
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
    return []

def update_chat_history(chat_id: int, new_history: list):
    """Updates and prunes the chat history for a given chat ID in MongoDB."""
    if not is_db_connected():
        return
    try:
        # Prune history: Keep only the last CHAT_HISTORY_LENGTH messages
        pruned_history = new_history[-CHAT_HISTORY_LENGTH:]
        
        chat_history_col.update_one(
            {"_id": str(chat_id)},
            {"$set": {"history": pruned_history}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error updating chat history: {e}")

def reset_chat_history(chat_id: int):
    """Deletes the chat history for a given chat ID."""
    if not is_db_connected():
        return
    try:
        chat_history_col.delete_one({"_id": str(chat_id)})
        logger.info(f"Chat history reset for chat_id: {chat_id}")
    except Exception as e:
        logger.error(f"Error resetting chat history: {e}")

# --- (Existing DB functions: log_user, is_user_blocked, etc... are unchanged) ---
def log_user(user: Update.effective_user):
    if not user or not is_db_connected():
        return
    try:
        user_id_str = str(user.id)
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
        return blocked_col.find_one({"_id": user_id}) is not None
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
            {"_id": user_id_to_block}, {"$set": {"blocked": True}}, upsert=True
        )
        return f"User {user_id_to_block} has been blocked."
    except Exception as e:
        logger.error(f"Error in block_user: {e}")
        return "An error occurred while blocking."

def unblock_user(user_id_to_unblock: int) -> str:
    if not is_db_connected():
        return "Database error."
    try:
        result = blocked_col.delete_one({"_id": user_id_to_unblock})
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

# --- ADMIN COMMAND HANDLERS (Unchanged) ---
# ... (all admin functions: admin_panel, admin_stats_command, etc. are identical) ...
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
        "<b>News Command (Admin-Only):</b>\n"
        "• <code>/news [query]</code> - Fetches verified news. \n"
        "  (e.g., <code>/news</code>, <code>/news international</code>)\n\n"
        "<b>Personality Management:</b>\n"
        "• <code>/admin_get_prompt &lt;name&gt;</code> - Shows the system prompt for 'default', 'spiritual', or 'nationalist'.\n"
        "• <div><code>/admin_set_prompt &lt;name&gt; &lt;prompt_text&gt;</code> - Sets a new system prompt for a personality.</div>"
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
        message = block_user(user_id_to_block)
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
        message = unblock_user(user_id_to_unblock)
        await update.message.reply_text(message)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /unblock <user_id>")

async def admin_get_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    try:
        personality_name = context.args[0].lower()
        if personality_name in PERSONALITIES:
            await update.message.reply_text(
                f"<b>Prompt for '{personality_name}':</b>\n\n{PERSONALITIES[personality_name]}",
                parse_mode=ParseMode.HTML,
            )
        else:
            await update.message.reply_text(
                "Personality not found. Use 'default', 'spiritual', or 'nationalist'."
            )
    except IndexError:
        await update.message.reply_text("Usage: /admin_get_prompt <name>")

async def admin_set_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text(
            "You do not have permission to use this command."
        )
        return
    try:
        personality_name = context.args[0].lower()
        if personality_name not in PERSONALITIES:
            await update.message.reply_text(
                "Personality not found. Use 'default', 'spiritual', or 'nationalist'."
            )
            return
        new_prompt = " ".join(context.args[1:])
        if not new_prompt:
            await update.message.reply_text("Error: Prompt cannot be empty.")
            return
        PERSONALITIES[personality_name] = new_prompt
        await update.message.reply_text(
            f"Successfully updated prompt for '{personality_name}'."
        )
    except IndexError:
        await update.message.reply_text(
            "Usage: /admin_set_prompt <name> <new_prompt_text>"
        )

# --- PUBLIC COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
    context.chat_data.setdefault("personality", "default")
    update_active_chats(update.effective_chat.id, "add")
    
    # --- NEW: Reset history on /start ---
    reset_chat_history(update.effective_chat.id)
    
    welcome_text = (
        f"Hi {user.first_name}! I'm Ananya, your friendly AI assistant. 🇮🇳\n\n"
        "I'm here to chat, answer questions, and help you out. "
        "By default, I'm in my natural, helpful personality.\n"
        "(P.S. I've reset our conversation memory for a fresh start!)"
    )
    if (
        update.effective_chat.type == ChatType.GROUP
        or update.effective_chat.type == ChatType.SUPERGROUP
    ):
        welcome_text += (
            "\n\n<b>Group Chat Info:</b>\n"
            f"To talk to me in this group, please @-mention me (e.g., @{context.bot.username}) or reply to my messages."
        )
    welcome_text += "\n\nType /help to see all my commands and personalities!"
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.HTML)

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (Unchanged) ...
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
        "• <div><code>/start</code> - Welcome message & resets chat memory.</div>\n"
        "• <div><code>/help</code> - Shows this help panel.</div>\n"
        "• <div><code>/reset</code> - Resets me to my default friendly personality & clears chat memory.</div>\n\n"
        "<b>Personalities:</b>\n"
        "• <div><code>/spiritual</code> - I become a spiritual guide based on Hindu granths. (Resets chat memory)</div>\n"
        "• <div><code>/nationalist</code> - I become a proud, patriotic Indian. (Resets chat memory)</div>\n\n"
        f"For more information and help, you can contact my admin: <code>{ADMIN_USER_ID}</code>"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def set_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
        
    # --- NEW: Reset history when changing personality ---
    reset_chat_history(update.effective_chat.id)
    
    command = update.message.text.split("@")[0][1:].lower()
    if command in PERSONALITIES:
        context.chat_data["personality"] = command
        await update.message.reply_text(
            f"I am now in <b>{command}</b> mode. Our conversation history has been reset for this new topic. How can I help?",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text("I don't recognize that personality.")

async def reset_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user)
    if is_user_blocked(user.id):
        return
        
    # --- NEW: Reset history on /reset ---
    reset_chat_history(update.effective_chat.id)
    
    context.chat_data["personality"] = "default"
    await update.message.reply_text("I'm back to my natural self! Our conversation history has been reset.")

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
        # --- MODIFIED: Call Gemini *without* chat history ---
        response_text = get_gemini_response(
            query,
            update.effective_chat.id, # Pass chat_id, but set use_chat_history to False
            system_prompt_override=news_system_prompt,
            use_search=True,
            use_chat_history=False # <-- This is the key
        )
        await update.message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Error in /news command: {e}")
        await update.message.reply_text(
            "Sorry, I couldn't fetch the news right now. Please try again later."
        )

# --- GEMINI API CALL (Now SYNCHRONOUS and with MEMORY) ---
# We use a synchronous client, as the async one caused event loop errors with gunicorn
gemini_client = httpx.Client(timeout=60.0)

def get_gemini_response(
    prompt: str,
    chat_id: int,
    system_prompt_override: str = None,
    use_search: bool = False,
    chat_personality: str = "default",
    use_chat_history: bool = True
) -> str:
    """
    Sends a prompt to the Gemini API using the synchronous httpx client.
    *** NEW: Now supports loading and saving chat history via MongoDB. ***
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set.")
        return "Sorry, my AI brain is not configured. (Admin: Check GEMINI_API_KEY)"

    api_url = f"https{os.environ.get('GEMINI_API_URL', '://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-09-2025:generateContent')}?key={GEMINI_API_KEY}"

    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        system_prompt = PERSONALITIES.get(chat_personality, PERSONALITIES["default"])

    headers = {"Content-Type": "application/json"}
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    # --- NEW: Build payload with or without history ---
    chat_history = []
    if use_chat_history:
        chat_history = get_chat_history(chat_id)
        chat_history.append({"role": "user", "parts": [{"text": prompt}]})
        payload["contents"] = chat_history
    else:
        # This is for /news or other one-off commands
        payload["contents"] = [{"parts": [{"text": prompt}]}]

    if use_search:
        payload["tools"] = [{"google_search": {}}]
        # Add "Search and answer:" only to the *last* user prompt
        payload["contents"][-1]["parts"][0]["text"] = (
            "Search and answer: " + payload["contents"][-1]["parts"][0]["text"]
        )

    try:
        # Use the global synchronous client to make the call
        response = gemini_client.post(api_url, json=payload, headers=headers)
        
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
                text = "I'm sorry, I can't respond to that."
            else:
                logger.warning(f"Gemini returned empty text. Full response: {result}")
                text = "I'm not sure how to respond to that."
        
        # --- NEW: Save the response to history ---
        if use_chat_history:
            chat_history.append({"role": "model", "parts": [{"text": text}]})
            update_chat_history(chat_id, chat_history)

        return text

    except httpx.HTTPStatusError as e:
        logger.error(f"Gemini API request failed with status {e.response.status_code}: {e.response.text}")
        if e.response.status_code == 400:
             return "Sorry, my AI brain had a problem with that request. (Admin: 400 Bad Request)"
        if e.response.status_code == 403:
             return "Sorry, my AI brain isn't working right now. (Admin: Check Gemini API Key permissions)"
        if e.response.status_code == 500:
             return "Sorry, my AI brain is having problems. (Admin: 500 Server Error)"
        return f"Sorry, I'm having trouble connecting to my brain. (Error: {e})"
    except httpx.RequestError as e:
        logger.error(f"Gemini API request failed: {e}")
        return f"Sorry, I'm having trouble connecting to my brain. (Error: {e})"
    except Exception as e:
        logger.error(f"Error processing Gemini response: {e}. Full response: {response.text if 'response' in locals() else 'N/A'}")
        return "Sorry, I encountered an unexpected error."


# --- CORE MESSAGE HANDLER ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    log_user(user)
    if is_user_blocked(user.id):
        return
    prompt = update.message.text
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
    if not prompt:
        return
    personality = context.chat_data.get("personality", "default")
    await update.message.chat.send_action(action="typing")
    try:
        # --- MODIFIED: Pass chat_id and use_chat_history=True ---
        response_text = get_gemini_response(
            prompt, 
            chat.id, 
            chat_personality=personality,
            use_chat_history=True # <-- This is the default
        )
        await update.message.reply_text(response_text)
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            "Sorry, I had a little hiccup. Could you try that again?"
        )

# --- CHAT MEMBER HANDLER (Unchanged) ---
async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (unchanged) ...
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

# --- ADMIN HELPER (Unchanged) ---
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID

# --- BOT & WEBHOOK INITIALIZATION ---
try:
    if TELEGRAM_BOT_TOKEN:
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        logger.info("Telegram Application built successfully.")
    else:
        logger.error("FATAL: TELEGRAM_BOT_TOKEN is not set. Application not built.")
        application = None
except Exception as e:
    logger.error(f"FATAL: Failed to build Telegram application. ERROR: {e}")
    application = None

# --- Register all handlers (Unchanged) ---
if application:
    # Admin
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("admin_stats", admin_stats_command))
    application.add_handler(CommandHandler("block", block_command))
    application.add_handler(CommandHandler("unblock", unblock_command))
    application.add_handler(CommandHandler("admin_get_prompt", admin_get_prompt))
    application.add_handler(CommandHandler("admin_set_prompt", admin_set_prompt))
    application.add_handler(CommandHandler("news", news_command))
    # Public
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", show_help))
    application.add_handler(CommandHandler("reset", reset_personality))
    application.add_handler(CommandHandler("spiritual", set_personality))
    application.add_handler(CommandHandler("nationalist", set_personality))
    # Message
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    # Chat Member
    application.add_handler(
        ChatMemberHandler(track_chats, ChatMemberHandler.CHAT_MEMBER)
    )
else:
    logger.error("Application object is None, not registering handlers.")

# --- FLASK APP FOR RENDER (Unchanged) ---
app = Flask(__name__)

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>", methods=["GET"])
def health_check(path):
    return "Hello! I am Ananya, and I am alive."

@app.route("/admin_debug/<int:user_id>", methods=["GET"])
def debug_vars(user_id):
    if not is_admin(user_id):
        return "Access denied.", 403
    
    def get_key_preview(key):
        val = os.environ.get(key)
        if val is None:
            return f"<b>{key}:</b> <span style='color: red;'>NOT SET!</span>"
        if len(val) < 8:
            return f"<b>{key}:</b> <span style='color: red;'>VALUE IS TOO SHORT!</span>"
        return f"<b>{key}:</b> <span style='color: green;'>Set (starts: '{val[:4]}', ends: '{val[-4:]}')</span>"

    admin_id = os.environ.get("ADMIN_USER_ID")
    if admin_id is None:
        admin_check = "<span style='color: red;'>ADMIN_USER_ID IS NOT SET!</span>"
    else:
        admin_check = f"<span style='color: green;'>Set (value: {admin_id})</span>"

    db_check = (
        "<b>Database:</b> <span style='color: red;'>NOT CONNECTED (Check MONGODB_URI)</span>"
    )
    if client and is_db_connected():
        try:
            client.server_info()
            db_check = "<b>Database:</b> <span style='color: green;'>MongoDB Connected!</span>"
        except Exception as e:
            db_check = (
                f"<b>Database:</b> <span style='color: red;'>MongoDB FAILED: {e}</span>"
            )

    return (
        "<h1>Ananya Bot - Admin Debug</h1>"
        f"<p>{get_key_preview('TELEGRAM_BOT_TOKEN')}</p>"
        f"<p>{get_key_preview('GEMINI_API_KEY')}</p>"
        f"<p>{get_key_preview('MONGODB_URI')}</p>"
        f"<p><b>ADMIN_USER_ID:</b> {admin_check}</p>"
        f"<hr>"
        f"<p>{db_check}</p>"
    ), 200

# --- WEBHOOK HANDLER (Unchanged, uses the final fix) ---
@app.route("/webhook", methods=["POST"])
async def webhook():
    if application is None:
        logger.error(
            "Webhook called, but application failed to build. Check TELEGRAM_BOT_TOKEN."
        )
        return "error: application not configured", 500
    try:
        # 1. INITIALIZE the bot for this request
        await application.initialize()
        
        # 2. Process the update
        update_json = flask_request.get_json()
        update = Update.de_json(update_json, application.bot)
        await application.process_update(update)
        
        # 3. SHUT DOWN the bot for this request
        await application.shutdown()
        
        return "ok", 200
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return "error", 500

# --- WEBHOOK SET/REMOVE ROUTES (Unchanged) ---
@app.route("/set_webhook", methods=["GET"])
async def set_webhook():
    if application is None:
        logger.error(
            "set_webhook called, but application failed to build. Check TELEGRAM_BOT_TOKEN."
        )
        return "error: application not configured", 500
    if not ADMIN_USER_ID:
        return "Admin ID not set.", 500

    host = flask_request.headers.get("Host")
    if not host:
        return "Could not determine host URL.", 500

    host = flask_request.headers.get("x-forwarded-host", host)
    webhook_url = f"https://{host}/webhook"

    try:
        await application.initialize()
        await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        await application.shutdown()
        
        return f"Webhook successfully set to: {webhook_url}", 200
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return f"Failed to set webhook: {e}", 500

@app.route("/remove_webhook", methods=["GET"])
async def remove_webhook():
    if application is None:
        logger.error(
            "remove_webhook called, but application failed to build. Check TELEGRAM_BOT_TOKEN."
        )
        return "error: application not configured", 500
    try:
        await application.initialize()
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.shutdown()
        
        return "Webhook successfully removed.", 200
    except Exception as e:
        logger.error(f"Failed to remove webhook: {e}")
        return f"Failed to remove webhook: {e}", 500

