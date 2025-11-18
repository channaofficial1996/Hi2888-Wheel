# main.py  — Spin Wheel Bot (Flask + Polling, Railway ready)

import os
import threading
import logging

from flask import Flask, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------- Logging ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("spinwheel")

# ---------- ENV ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://web-production-32a7e.up.railway.app

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set (e.g. https://xxx.up.railway.app)")

# ---------- Telegram handlers ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wheel_url = f"{WEBAPP_URL}/wheel"

    keyboard = [[
        InlineKeyboardButton(
            text="🎰 Open Spin Wheel",
            web_app=WebAppInfo(url=wheel_url)
        )
    ]]

    await update.message.reply_text(
        "Welcome! 🎉\nClick the button below to spin the wheel.",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    log.info("Handled /start from user %s", update.effective_user.id)


def run_bot():
    """Run Telegram bot with polling (main job)."""
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    log.info("Starting bot polling...")
    application.run_polling()


# ---------- Flask app ----------
flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return "Spin Wheel Telegram Bot is running ✅"

@flask_app.route("/wheel")
def wheel_page():
    # Serve wheel.html from current directory
    return send_from_directory(".", "wheel.html")

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    log.info(f"Starting Flask on port {port}")
    flask_app.run(host="0.0.0.0", port=port)


# ---------- Main ----------
if __name__ == "__main__":
    # Run Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Run bot in main thread
    run_bot()
