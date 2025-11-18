Spin Wheel Telegram Bot — 100% Railway Ready
===========================================

Files
-----
- main.py        : Telegram bot (polling) + Flask web server
- wheel.html     : Spin wheel WebApp UI
- requirements.txt
- Procfile       : For Railway

How to deploy on Railway
------------------------

1. Create a new GitHub repo and upload all these files, OR upload them directly in Railway.

2. On Railway:
   - Create New Project -> Deploy from GitHub (this repo).
   - After first deploy, go to "Variables" and set:

     BOT_TOKEN  = your Telegram bot token (from @BotFather)
     WEBAPP_URL = your Railway URL, e.g.
                  https://your-app-name.up.railway.app

3. Redeploy the service if needed.

4. Test in browser:
   - https://your-app-name.up.railway.app/
     -> should show: "Spin Wheel Telegram Bot is running ✅"

   - https://your-app-name.up.railway.app/wheel
     -> should show the spin wheel UI.

5. Open your bot in Telegram and send:

   /start

   You should receive a welcome message with a button:
   "🎰 Open Spin Wheel"

   Tap the button to open the wheel in a popup WebApp.
