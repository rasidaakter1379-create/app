import os
import asyncio
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ---------------- LOGGING ----------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ---------------- CONFIG ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing")

MESSAGES = {}          # {chat_id: [message_id, ...]}
ENABLED_GROUPS = set() # enabled group ids

ANNOUNCEMENT_TEXT = (
    "সবাইকে ধন্যবাদ, এখানে আপনার মা, বোন, আন্টি, প্রতিবেশী, শালী এর সাথে যদি কিছু করার ইচ্ছা থাকে।\n"
    "এবং করতে পারেন তাহলে সবার সাথে শেয়ার করবেন। এবং কোন পন্থা অবলম্বন করেছেন তাও বলবেন যাতে অন্য\n"
    "কেউ উপকৃত হয়।\n\n"
    "যেকোনো উপকারী তথ্য, অভিজ্ঞতা বা পরামর্শ শেয়ার করলে সবাই উপকৃত হবে।"
)

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
    ENABLED_GROUPS.add(update.effective_chat.id)
    await update.message.reply_text("✅ Auto cleanup ENABLED for this group.")

async def disable_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    ENABLED_GROUPS.discard(update.effective_chat.id)
    await update.message.reply_text("❌ Auto cleanup DISABLED for this group.")

# ---------------- MESSAGE HANDLER ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    # bot নিজের message ignore করবে
    if msg.from_user.is_bot:
        return

    chat_id = msg.chat.id

    try:
        member = await context.bot.get_chat_member(chat_id, msg.from_user.id)
    except Exception:
        return

    # admin message auto pin
    if member.status in ("administrator", "creator"):
        try:
            await msg.pin(disable_notification=True)
        except Exception:
            pass
        return

    # cleanup off হলে কিছু করবে না
    if chat_id not in ENABLED_GROUPS:
        return

    # message save for delete
    MESSAGES.setdefault(chat_id, []).append(msg.message_id)

# ---------------- DAILY CLEANUP ----------------
async def daily_cleanup(app):
    bot = app.bot

    for chat_id, message_ids in list(MESSAGES.items()):
        if chat_id not in ENABLED_GROUPS:
            continue

        for mid in message_ids:
            try:
                await bot.delete_message(chat_id, mid)
            except Exception:
                pass

        try:
            await bot.send_message(chat_id, ANNOUNCEMENT_TEXT)
        except Exception:
            pass

    MESSAGES.clear()

# ---------------- MAIN ----------------
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("enable_cleanup", enable_cleanup))
    app.add_handler(CommandHandler("disable_cleanup", disable_cleanup))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        daily_cleanup,
        "cron",
        hour=0,
        minute=0,
        args=[app],
    )
    scheduler.start()

    logging.info("🤖 Bot started successfully")
    await app.run_polling()

# ---------------- ENTRY ----------------
if __name__ == "__main__":
    asyncio.run(main())
