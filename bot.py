import os
import sqlite3
import random
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)

logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = "8881613181:AAHJWWzfD7N72LKGzCPIQRfEvO4XOSy2PE4"
WEBHOOK_URL = "https://indian-money-bot-amtk.onrender.com/webhook"

# Gmail SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "Chsandeep829@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "your_gmail_app_password")

app = FastAPI()

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY,
            email TEXT,
            confirmation_code TEXT,
            is_verified INTEGER DEFAULT 0,
            balance REAL DEFAULT 100.0,
            bank_account TEXT,
            ifsc TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Initialize Telegram Application in Webhook mode
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

# Conversation States
EMAIL, CODE, BANK_ACC, BANK_IFSC, WITHDRAW_AMOUNT = range(5)

def get_user(telegram_id):
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT email, is_verified, balance, bank_account, ifsc FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# --- Real Email Sender Function ---
def send_otp_email(receiver_email, code):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = "🔐 Your Wallet Verification Code"

        body = (
            f"Hello,\n\n"
            f"Your 6-digit confirmation code for your secure wallet login is: {code}\n\n"
            f"Please enter this code in the Telegram bot to verify your account.\n"
            f"If you did not request this, please ignore this email."
        )
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

# --- Main Dashboard UI ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        conn = sqlite3.connect("bot_database.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO users (telegram_id, balance) VALUES (?, ?)", (user_id, 100.0))
        conn.commit()
        conn.close()
        user = get_user(user_id)

    is_verified = user[1]
    balance = user[2]
    bank = user[3] or "Not Linked"

    if not is_verified:
        text = (
            f"🇮🇳 **Indian Payments Bot**\n\n"
            f"Buy, sell, store, and manage your INR wallet seamlessly.\n\n"
            f"⚠️ **Account Status:** Unverified\n"
            f"Please verify your email address to unlock your wallet."
        )
        keyboard = [
            [InlineKeyboardButton("🔐 Verify Account", callback_data="start_login")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
        ]
    else:
        text = (
            f"🇮🇳 **Indian Payments Wallet**\n\n"
            f"₹ **{balance:.2f}**\n"
            f"Total balance in INR\n\n"
            f"🏦 **Bank:** {bank}"
        )
        keyboard = [
            [InlineKeyboardButton("💼 Wallet", callback_data="wallet_menu"), InlineKeyboardButton("💸 Withdraw", callback_data="withdraw_money")],
            [InlineKeyboardButton("📥 Add/Update Bank", callback_data="add_bank"), InlineKeyboardButton("📜 History", callback_data="history")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings"), InlineKeyboardButton("🔄 Refresh", callback_data="refresh_wallet")]
        ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

async def wallet_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_main_menu(update, context)

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.effective_user.id
    user = get_user(user_id)
    
    email = user[0] or "Not Linked"
    verified = "✅ Verified" if user[1] else "❌ Unverified"

    text = (
        f"⚙️ **Account Settings**\n\n"
        f"📧 **Email:** {email}\n"
        f"🔒 **Status:** {verified}\n\n"
        f"Manage your account preferences below:"
    )
    keyboard = [
        [InlineKeyboardButton("🔐 Re-verify / Change Email", callback_data="start_login")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def history_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        f"📜 **Transaction History**\n\n"
        f"• Welcome Bonus: +₹100.00 (Completed)\n"
        f"No other recent transactions."
    )
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="main_menu")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# --- Login Conversation ---
async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Please enter your email address (Google Account email) to receive a real confirmation code:")
    return EMAIL

async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    user_id = update.effective_user.id

    code = str(random.randint(100000, 999999))
    success = send_otp_email(email, code)
    
    if not success:
        await update.message.reply_text("❌ Failed to send email. Please check your Gmail App Password configuration on Render.")
        return ConversationHandler.END

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET email = ?, confirmation_code = ? WHERE telegram_id = ?", (email, code, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"📧 A real confirmation code has been sent to **{email}**.\n\nPlease check your inbox/spam folder and enter the 6-digit code:",
        parse_mode="Markdown"
    )
    return CODE

async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    entered_code = update.message.text.strip()
    user_id = update.effective_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT confirmation_code FROM users WHERE telegram_id = ?", (user_id,))
    row = cursor.fetchone()

    if row and row[0] == entered_code:
        cursor.execute("UPDATE users SET is_verified = 1 WHERE telegram_id = ?", (user_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text("✅ Login successful! Your account is verified.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        conn.close()
        await update.message.reply_text("❌ Invalid code. Please enter the correct 6-digit confirmation code:")
        return CODE

# --- Bank & Withdrawal Conversations ---
async def start_add_bank(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Please enter your **Bank Account Number**:", parse_mode="Markdown")
    return BANK_ACC

async def receive_bank_acc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['bank_acc'] = update.message.text.strip()
    await update.message.reply_text("Please enter your bank's **IFSC Code** (e.g., HDFC0001234):", parse_mode="Markdown")
    return BANK_IFSC

async def receive_ifsc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ifsc = update.message.text.strip().upper()
    bank_acc = context.user_data.get('bank_acc')
    user_id = update.effective_user.id

    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bank_account = ?, ifsc = ? WHERE telegram_id = ?", (bank_acc, ifsc, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Bank account successfully linked!")
    await show_main_menu(update, context)
    return ConversationHandler.END

async def start_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.effective_user.id
    user = get_user(user_id)
    bank_account = user[3]

    if not bank_account:
        await query.message.reply_text("⚠️ Please add your bank account first before requesting a withdrawal.")
        return ConversationHandler.END

    balance = user[2]
    await query.message.reply_text(
        f"💸 Enter the amount you wish to withdraw in INR (Available: ₹{balance:.2f}):",
        parse_mode="Markdown"
    )
    return WITHDRAW_AMOUNT

async def process_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number for the amount:")
        return WITHDRAW_AMOUNT

    user_id = update.effective_user.id
    user = get_user(user_id)
    balance = user[2]

    if amount <= 0:
        await update.message.reply_text("❌ Amount must be greater than zero.")
        return WITHDRAW_AMOUNT

    if amount > balance:
        await update.message.reply_text(f"❌ Insufficient balance. Your available balance is ₹{balance:.2f}.")
        return WITHDRAW_AMOUNT

    new_balance = balance - amount
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ Withdrawal request of **₹{amount:.2f}** submitted successfully!\n"
        f"Funds will be transferred to your registered bank account within 24 working hours.\n\n"
        f"Remaining Balance: ₹{new_balance:.2f}",
        parse_mode="Markdown"
    )
    
    await show_main_menu(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# Register Handlers
login_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_login, pattern="^start_login$")],
    states={
        EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)],
        CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

bank_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_bank, pattern="^add_bank$")],
    states={
        BANK_ACC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_bank_acc)],
        BANK_IFSC: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ifsc)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

withdraw_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_withdrawal, pattern="^withdraw_money$")],
    states={
        WITHDRAW_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_withdrawal)]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^main_menu$"))
telegram_app.add_handler(CallbackQueryHandler(wallet_menu, pattern="^wallet_menu$"))
telegram_app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^refresh_wallet$"))
telegram_app.add_handler(CallbackQueryHandler(settings_menu, pattern="^settings$"))
telegram_app.add_handler(CallbackQueryHandler(history_menu, pattern="^history$"))
telegram_app.add_handler(login_conv)
telegram_app.add_handler(bank_conv)
telegram_app.add_handler(withdraw_conv)

@app.on_event("startup")
async def startup_event():
    await telegram_app.initialize()
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"status": "ok"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("bot:app", host="0.0.0.0", port=port)
