import os
import threading
import logging

from flask import Flask, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wheelbot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://your-app.up.railway.app

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    wheel_url = f"{WEBAPP_URL}/wheel"
    button = InlineKeyboardButton("🎰 Open Spin Wheel", web_app=WebAppInfo(url=wheel_url))
    await update.message.reply_text(
        "Welcome! 🎉\nPress the button below to spin the wheel!",
        reply_markup=InlineKeyboardMarkup([[button]])
    )
    log.info("User %s used /start", update.effective_user.id)

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    log.info("🚀 Bot polling started...")
    app.run_polling()

app = Flask(__name__)

@app.route("/")
def index():
    return "Spin Wheel Telegram Bot is running ✅"

@app.route("/wheel")
def wheel():
    return send_from_directory(".", "wheel.html")

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    log.info(f"🌐 Flask running on port {port}")
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot()
