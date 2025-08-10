import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.helpers import escape_markdown
import datetime
import pytz

# توکن ربات و آیدی ادمین رو قبلا گذاشتی
TOKEN = "8055147620:AAEZfCmktvz4xD2LcxzYPHPV8WsibkKJsFQ"
ADMIN_ID = 780486613

# آیدی چنل شما (یا یوزرنیم با @)
CHANNEL_ID = -1001891111619
CHANNEL_USERNAME = "@YourChannelUsername"  # اگه می‌خوای بجای آیدی از یوزرنیم استفاده کنی

# تنظیم منطقه زمانی (برای دقت در شمارش 24 ساعت)
TIMEZONE = pytz.timezone('Europe/Berlin')  # قابل تغییر به منطقه زمانی خودت

# لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# دیکشنری‌های مدیریت وضعیت
admin_reply_target = {}
user_is_replying_to_admin = {}
admin_is_sending_to_channel = {}
user_last_heart_time = {}

# وضعیت ادمین برای ارسال پیام به کانال (متن، موزیک، ویس)
admin_states = {}

# --- تابع استارت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"User {user.id} started the bot.")

    keyboard_buttons = []

    keyboard_buttons.append([
        InlineKeyboardButton("ارسال مسیج به صورت ناشناس به ممد", callback_data="send_anonymous_message")
    ])
    keyboard_buttons.append([
        InlineKeyboardButton("❤️ ارسال قلب برای ممد", callback_data="send_heart_to_mammad")
    ])

    if user.id == ADMIN_ID:
        keyboard_buttons.append([
            InlineKeyboardButton("📢 ارسال پیام به چنل", callback_data="start_send_to_channel")
        ])

    reply_markup_start = InlineKeyboardMarkup(keyboard_buttons)

    await update.message.reply_html(
        f"سلااام {user.mention_html()} ! \nبه ربات ناشناس Thesweetelf خوش اومدی .\nهر پیامی که اینجا بفرستی ناشناس برای ممد میفرستم ;) ❤️",
        reply_markup=reply_markup_start
    )

# --- دکمه‌ها ---

async def start_anonymous_message_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("حالا پیام خود را برای ارسال ناشناس به ممد تایپ و ارسال کنید.")

async def start_send_to_channel_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ شما دسترسی برای استفاده از این دکمه را ندارید.")
        return
    admin_states[query.from_user.id] = "awaiting_channel_content"
    logger.info(f"Admin {query.from_user.id} started sending message to channel process.")
    await query.edit_message_text("حالا پیام خود را برای ارسال به کانال تایپ یا ارسال موزیک/ویس کنید.")

async def send_heart_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_chat_id = query.message.chat_id

    current_time = datetime.datetime.now(TIMEZONE)
    if user_id in user_last_heart_time:
        last_heart_time = user_last_heart_time[user_id]
        time_since_last_heart = current_time - last_heart_time
        if time_since_last_heart < datetime.timedelta(hours=24):
            remaining_time = datetime.timedelta(hours=24) - time_since_last_heart
            hours, remainder = divmod(remaining_time.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            await query.answer(
                f"❌ شما قبلاً امروز قلب فرستاده‌اید. لطفا {int(hours)} ساعت و {int(minutes)} دقیقه دیگر تلاش کنید.",
                show_alert=True
            )
            logger.info(f"User {user_id} tried to send heart again within 24 hours.")
            return

    user_last_heart_time[user_id] = current_time
    await query.answer("❤️ قلب شما برای ممد ارسال شد!")

    escaped_user_id = escape_markdown(str(user_id), version=2)
    admin_notification = f"**❤️ یک قلب ناشناس جدید** (از ID: `{escaped_user_id}`)"

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_notification,
            parse_mode="MarkdownV2"
        )
        logger.info(f"User {user_id} sent a heart to admin.")

        await context.bot.send_message(
            chat_id=user_chat_id,
            text="❤️ ممنون از قلب زیبات، ممد پیام شما رو دریافت کرد!",
            parse_mode="Markdown"
        )
        logger.info(f"Thank you message sent to user {user_id} for sending heart.")
    except Exception as e:
        logger.error(f"Error sending heart or thank you message: {e}")
        if user_id in user_last_heart_time and user_last_heart_time[user_id] == current_time:
            del user_last_heart_time[user_id]
        await query.edit_message_text(f"❌ متاسفانه خطایی در ارسال قلب شما رخ داد: {e}")

# --- ارسال پیام ناشناس به ادمین ---
async def handle_anonymous_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text
    chat_id_of_sender = update.message.chat_id

    escaped_user_id = escape_markdown(str(user_id), version=2)
    escaped_message_text = escape_markdown(message_text, version=2)

    notification_text = f"**📩 پیام ناشناس جدید** (ID: `{escaped_user_id}`):\n\n*{escaped_message_text}*\n\n"

    keyboard_for_admin = [[
        InlineKeyboardButton(
            "↩️ پاسخ به این کاربر",
            callback_data=f"reply_callback_{chat_id_of_sender}"
        )
    ]]
    reply_markup_for_admin = InlineKeyboardMarkup(keyboard_for_admin)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=notification_text,
            parse_mode="MarkdownV2",
            reply_markup=reply_markup_for_admin
        )
        logger.info(f"Anonymous message sent from {user_id} to admin.")
        await update.message.reply_text("پیام شما با موفقیت به ادمین ارسال شد! منتظر پاسخ باشید 😉")
    except Exception as e:
        logger.error(f"Error sending anonymous message to admin: {e}")
        await update.message.reply_text(f"❌ خطایی در ارسال پیام شما رخ داد: {e}")

# --- دکمه پاسخ ادمین به کاربر ---
async def handle_admin_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ شما دسترسی برای استفاده از این دکمه را ندارید.")
        return

    target_chat_id = int(query.data.split('_')[2])
    admin_reply_target[query.from_user.id] = target_chat_id

    logger.info(f"Admin {query.from_user.id} clicked reply button for user {target_chat_id}.")

    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"حالا میتونی پاسخت رو به کاربر `{target_chat_id}` بفرستی.",
        parse_mode="MarkdownV2"
    )
    await query.edit_message_reply_markup(reply_markup=None)

# --- ارسال پاسخ ادمین به کاربر ---
async def admin_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and update.effective_user.id in admin_is_sending_to_channel:
        # ارسال پیام به کانال
        admin_is_sending_to_channel.pop(update.effective_user.id)
        message_to_send = update.message.text
        try:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=message_to_send,
                parse_mode="Markdown"
            )
            await update.message.reply_text(f"✅ پیام شما با موفقیت به کانال ارسال شد.")
            logger.info(f"Admin sent message to channel.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطایی در ارسال پیام به کانال رخ داد: {e}")
            logger.error(f"Error sending message to channel: {e}")
        return

    elif update.effective_user.id == ADMIN_ID and update.effective_user.id in admin_reply_target:
        target_chat_id = admin_reply_target.pop(update.effective_user.id)
        reply_text = update.message.text
        escaped_reply_text = escape_markdown(reply_text, version=2)

        keyboard_for_user = [[
            InlineKeyboardButton(
                "↩️ پاسخ به Thesweetelf",
                callback_data=f"user_reply_callback_{ADMIN_ID}"
            ),
            InlineKeyboardButton(
                "✔️ پیام رو خوندم",
                callback_data=f"seen_callback_{update.effective_user.id}_{target_chat_id}"
            )
        ]]
        reply_markup_for_user = InlineKeyboardMarkup(keyboard_for_user)

        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text=f"📨 پاسخ Thesweetelf:\n\n*{escaped_reply_text}*",
                parse_mode="MarkdownV2",
                reply_markup=reply_markup_for_user
            )
            logger.info(f"Admin replied to user {target_chat_id}.")
            await update.message.reply_text(f"✅ پاسخ شما با موفقیت به کاربر `{target_chat_id}` ارسال شد.")
        except Exception as e:
            logger.error(f"Error sending reply to user: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال پاسخ رخ داد: {e}")
    elif update.effective_user.id == ADMIN_ID:
        logger.warning(f"Admin sent message but no action: '{update.message.text}'")

# --- دکمه دیدن پیام ---
async def handle_seen_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("پیام شما به Thesweetelf ارسال شد.")

    parts = query.data.split('_')
    original_admin_id = int(parts[2])
    user_who_saw_id = int(parts[3])

    try:
        escaped_user_id = escape_markdown(str(user_who_saw_id), version=2)
        await context.bot.send_message(
            chat_id=original_admin_id,
            text=f"👁️‍🗨️ کاربر `{escaped_user_id}` پیام شما را دید.",
            parse_mode="MarkdownV2"
        )
        logger.info(f"Seen notification sent to admin.")
    except Exception as e:
        logger.error(f"Error sending seen notification: {e}")

    await query.edit_message_reply_markup(reply_markup=None)

# --- دکمه پاسخ کاربر به ادمین ---
async def handle_user_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    target_admin_id = int(query.data.split('_')[3])
    user_id = query.from_user.id

    user_is_replying_to_admin[user_id] = target_admin_id

    logger.info(f"User {user_id} clicked reply button to admin {target_admin_id}.")
    await query.edit_message_text("حالا پیام خود را برای Thesweetelf ارسال کنید.")

# --- مدیریت پیام‌های کاربران ---
async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text

    if user_id in user_is_replying_to_admin:
        target_admin_id = user_is_replying_to_admin.pop(user_id)

        escaped_user_id = escape_markdown(str(user_id), version=2)
        escaped_message_text = escape_markdown(message_text, version=2)

        admin_message = (
            f"↩️ *پاسخ کاربر* (ID: `{escaped_user_id}`) به Thesweetelf:\n\n"
            f"*{escaped_message_text}*"
        )
        try:
            await context.bot.send_message(
                chat_id=target_admin_id,
                text=admin_message,
                parse_mode="MarkdownV2"
            )
            await update.message.reply_text("پاسخ شما با موفقیت به Thesweetelf ارسال شد.")
        except Exception as e:
            logger.error(f"Error sending user reply: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال پاسخ رخ داد: {e}")
        return

    if update.message.reply_to_message and update.message.reply_to_message.from_user.is_bot and update.message.reply_to_message.from_user.id == context.bot.id:
        logger.info(f"User {user_id} manually replied to bot's message.")

        escaped_user_id = escape_markdown(str(user_id), version=2)
        escaped_message_text = escape_markdown(message_text, version=2)

        admin_message = (
            f"↩️ *پاسخ کاربر* (ID: `{escaped_user_id}`) به پیام شما:\n\n"
            f"*{escaped_message_text}*"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode="MarkdownV2"
            )
            await update.message.reply_text("پاسخ شما به Thesweetelf ارسال شد.")
        except Exception as e:
            logger.error(f"Error sending manual reply: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال پاسخ شما رخ داد: {e}")
        return

    # اگه هیچکدوم از شرایط نبود، پیام ناشناس جدید محسوب میشه
    await handle_anonymous_message(update, context)
    logger.info(f"New anonymous message from user {user_id}.")

# --- اینجا قابلیت ارسال موزیک و ویس توسط ادمین به کانال اضافه شده ---

async def admin_audio_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        try:
            await context.bot.send_audio(
                chat_id=CHANNEL_ID,
                audio=update.message.audio.file_id,
                caption=update.message.caption or "🎵 موزیک جدید از ادمین",
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ موزیک با موفقیت به کانال ارسال شد.")
            logger.info("Audio sent by admin to channel")
        except Exception as e:
            logger.error(f"Error sending audio to channel: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال موزیک رخ داد: {e}")

async def admin_voice_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        try:
            await context.bot.send_voice(
                chat_id=CHANNEL_ID,
                voice=update.message.voice.file_id,
                caption=update.message.caption or "🎙 ویس جدید از ادمین",
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ ویس با موفقیت به کانال ارسال شد.")
            logger.info("Voice sent by admin to channel")
        except Exception as e:
            logger.error(f"Error sending voice to channel: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال ویس رخ داد: {e}")

# --- پیام‌های دریافت شده توسط ادمین برای ارسال به کانال (متن) ---
async def handle_admin_channel_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and admin_states.get(user_id) == "awaiting_channel_content":
        admin_states[user_id] = None
        try:
            if update.message.text:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=update.message.text)
                await update.message.reply_text("✅ پیام متنی با موفقیت به کانال ارسال شد.")
            elif update.message.audio:
                await context.bot.send_audio(chat_id=CHANNEL_ID, audio=update.message.audio.file_id,
                                             caption=update.message.caption or "")
                await update.message.reply_text("✅ موزیک با موفقیت به کانال ارسال شد.")
            elif update.message.voice:
                await context.bot.send_voice(chat_id=CHANNEL_ID, voice=update.message.voice.file_id,
                                             caption=update.message.caption or "")
                await update.message.reply_text("✅ ویس با موفقیت به کانال ارسال شد.")
            else:
                await update.message.reply_text("❌ فرمت پیام پشتیبانی نمی‌شود.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال به کانال: {e}")
            logger.error(f"Error sending content to channel: {e}")
        return

# --- هندلر اصلی ---
def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))

    application.add_handler(CallbackQueryHandler(start_anonymous_message_process, pattern="^send_anonymous_message$"))
    application.add_handler(CallbackQueryHandler(send_heart_to_admin, pattern="^send_heart_to_mammad$"))
    application.add_handler(CallbackQueryHandler(start_send_to_channel_process, pattern="^start_send_to_channel$"))

    application.add_handler(CallbackQueryHandler(handle_admin_reply_button, pattern="^reply_callback_"))
    application.add_handler(CallbackQueryHandler(handle_user_reply_button, pattern="^user_reply_callback_"))
    application.add_handler(CallbackQueryHandler(handle_seen_button, pattern="^seen_callback_"))

    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & (~filters.Chat(ADMIN_ID)), handle_user_messages))
    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(ADMIN_ID) & (~filters.COMMAND), admin_text_reply))

    # هندلر برای ارسال موزیک و ویس توسط ادمین (مستقیم به کانال)
    application.add_handler(MessageHandler(filters.AUDIO & filters.Chat(ADMIN_ID), admin_audio_to_channel))
    application.add_handler(MessageHandler(filters.VOICE & filters.Chat(ADMIN_ID), admin_voice_to_channel))

    # هندلر برای ارسال پیام متنی یا موزیک یا ویس در حالت انتظار ارسال به کانال
    application.add_handler(MessageHandler(filters.ALL & filters.Chat(ADMIN_ID), handle_admin_channel_content))

    logger.info("Bot started.")
    application.run_polling()

if __name__ == "__main__":
    main()
