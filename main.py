# main.py  — Spin Wheel Bot using Webhook (Railway ready)
import os
from pathlib import Path

from aiohttp import web
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import Application, CommandHandler, ContextTypes

# ========================
# ENV CONFIG
# ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")  # e.g. https://web-production-32a7e.up.railway.app

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
if not WEBAPP_URL:
    raise RuntimeError("WEBAPP_URL is not set (e.g. https://xxx.up.railway.app)")


# ========================
# TELEGRAM HANDLERS
# ========================
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


# ========================
# AIOHTTP + WEBHOOK
# ========================
async def handle_webhook(request: web.Request) -> web.Response:
    """Receive updates from Telegram and pass to PTB Application."""
    app: Application = request.app["tg_app"]
    data = await request.json()
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return web.Response(text="OK")


async def index(request: web.Request) -> web.Response:
    return web.Response(
        text="Spin Wheel Telegram Bot is running ✅",
        content_type="text/html",
    )


async def wheel_page(request: web.Request) -> web.FileResponse:
    wheel_file = Path(__file__).with_name("wheel.html")
    return web.FileResponse(wheel_file)


async def on_startup(app: web.Application):
    """Start telegram Application + set webhook."""
    tg_app: Application = app["tg_app"]

    await tg_app.initialize()
    await tg_app.start()

    webhook_url = f"{WEBAPP_URL}/webhook"
    await tg_app.bot.set_webhook(webhook_url)

    print(f"[startup] Webhook set to: {webhook_url}")


async def on_shutdown(app: web.Application):
    """Cleanup when server stops."""
    tg_app: Application = app["tg_app"]
    await tg_app.bot.delete_webhook()
    await tg_app.stop()
    await tg_app.shutdown()
    print("[shutdown] Telegram bot stopped")


def main():
    # Telegram Application
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start))

    # Aiohttp web app
    web_app = web.Application()
    web_app["tg_app"] = tg_app

    web_app.router.add_get("/", index)
    web_app.router.add_get("/wheel", wheel_page)
    web_app.router.add_post("/webhook", handle_webhook)

    web_app.on_startup.append(on_startup)
    web_app.on_shutdown.append(on_shutdown)

    port = int(os.environ.get("PORT", 8000))
    web.run_app(web_app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
