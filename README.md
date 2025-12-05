# 🤖 Ananya Bot - Multi-Personality AI Telegram Bot

<div align="center">

![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram&style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.9%2B-green?logo=python&style=for-the-badge)
![Gemini API](https://img.shields.io/badge/Google-Gemini-purple?style=for-the-badge)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-green?logo=mongodb&style=for-the-badge)
![Render](https://img.shields.io/badge/Hosted%20on-Render-46E3B7?style=for-the-badge)

**A friendly, AI-powered Telegram companion with multiple personalities, image generation, real-time logging, and advanced admin features.**

[Features](#-features) • [Setup](#-setup) • [Commands](#-commands) • [Configuration](#-configuration) • [Deployment](#-deployment)

</div>

---

## ✨ Features

### 🧠 Multi-Personality AI System
- **Default Mode:** Warm, friendly, and natural-sounding companion
- **Spiritual Mode** (`/set spiritual`): Wise guide drawing from Hindu philosophy (Vedas, Gita, Puranas)
- **Nationalist Mode** (`/set nationalist`): Proud Indian sharing cultural insights
- **Custom Personalities:** Admin can create unlimited custom personalities via database

### 🎨 Image Generation
- **`/send_image`** - Generates beautiful AI portrait of Ananya
- **`/gen_image <description>`** - Creates custom images from natural language descriptions
- **Natural Language Triggers:**
  - "Send your image" → Generates Ananya's picture
  - "Generate image of..." → Creates custom images
- Powered by **Google Gemini 3.0 Pro**

### 🎙️ Advanced Voice System
- **`/voice <name>`** - Switch between 7 unique voices
- **`/say <text>`** - Convert text to speech in selected voice
- Available voices: Kore, Puck, Leda, Erinome, Algenib, Achird, Vindemiatrix
- Each voice sounds distinctly different
- Audio delivered as WAV files
- Powered by **Google Gemini 2.5 Flash TTS**

### 💾 Chat Logging & Analytics
- **MongoDB Integration:** Comprehensive chat history and user tracking
- **Admin Commands:**
  - `/admin_logs [limit]` - View recent activity logs (50-500 entries)
  - `/admin_user_logs <user_id> [limit]` - Detailed user-specific activity
- **Real-time Telegram Channel Logging** - Live activity feed to private Telegram channel
- Tracks: Messages, images, voice notes, commands, user metadata

### 👥 Memory & Context
- **Long-term Conversation Memory:** Retains last 20 messages per chat
- **Persistent Database:** All user data and preferences stored in MongoDB
- **Smart Context:** Uses chat history for coherent, contextual responses
- **User Tracking:** Monitors first seen, last seen, message count, action count

### 🛡️ Admin Control Panel
- **Password-Protected Dashboard:** Secure web interface for admin controls
- **Bot Statistics:**
  - Total unique users
  - Blocked users
  - Active group chats
  - Real-time user statistics
- **User Management:**
  - `/block <user_id>` - Instantly block abusive users
  - `/unblock <user_id>` - Restore blocked users
- **Personality Management:**
  - `/admin_get_prompt <name>` - View any personality prompt
  - `/admin_set_prompt <name> <text>` - Create/update personality
  - `/admin_delete_prompt <name>` - Remove custom personality
- **Broadcast:** `/broadcast <text>` - Send message to all users

### 📰 Additional Features
- **News Command:** `/news [query]` - Fetch verified news using web search
- **Group Chat Support:** Works in groups with smart @-mention detection
- **Private/Group Detection:** Different behavior for private vs group chats
- **User Membership Verification:** Force users to join community channel/group
- **Force-Join Mechanism:** Verify membership before using bot
- **On/Off Switch:** Global bot enable/disable without redeploy
- **Error Logging:** Real-time error tracking and debugging

### 📊 Monitoring & Logging
- **Database Logs:** Complete audit trail in MongoDB
- **Telegram Channel Logs:** Real-time activity feed with:
  - 📝 User activity (commands, settings)
  - 💬 Message samples (10% sampling)
  - 🎨 Generated images
  - 🚨 Error logs
- **Admin Access:** View logs via commands or Telegram channel

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- MongoDB Atlas (free tier available)
- Google Gemini API key
- Telegram Bot (from @BotFather)
- Render account (for hosting)

### Local Development

```bash
# Clone repository
git clone https://github.com/yourusername/ananyabot.git
cd ananyabot

# Install dependencies
pip install -r requirements.txt

# Create .env file
echo "TELEGRAM_BOT_TOKEN=your_token" > .env
echo "GEMINI_API_KEY=your_api_key" >> .env
echo "MONGODB_URI=your_mongodb_uri" >> .env
echo "ADMIN_USER_ID=your_user_id" >> .env
echo "DASHBOARD_PASSWORD=secure_password" >> .env
echo "SECRET_KEY=random_secret_key" >> .env
echo "LOG_CHANNEL_ID=-100123456789" >> .env

# Run locally
python app.py
```

---

## 📋 Commands

### 👤 User Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Welcome message & initialization | `/start` |
| `/help` | Show all available commands | `/help` |
| `/set <name>` | Change personality | `/set spiritual` |
| `/voice <name>` | Change speaking voice | `/voice puck` |
| `/say <text>` | Convert text to speech | `/say Hello world` |
| `/send_image` | Get picture of Ananya | `/send_image` |
| `/gen_image <desc>` | Generate custom image | `/gen_image sunset over ocean` |
| `/reset` | Reset to default personality | `/reset` |

**Natural Language Triggers:**
- "Send your image" → Generates Ananya's picture
- "What do you look like?" → Generates Ananya's picture
- "Generate image of..." → Creates custom image
- "Draw..." → Creates custom image

### 🔐 Admin Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/admin` | Show admin panel | Admin only |
| `/admin_stats` | Bot statistics | Admin only |
| `/admin_logs [limit]` | View activity logs | Admin only |
| `/admin_user_logs <id> [limit]` | User-specific logs | Admin only |
| `/block <user_id>` | Block user | Admin only |
| `/unblock <user_id>` | Unblock user | Admin only |
| `/admin_get_prompt <name>` | View personality prompt | Admin only |
| `/admin_set_prompt <name> <prompt>` | Create/edit personality | Admin only |
| `/admin_delete_prompt <name>` | Delete personality | Admin only |
| `/news [query]` | Fetch news | Admin only |
| `/broadcast <text>` | Send to all users | Admin only |

---

## ⚙️ Configuration

### Environment Variables

```env
# Required
TELEGRAM_BOT_TOKEN=123456:ABCDEFghijklmnopqrstuvwxyz  # From @BotFather
GEMINI_API_KEY=AIza_your_api_key_here                  # Google AI Studio
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/ananya_bot
ADMIN_USER_ID=123456789                                # Your Telegram ID

# Recommended
DASHBOARD_PASSWORD=StrongSecurePassword123             # For admin dashboard
SECRET_KEY=RandomSecretKeyForFlaskSessions             # Flask encryption
LOG_CHANNEL_ID=-100123456789                           # Private Telegram channel

# Optional
RENDER_EXTERNAL_URL=https://your-app.onrender.com     # Auto-set by Render
```

### Log Channel Setup

1. **Create Private Telegram Channel**
   - Open Telegram → Create Channel → "Ananya Bot Logs"
   - Set to Private
   - Add bot with message permissions

2. **Get Channel ID**
   - Forward message to @RawDataBot
   - Look for `"chat": {"id": -100123456789}`

3. **Configure on Render**
   - Service Settings → Environment
   - Add: `LOG_CHANNEL_ID = -100123456789`
   - Redeploy

### MongoDB Setup

1. **Create MongoDB Atlas Account**
   - Go to mongodb.com/cloud/atlas
   - Create free tier cluster
   - Create database user
   - Add IP whitelist (0.0.0.0/0 for Render)

2. **Get Connection String**
   - Cluster → Connect → Python driver
   - Copy connection string
   - Replace `<password>` with your password

3. **Create Database Collections**
   - Collections are auto-created by bot
   - Database name: `ananya_bot`

---

## 📂 Database Schema

### Collections

```
ananya_bot/
├── users              # User information
├── blocked_users      # Blocked user IDs
├── active_chats       # Active group chats
├── chat_history       # Conversation history (20 msgs/chat)
├── chat_logs          # Complete activity audit trail
├── prompts            # Custom personalities
├── bot_status         # Bot on/off status
└── session/           # Flask sessions (auto-created)
```

### Sample Log Entry

```json
{
  "timestamp": "2025-12-05T15:30:45Z",
  "user_id": 123456789,
  "user_name": "John",
  "user_username": "john_doe",
  "user_last_name": "Doe",
  "user_is_bot": false,
  "user_language_code": "en",
  "chat_id": 987654321,
  "message_type": "text",
  "message_text": "Hello Ananya!",
  "action": "/voice",
  "details": {"voice": "puck", "chat_id": 123456789}
}
```

---

## 🌐 Deployment

### Deploy on Render.com

1. **Connect Repository**
   - Go to render.com → New → Web Service
   - Connect your GitHub repository
   - Select main branch

2. **Configure Service**
   - Name: `ananya-bot`
   - Environment: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app`

3. **Set Environment Variables**
   ```
   TELEGRAM_BOT_TOKEN=your_token
   GEMINI_API_KEY=your_key
   MONGODB_URI=your_uri
   ADMIN_USER_ID=your_id
   DASHBOARD_PASSWORD=password
   SECRET_KEY=secret
   LOG_CHANNEL_ID=-100123456789
   ```

4. **Deploy**
   - Click "Create Web Service"
   - Render will automatically deploy
   - Service runs 24/7 on free tier

5. **Verify Deployment**
   - Check Render logs for "Bot started successfully"
   - Send `/help` to bot on Telegram
   - Check log channel for activity

### Webhook Setup

Bot automatically sets webhook on Render:
```
https://your-service.onrender.com/webhook
```

View webhook info: `/set_webhook` (admin)
Remove webhook: `/remove_webhook` (admin)

---

## 🔧 Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Bot Framework** | python-telegram-bot (PTB) | Telegram API wrapper |
| **AI/ML** | Google Gemini API | Conversational AI & image gen |
| **Database** | MongoDB Atlas | Data persistence |
| **Web Server** | Flask | Webhook handling |
| **Authentication** | Flask-Bcrypt | Password hashing |
| **Sessions** | Flask-Session | Admin login sessions |
| **Text-to-Speech** | Gemini 2.5 Flash TTS | Voice generation |
| **Image Generation** | Gemini 3.0 Pro | Custom images |
| **Hosting** | Render.com | 24/7 uptime |
| **HTTP Client** | Requests | API calls |

---

## 📦 Dependencies

```
Flask>=3.0.0
Flask-Bcrypt>=1.0.1
Flask-Session>=0.5.0
python-telegram-bot[aiohttp]>=21.0.0
requests>=2.31.0
gunicorn>=21.2.0
pymongo[srv]>=4.6.0
Pillow>=10.0.0
```

---

## 🛡️ Security Features

✅ **Admin Protection:** Commands restricted to ADMIN_USER_ID
✅ **Password Hashing:** Dashboard password bcrypt-encrypted
✅ **Session Management:** Secure Flask sessions with SECRET_KEY
✅ **No API Key Leaks:** Error messages don't expose API keys
✅ **User Blocking:** Granular control over bot access
✅ **Rate Limiting:** 10% message sampling to prevent spam
✅ **Input Validation:** All user inputs sanitized
✅ **HTTPS Only:** Telegram webhooks require HTTPS

---

## 📊 Monitoring

### View Bot Statistics
```
/admin_stats
```
Shows:
- Total unique users
- Blocked users
- Active group chats

### View Activity Logs
```
/admin_logs 100           # Last 100 activities
/admin_user_logs 123456789 50  # User's last 50 activities
```

### Real-time Monitoring
- Check Telegram log channel for live updates
- All activities logged with timestamps
- Errors tracked with full context

---

## 🐛 Troubleshooting

### Bot Not Responding
**Solution:**
```
1. Check TELEGRAM_BOT_TOKEN on Render
2. Verify webhook: https://your-app.onrender.com/set_webhook
3. Check Render logs for errors
```

### Images Not Generating
**Solution:**
```
1. Verify GEMINI_API_KEY is valid
2. Check API quota in Google Cloud Console
3. Ensure model: "gemini-3.0-pro" is available
```

### No Logs in Channel
**Solution:**
```
1. Verify LOG_CHANNEL_ID format: -100...
2. Add bot to channel with message permissions
3. Check Render logs: "Error sending to log channel"
```

### Database Connection Failed
**Solution:**
```
1. Verify MONGODB_URI format
2. Add Render IP to MongoDB whitelist (0.0.0.0/0)
3. Check MongoDB cluster status
```

---

## 📝 Available Personalities

### Built-in
- **default** - Friendly, helpful companion
- **spiritual** - Hindu philosophy guide
- **nationalist** - Proud Indian with cultural insights

### Create Custom
```
/admin_set_prompt my_personality "You are..."
/set my_personality
```

---

## 🎤 Available Voices

| Voice | Style | Description |
|-------|-------|-------------|
| kore | Clear, Firm | Professional and clear |
| puck | Upbeat, Friendly | Cheerful and enthusiastic |
| leda | Youthful, Bright | Young and vibrant |
| erinome | Clear, Professional | Formal and polished |
| algenib | Gravelly, Deep | Rich and warm |
| achird | Friendly, Warm | Approachable and kind |
| vindemiatrix | Gentle, Soft | Calm and soothing |

---

## 🎨 Image Generation Examples

```
/gen_image a sunset over the ocean with palm trees
/gen_image futuristic city with neon lights
/gen_image a cat wearing sunglasses
```

Or in natural language:
```
"Generate image of a magical forest"
"Create a picture of northern lights"
"Draw a dragon"
```

---

## 📚 Documentation

- [Log Channel Setup Guide](LOG_CHANNEL_SETUP.md)
- [Chat Logging Features](LOGGING_FEATURE.md)
- [Image Generation & Voice](FEATURES_ADDED.md)
- [Complete Feature Guide](COMPLETE_FEATURE_GUIDE.md)

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open Pull Request

---

## 📄 License

This project is licensed under the MIT License - see LICENSE file for details.

---

## 💬 Support

For issues and questions:
1. Check [Troubleshooting](#-troubleshooting) section
2. Review documentation files
3. Check Render service logs
4. Create an issue on GitHub

---

## 🙏 Acknowledgments

- **Google Gemini API** - AI and image generation
- **Telegram Bot API** - Bot framework
- **MongoDB Atlas** - Database hosting
- **Render** - Web service hosting
- **python-telegram-bot** - Telegram wrapper library

---

## 📊 Project Statistics

- **Lines of Code:** 2300+
- **Commands:** 20+
- **Database Collections:** 8
- **APIs Integrated:** 4
- **Deployment Platforms:** 1
- **Active Features:** 30+

---

<div align="center">

**Made with ❤️ for Telegram**

If you find this bot useful, please give it a ⭐!

[Report Bug](https://github.com/yourusername/ananyabot/issues) • [Request Feature](https://github.com/yourusername/ananyabot/issues) • [View Roadmap](https://github.com/yourusername/ananyabot/projects)

</div>


Uses Google Search grounding via the Gemini API to fetch, summarize, and cite real-time, verified news from the internet.

🛠️ Tech Stack

Core: Python 3.11+

Web Server: Flask, Gunicorn

Bot Framework: python-telegram-bot

AI: gemini-2.5-flash-preview-09-2025 via Google's Generative Language API

Database: MongoDB Atlas (accessed via pymongo)

API Calls: httpx (for stable, synchronous API calls)

Hosting: Render (as a Web Service)

🚀 Deployment Guide (on Render)

This project is configured for deployment on Render's free tier.

Step 1: Get All Secret Keys

You will need four secret keys. Store them in a safe place.

TELEGRAM_BOT_TOKEN: Get this from @BotFather on Telegram.

GEMINI_API_KEY: Get this from Google AI Studio.

MONGODB_URI: Get this from MongoDB Atlas.

Create a free M0 cluster.

Go to "Database Access" and create a user with a username and password.

Go to "Network Access" and add 0.0.0.0/0 ("Allow Access from Anywhere").

Go to "Database", click "Connect" -> "Drivers", and copy your connection string (URI). Replace <username> and <password> with your credentials.

ADMIN_USER_ID: Get your numeric Telegram ID from @userinfobot.

Step 2: Set Up GitHub

Push the two project files to a new GitHub repository:

app.py

requirements.txt

Step 3: Deploy on Render

Sign up for Render.com (you can use your GitHub account).

On your dashboard, click "New +" -> "Web Service".

Connect your GitHub and select your bot's repository.

Fill in the service details:

Name: ananya-bot (or your preferred name)

Environment: Python 3

Build Command: pip install -r requirements.txt

Start Command: gunicorn app:app

Instance Type: Free

Click "Create Web Service".

Step 4: Add Environment Variables

Your first build will likely fail. This is normal.

Go to the "Environment" tab for your new service.

Click "Add Environment Variable" and add your four secret keys from Step 1:

TELEGRAM_BOT_TOKEN

GEMINI_API_KEY

MONGODB_URI

ADMIN_USER_ID

Adding these will trigger a new deployment. Wait for it to finish and say "Live".

Step 5: Set the Webhook

This is the final step to connect Telegram to your new server.

Copy your new Render URL from the top of the dashboard (e.g., https-ananyabot.onrender.com).

Get your TELEGRAM_BOT_TOKEN from Step 1.

Open a new browser tab and paste in the following URL, replacing the placeholders:

[https://api.telegram.org/bot](https://api.telegram.org/bot)<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_RENDER_URL>/webhook


Example:

[https://api.telegram.org/bot12345:ABCDE/setWebhook?url=https://ananyabot.onrender.com/webhook](https://api.telegram.org/bot12345:ABCDE/setWebhook?url=https://ananyabot.onrender.com/webhook)


Press Enter. Your browser should show:
{"ok":true,"result":true,"description":"Webhook was set"}

Your bot is now live and will respond in Telegram!

📜 License

Copyright 2024, Aniket Singha Roy

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0


Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
