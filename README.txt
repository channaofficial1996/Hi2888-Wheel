Spin Wheel Telegram Bot (Railway Ready)
======================================

Files
-----
- main.py        : Telegram bot + Flask server
- wheel.html     : Spin wheel WebApp UI
- requirements.txt
- Procfile       : For Railway

How to use
----------

1. Create a new Git repo with these files, then push to GitHub (or connect directly in Railway).

2. On Railway:
   - Create a new project -> Deploy from GitHub (this repo).
   - After the first deploy, go to Variables and set:

     BOT_TOKEN  = your Telegram bot token
     WEBAPP_URL = your Railway URL (e.g. https://your-app-name.up.railway.app)

3. Redeploy if needed.

4. In Telegram, open your bot and type:

   /start

5. Click: "🎰 Open Spin Wheel"

If WEBAPP_URL is wrong, the WebApp button will not open correctly.
Always copy the exact Railway URL shown in the project overview.
