Ananya Bot - A Multi-Personality AI Telegram Bot

Ananya is a feature-rich, conversational AI bot for Telegram, powered by Google's Gemini API and a persistent MongoDB database. She is designed to be a "human-like" companion who can change her personality on-demand, from a friendly helper to a spiritual guide.

This project is deployed as a webhook-based web service on Render, ensuring high availability and a stable, stateful (database-driven) experience for all users.

🌟 Key Features

Multi-Personality AI:

Default: A warm, friendly, and natural-sounding companion.

/spiritual: A wise guide who answers questions based on the wisdom of Hindu granths (Vedas, Gita, etc.).

/nationalist: A proud and enthusiastic Indian, happy to share positive insights about the country's culture and achievements.

Google Gemini Integration: All conversational logic is powered by the gemini-2.5-flash-preview-09-2025 model for fast, high-quality, and context-aware responses.

Persistent Database (MongoDB):

Logs all unique users who interact with the bot.

Manages a list of blocked users.

Keeps track of all active group chats.

Long-Term Chat Memory: Ananya remembers the context of your conversation. She loads the last 20 messages from your chat history (stored in MongoDB) to provide continuous and relevant replies.

Advanced Chat Logic:

Works seamlessly in both private chats and group chats.

In groups, she only responds to @-mentions or direct replies, preventing spam.

Full Admin Panel:

Protected by a hard-coded ADMIN_USER_ID.

/admin_stats: Shows live bot statistics (total users, blocked users, active chats).

/block <user_id>: Instantly blocks a user from interacting with the bot.

/unblock <user_id>: Unblocks a user.

/admin_get_prompt & /admin_set_prompt: Allows the admin to view or even hot-reload the bot's personality prompts live, without a redeploy.

Real-Time News Command:

An admin-only /news [query] command.

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
