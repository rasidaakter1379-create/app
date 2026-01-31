import os
import logging
import sqlite3
from datetime import datetime, timedelta
import pytz

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

from apscheduler.schedulers.background import BackgroundScheduler

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
TIMEZONE = pytz.timezone("Asia/Dhaka")

ANNOUNCEMENT_TEXT = (
    """সবাইকে ধন্যবাদ। এখানে আপনার মা, বোন, আন্টি, প্রতিবেশী, শালী-এর সাথে যদি কিছু করার ইচ্ছা থাকে এবং করতে পারেন,
    তাহলে সবার সাথে শেয়ার করবেন। এবং কোন পন্থা অবলম্বন করেছেন, তাও বলবেন; যাতে অন্য কেউ উপকৃত হয়। যেকোনো উপকারী তথ্য,
    অভিজ্ঞতা বা পরামর্শ শেয়ার করলে সবাই উপকৃত হবে।"""
)

logging.basicConfig(level=logging.INFO)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS messages (
    chat_id INTEGER,
    message_id INTEGER,
    created_at TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS enabled_groups (
    chat_id INTEGER PRIMARY KEY
)
""")

conn.commit()

# ---------------- HELPERS ----------------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )
    return member.status in ("administrator", "creator")


# ---------------- COMMANDS ----------------
async def enable_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return

    chat_id = update.effective_chat.id
    cur.execute(
        "INSERT OR IGNORE INTO enabled_groups (chat_id) VALUES (?)",
        (chat_id,)
    )
    conn.commit()
    await update.message.reply_text("✅ এই গ্রুপে auto cleanup চালু করা হয়েছে")


async def disable_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return

    chat_id = update.effective_chat.id
    cur.execute("DELETE FROM enabled_groups WHERE chat_id = ?", (chat_id,))
    conn.commit()
    await update.message.reply_text("❌ এই গ্রুপে auto cleanup বন্ধ করা হয়েছে")


# ---------------- MESSAGE HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    chat_id = msg.chat.id
    member = await context.bot.get_chat_member(chat_id, msg.from_user.id)

    # Admin / Creator → auto pin, never delete
    if member.status in ("administrator", "creator"):
        try:
            await msg.pin(disable_notification=True)
        except Exception:
            pass
        return

    # Check if group enabled
    cur.execute(
        "SELECT 1 FROM enabled_groups WHERE chat_id = ?",
        (chat_id,)
    )
    if not cur.fetchone():
        return

    # Save message with Bangladesh time
    now_bd = datetime.now(TIMEZONE).isoformat()
    cur.execute(
        "INSERT INTO messages (chat_id, message_id, created_at) VALUES (?, ?, ?)",
        (chat_id, msg.message_id, now_bd)
    )
    conn.commit()


# ---------------- CLEANUP LOGIC ----------------
async def cleanup_messages(app):
    bot = app.bot
    now_bd = datetime.now(TIMEZONE)

    cur.execute("SELECT chat_id, message_id, created_at FROM messages")
    rows = cur.fetchall()

    for chat_id, message_id, created_at in rows:
        msg_time = datetime.fromisoformat(created_at)
        if now_bd - msg_time >= timedelta(hours=24):
            try:
                await bot.delete_message(chat_id, message_id)
            except Exception:
                pass

            cur.execute(
                "DELETE FROM messages WHERE chat_id=? AND message_id=?",
                (chat_id, message_id)
            )
            conn.commit()

            # Post announcement after delete
            try:
                await bot.send_message(chat_id, ANNOUNCEMENT_TEXT)
            except Exception:
                pass


# ---------------- MAIN ----------------
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("enable_cleanup", enable_cleanup))
    app.add_handler(CommandHandler("disable_cleanup", disable_cleanup))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
    lambda: app.create_task(cleanup_messages(app)),
    trigger="cron",
    hour=0,
    minute=0,
    timezone=TIMEZONE,  # Asia/Dhaka
)
    scheduler.start()

    print("🤖 Production bot started (BD Timezone)")
    app.run_polling()


if __name__ == "__main__":
    main()
