import os
import threading
import logging
import time
import base64
from datetime import datetime, timedelta

import requests
from flask import Flask, send_from_directory, request, jsonify

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wheelbot-v4.1")

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://web-production-f91a3.up.railway.app
TARGET_GROUP_ID_ENV = os.getenv("TARGET_GROUP_ID")  # e.g. -1003317283401

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set")
if not TARGET_GROUP_ID_ENV:
    raise RuntimeError("TARGET_GROUP_ID is not set")

try:
    TARGET_GROUP_ID = int(TARGET_GROUP_ID_ENV.strip())
except ValueError:
    TARGET_GROUP_ID = TARGET_GROUP_ID_ENV.strip()

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# In-memory user states: chat_id -> dict
USER_STATES = {}

app = Flask(__name__)


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


def send_start_message(chat_id: int):
    # add version param to break Telegram WebApp cache
    wheel_url = f"{WEBAPP_URL}/wheel?v=41"
    text = (
        "🎰 សូមស្វាគមន៍មកកាន់កង់រង្វាន់!\n"
        "ចុចប៊ូតុងខាងក្រោមដើម្បី Spin Wheel 🎯"
    )
    reply_markup = {
        "inline_keyboard": [[
            {
                "text": "🎰 Open Spin Wheel",
                "web_app": {"url": wheel_url},
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
            log.error("sendStart failed: %s", r.text)
    except Exception:
        log.exception("Error sending start message")


def polling_loop():
    log.info("🚀 Bot polling loop started")
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

                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                if not chat_id:
                    continue

                text = (message.get("text") or "").strip()
                from_user = message.get("from") or {}
                username = from_user.get("username")

                state = USER_STATES.get(chat_id)

                # Handle form flow if user is in state
                if state and text:
                    stage = state.get("stage")

                    # 1) waiting for full name
                    if stage == "waiting_name":
                        state["name"] = text
                        state["stage"] = "waiting_phone"
                        send_message(
                            chat_id,
                            "📞 សូមបញ្ចូលលេខទូរស័ព្ទរបស់អ្នក។"
                        )
                        continue

                    # 2) waiting for phone
                    if stage == "waiting_phone":
                        state["phone"] = text
                        prize = state.get("prize", "Unknown prize")
                        name = state.get("name", "-")
                        phone = state.get("phone", "-")
                        file_id = state.get("file_id")

                        # confirm to user
                        confirm = (
                            "🎉 បញ្ចប់ការបំពេញព័ត៌មាន!\n"
                            "សូមរង់ចាំភ្នាក់ងារទាក់ទងមកវិញ 🙏\n\n"
                            f"🎁 Prize: {prize}\n"
                            f"👤 Name: {name}\n"
                            f"📞 Phone: {phone}"
                        )
                        send_message(chat_id, confirm)

                        # send to group
                        now_bkk = datetime.utcnow() + timedelta(hours=7)
                        dt_str = now_bkk.strftime("%Y-%m-%d %H:%M:%S")
                        uname_str = f"@{username}" if username else "-"

                        summary = (
                            f"🎁 *New Prize Claim*\n\n"
                            f"📅 DATE/TIME (Bangkok): `{dt_str}`\n"
                            f"🆔 ID: `{chat_id}`\n"
                            f"👤 Full name: *{name}*\n"
                            f"📛 Username: {uname_str}\n"
                            f"📞 Phone: `{phone}`\n"
                            f"🎯 Prize: *{prize}*"
                        )

                        try:
                            if file_id:
                                r3 = requests.post(
                                    f"{API_URL}/sendPhoto",
                                    json={
                                        "chat_id": TARGET_GROUP_ID,
                                        "photo": file_id,
                                        "caption": summary,
                                        "parse_mode": "Markdown",
                                    },
                                    timeout=30,
                                )
                            else:
                                r3 = requests.post(
                                    f"{API_URL}/sendMessage",
                                    json={
                                        "chat_id": TARGET_GROUP_ID,
                                        "text": summary,
                                        "parse_mode": "Markdown",
                                    },
                                    timeout=30,
                                )
                            if not r3.ok:
                                log.error("send to group failed: %s", r3.text)
                        except Exception:
                            log.exception("Error sending to group")

                        USER_STATES.pop(chat_id, None)
                        continue

                # No active state: handle /start
                if text == "/start":
                    send_start_message(chat_id)
                    continue

        except Exception:
            log.exception("Error in polling loop")
            time.sleep(5)


@app.route("/")
def index():
    return "Spin Wheel Telegram Bot v4.1 is running ✅"


@app.route("/wheel")
def wheel():
    return send_from_directory(".", "wheel.html")


@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True, silent=True) or {}
    log.info("Received /claim: %s", data)

    user_id = data.get("user_id")
    prize = data.get("prize", "Unknown prize")
    image_data = data.get("image")  # may be None for fallback

    if user_id is None:
        return jsonify({"ok": False, "error": "missing user_id"}), 400

    try:
        chat_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "bad user_id"}), 400

    file_id = None

    # Try to decode screenshot if present (primary flow)
    if image_data:
        try:
            prefix = "base64,"
            idx = image_data.find(prefix)
            if idx != -1:
                b64_data = image_data[idx + len(prefix):]
            else:
                # assume full dataURL or plain base64
                if "," in image_data:
                    b64_data = image_data.split(",", 1)[1]
                else:
                    b64_data = image_data
            img_bytes = base64.b64decode(b64_data)

            files = {"photo": ("wheel.png", img_bytes)}
            caption = f"🎯 Prize: {prize}"

            resp = requests.post(
                f"{API_URL}/sendPhoto",
                data={"chat_id": chat_id, "caption": caption},
                files=files,
                timeout=30,
            )
            if resp.ok:
                try:
                    photos = resp.json()["result"]["photo"]
                    file_id = photos[-1]["file_id"]
                except Exception:
                    file_id = None
            else:
                log.error("sendPhoto to user failed: %s", resp.text)
        except Exception:
            log.exception("Failed to decode or send screenshot, falling back to text only")

    # Setup user state regardless of screenshot success
    USER_STATES[chat_id] = {
        "stage": "waiting_name",
        "prize": prize,
        "file_id": file_id,
    }

    # Ask for full name (Khmer)
    msg = (
        f"🎉 អបអរសាទរ! អ្នកបានឈ្នះរង្វាន់: *{prize}*\n\n"
        "✍️ សូមផ្ញើឈ្មោះពេញរបស់អ្នកមកខ្ញុំ។"
    )
    send_message(chat_id, msg, parse_mode="Markdown")

    return jsonify({"ok": True})


def run_flask():
    port = int(os.environ.get("PORT", 8000))
    log.info("🌐 Flask running on port %s", port)
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    polling_loop()
