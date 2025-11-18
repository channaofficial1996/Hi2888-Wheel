# main.py  — 2888 Wheel (final v5)
# - Flask run on port 8080
# - /wheel serve wheel.html
# - /claim ពី WebApp -> bot DM (Name, Phone) -> report ទៅ group

import os
import time
import base64
import logging
from datetime import datetime
from io import BytesIO
from threading import Thread

import requests
from flask import Flask, request, jsonify, send_from_directory

# --------- ENV ---------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "").rstrip("/")
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")  # keep as string

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL not set")
if not TARGET_GROUP_ID:
    raise RuntimeError("TARGET_GROUP_ID not set")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wheelbot-final")

# user_id -> state data
user_states = {}  # { user_id: {"step": "...", "prize": "...", "photo_id": "..."} }

# --------- Telegram helpers ---------
def tg_request(method: str, params: dict = None, files: dict = None):
    url = f"{API_URL}/{method}"
    try:
        if files:
            r = requests.post(url, data=params or {}, files=files, timeout=30)
        else:
            r = requests.post(url, json=params or {}, timeout=30)
        if not r.ok:
            log.error("Telegram API error %s: %s", method, r.text)
        return r.json()
    except Exception as e:
        log.exception("Telegram request failed: %s", e)
        return None


def send_message(chat_id, text, reply_markup=None):
    return tg_request(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
        },
    )


def send_photo(chat_id, photo, caption=None):
    """photo can be file_id (str) or BytesIO."""
    if isinstance(photo, str) and not hasattr(photo, "read"):
        # existing file_id
        return tg_request(
            "sendPhoto",
            {"chat_id": chat_id, "photo": photo, "caption": caption or ""},
        )
    else:
        files = {"photo": ("wheel.png", photo, "image/png")}
        return tg_request(
            "sendPhoto",
            {"chat_id": chat_id, "caption": caption or ""},
            files=files,
        )


def send_start_message(chat_id: int):
    # បញ្ជូន chat_id (cid) ទៅក្នុង URL ដើម្បី WebApp ប្រើ
    wheel_url = f"{WEBAPP_URL}/wheel?cid={chat_id}&v=42"

    text = (
        "🎰 សូមស្វាគមន៍មកកាន់កង់រង្វាន់!\n"
        "ចុចប៊ូតុងខាងក្រោម ដើម្បីចាប់ផ្តើម SPIN Wheel 🎯"
    )
    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "🎰 Open Spin Wheel",
                    "web_app": {"url": wheel_url},
                }
            ]
        ]
    }
    send_message(chat_id, text, reply_markup=reply_markup)


# --------- Flask app ---------
app = Flask(__name__)


@app.route("/")
def index():
    return "Spin Wheel Telegram Bot is running ✅"


# 👉 serve wheel.html ដោយផ្ទាល់ (wheel.html នៅគន្លងដូច main.py)
@app.route("/wheel")
def wheel_page():
    return send_from_directory(".", "wheel.html")


@app.route("/claim", methods=["POST"])
def claim():
    """
    Called from wheel.html (WebApp) with JSON:
    { "user_id": "...", "prize": "...", "image": "data:image/png;base64,..." }
    """
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    prize = data.get("prize")
    image_data_url = data.get("image")

    if not user_id:
        log.error("/claim without user_id: %s", data)
        return jsonify({"ok": False, "error": "missing user_id"}), 400

    log.info("Received claim from %s: %s", user_id, prize)

    photo_id = None

    # បើមាន screenshot -> ផ្ញើរូបទៅ user ហើយសរសេរកូដ file_id ទុក
    if image_data_url and image_data_url.startswith("data:image"):
        try:
            header, b64 = image_data_url.split(",", 1)
            img_bytes = base64.b64decode(b64)
            bio = BytesIO(img_bytes)
            bio.name = "wheel.png"
            resp = send_photo(
                user_id,
                bio,
                caption=f"🎰 លទ្ធផលកង់រង្វាន់របស់អ្នក:\n<b>{prize}</b>",
            )
            if resp and resp.get("ok"):
                photo_list = resp["result"]["photo"]
                photo_id = photo_list[-1]["file_id"]
        except Exception as e:
            log.exception("Failed to decode/send screenshot: %s", e)

    # save state
    user_states[str(user_id)] = {
        "step": "ask_name",
        "prize": prize,
        "photo_id": photo_id,
        "created_at": time.time(),
    }

    # ask name
    send_message(
        user_id,
        "🎉 អបអរសាទរ! អ្នកទទួលបានរង្វាន់ <b>{}</b> 🎁\n\n"
        "សូមបញ្ចូល <b>ឈ្មោះពេញ</b> របស់អ្នក៖".format(prize),
    )

    return jsonify({"ok": True})


# --------- Polling loop ---------
def handle_update(update: dict):
    """Handle one Telegram update (for long polling)."""
    if "message" not in update:
        return
    msg = update["message"]
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")
    from_user = msg.get("from", {})
    user_id = from_user.get("id")

    # commands
    if text == "/start":
        send_start_message(chat_id)
        return

    if not isinstance(text, str):
        return

    state = user_states.get(str(user_id))
    if not state:
        return  # no active claim

    step = state.get("step")

    # Step 1: ask_name
    if step == "ask_name":
        full_name = text.strip()
        if not full_name:
            send_message(chat_id, "សូមបញ្ចូល <b>ឈ្មោះពេញ</b> ម្ដងទៀត 🙏")
            return
        state["full_name"] = full_name
        state["step"] = "ask_phone"
        send_message(
            chat_id,
            "✅ បានឈ្មោះ៖ <b>{}</b>\n\nសូមបន្តបញ្ចូល <b>លេខទូរស័ព្ទ</b> របស់អ្នក៖".format(
                full_name
            ),
        )
        return

    # Step 2: ask_phone
    if step == "ask_phone":
        phone = text.strip()
        state["phone"] = phone
        state["step"] = "done"

        prize = state.get("prize", "-")
        photo_id = state.get("photo_id")
        username = from_user.get("username")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # confirm to user
        send_message(
            chat_id,
            "🎉 <b>បញ្ជាក់ជោគជ័យ!</b>\n\n"
            "ឈ្មោះ៖ <b>{}</b>\n"
            "លេខទូរស័ព្ទ៖ <b>{}</b>\n"
            "រង្វាន់៖ <b>{}</b>\n\n"
            "សូមរង់ចាំភ្នាក់ងារ ទាក់ទងមកវិញ ❤️".format(
                state["full_name"], phone, prize
            ),
        )

        # report to group
        report = (
            "🎁 <b>New Prize Claim</b>\n\n"
            f"📅 <b>Date/Time (Bangkok)</b>: {now_str}\n"
            f"🆔 <b>User ID</b>: <code>{user_id}</code>\n"
            f"👤 <b>Full name</b>: {state['full_name']}\n"
            f"📞 <b>Phone</b>: {phone}\n"
            f"🎯 <b>Prize</b>: {prize}\n"
        )
        if username:
            report += f"📛 <b>Username</b>: @{username}\n"

        if photo_id:
            send_photo(TARGET_GROUP_ID, photo_id, caption=report)
        else:
            send_message(TARGET_GROUP_ID, report)

        # cleanup
        user_states.pop(str(user_id), None)


def run_bot_loop():
    log.info("🚀 Bot long-polling loop started")
    offset = None
    while True:
        try:
            resp = requests.get(
                f"{API_URL}/getUpdates",
                params={"timeout": 50, "offset": offset},
                timeout=60,
            ).json()
        except Exception as e:
            log.exception("getUpdates failed: %s", e)
            time.sleep(3)
            continue

        if not resp.get("ok"):
            log.error("getUpdates error: %s", resp)
            time.sleep(3)
            continue

        for upd in resp.get("result", []):
            offset = upd["update_id"] + 1
            handle_update(upd)


if __name__ == "__main__":
    # Railway: run Flask + polling in same process using threads
    Thread(target=run_bot_loop, daemon=True).start()
    log.info("🌐 Flask running on port 8080")
    app.run(host="0.0.0.0", port=8080)
