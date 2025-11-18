Spin Wheel Telegram Bot (Lite v3)
=================================

Features
--------
- Spin wheel WebApp (Telegram Web App)
- Big result in the center of the wheel + confetti + (optional) clap sound
- Claim Prize button:
  - Takes screenshot of the wheel (html2canvas)
  - Sends screenshot + prize to the bot
  - Bot asks user for full name and then phone number
  - Bot sends confirmation to user
  - Bot forwards info to TARGET_GROUP_ID with:
      DATE/TIME (Bangkok), ID, Full name, Username, Phone, Prize + screenshot

Files
-----
- main.py        : Telegram bot (long polling via requests) + Flask web server
- wheel.html     : WebApp UI (HTML + JS)
- requirements.txt
- Procfile

Environment variables (Railway)
-------------------------------
BOT_TOKEN       = your Telegram bot token (from @BotFather)
WEBAPP_URL     = your Railway URL, e.g. https://your-app-name.up.railway.app
TARGET_GROUP_ID = Telegram group/channel id for receiving leads (e.g. -1001234567890)

Notes
-----
- You can change prize texts and agentUrl in wheel.html.
- Optional: set clapSound.src in wheel.html to a real mp3 URL for clap sound.
