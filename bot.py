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

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# data storage
MESSAGES = {}        # chat_id -> [(chat_id, message_id)]
ENABLED_GROUPS = set()

ANNOUNCEMENT_TEXT = (
    "সবাইকে ধন্যবাদ, এখানে আপনার মা, বোন, আন্টি, প্রতিবেশী, শালী এর সাথে যদি কিছু করার ইচ্ছা থাকে।
    এবং করতে পারেন তাহলে সবার সাথে শেয়ার করবেন।এবং কোন পন্থা অবলম্বন করেছেন তাও বলবেন যাতে অন্য
    কেউ উপকৃত হয়্ছে।
    যেকোনো উপকারী তথ্য, অভিজ্ঞতা বা পরামর্শ শেয়ার করলে সবাই উপকৃত হবে।"
)


# ---------- helpers ----------
async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )
    return member.status in ("administrator", "creator")


# ---------- commands ----------
async def enable_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    ENABLED_GROUPS.add(update.effective_chat.id)
    await update.message.reply_text("✅ এই গ্রুপে auto cleanup চালু করা হয়েছে")


async def disable_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, context):
        return
    ENABLED_GROUPS.discard(update.effective_chat.id)
    await update.message.reply_text("❌ এই গ্রুপে auto cleanup বন্ধ করা হয়েছে")


# ---------- message handler ----------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg:
        return

    chat_id = msg.chat.id
    member = await context.bot.get_chat_member(chat_id, msg.from_user.id)

    # admin/creator → auto pin
    if member.status in ("administrator", "creator"):
        try:
            await msg.pin(disable_notification=True)
        except Exception:
            pass
        return

    # only if cleanup enabled
    if chat_id not in ENABLED_GROUPS:
        return

    MESSAGES.setdefault(chat_id, []).append((chat_id, msg.message_id))


# ---------- daily cleanup ----------
async def daily_cleanup(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot

    for chat_id, msgs in list(MESSAGES.items()):
        if chat_id not in ENABLED_GROUPS:
            continue

        for cid, mid in msgs:
            try:
                await bot.delete_message(cid, mid)
            except Exception:
                pass

        try:
            await bot.send_message(chat_id, ANNOUNCEMENT_TEXT)
        except Exception:
            pass

    MESSAGES.clear()


# ---------- main ----------
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN missing")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("enable_cleanup", enable_cleanup))
    app.add_handler(CommandHandler("disable_cleanup", disable_cleanup))
    app.add_handler(MessageHandler(filters.ALL, handle_message))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        daily_cleanup,
        "cron",
        hour=0,
        minute=0,
        args=[app],
    )
    scheduler.start()

    print("🤖 Bot started successfully")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
