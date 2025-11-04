# -*- coding: utf-8 -*-
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
- NEW: Public TTS (Text-to-Speech) command.
"""

import logging
import os
import requests  # <-- The stable, synchronous library
import json
import asyncio  # <-- THE NEW FIX IS HERE
import base64   # <-- NEW FOR IMAGES
import io       # <-- NEW FOR IMAGES
import wave     # <-- NEW FOR TTS
import struct   # <-- NEW FOR TTS
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
from telegram.error import Forbidden, BadRequest # <-- NEW for broadcast

# --- Flask App for Render ---
from flask import Flask, request as flask_request
import pymongo
import threading  # <-- Import threading for the lock

# --- CONFIGURATION (from Render Environment Variables) ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MONGODB_URI = os.environ.get("MONGODB_URI")

try:
    ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID"))
except (ValueError, TypeError):
    print("FATAL: ADMIN_USER_ID is not set or invalid.")
    ADMIN_USER_ID = 0

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
# Silence chatty libraries
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
    history_col = db.chat_history  # <-- Collection for chat memory
    logger.info("MongoDB client created and collections initialized.")
except Exception as e:
    logger.error(f"FATAL: Could not create MongoDB client: {e}")
    client = None
    db = None
    users_col = None
    blocked_col = None
    chats_col = None
    history_col = None  # <-- Make sure this is also None on failure

# --- MONGODB DATABASE FUNCTIONS ---
def is_db_connected():
    if (
        db is None
        or users_col is None
        or blocked_col is None
        or chats_col is None
        or history_col is None  # <-- Check for history collection
        or client is None
    ):
        logger.error("Database client is not configured.")
        return False
    # Test connection
    try:
        client.server_info()  # This will raise an exception if connection is bad
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def log_user(user: Update.effective_user):
    if not user or not is_db_connected():
        return
    try:
        user_id_str = str(user.id)
        # We only want to log users, not chats (which can also be an 'user' object)
        if user.id < 0: # User IDs are positive, chat IDs are negative
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


# --- NEW CHAT HISTORY FUNCTIONS ---
CHAT_HISTORY_LIMIT = 20  # Max number of messages (10 user, 10 bot) to keep


def get_chat_history(chat_id: int) -> list:
    """Fetches the chat history from MongoDB."""
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
    """Saves the updated chat history to MongoDB, trimming if necessary."""
    if not is_db_connected():
        return
    try:
        # Trim history to the last CHAT_HISTORY_LIMIT messages
        if len(history) > CHAT_HISTORY_LIMIT:
            history = history[-CHAT_HISTORY_LIMIT:]

        history_col.update_one(
            {"_id": chat_id}, {"$set": {"history": history}}, upsert=True
        )
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")


# --- ADMIN COMMAND HANDLERS (NOW ASYNC) ---
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
        "<b>Personality Management:</b>\n"
        "• <code>/admin_get_prompt &lt;name&gt;</code> - Shows prompt for 'default', 'spiritual', or 'nationalist'.\n"
        "• <code>/admin_set_prompt &lt;name&gt; &lt;text&gt;</code> - Sets a new prompt for a personality."
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


# --- NEW: BROADCAST COMMANDS ---

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles text and image broadcasts from the admin."""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("You do not have permission to use this command.")
        return

    if not is_db_connected():
        await update.message.reply_text("Database not connected. Cannot fetch user list.")
        return

    text_to_send = None
    photo_to_send = None
    caption_to_send = None

    # Case 1: Text broadcast
    # /broadcast Hello world
    if update.message.text:
        text_to_send = " ".join(context.args)
        if not text_to_send:
            await update.message.reply_text("Usage: /broadcast <text to send>\nOr send an image with /broadcast in the caption.")
            return
    
    # Case 2: Image broadcast
    # Admin sends a photo with the caption "/broadcast New update!"
    elif update.message.photo:
        photo_to_send = update.message.photo[-1].file_id
        if update.message.caption:
             # Remove the "/broadcast" part from the caption
            caption_to_send = " ".join(update.message.caption.split(' ')[1:])
        if not caption_to_send:
            caption_to_send = None # Send image with no caption if none provided
    
    else:
        await update.message.reply_text("I can only broadcast text or a photo with a caption.")
        return

    # Fetch all user IDs from the database
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
            user_id = int(user_id_str) # Convert string ID from DB to int
            if user_id == ADMIN_USER_ID:
                success_count += 1 # Skip admin, but count as "success"
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
        
        # Be nice to Telegram's API to avoid rate limits
        await asyncio.sleep(0.1) 

    await update.message.reply_text(
        f"<b>Broadcast Complete!</b>\n"
        f"• Sent to: {success_count} users (including admin)\n"
        f"• Failed for: {failure_count} users",
        parse_mode=ParseMode.HTML
    )

# --- NEW: TTS (TEXT-TO-SPEECH) COMMAND ---

def generate_voice_response(text_to_speak: str) -> bytes:
    """Calls Gemini TTS API and returns the raw PCM audio data."""
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set.")
        return b"" # Return empty bytes

    api_url = f"https{os.environ.get('GEMINI_API_URL', '://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent')}?key={GEMINI_API_KEY}"

    # We can control the voice style in the prompt
    prompt = f"Say this in a friendly, female, Hinglish voice: {text_to_speak}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    # "Kore" is a good, clear female-sounding voice
                    "prebuiltVoiceConfig": {"voiceName": "Kore"} 
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
            return b""
            
        return base64.b64decode(audio_data)

    except Exception as e:
        logger.error(f"Error in generate_voice_response: {e}")
        return b""

def pcm_to_wav(pcm_data: bytes) -> io.BytesIO:
    """
    Safely packages raw 16-bit 24kHz PCM data into a .wav file in memory.
    This requires NO external libraries (like ffmpeg).
    """
    if not pcm_data:
        return None

    wav_buffer = io.BytesIO()
    
    # Use the 'wave' standard library to write the WAV header correctly
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(1)       # Mono
        wf.setsampwidth(2)       # 16-bit (2 bytes)
        wf.setframerate(24000)   # 24kHz (Gemini TTS default)
        wf.writeframes(pcm_data) # Write the raw audio data
        
    wav_buffer.seek(0) # Rewind the buffer to the beginning
    return wav_buffer


async def say_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Public command to generate Text-to-Speech."""
    user = update.effective_user
    log_user(user) # Log the user
    if is_user_blocked(user.id): # Check if blocked
        return

    text_to_speak = " ".join(context.args)
    if not text_to_speak:
        await update.message.reply_text("Usage: /say <text to speak>")
        return

    await update.message.chat.send_action(action="typing")

    try:
        # 1. Generate the raw PCM audio from Gemini
        pcm_data = generate_voice_response(text_to_speak) # Sync function
        if not pcm_data:
            await update.message.reply_text("Sorry, I couldn't generate the audio.")
            return

        # 2. Package the PCM data into a .wav file
        wav_file = pcm_to_wav(pcm_data) # Sync function
        if not wav_file:
            await update.message.reply_text("Sorry, I couldn't package the audio file.")
            return

        # 3. Send the .wav file as an audio document
        await update.message.reply_audio(audio=wav_file, title="ananya_reply.wav", filename="ananya_reply.wav")

    except Exception as e:
        logger.error(f"Error in /say command: {e}")
        await update.message.reply_text("An error occurred while generating the audio.")


# --- PUBLIC COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user) # Sync function
    if is_user_blocked(user.id): # Sync function
        return
    context.chat_data.setdefault("personality", "default")
    update_active_chats(update.effective_chat.id, "add") # Sync function
    
    welcome_text = (
        f"Hi {user.first_name}! I'm Ananya, your friendly AI assistant. 🇮🇳\n\n"
        "I'm here to chat, answer questions, and help you out. "
        "By default, I'm in my natural, helpful personality."
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
    user = update.effective_user
    log_user(user) # Sync function
    if is_user_blocked(user.id): # Sync function
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
        "<code>/say &lt;text&gt;</code> - <b>NEW:</b> I will speak the text back to you!\n\n"
        "<b>Personalities:</b>\n"
        "<code>/spiritual</code> - I become a spiritual guide based on Hindu granths.\n"
        "<code>/nationalist</code> - I become a proud, patriotic Indian.\n\n"
        f"For more information and help, you can contact my admin: @certifiedbandichor"
    )

    try:
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Error in /help command: {e}")
        await update.message.reply_text(
            "There was an error showing the help message.",
        )


async def set_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user) # Sync function
    if is_user_blocked(user.id): # Sync function
        return
    command = update.message.text.split("@")[0][1:].lower()
    if command in PERSONALITIES:
        context.chat_data["personality"] = command
        await update.message.reply_text(
            f"I am now in <b>{command}</b> mode. How can I help?",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text("I don't recognize that personality.")


async def reset_personality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log_user(user) # Sync function
    if is_user_blocked(user.id): # Sync function
        return
    context.chat_data["personality"] = "default"
    # Also clear the chat history for this chat
    if is_db_connected():
        history_col.delete_one({"_id": update.effective_chat.id}) # Sync function
    await update.message.reply_text(
        "I'm back to my natural self! I've also cleared our recent chat history for a fresh start.",
    )


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    log_user(update.effective_user) # Sync function
    if is_user_blocked(user_id): # Sync function
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
        # News command does not use chat history
        response_text = get_gemini_response( # Sync function
            query,
            system_prompt_override=news_system_prompt,
            use_search=True,
            chat_history=[],  # Pass empty history
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
    """
    Sends a prompt to the Gemini API using the synchronous requests client.
    Now includes chat history AND image data.
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set.")
        return "Sorry, my AI brain is not configured. (Admin: Check GEMINI_API_KEY)"

    # --- THIS IS THE CHANGE ---
    api_url = f"https{os.environ.get('GEMINI_API_URL', '://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent')}?key={GEMINI_API_KEY}"

    if system_prompt_override:
        system_prompt = system_prompt_override
    else:
        system_prompt = PERSONALITIES.get(chat_personality, PERSONALITIES["default"])

    # Build the parts for the last user message
    user_parts = []
    # Prompt text *always* comes first
    if prompt:
        user_parts.append({"text": prompt})
    # Then append the image
    if image_data_base64:
        user_parts.append(
            {"inlineData": {"mimeType": image_mime_type, "data": image_data_base64}}
        )
        
    # If no text and no image, something is wrong
    if not user_parts:
        logger.warning("get_gemini_response called with no prompt and no image.")
        return "What was that? I didn't get your message."

    # Build the full conversation history
    conversation_history = chat_history + [{"role": "user", "parts": user_parts}]

    payload = {
        "contents": conversation_history,  # Send the whole conversation
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }

    if use_search:
        payload["tools"] = [{"google_search": {}}]
        # When searching, we don't send the whole history, just the query
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
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id

    log_user(user) # Sync function
    if is_user_blocked(user.id): # Sync function
        return

    prompt = update.message.text
    if not prompt:
        # This will allow the handler to process messages with only images/captions
        # But we must ensure it's not a voice or photo, which are handled separately
        if update.message.voice or update.message.photo:
            return
        prompt = "" # Set a default empty prompt if text is None

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
        # If there's still no prompt and it's not a media type we handle, exit.
        return

    personality = context.chat_data.get("personality", "default")

    await update.message.chat.send_action(action="typing")

    try:
        # 1. Get history from DB
        chat_history = get_chat_history(chat_id) # Sync function

        # 2. Get response from Gemini
        response_text = get_gemini_response( # Sync function
            prompt, chat_history=chat_history, chat_personality=personality
        )

        # 3. Send response to user
        await update.message.reply_text(response_text)

        # 4. Update history in DB
        chat_history.append({"role": "user", "parts": [{"text": prompt}]})
        chat_history.append({"role": "model", "parts": [{"text": response_text}]})
        save_chat_history(chat_id, chat_history) # Sync function

    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text(
            "Sorry, I had a little hiccup. Could you try that again?",
        )

# --- NEW: IMAGE HANDLER (NOW ASYNC) ---
async def handle_image_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id

    log_user(user) # Sync function
    if is_user_blocked(user.id): # Sync function
        return
    
    await update.message.chat.send_action(action="typing")

    try:
        # Get the largest photo
        photo_file = await update.message.photo[-1].get_file()
        
        # --- THIS IS THE FIX ---
        # Download as bytes to memory
        file_bytes_io = io.BytesIO()
        await photo_file.download_to_memory(out=file_bytes_io)
        # --- END OF FIX ---

        file_bytes_io.seek(0)
        image_bytes = file_bytes_io.read()
        
        # Convert to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Get the user's caption, if any
        prompt = update.message.caption
        if not prompt:
            prompt = "Please describe this image in a friendly and conversational way. Be brief unless the image is complex."
        
        # Get chat history (it's good for context, e.g., "what is this?")
        chat_history = get_chat_history(chat_id) # Sync function
        
        # Call Gemini with the image data
        response_text = get_gemini_response( # Sync function
            prompt,
            chat_history=chat_history,
            image_data_base64=image_base64,
            image_mime_type="image/jpeg" # Assuming most Telegram photos are jpeg
        )

        # Send response
        await update.message.reply_text(text=response_text, reply_to_message_id=update.message.message_id)

        # Update history
        history_prompt = f"[User sent an image with caption: {prompt}]"
        chat_history.append({"role": "user", "parts": [{"text": history_prompt}]})
        chat_history.append({"role": "model", "parts": [{"text": response_text}]})
        save_chat_history(chat_id, chat_history) # Sync function

    except Exception as e:
        logger.error(f"Error in handle_image_message: {e}")
        await update.message.reply_text(
            "Sorry, I had trouble seeing that image. Could you try again?",
        )

# --- NEW: VOICE HANDLER (NOW ASYNT) ---
async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    chat_id = chat.id

    log_user(user) # Sync function
    if is_user_blocked(user.id): # Sync function
        return

    # User-requested Hinglish reply
    reply_text = "Arre waah, voice note! Cool. Main abhi voice notes sun nahi sakti, kyunki mere paas kaan nahi hain! 😅 \nAap type karke bataoge toh main pakka reply karungi!"
    
    await update.message.reply_text(text=reply_text, reply_to_message_id=update.message.message_id)
    
    # We can log that a voice note was sent, but we can't log its content
    try:
        chat_history = get_chat_history(chat_id) # Sync function
        chat_history.append({"role": "user", "parts": [{"text": "[User sent a voice note]"}]})
        chat_history.append({"role": "model", "parts": [{"text": reply_text}]})
        save_chat_history(chat_id, chat_history) # Sync function
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
            update_active_chats(chat_id, "add") # Sync function
        elif status in [ChatMember.LEFT, ChatMember.KICKED]:
            logger.info(f"Removed from chat: {chat_id}")
            update_active_chats(chat_id, "remove") # Sync function


# --- ADMIN HELPER ---
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID


# --- BOT & WEBHOOK INITIALIZATION ---
# A lock to ensure only one thread initializes the bot
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
                    # Admin
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
                    application.add_handler(CommandHandler("news", news_command))
                    
                    # --- NEW: Broadcast Handler ---
                    # We also listen for photos, so we use a different filter
                    application.add_handler(CommandHandler("broadcast", broadcast_command))
                    application.add_handler(MessageHandler(filters.PHOTO & filters.Caption(("/broadcast")), broadcast_command))
                    
                    # --- NEW: TTS Handler (Now Public) ---
                    application.add_handler(CommandHandler("say", say_command))
                    
                    # Public
                    application.add_handler(CommandHandler("start", start))
                    application.add_handler(CommandHandler("help", show_help))
                    application.add_handler(CommandHandler("reset", reset_personality))
                    application.add_handler(
                        CommandHandler("spiritual", set_personality)
                    )
                    application.add_handler(
                        CommandHandler("nationalist", set_personality)
                    )
                    
                    # --- NEW HANDLERS ---
                    # Add image and voice handlers *before* the general text handler
                    application.add_handler(
                        MessageHandler(filters.PHOTO & ~filters.Caption(("/broadcast")), handle_image_message)
                    )
                    application.add_handler(
                        MessageHandler(filters.VOICE, handle_voice_message)
                    )
                    # --- END NEW HANDLERS ---

                    # Message (must be last)
                    application.add_handler(
                        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
                    )
                    # Chat Member
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
# Initialize the bot object immediately when the app starts
get_application()


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

    db_check = "<b>Database:</b> <span style='color: red;'>NOT CONNECTED (Check MONGODB_URI)</span>"
    if is_db_connected():  # Use our safe check
        db_check = "<b>Database:</b> <span style='color: green;'>MongoDB Connected!</span>"
    else:
        # Try to get a specific error
        try:
            client.server_info()
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


# --- THIS IS THE FINAL FIX ---
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
    try:
        # Get the JSON data from Telegram
        update_json = flask_request.get_json()
        
        # Create an Update object from the JSON
        update = Update.de_json(update_json, application.bot)
        
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

# --- This function also needs the asyncio.run() fix ---
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
    
    # --- WEBHOOK URL FIX ---
    # Check if Render provides its external URL, otherwise build it
    render_url = os.environ.get('RENDER_EXTERNAL_URL')
    if render_url:
        # RENDER_EXTERNAL_URL already includes https://
        webhook_url = f"{render_url}/webhook"
    else:
        # Build it manually, ensuring no double "://"
        webhook_url = f"https{os.environ.get('RENDER_EXTERNAL_URL', '://' + host)}/webhook" # Render is always https
    # --- END WEBHOOK URL FIX ---

    try:
        # --- THE FIX ---
        # We must use asyncio.run() to call async functions
        async def _set_webhook_async():
            await application.initialize() # Initialize for this task
            await application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            
            # Set the bot's commands
            bot_commands = [
                BotCommand("start", "Welcome message"),
                BotCommand("help", "Show help and commands"),
                BotCommand("reset", "Reset to default personality"),
                BotCommand("spiritual", "Switch to spiritual guide mode"),
                BotCommand("nationalist", "Switch to proud nationalist mode"),
            ]
            await application.bot.set_my_commands(bot_commands)
            
            # Set the bot's name
            await application.bot.set_my_name("Ananya")
            await application.shutdown() # Shutdown after this task

        asyncio.run(_set_webhook_async())
        # --- END OF FIX ---
        
        return f"Webhook successfully set to: {webhook_url}. Bot name and commands updated.", 200
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return f"Failed to set webhook: {e}", 500

# --- This function also needs the asyncio.run() fix ---
@app.route("/remove_webhook", methods=["GET"])
def remove_webhook():
    if application is None:
        logger.error(
            "remove_webhook called, but application failed to build. Check TELEGRAM_BOT_TOKEN."
        )
        return "error: application not configured", 500
    try:
        # --- THE FIX ---
        async def _remove_webhook_async():
            await application.initialize()
            await application.bot.delete_webhook(drop_pending_updates=True)
            await application.shutdown()

        asyncio.run(_remove_webhook_async())
        # --- END OF FIX ---
        
        return "Webhook successfully removed.", 200
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        return f"Failed to remove webhook: {e}", 500

if __name__ != "__main__":
    # This block runs when Gunicorn starts the app
    # We need to initialize the application and its handlers
    get_application()

