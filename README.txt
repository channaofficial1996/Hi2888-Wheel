Spin Wheel Telegram Bot (Lite, No telegram-lib)
==============================================

This version does NOT use python-telegram-bot.
It uses plain HTTP requests to the Telegram Bot API, so it avoids
all library version issues and works on Railway out of the box.

Files
-----
- main.py        : Telegram bot (long polling via requests) + Flask web server
- wheel.html     : Spin wheel WebApp UI
- requirements.txt
- Procfile       : For Railway

Steps to deploy on Railway
--------------------------

1. Create a new GitHub repo and upload all these files
   OR create a new Railway project and upload them directly.

2. On Railway:
   - Add environment variables:

     BOT_TOKEN  = your Telegram bot token (from @BotFather)
     WEBAPP_URL = your Railway URL, e.g.
                  https://your-app-name.up.railway.app

3. Redeploy the service.

4. Test in browser:
   - https://your-app-name.up.railway.app/
     -> should show: "Spin Wheel Telegram Bot (lite) is running ✅"

   - https://your-app-name.up.railway.app/wheel
     -> shows the spin wheel UI.

5. In Telegram, open your bot and send:

   /start

   You should receive a message with a button:
   "🎰 Open Spin Wheel"

   Tap the button to open the wheel in a popup WebApp.
