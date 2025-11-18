Spin Wheel Telegram Bot v4.1
================================

- Spin wheel Telegram WebApp with big center result + confetti
- Claim sends screenshot + prize back to bot (if possible)
- Fallback: if screenshot fails, claim still works with text only
- Bot asks for full name & phone number
- Bot forwards lead (with or without screenshot) to TARGET_GROUP_ID
  including DATE/TIME (Bangkok), ID, name, username, phone, prize.

Files
-----
- main.py        : Flask app + Telegram long polling bot (requests)
- wheel.html     : WebApp page (served at /wheel)
- requirements.txt
- Procfile

Environment variables (Railway)
-------------------------------
BOT_TOKEN       = your Telegram bot token
WEBAPP_URL     = your Railway URL, e.g. https://your-app-name.up.railway.app
TARGET_GROUP_ID = Telegram group/channel id to receive leads, e.g. -1003317283401
