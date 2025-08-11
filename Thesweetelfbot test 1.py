import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from telegram.helpers import escape_markdown
import datetime
import pytz
import json
import os
import uuid

# توکن ربات و آیدی ادمین
TOKEN = "8055147620:AAEZfCmktvz4xD2LcxzYPHPV8WsibkKJsFQ"
ADMIN_ID = 780486613

# آیدی چنل شما (یا یوزرنیم با @)
CHANNEL_ID = -1001891111619

# تنظیم منطقه زمانی بر اساس ایران
TIMEZONE = pytz.timezone('Asia/Tehran')

# لاگینگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- دیکشنری‌های مدیریت وضعیت (State Management) ---
admin_reply_target = {}
user_is_replying_to_admin = {}
admin_is_sending_to_channel = {}
user_last_heart_time = {}
pending_admin_messages = {}

# --- ویژگی جدید: شماره‌گذاری، بلاک و ذخیره دائمی ---
DATA_FILE = 'user_data.json'
user_numbers = {}
blocked_users = set()
next_user_number = 1

def load_data():
    """Loads user numbers, blocked users, and next user number from a JSON file."""
    global user_numbers, blocked_users, next_user_number
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                user_numbers = {int(k): v for k, v in data.get('user_numbers', {}).items()}
                blocked_users = set(data.get('blocked_users', []))
                next_user_number = data.get('next_user_number', 1)
                logger.info("User data loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load user data: {e}")

def save_data():
    """Saves user numbers, blocked users, and next user number to a JSON file."""
    data = {
        'user_numbers': user_numbers,
        'blocked_users': list(blocked_users),
        'next_user_number': next_user_number
    }
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f)
            logger.info("User data saved successfully.")
    except Exception as e:
        logger.error(f"Failed to save user data: {e}")

def get_user_number(user_id):
    """Assigns a unique number to a user if they don't have one and saves it."""
    global next_user_number
    if user_id not in user_numbers:
        user_numbers[user_id] = next_user_number
        next_user_number += 1
        save_data()
    return user_numbers[user_id]
# --- پایان ویژگی جدید ---

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
            InlineKeyboardButton("📢 ارسال پیام به چنل", callback_data="start_send_to_channel"),
            InlineKeyboardButton("🧑‍💻 لیست کاربران", callback_data="show_user_list")
        ])

    reply_markup_start = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.message.reply_html(
        f"سلااام {user.mention_html()} ! \nبه ربات ناشناس Thesweetelf خوش اومدی .\nهر پیامی که اینجا بفرستی ناشناس برای ممد میفرستم 😉 ❤️",
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
    admin_is_sending_to_channel[query.from_user.id] = True
    logger.info(f"Admin {query.from_user.id} started sending message to channel process.")
    await query.edit_message_text("حالا پیام خود را برای ارسال به کانال تایپ یا ارسال موزیک/ویس کنید.")

async def send_heart_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    user_chat_id = query.message.chat_id

    if user_id in blocked_users:
        await query.answer("❌ شما مسدود هستید و نمی‌توانید پیام ارسال کنید.")
        return

    user_number = get_user_number(user_id)
    
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
    admin_notification = f"**❤️ یک قلب ناشناس جدید** \(از کاربر شماره `{user_number}` \- ID: `{escaped_user_id}`\)"

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
    if user_id in blocked_users:
        logger.info(f"Blocked user {user_id} tried to send a message.")
        await update.message.reply_text("❌ شما مسدود هستید و نمی‌توانید پیام ارسال کنید.")
        return

    message_text = update.message.text
    chat_id_of_sender = update.message.chat_id

    user_number = get_user_number(user_id)

    escaped_user_id = escape_markdown(str(user_id), version=2)
    escaped_message_text = escape_markdown(message_text, version=2)
    
    notification_text = f"**📩 پیام ناشناس جدید** \(کاربر شماره `{user_number}` \- ID: `{escaped_user_id}`\):\n\n*{escaped_message_text}*\n\n"

    keyboard_for_admin = [[
        InlineKeyboardButton(
            "↩️ پاسخ به این کاربر",
            callback_data=f"reply_callback_{chat_id_of_sender}"
        ),
        InlineKeyboardButton(
            "✔️ پیام رو خوندم",
            callback_data=f"admin_seen_callback"
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

    user_number = user_numbers.get(target_chat_id, "نامشخص")
    
    logger.info(f"Admin {query.from_user.id} clicked reply button for user {target_chat_id}.")
    
    await context.bot.send_message(
        chat_id=query.message.chat.id,
        text=f"حالا میتونی پاسخت رو به کاربر شماره `{user_number}` بفرستی.",
        parse_mode="MarkdownV2"
    )
    await query.edit_message_reply_markup(reply_markup=None)

# --- ارسال پاسخ ادمین به کاربر ---
async def admin_text_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and admin_is_sending_to_channel.get(update.effective_user.id):
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
        
        if target_chat_id in blocked_users:
            await update.message.reply_text(f"❌ کاربر مورد نظر مسدود است. برای ارسال پیام، ابتدا او را آنبلاک کنید.")
            return

        message_id = str(uuid.uuid4())
        pending_admin_messages[message_id] = reply_text

        keyboard_for_user = [[
            InlineKeyboardButton("دریافت پیام", callback_data=f"show_message_{message_id}_{target_chat_id}")
        ]]
        reply_markup_for_user = InlineKeyboardMarkup(keyboard_for_user)

        try:
            await context.bot.send_message(
                chat_id=target_chat_id,
                text="📨 شما یک پیام از طرف Thesweetelf دارید!",
                reply_markup=reply_markup_for_user
            )
            logger.info(f"Admin replied to user {target_chat_id}, notification sent.")
            await update.message.reply_text(f"✅ پیام شما با موفقیت به کاربر `{target_chat_id}` ارسال شد. منتظر دریافت پیام توسط کاربر باشید.")
        except Exception as e:
            logger.error(f"Error sending reply notification to user: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال پاسخ رخ داد: {e}")
    elif update.effective_user.id == ADMIN_ID:
        logger.warning(f"Admin sent message but no action: '{update.message.text}'")

# --- تابع برای نمایش پیام ادمین پس از کلیک کاربر ---
async def show_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    message_id = parts[2]
    target_chat_id = int(parts[3])
    
    if query.from_user.id != target_chat_id:
        await query.edit_message_text("❌ این پیام برای شما نیست.")
        return

    reply_text = pending_admin_messages.pop(message_id, None)

    if not reply_text:
        await query.edit_message_text("❌ پیام مورد نظر پیدا نشد یا قبلاً مشاهده شده است.")
        return
    
    # --- ارسال اعلان دیده‌شدن پیام به ادمین ---
    user_number = user_numbers.get(target_chat_id, "نامشخص")
    escaped_user_id = escape_markdown(str(target_chat_id), version=2)
    seen_notification_text = f"👁️‍🗨️ کاربر شماره `{user_number}` پیام شما را دید\."
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=seen_notification_text,
            parse_mode="MarkdownV2"
        )
        logger.info(f"Seen notification sent to admin for user {target_chat_id}.")
    except Exception as e:
        logger.error(f"Error sending automated seen notification: {e}")

    escaped_reply_text = escape_markdown(reply_text, version=2)
    
    keyboard_for_user = [[
        InlineKeyboardButton(
            "↩️ پاسخ به Thesweetelf",
            callback_data=f"user_reply_callback_{ADMIN_ID}"
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
        await query.edit_message_text("✅ پیام دریافت شد.")
        logger.info(f"User {target_chat_id} viewed admin message {message_id}.")
    except Exception as e:
        logger.error(f"Error sending final reply to user: {e}")
        await query.edit_message_text(f"❌ خطایی در نمایش پیام رخ داد: {e}")

# --- دکمه پاسخ کاربر به ادمین ---
async def handle_user_reply_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    target_admin_id = int(query.data.split('_')[3])
    user_id = query.from_user.id
    if user_id in blocked_users:
        await query.edit_message_text("❌ شما مسدود هستید و نمی‌توانید به ادمین پیام دهید.")
        return

    user_is_replying_to_admin[user_id] = target_admin_id
    
    logger.info(f"User {user_id} clicked reply button to admin {target_admin_id}.")
    await query.edit_message_text("حالا پیام خود را برای Thesweetelf ارسال کنید.")

# --- دکمه دیده شدن پیام توسط ادمین ---
async def handle_admin_seen_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✔️ پیام توسط شما دیده شد.")
    logger.info(f"Admin {query.from_user.id} marked a user message as seen.")

# --- مدیریت پیام‌های کاربران ---
async def handle_user_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in blocked_users:
        logger.info(f"Blocked user {user_id} tried to send a message.")
        await update.message.reply_text("❌ شما مسدود هستید و نمی‌توانید پیام ارسال کنید.")
        return

    message_text = update.message.text
    chat_id_of_sender = update.message.chat_id

    if user_id in user_is_replying_to_admin:
        target_admin_id = user_is_replying_to_admin.pop(user_id)
        
        user_number = user_numbers.get(user_id, "نامشخص")
        
        escaped_user_id = escape_markdown(str(user_id), version=2)
        escaped_message_text = escape_markdown(message_text, version=2)

        keyboard_for_admin = [[
            InlineKeyboardButton(
                "↩️ پاسخ به این کاربر",
                callback_data=f"reply_callback_{chat_id_of_sender}"
            ),
            InlineKeyboardButton(
                "✔️ پیام رو خوندم",
                callback_data=f"admin_seen_callback"
            )
        ]]
        reply_markup_for_admin = InlineKeyboardMarkup(keyboard_for_admin)

        admin_message = (
            f"↩️ *پاسخ کاربر شماره `{user_number}`* \(ID: `{escaped_user_id}`\) به Thesweetelf:\n\n"
            f"*{escaped_message_text}*"
        )
        try:
            await context.bot.send_message(
                chat_id=target_admin_id,
                text=admin_message,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup_for_admin
            )
            await update.message.reply_text("پاسخ شما با موفقیت به Thesweetelf ارسال شد.")
        except Exception as e:
            logger.error(f"Error sending user reply: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال پاسخ رخ داد: {e}")
        return

    if update.message.reply_to_message and update.message.reply_to_message.from_user.is_bot and update.message.reply_to_message.from_user.id == context.bot.id:
        logger.info(f"User {user_id} manually replied to bot's message.")
        
        user_number = user_numbers.get(user_id, "نامشخص")
        
        escaped_user_id = escape_markdown(str(user_id), version=2)
        escaped_message_text = escape_markdown(message_text, version=2)

        keyboard_for_admin = [[
            InlineKeyboardButton(
                "↩️ پاسخ به این کاربر",
                callback_data=f"reply_callback_{chat_id_of_sender}"
            ),
            InlineKeyboardButton(
                "✔️ پیام رو خوندم",
                callback_data=f"admin_seen_callback"
            )
        ]]
        reply_markup_for_admin = InlineKeyboardMarkup(keyboard_for_admin)

        admin_message = (
            f"↩️ *پاسخ کاربر شماره `{user_number}`* \(ID: `{escaped_user_id}`\) به پیام شما:\n\n"
            f"*{escaped_message_text}*"
        )
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode="MarkdownV2",
                reply_markup=reply_markup_for_admin
            )
            await update.message.reply_text("پاسخ شما به Thesweetelf ارسال شد.")
        except Exception as e:
            logger.error(f"Error sending manual reply: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال پاسخ شما رخ داد: {e}")
        return

    await handle_anonymous_message(update, context)
    logger.info(f"New anonymous message from user {user_id}.")

# --- قابلیت‌های ارسال محتوا به کانال ---
async def admin_audio_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and admin_is_sending_to_channel.get(update.effective_user.id):
        admin_is_sending_to_channel.pop(update.effective_user.id, None)
        try:
            await context.bot.send_audio(
                chat_id=CHANNEL_ID,
                audio=update.message.audio.file_id,
                caption=None,
                parse_mode="Markdown"
            )
            await update.message.reply_text("✅ موزیک با موفقیت به کانال ارسال شد.")
            logger.info("Audio sent by admin to channel")
        except Exception as e:
            logger.error(f"Error sending audio to channel: {e}")
            await update.message.reply_text(f"❌ خطایی در ارسال موزیک رخ داد: {e}")

async def admin_voice_to_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID and admin_is_sending_to_channel.get(update.effective_user.id):
        admin_is_sending_to_channel.pop(update.effective_user.id, None)
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

async def handle_admin_channel_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id == ADMIN_ID and admin_is_sending_to_channel.get(user_id):
        admin_is_sending_to_channel.pop(user_id, None)
        try:
            if update.message.text:
                await context.bot.send_message(chat_id=CHANNEL_ID, text=update.message.text)
                await update.message.reply_text("✅ پیام متنی با موفقیت به کانال ارسال شد.")
            elif update.message.audio:
                await context.bot.send_audio(chat_id=CHANNEL_ID, audio=update.message.audio.file_id,
                                             caption=None)
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

# --- توابع جدید برای پنل ادمین ---
async def show_user_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ شما دسترسی برای استفاده از این دکمه را ندارید.")
        return

    keyboard_buttons = []
    # مرتب‌سازی کاربران بر اساس شماره
    sorted_users = sorted(user_numbers.items(), key=lambda item: item[1])
    for user_id, user_num in sorted_users:
        is_blocked = "🔒" if user_id in blocked_users else ""
        button_text = f"{is_blocked} کاربر شماره {user_num} (ID: {user_id})"
        keyboard_buttons.append([InlineKeyboardButton(button_text, callback_data=f"user_panel_{user_id}")])

    keyboard_buttons.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back_to_main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    await query.edit_message_text("لیست کاربران:", reply_markup=reply_markup)

async def show_user_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("⛔ شما دسترسی برای استفاده از این دکمه را ندارید.")
        return

    user_id = int(query.data.split('_')[2])
    user_num = user_numbers.get(user_id, "نامشخص")
    
    is_blocked = user_id in blocked_users
    block_button_text = "🔓 آنبلاک کاربر" if is_blocked else "🔒 بلاک کاربر"
    block_button_callback = f"unblock_user_{user_id}" if is_blocked else f"block_user_{user_id}"

    keyboard_buttons = [
        [InlineKeyboardButton("↩️ مسیج به این کاربر", callback_data=f"reply_callback_{user_id}")],
        [InlineKeyboardButton(block_button_text, callback_data=block_button_callback)],
        [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="show_user_list")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard_buttons)

    text = f"پروفایل کاربر شماره {user_num} (ID: {user_id})"
    if is_blocked:
        text += "\n\n⚠️ این کاربر مسدود است."
    
    await query.edit_message_text(text, reply_markup=reply_markup)

async def block_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return
        
    user_id_to_block = int(query.data.split('_')[2])
    blocked_users.add(user_id_to_block)
    save_data()

    user_num = user_numbers.get(user_id_to_block, "نامشخص")
    await query.edit_message_text(f"❌ کاربر شماره {user_num} (ID: {user_id_to_block}) با موفقیت مسدود شد.")
    logger.info(f"Admin {query.from_user.id} blocked user {user_id_to_block}.")
    
    try:
        await context.bot.send_message(user_id_to_block, "⚠️ شما از طرف ادمین مسدود شده‌اید و نمی‌توانید پیام ارسال کنید.")
    except Exception as e:
        logger.warning(f"Could not send blocked message to user {user_id_to_block}: {e}")

async def unblock_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID:
        return

    user_id_to_unblock = int(query.data.split('_')[2])
    if user_id_to_unblock in blocked_users:
        blocked_users.remove(user_id_to_unblock)
        save_data()
    
    user_num = user_numbers.get(user_id_to_unblock, "نامشخص")
    await query.edit_message_text(f"✅ کاربر شماره {user_num} (ID: {user_id_to_unblock}) با موفقیت از حالت مسدودی خارج شد.")
    logger.info(f"Admin {query.from_user.id} unblocked user {user_id_to_unblock}.")
    
    try:
        await context.bot.send_message(user_id_to_unblock, "✅ شما از حالت مسدودی خارج شدید و می‌توانید دوباره پیام ارسال کنید.")
    except Exception as e:
        logger.warning(f"Could not send unblocked message to user {user_id_to_unblock}: {e}")

async def back_to_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    keyboard_buttons = []
    keyboard_buttons.append([
        InlineKeyboardButton("ارسال مسیج به صورت ناشناس به ممد", callback_data="send_anonymous_message")
    ])
    keyboard_buttons.append([
        InlineKeyboardButton("❤️ ارسال قلب برای ممد", callback_data="send_heart_to_mammad")
    ])
    if user.id == ADMIN_ID:
        keyboard_buttons.append([
            InlineKeyboardButton("📢 ارسال پیام به چنل", callback_data="start_send_to_channel"),
            InlineKeyboardButton("🧑‍💻 لیست کاربران", callback_data="show_user_list")
        ])
    reply_markup_start = InlineKeyboardMarkup(keyboard_buttons)
    await query.edit_message_text(
        text="به منوی اصلی بازگشتید.",
        reply_markup=reply_markup_start
    )

# --- هندلر اصلی ---
def main() -> None:
    load_data()
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(start_anonymous_message_process, pattern="^send_anonymous_message$"))
    application.add_handler(CallbackQueryHandler(send_heart_to_admin, pattern="^send_heart_to_mammad$"))
    application.add_handler(CallbackQueryHandler(start_send_to_channel_process, pattern="^start_send_to_channel$"))
    application.add_handler(CallbackQueryHandler(handle_admin_reply_button, pattern="^reply_callback_"))
    application.add_handler(CallbackQueryHandler(handle_user_reply_button, pattern="^user_reply_callback_"))
    application.add_handler(CallbackQueryHandler(handle_admin_seen_button, pattern="^admin_seen_callback"))
    application.add_handler(CallbackQueryHandler(show_admin_message, pattern="^show_message_"))
    
    # هندلرهای جدید برای پنل ادمین
    application.add_handler(CallbackQueryHandler(show_user_list, pattern="^show_user_list$"))
    application.add_handler(CallbackQueryHandler(show_user_panel, pattern="^user_panel_"))
    application.add_handler(CallbackQueryHandler(block_user, pattern="^block_user_"))
    application.add_handler(CallbackQueryHandler(unblock_user, pattern="^unblock_user_"))
    application.add_handler(CallbackQueryHandler(back_to_main_menu, pattern="^back_to_main_menu$"))

    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND) & (~filters.Chat(ADMIN_ID)), handle_user_messages))
    application.add_handler(MessageHandler(filters.TEXT & filters.Chat(ADMIN_ID) & (~filters.COMMAND), admin_text_reply))

    application.add_handler(MessageHandler(filters.AUDIO & filters.Chat(ADMIN_ID), admin_audio_to_channel))
    application.add_handler(MessageHandler(filters.VOICE & filters.Chat(ADMIN_ID), admin_voice_to_channel))
    application.add_handler(MessageHandler(filters.ALL & filters.Chat(ADMIN_ID), handle_admin_channel_content))

    logger.info("Bot started.")
    application.run_polling()

if __name__ == "__main__":
    main()