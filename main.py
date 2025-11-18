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
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://your-app.up.railway.app
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")  # e.g. -1001234567890 (optional)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set")

if TARGET_GROUP_ID:
    try:
        TARGET_GROUP_ID = int(TARGET_GROUP_ID)
    except ValueError:
        log.warning("TARGET_GROUP_ID is not a valid int, using as string")
else:
    TARGET_GROUP_ID = None

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# In-memory user states: chat_id -> dict
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


def send_start_message(chat_id: int):
    wheel_url = f"{WEBAPP_URL}/wheel"
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

                chat = message.get("chat") or {}
                chat_id = chat.get("id")
                if not chat_id:
                    continue

                text = (message.get("text") or "").strip()

                # Check if this user is in a conversation flow
                state = USER_STATES.get(chat_id)
                if state and text:
                    stage = state.get("stage")

                    # 1) Waiting for full name
                    if stage == "waiting_name":
                        state["name"] = text
                        state["stage"] = "waiting_phone"
                        send_message(
                            chat_id,
                            "📞 សូមបញ្ចូលលេខទូរស័ព្ទរបស់អ្នក (ABA / Telegram)។"
                        )
                        continue

                    # 2) Waiting for phone number
                    if stage == "waiting_phone":
                        state["phone"] = text
                        prize = state.get("prize", "Unknown prize")
                        username = state.get("username")
                        name = state.get("name")
                        phone = state.get("phone")
                        file_id = state.get("file_id")

                        # Confirm to user
                        confirm = (
                            "✅ ឈ្មោះ និងលេខទូរស័ព្ទរបស់អ្នកត្រូវបានរក្សាទុក។\n"
                            "សូមរង់ចាំភ្នាក់ងារទាក់ទងមកវិញ។\n\n"
                            f"🎁 Prize: {prize}\n"
                            f"👤 Name: {name}\n"
                            f"📞 Phone: {phone}"
                        )
                        send_message(chat_id, confirm)

                        # Send summary to group if configured
                        if TARGET_GROUP_ID:
                            now_bkk = datetime.utcnow() + timedelta(hours=7)
                            dt_str = now_bkk.strftime("%Y-%m-%d %H:%M:%S")
                            uname_str = f"@{username}" if username else "-"

                            summary = (
                                f"📅 DATE/TIME (Bangkok): {dt_str}\n"
                                f"🆔 ID: {chat_id}\n"
                                f"👤 Full name: {name}\n"
                                f"📛 Username: {uname_str}\n"
                                f"📞 Phone: {phone}\n"
                                f"🎁 Prize: {prize}"
                            )

                            try:
                                if file_id:
                                    r3 = requests.post(
                                        f"{API_URL}/sendPhoto",
                                        json={
                                            "chat_id": TARGET_GROUP_ID,
                                            "photo": file_id,
                                            "caption": summary,
                                        },
                                        timeout=30,
                                    )
                                else:
                                    r3 = requests.post(
                                        f"{API_URL}/sendMessage",
                                        json={
                                            "chat_id": TARGET_GROUP_ID,
                                            "text": summary,
                                        },
                                        timeout=30,
                                    )
                                if not r3.ok:
                                    log.error("send to group failed: %s", r3.text)
                            except Exception:
                                log.exception("Error sending summary to group")

                        # Clear state
                        USER_STATES.pop(chat_id, None)
                        continue

                # No active state: handle commands
                if text.startswith("/start"):
                    log.info("Received /start from chat_id=%s", chat_id)
                    send_start_message(chat_id)
                    continue

        except Exception:
            log.exception("Error in polling loop")
            time.sleep(5)


app = Flask(__name__)


@app.route("/")
def index():
    return "Spin Wheel Telegram Bot (lite v3) is running ✅"


@app.route("/wheel")
def wheel():
    return send_from_directory(".", "wheel.html")


@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True, silent=True) or {}
    image_data = data.get("image")
    prize = data.get("prize", "Unknown prize")
    user_id = data.get("user_id")
    username = data.get("username")
    first_name = data.get("first_name")
    last_name = data.get("last_name")

    if not image_data or user_id is None:
        return {"ok": False, "error": "missing image or user_id"}, 400

    try:
        chat_id = int(user_id)
    except (TypeError, ValueError):
        return {"ok": False, "error": "bad user_id"}, 400

    # Decode base64 image
    prefix = "base64,"
    idx = image_data.find(prefix)
    if idx != -1:
        b64_data = image_data[idx + len(prefix):]
    else:
        b64_data = image_data

    try:
        img_bytes = base64.b64decode(b64_data)
    except Exception:
        log.exception("Failed to decode image")
        return {"ok": False, "error": "decode_error"}, 400

    files = {"photo": ("wheel.png", img_bytes)}
    caption = f"🎉 Prize: {prize}"

    try:
        resp = requests.post(
            f"{API_URL}/sendPhoto",
            data={"chat_id": chat_id, "caption": caption},
            files=files,
            timeout=30,
        )
        if not resp.ok:
            log.error("sendPhoto failed: %s", resp.text)
            return {"ok": False, "error": "sendPhoto_failed"}, 500

        res_json = resp.json()
        file_id = None
        try:
            photos = res_json["result"]["photo"]
            file_id = photos[-1]["file_id"]
        except Exception:
            pass

        # Save state for this user
        USER_STATES[chat_id] = {
            "stage": "waiting_name",
            "prize": prize,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "file_id": file_id,
        }

        # Ask for full name (Khmer)
        msg = (
            f"🎉 អបអរសាទរ! អ្នកបានរង្វាន់: *{prize}*\n\n"
            "សូមផ្ញើឈ្មោះពេញរបស់អ្នកមកខ្ញុំ។"
        )
        send_message(chat_id, msg, parse_mode="Markdown")

    except Exception:
        log.exception("Error in /claim sending photo")
        return {"ok": False, "error": "exception"}, 500

    return {"ok": True}


def run_flask():
    port = int(os.environ.get("PORT", 8000))
    log.info(f"🌐 Flask running on port {port}")
    app.run(host="0.0.0.0", port=port)


if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_bot_polling()
