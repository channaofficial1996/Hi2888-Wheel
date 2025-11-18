import os
import threading
import logging
import time
import requests
from flask import Flask, send_from_directory

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wheelbot-lite")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://your-app.up.railway.app

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ---------------- Telegram basic polling (no external lib) ---------------- #

def send_start_message(chat_id: int):
    wheel_url = f"{WEBAPP_URL}/wheel"
    text = "Welcome! 🎉\nPress the button below to spin the wheel!"
    reply_markup = {
        "inline_keyboard": [[
            {
                "text": "🎰 Open Spin Wheel",
                "web_app": {"url": wheel_url}
            }
        ]]
    }
    try:
        r = requests.post(
            f"{API_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "reply_markup": reply_markup,
            },
            timeout=10,
        )
        if not r.ok:
            log.error("sendMessage failed: %s", r.text)
    except Exception:
        log.exception("Error sending start message")


def run_bot_polling():
    log.info("🚀 Bot polling loop started (requests + long polling)")
    offset = None
    while True:
        try:
            r = requests.get(
                f"{API_URL}/getUpdates",
                params={"timeout": 50, "offset": offset},
                timeout=60,
            )
            if not r.ok:
                log.error("getUpdates failed: %s", r.text)
                time.sleep(5)
                continue

            data = r.json()
            if not data.get("ok"):
                log.error("getUpdates not ok: %s", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message")
                if not message:
                    continue

                text = message.get("text") or ""
                chat = message.get("chat") or {}
                chat_id = chat.get("id")

                if not chat_id:
                    continue

                if text.startswith("/start"):
                    log.info("Received /start from chat_id=%s", chat_id)
                    send_start_message(chat_id)

        except Exception:
            log.exception("Error in polling loop")
            time.sleep(5)


# ---------------- Flask web app for Railway & wheel UI ---------------- #

app = Flask(__name__)

@app.route("/")
def index():
    return "Spin Wheel Telegram Bot (lite) is running ✅"

@app.route("/wheel")
def wheel():
    return send_from_directory(".", "wheel.html")

def run_flask():
    port = int(os.environ.get("PORT", 8000))
    log.info(f"🌐 Flask running on port {port}")
    app.run(host="0.0.0.0", port=port)


# ---------------- Main entry ---------------- #

if __name__ == "__main__":
    # Start Flask in background
    threading.Thread(target=run_flask, daemon=True).start()
    # Start polling in main thread
    run_bot_polling()
