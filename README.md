Ananya Bot - A Multi-Personality AI Telegram Bot

Ananya is a feature-rich, conversational AI bot for Telegram, powered by Google's Gemini API and a persistent MongoDB database. She is designed to be a "human-like" companion who can change her personality on-demand, from a friendly helper to a spiritual guide.

This project is deployed as a webhook-based web service on Render, ensuring high availability and a stable, stateful (database-driven) experience for all users.

🌟 Key Features

Multi-Personality AI:

Default: A warm, friendly, and natural-sounding companion.

/spiritual: A wise guide who answers questions based on the wisdom of Hindu granths (Vedas, Gita, etc.).

/nationalist: A proud and enthusiastic Indian, happy to share positive insights about the country's culture and achievements.

Google Gemini Integration: All conversational logic is powered by the gemini-2.5-flash-preview-09-2025 model for fast, high-quality, and context-aware responses.

Advanced Chat Logic:

Works seamlessly in both private chats and group chats.

In groups, she only responds to @-mentions or direct replies, preventing spam.

Persistent Database (MongoDB):

Logs all unique users who interact with the bot.

Saves user data (username, first name, last seen).

Remembers which chats are active.

Manages a "block list" for user moderation.

Full Admin Panel:

Protected by a hard-coded ADMIN_USER_ID.

/admin_stats: Shows real-time bot statistics (total users, blocked users, active chats) queried directly from the database.

/block & /unblock: Allows the admin to ban or unban any user from the bot.

/admin_get_prompt & /admin_set_prompt: Lets the admin view or even hot-reload a new personality prompt live without redeploying.

Real-Time News Command:

Admin-only /news command.

Uses Gemini's Google Search grounding to fetch and summarize real-time, verified news from the internet, complete with sources.

Asynchronous & Scalable:

Built with Flask and gunicorn to run as a reliable web server.

Uses httpx for non-blocking asynchronous API calls to the Gemini API, preventing crashes under load.

🛠️ Tech Stack

Language: Python 3.12

AI Model: Google Gemini 2.5 Flash

Platform: Telegram Bot API

Hosting: Render (Free Web Service)

Web Server: Flask & Gunicorn

Database: MongoDB Atlas (Free M0 Cluster)

Core Libraries: python-telegram-bot, pymongo, httpx

🚀 Deployment Guide (on Render)

This bot is designed to be deployed as a free Web Service on Render.

1. Get Your API Keys (The "Secrets")

You will need four secret keys.

TELEGRAM_BOT_TOKEN:

Talk to the @BotFather on Telegram.

Create your bot and copy the API token.

GEMINI_API_KEY:

Go to Google AI Studio (Makersuite).

Create a new API key.

MONGODB_URI:

Create a free account on MongoDB Atlas.

Build a new Free (M0) cluster.

IMPORTANT:

Under Network Access, click "Add IP Address" and add 0.0.0.0/0 ("Allow Access from Anywhere").

Under Database Access, create a new database user (e.g., ananya_user) and set a password.

Click "Connect" -> "Drivers" and copy your Connection String (URI).

Paste the string and replace <username> and <password> with your database user's credentials.

ADMIN_USER_ID:

Talk to @userinfobot on Telegram.

It will instantly reply with your numeric Telegram ID.

2. Set Up Your GitHub Repository

Create a new, public GitHub repository (e.g., ananya-telegram-bot).

Add the app.py file to this repository.

Add the requirements.txt file to this repository.

(Optional) Add this README.md file!

3. Deploy on Render

Sign up for a free account on Render.com (you can link your GitHub).

On the Render Dashboard, click New + -> Web Service.

Connect your GitHub and select your new bot repository.

Fill in the settings:

Name: ananya-bot (or your preferred name)

Root Directory: (leave blank)

Environment: Python 3

Build Command: pip install -r requirements.txt

Start Command: gunicorn app:app

Instance Type: Free

Click "Create Web Service". Render will start its first build (it might fail, this is okay).

4. Add Your Secrets (Environment Variables)

In your new Render service, go to the "Environment" tab.

Click "Add Environment Variable" and add all four of your secrets from Step 1:

TELEGRAM_BOT_TOKEN

GEMINI_API_KEY

MONGODB_URI

ADMIN_USER_ID

Adding these will automatically trigger a new, successful deployment.

5. Set the Webhook (Final Step)

Wait for your Render deployment to say "Live".

At the top of the page, copy your new URL. It will look like:
https://ananya-bot.onrender.com

Set the webhook manually. Open a new, empty browser tab and paste this URL, replacing the two placeholders:

https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_RENDER_URL>/webhook

Example:
https://api.telegram.org/bot12345:ABC.../setWebhook?url=https://ananya-bot.onrender.com/webhook

Press Enter. Your browser will show {"ok":true,"result":true,"description":"Webhook was set"}.

You are done. Your bot is now live, deployed, and ready to talk to users on Telegram.