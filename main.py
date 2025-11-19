# main.py — 2888 Wheel v4.2.2 PRO
# Flask + Telegram Long Poll + Screenshot Claim
# Author: ChatGPT PRO Upgrade for Channa 🔥

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
log = logging.getLogger("wheelbot-v4-2-2")

# Memory states
user_states = {}      # user_id -> {step, prize, photo_id, full_name, phone}
user_limits = {}      # user_id -> rate-limit info


# ---------- Telegram Helper ----------
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


def send_message(chat_id, text, reply_markup=None, parse_html=True):
    params = {"chat_id": chat_id, "text": text}
    if parse_html:
        params["parse_mode"] = "HTML"
    if reply_markup:
        params["reply_markup"] = reply_markup
    return tg_request("sendMessage", params)


def send_photo(chat_id, photo, caption=None):
    if isinstance(photo, str) and not hasattr(photo, "read"):
        params = {"chat_id": chat_id, "photo": photo}
        if caption:
            params["caption"] = caption
        return tg_request("sendPhoto", params)

    files = {"photo": ("wheel.png", photo, "image/png")}
    params = {"chat_id": chat_id}
    if caption:
        params["caption"] = caption
    return tg_request("sendPhoto", params, files=files)


def send_start_message(chat_id: int):
    wheel_url = f"{WEBAPP_URL}/wheel?cid={chat_id}&v=4_2_2"
    txt = "🎰 សូមស្វាគមន៍មកកាន់កម្មវិធីកង់រង្វាន់!\nចុចប៊ូតុងខាងក្រោម ដើម្បី SPIN 🎯"
    kb = {"inline_keyboard": [[{"text": "🎰 Open Spin Wheel", "web_app": {"url": wheel_url}}]]}
    send_message(chat_id, txt, reply_markup=kb)


# ---------- Limit System ----------
def check_rate_limit(user_id: str):
    now = time.time()
    today = date.today().isoformat()
    info = user_limits.get(user_id)

    if not info:
        info = {"last": 0.0, "day": today, "count": 0}
        user_limits[user_id] = info

    # New day reset
    if info["day"] != today:
        info["day"] = today
        info["count"] = 0

    # Seconds limit
    if now - info["last"] < MIN_SECONDS_BETWEEN_CLAIMS:
        return False, "⏳ សូមរង់ចាំបន្តិច មុនពេល SPIN ឡើងវិញ។"

    # Daily quota
    if info["count"] >= MAX_DAILY_CLAIMS:
        return False, "🚫 ពេញកូតាប្រចាំថ្ងៃ! សូមមកលេងម្ដងទៀតថ្ងៃស្អែក។"

    info["last"] = now
    info["count"] += 1
    return True, None


# ---------- Flask ----------
app = Flask(__name__)


@app.route("/")
def index():
    return "Spin Wheel Bot v4.2.2 PRO Running ✅"


@app.route("/wheel")
def wheel_page():
    return send_from_directory(".", "wheel.html")


@app.route("/claim", methods=["POST"])
def claim():
    data = request.get_json(force=True, silent=True) or {}
    user_id = data.get("user_id")
    prize = data.get("prize")
    image_data = data.get("image")

    if not user_id:
        return jsonify({"ok": False, "error": "missing user_id"}), 400

    uid = str(user_id)

    # Try Again => no name/phone
    if prize and prize.lower().strip() == "try again":
        send_message(
            user_id,
            "🏁 លទ្ធផលរង្វាន់៖ <b>Try Again</b>\n\n"
            "សូមសាកល្បងម្ដងទៀត nhé! 🍀",
        )
        return jsonify({"ok": True})

    # Rate limit checking
    ok, msg = check_rate_limit(uid)
    if not ok:
        send_message(user_id, msg, parse_html=False)
        return jsonify({"ok": False, "error": "rate_limited"}), 429

    photo_id = None
    if image_data and image_data.startswith("data:image"):
        try:
            _, b64 = image_data.split(",", 1)
            img = BytesIO(base64.b64decode(b64))
            img.name = "wheel.png"
            resp = send_photo(user_id, img, caption=f"🎰 លទ្ធផលរង្វាន់: {prize}")
            if resp and resp.get("ok"):
                ph = resp["result"]["photo"]
                photo_id = ph[-1]["file_id"]
        except:
            pass

    user_states[uid] = {"step": "ask_name", "prize": prize, "photo_id": photo_id}
    time.sleep(1)

    send_message(
        user_id,
        f"🎉 អបអរសាទរ! អ្នកទទួលបានរង្វាន់: <b>{prize}</b> 🎁\n\n"
        "✍ សូមវាយបញ្ចូល <b>ឈ្មោះពេញ</b>។",
    )
    return jsonify({"ok": True})

# ---------- Telegram Poll ----------
def handle_update(update: dict):
    if "message" not in update:
        return

    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")
    user_id = msg.get("from", {}).get("id")
    uid = str(user_id)

    # START
    if isinstance(text, str) and text.startswith("/start"):
        send_start_message(chat_id)
        return

    if not isinstance(text, str):
        return

    st = user_states.get(uid)
    if not st:
        return

    # STEP 1: NAME
    if st["step"] == "ask_name":
        full = text.strip()
        if not full:
            send_message(chat_id, "🙏 សូមវាយឈ្មោះម្តងទៀត។")
            return
        st["full_name"] = full
        st["step"] = "ask_phone"
        send_message(chat_id, f"👤 ឈ្មោះ៖ <b>{full}</b>\n\n📞 សូមវាយបញ្ចូលលេខទូរស័ព្ទ។")
        return

    # STEP 2: PHONE
    if st["step"] == "ask_phone":
        phone = text.strip()
        if not phone:
            send_message(chat_id, "📞 សូមវាយលេខទូរស័ព្ទម្តងទៀត។")
            return

        st["phone"] = phone
        st["step"] = "done"

        prize = st["prize"]
        photo_id = st["photo_id"]
        username = msg.get("from", {}).get("username")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Final message with contact buttons
        final_txt = (
            "🎉 <b>បញ្ជាក់ទទួលបានរង្វាន់ជោគជ័យ!</b>\n\n"
            f"🎁 Prize: <b>{prize}</b>\n"
            f"👤 Name: <b>{st['full_name']}</b>\n"
            f"📞 Phone: <b>{phone}</b>\n\n"
            "សូមរង់ចាំភ្នាក់ងារទាក់ទងមកវិញ ❤️\n"
            "បើចង់ទាក់ទងភ្នាក់ងារទាន់ចិត្ត៖"
        )

        kb = {
            "inline_keyboard": [
                [
                    {"text": "💬 Telegram", "url": "https://t.me/Hi2888CS1"},
                    {"text": "📩 Messenger", "url": "m.me/920030077853046"},
                ]
            ]
        }

        send_message(chat_id, final_txt, reply_markup=kb)
        
# Report to group (with clickable user id link)
rep = [
    "🎁 New Prize Claim",
    f"📅 {now}",
    f'🆔 User: <a href="tg://user?id={uid}">{uid}</a>',
    f"👤 Full name: <b>{st['full_name']}</b>",
    f"📞 Phone: <b>{phone}</b>",
    f"🎯 Prize: <b>{prize}</b>",
]

if username:
    rep.append(f"📛 Username: @{username}")

txt = "\n".join(rep)

# Send with image if available
if photo_id:
    send_photo(TARGET_GROUP_ID, photo_id, caption=txt, parse_html=True)
else:
    send_message(TARGET_GROUP_ID, txt, parse_html=True)


def run_bot():
    log.info("🚀 Bot polling started")
    offset = None
    while True:
        try:
            r = requests.get(f"{API_URL}/getUpdates", params={"timeout": 50, "offset": offset}, timeout=60).json()
            if not r.get("ok"):
                time.sleep(3)
                continue
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                handle_update(upd)
        except:
            time.sleep(3)


# ---------- START ----------
if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    log.info("🌐 Flask running on 8080")
    app.run(host="0.0.0.0", port=8080)
