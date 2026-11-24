"""
ScamShield Telegram bot (free).

Setup:
  1. In Telegram, message @BotFather -> /newbot -> copy the token.
  2. Put TELEGRAM_BOT_TOKEN=... and SCAMSHIELD_API_URL=https://<your-space>.hf.space in .env
  3. python bot/telegram_bot.py      (keep it running; free option: run it on your laptop,
     or as a second free Hugging Face Space / Render background worker)

Users can: send text, forward a suspicious message, send a link, or send a screenshot.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler,
                          filters)

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

API = os.environ.get("SCAMSHIELD_API_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
logging.basicConfig(level=logging.INFO)

EMOJI = {"scam": "🚨 SCAM", "suspicious": "⚠️ SUSPICIOUS", "safe": "✅ LOOKS SAFE"}
WELCOME = ("🛡️ *ScamShield*\n\nForward me any suspicious message, link or screenshot "
           "and I'll tell you if it's a scam.\n\nFree • Private (personal data is removed before saving)")


def format_result(d: dict) -> str:
    lines = [f"*{EMOJI[d['verdict']]}*  —  risk {round(d['risk_score'] * 100)}%", "", d["explanation"]]
    if d["reasons"]:
        lines += ["", "*Why:*"] + [f"• {r}" for r in d["reasons"][:4]]
    lines += ["", "*What to do:*"] + [f"• {a}" for a in d["advice"]]
    return "\n".join(lines)


def feedback_keyboard(analysis_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("👍 Correct", callback_data=f"fb:1:{analysis_id}"),
                                  InlineKeyboardButton("👎 Wrong", callback_data=f"fb:0:{analysis_id}")]])


async def reply(update: Update, data: dict) -> None:
    await update.message.reply_text(format_result(data), parse_mode="Markdown",
                                    reply_markup=feedback_keyboard(data["analysis_id"]),
                                    disable_web_page_preview=True)


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, parse_mode="Markdown")


async def on_text(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or update.message.caption or "")[:5000]
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{API}/api/analyze/text", json={"text": text, "channel": "telegram"})
    if r.status_code != 200:
        await update.message.reply_text("Sorry, I couldn't check that right now. Please try again.")
        return
    await reply(update, r.json())


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    photo = update.message.photo[-1]  # largest size
    file = await context.bot.get_file(photo.file_id)
    data = bytes(await file.download_as_bytearray())
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{API}/api/analyze/image", files={"file": ("shot.jpg", data, "image/jpeg")},
                              data={"channel": "telegram"})
    if r.status_code != 200:
        detail = r.json().get("detail", "Could not read the image.") if r.headers.get("content-type", "").startswith("application/json") else "Error"
        await update.message.reply_text(f"Sorry: {detail}")
        return
    await reply(update, r.json())


async def on_feedback(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    _, ok, analysis_id = q.data.split(":", 2)
    async with httpx.AsyncClient(timeout=15) as client:
        await client.post(f"{API}/api/feedback", json={"analysis_id": analysis_id, "is_correct": ok == "1"})
    await q.answer("Thanks! This helps the AI learn.")
    await q.edit_message_reply_markup(reply_markup=None)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env (get it from @BotFather).")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler(["start", "help"], start))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(CallbackQueryHandler(on_feedback, pattern=r"^fb:"))
    app.run_polling()


if __name__ == "__main__":
    main()
