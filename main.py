# main.py — 2888 Wheel v4.2.1 PRO
# - Flask run on port 8080
# - /wheel serve wheel.html
# - /claim ពី WebApp -> DM (Screenshot + Prize + Name + Phone) -> Report ទៅ Group
#
# ENV (Railway Variables):
#   BOT_TOKEN         = "....."
#   WEBAPP_URL        = "https://web-production-f91a3.up.railway.app"
#   TARGET_GROUP_ID   = "-1003317283401"
#   MAX_DAILY_CLAIMS  = "20"         (optional)
#   MIN_SECONDS_BETWEEN_CLAIMS = "60" (optional)

import os
import time
import base64
import logging
from datetime import datetime, date
from io import BytesIO
from threading import Thread

import requests
from flask import Flask, request, jsonify, send_from_directory

# ---------- ENV ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = (os.getenv("WEBAPP_URL") or "").rstrip("/")
TARGET_GROUP_ID = os.getenv("TARGET_GROUP_ID")

MAX_DAILY_CLAIMS = int(os.getenv("MAX_DAILY_CLAIMS", "20"))
MIN_SECONDS_BETWEEN_CLAIMS = int(os.getenv("MIN_SECONDS_BETWEEN_CLAIMS", "60"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL not set")
if not TARGET_GROUP_ID:
    raise RuntimeError("TARGET_GROUP_ID not set")

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("wheelbot-v4-2-1")

# user_id -> state
user_states = {}      # វិនិយោគ state សម្រាប់ flow: name -> phone
# user_id -> counters
user_limits = {}      # {"last_ts": float, "day": "YYYY-MM-DD", "count": int}

# ---------- Telegram helpers ----------
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


def send_message(chat_id, text, reply_markup=None, parse_html: bool = True):
    params = {
        "chat_id": chat_id,
        "text": text,
    }
    if parse_html:
        params["parse_mode"] = "HTML"
    if reply_markup:
        params["reply_markup"] = reply_markup
    return tg_request("sendMessage", params)


def send_photo(chat_id, photo, caption=None):
    """
    photo អាចជា file_id (str) ឬ BytesIO.
    Caption នៅទីនេះ យើងមិនប្រើ HTML tag ទេ -> សុទ្ធតែ text សាមញ្ញ។
    """
    if isinstance(photo, str) and not hasattr(photo, "read"):
        params = {
            "chat_id": chat_id,
            "photo": photo,
        }
        if caption:
            params["caption"] = caption
        return tg_request("sendPhoto", params)
    else:
        files = {"photo": ("wheel.png", photo, "image/png")}
        params = {"chat_id": chat_id}
        if caption:
            params["caption"] = caption
        return tg_request("sendPhoto", params, files=files)


def send_start_message(chat_id: int):
    wheel_url = f"{WEBAPP_URL}/wheel?cid={chat_id}&v=4_2_1"
    text = (
        "🎰 សូមស្វាគមន៍មកកាន់កម្មវិធីកង់រង្វាន់!\n"
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


def check_rate_limit(user_id: str):
    """បងារ Claim ជាធម្មតា: limit seconds និង limit per day."""
    now_ts = time.time()
    today = date.today().isoformat()

    info = user_limits.get(user_id)
    if not info:
        info = {"last_ts": 0.0, "day": today, "count": 0}
        user_limits[user_id] = info

    # reset count បើថ្ងៃថ្មី
    if info["day"] != today:
        info["day"] = today
        info["count"] = 0

    # second-based limit
    if now_ts - info["last_ts"] < MIN_SECONDS_BETWEEN_CLAIMS:
        return False, "⏳ សូមរង់ចាំបន្តិច មុនពេល SPIN ឡើងវិញ។"

    # daily count limit
    if info["count"] >= MAX_DAILY_CLAIMS:
        return False, "🚫 អ្នកបានលេងពេញកូតាប្រចាំថ្ងៃរួចហើយ។ សូមមកលេងម្ដងទៀតថ្ងៃស្អែក។"

    # OK
    info["last_ts"] = now_ts
    info["count"] += 1
    return True, None

# ---------- Flask app ----------
app = Flask(__name__)


@app.route("/")
def index():
    return "Spin Wheel Telegram Bot v4.2.1 PRO is running ✅"


@app.route("/wheel")
def wheel_page():
    # serve wheel.html ជា static file (ដាក់ឯកសារនេះនៅថតដូច main.py)
    return send_from_directory(".", "wheel.html")


@app.route("/claim", methods=["POST"])
def claim():
    """
    JSON ត្រូវមកពី wheel.html:
    {
      "user_id": 5529...,
      "prize": "Lucky Spin x2",
      "image": "data:image/png;base64,...."
    }
    """
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    prize = data.get("prize")
    image_data_url = data.get("image")

    if not user_id:
        log.error("/claim missing user_id: %s", data)
        return jsonify({"ok": False, "error": "missing user_id"}), 400

    user_id_str = str(user_id)
    log.info("Received claim from %s: %s", user_id_str, prize)

    # Rate-limit & daily quota
    ok, msg = check_rate_limit(user_id_str)
    if not ok:
        # ផ្ញើសារ notify ទៅ user
        send_message(user_id, msg, parse_html=False)
        return jsonify({"ok": False, "error": "rate_limited"}), 429

    photo_id = None

    # Decode & send screenshot (optional but recommended)
    if image_data_url and image_data_url.startswith("data:image"):
        try:
            header, b64 = image_data_url.split(",", 1)
            img_bytes = base64.b64decode(b64)
            bio = BytesIO(img_bytes)
            bio.name = "wheel.png"

            # caption សាមញ្ញ គ្មាន HTML
            cap = f"🎰 លទ្ធផលកង់រង្វាន់របស់អ្នក: {prize}"
            resp = send_photo(user_id, bio, caption=cap)
            if resp and resp.get("ok"):
                ph = resp["result"]["photo"]
                photo_id = ph[-1]["file_id"]
        except Exception as e:
            log.exception("Failed to decode/send screenshot: %s", e)

    # Save state: បន្ទាប់សួរឈ្មោះ
    user_states[user_id_str] = {
        "step": "ask_name",
        "prize": prize,
        "photo_id": photo_id,
        "created_at": time.time(),
    }

    # sleep តិចៗ ដើម្បី WebApp បិទសិន (ជួយឲ្យ message មិនបាត់)
    time.sleep(1.0)

    # Ask full name
    text = (
        f"🎉 អបអរសាទរ! អ្នកទទួលបានរង្វាន់៖ <b>{prize}</b> 🎁\n\n"
        "✍ សូមវាយបញ្ចូល <b>ឈ្មោះពេញ</b> របស់អ្នក។"
    )
    send_message(user_id, text, parse_html=True)

    return jsonify({"ok": True})


# ---------- Telegram long-poll ----------
def handle_update(update: dict):
    if "message" not in update:
        return

    msg = update["message"]
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    text = msg.get("text", "")
    from_user = msg.get("from", {})
    user_id = from_user.get("id")
    user_id_str = str(user_id)

    # Commands
    if isinstance(text, str) and text.startswith("/start"):
        send_start_message(chat_id)
        return

    # Only handle text for state machine
    if not isinstance(text, str):
        return

    state = user_states.get(user_id_str)
    if not state:
        # no active claim for this user
        return

    step = state.get("step")

    # ----- STEP 1: Ask name -----
    if step == "ask_name":
        full_name = text.strip()
        if not full_name:
            send_message(chat_id, "🙏 សូមវាយបញ្ចូល <b>ឈ្មោះពេញ</b> ម្តងទៀត។")
            return

        state["full_name"] = full_name
        state["step"] = "ask_phone"

        send_message(
            chat_id,
            f"✅ បានឈ្មោះ៖ <b>{full_name}</b>\n\n"
            "📞 សូមវាយបញ្ចូល <b>លេខទូរស័ព្ទ</b> របស់អ្នក។",
        )
        return

    # ----- STEP 2: Ask phone -----
    if step == "ask_phone":
        phone = text.strip()
        if not phone:
            send_message(chat_id, "📞 សូមវាយបញ្ចូលលេខទូរស័ព្ទម្តងទៀត។")
            return

        state["phone"] = phone
        state["step"] = "done"

        prize = state.get("prize", "-")
        photo_id = state.get("photo_id")
        username = from_user.get("username")
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Confirm to user
        send_message(
            chat_id,
            "🎉 <b>បញ្ជាក់ទទួលបានរង្វាន់ជោគជ័យ!</b>\n\n"
            f"🎁 Prize: <b>{prize}</b>\n"
            f"👤 Name: <b>{state['full_name']}</b>\n"
            f"📞 Phone: <b>{phone}</b>\n\n"
            "សូមរង់ចាំភ្នាក់ងារទាក់ទងមកវិញ ❤️",
        )

        # Report message to group (plain text caption)
        report_lines = [
            "🎁 New Prize Claim",
            "",
            f"📅 Date/Time (Bangkok): {now_str}",
            f"🆔 User ID: {user_id_str}",
            f"👤 Full name: {state['full_name']}",
            f"📞 Phone: {phone}",
            f"🎯 Prize: {prize}",
        ]
        if username:
            report_lines.append(f"📛 Username: @{username}")

        report = "\n".join(report_lines)

        if photo_id:
            send_photo(TARGET_GROUP_ID, photo_id, caption=report)
        else:
            send_message(TARGET_GROUP_ID, report, parse_html=False)

        # Clear state
        user_states.pop(user_id_str, None)


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
    # Run polling + Flask in single process
    Thread(target=run_bot_loop, daemon=True).start()
    log.info("🌐 Flask running on port 8080")
    app.run(host="0.0.0.0", port=8080)
