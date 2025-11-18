import os
import threading

from flask import Flask, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

# ========================
# ENV CONFIG
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://your-app.up.railway.app

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set (e.g. https://your-app.up.railway.app)")

# ========================
# TELEGRAM BOT HANDLERS
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send button to open spin wheel WebApp."""
    wheel_url = f"{WEBAPP_URL}/wheel"

    keyboard = [
        [
            InlineKeyboardButton(
                text="🎰 Open Spin Wheel",
                web_app=WebAppInfo(url=wheel_url)
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome! 🎉\nClick the button below to open the spin wheel.",
        reply_markup=reply_markup,
    )


def run_bot():
    """Run Telegram bot with polling."""
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.run_polling()


# ========================
# FLASK APP (for Railway & WebApp)
# ========================

flask_app = Flask(__name__)


@flask_app.route("/")
def index():
    return "Spin Wheel Telegram Bot is running ✅"


@flask_app.route("/wheel")
def wheel_page():
    # Serve the wheel.html file from current directory
    return send_from_directory(".", "wheel.html")


def run_flask():
    port = int(os.environ.get("PORT", 8000))
    flask_app.run(host="0.0.0.0", port=port)


# ========================
# MAIN ENTRY
# ========================

if __name__ == "__main__":
    # Run bot in background thread
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    # Run Flask (main thread – for Railway)
    run_flask()
