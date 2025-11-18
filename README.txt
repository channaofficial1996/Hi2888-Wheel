Spin Wheel Telegram Bot (Lite v2)
=================================

- Center big result overlay on wheel
- Celebration emojis and (optional) clap sound
- Two buttons: Claim Prize + Contact Agent
- Claim Prize sends data back to the bot via WebApp and the bot
  replies asking for user info.

Files
-----
- main.py        : Telegram bot (long polling via requests) + Flask
- wheel.html     : WebApp UI
- requirements.txt
- Procfile

Environment variables
---------------------
BOT_TOKEN  = your Telegram bot token (from @BotFather)
WEBAPP_URL = your Railway URL, e.g. https://your-app-name.up.railway.app
