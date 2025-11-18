import os
import threading
import logging
import time
import base64
from datetime import datetime, timedelta

import requests
from flask import Flask, send_from_directory, request

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wheelbot-lite")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://web-production-f91a3.up.railway.app
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")  # e.g. -1003317283401

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set")
if not TARGET_GROUP_ID:
    raise RuntimeError("TARGET_GROUP_ID is not set")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# user state memory
USER_STATES = {}


def send_message(chat_id, text, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)
        if not r.ok:
            log.error("sendMessage failed: %s", r.text)
    except Exception:
        log.exception("Error sending message")


def send_start(chat_id: int):
    wheel_url = f"{WEBAPP_URL}/wheel?v=4"   # force Telegram WebApp refresh
    text = (
        "🎰 សូមស្វាគមន៍មកកាន់កង់រង្វាន់!\n"
        "ចុចប៊ូតុងខាងក្រោមដើម្បី SPIN 🎯"
    )
    reply_markup = {
        "inline_keyboard": [[
            {"text": "🎰 Open Spin Wheel", "web_app": {"url": wheel_url}}
        ]]
    }
    try:
        r = requests.post(
            f"{API_URL}/sendMessage",
            json={"chat_id": chat_id, "text": text, "reply_markup": reply_markup},
            timeout=10,
        )
        if not r.ok:
            log.error("sendStart failed: %s", r.text)
    except Exception:
        log.exception("Error sending start message")


def polling_loop():
    log.info("🚀 Bot polling started…")
    offset = None
    while True:
        try:
            r = requests.get(
                f"{API_URL}/getUpdates",
                params={"timeout": 50, "offset": offset},
                timeout=60,
            )
            if not r.ok:
                time.sleep(4)
                continue

            data = r.json()
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message")
                if not msg:
                    continue

                chat_id = msg["chat"]["id"]
                text = (msg.get("text") or "").strip()
                username = msg["chat"].get("username")

                # state machine
                state = USER_STATES.get(chat_id)

                if state:
                    stage = state.get("stage")

                    # waiting full name
                    if stage == "name":
                        state["name"] = text
                        state["stage"] = "phone"
                        send_message(chat_id, "📞 សូមបញ្ចូលលេខទូរស័ព្ទរបស់អ្នក")
                        continue

                    # waiting phone
                    if stage == "phone":
                        state["phone"] = text

                        now_bkk = datetime.utcnow() + timedelta(hours=7)
                        dt = now_bkk.strftime("%Y-%m-%d %H:%M:%S")

                        prize = state.get("prize")
                        uname = f"@{username}" if username else "-"

                        summary = (
                            f"📅 DATE/TIME (Bangkok): {dt}\n"
                            f"🆔 ID: {chat_id}\n"
                            f"👤 Full name: {state['name']}\n"
                            f"📛 Username: {uname}\n"
                            f"📞 Phone: {state['phone']}\n"
                            f"🎁 Prize: {prize}"
                        )

                        # send to user
                        send_message(chat_id, "🎉 បញ្ចប់ការចុះឈ្មោះ! សូមរង់ចាំភ្នាក់ងារទាក់ទង 🙏")

                        # forward to group
                        try:
                            file_id = state.get("file_id")
                            if file_id:
                                requests.post(
                                    f"{API_URL}/sendPhoto",
                                    json={
                                        "chat_id": TARGET_GROUP_ID,
                                        "photo": file_id,
                                        "caption": summary,
                                    },
                                    timeout=30
                                )
                            else:
                                requests.post(
                                    f"{API_URL}/sendMessage",
                                    json={"chat_id": TARGET_GROUP_ID, "text": summary},
                                    timeout=30
                                )
                        except Exception:
                            log.exception("Failed sending lead to group")

                        USER_STATES.pop(chat_id, None)
                        continue

                # no state → command handling
                if text == "/start":
                    send_start(chat_id)
        except Exception:
            time.sleep(4)


app = Flask(__name__)


@app.route("/")
def index():
    return "Spin Wheel Bot Lite v4 is running ✅"


@app.route("/wheel")
def wheel_page():
    return send_from_directory(".", "wheel.html")


@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True, silent=True) or {}
    image = data.get("image")
    prize = data.get("prize", "Unknown Prize")
    user_id = data.get("user_id")

    if not user_id or not image:
        return {"ok": False}, 400

    chat_id = int(user_id)

    # decode screenshot
    base64data = image.split("base64,")[-1]
    img_bytes = base64.b64decode(base64data)

    resp = requests.post(
        f"{API_URL}/sendPhoto",
        data={"chat_id": chat_id, "caption": f"🎯 Prize: {prize}"},
        files={"photo": ("wheel.png", img_bytes)},
        timeout=30
    )

    file_id = None
    try:
        photos = resp.json()["result"]["photo"]
        file_id = photos[-1]["file_id"]
    except:
        pass

    USER_STATES[chat_id] = {
        "stage": "name",
        "prize": prize,
        "file_id": file_id,
    }

    send_message(chat_id, f"🎉 អបអរសាទរ! អ្នកបានឈ្នះ *{prize}*\n\n✍️ សូមផ្ញើឈ្មោះពេញរបស់អ្នក", parse_mode="Markdown")

    return {"ok": True}


def run_flask():
    port = int(os.environ.get("PORT", 8000))
    log.info("🌐 Flask running on port %s", port)
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    polling_loop()
