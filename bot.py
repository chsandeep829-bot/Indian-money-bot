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
    MessageHandler,
    filters
)

logging.basicConfig(level=logging.INFO)

# --- Dynamic Bot Token Setup ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("\n--- Telegram Bot Setup ---")
    TELEGRAM_BOT_TOKEN = input("Enter your Telegram Bot Token (from @BotFather): ").strip()

WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://indian-money-bot-amtk.onrender.com/webhook")

# Gmail SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "Chsandeep829@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

app = FastAPI()

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
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

# Initialize Telegram Application
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

def get_user(telegram_id):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT email, is_verified, balance, bank_account, ifsc FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user

# --- Real Email Sender Function ---
def send_otp_email(receiver_email, code):
    try:
        # Strip any accidental spaces from app password
        clean_password = SENDER_PASSWORD.replace(" ", "")
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = "🔐 Your Wallet Verification Code"

        body = (
            f"Hello,\n\n"
            f"Your 6-digit confirmation code for your secure wallet login is: {code}\n\n"
            f"Please enter this code in the web app to verify your account.\n"
            f"If you did not request this, please ignore this email."
        )
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, clean_password)
        server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
        return False

# --- Full Web App Frontend (HTML/CSS/JS) ---
@app.get("/webapp", response_class=HTMLResponse)
async def webapp(telegram_id: int = 0):
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Indian Payments Wallet</title>
        <script src="https://telegram.org/js/telegram-web-app.js"></script>
        <style>
            body {{
                background-color: #0b0f19;
                color: #f8fafc;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                margin: 0;
                padding: 16px;
                display: flex;
                flex-direction: column;
                align-items: center;
            }}
            .container {{
                width: 100%;
                max-width: 400px;
            }}
            .card {{
                background: #1e293b;
                padding: 20px;
                border-radius: 16px;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
                margin-bottom: 16px;
            }}
            h2, h3 {{ margin-top: 0; }}
            input, button {{
                width: 100%;
                padding: 12px;
                border-radius: 8px;
                border: 1px solid #334155;
                background: #0f172a;
                color: white;
                font-size: 15px;
                margin-bottom: 12px;
                box-sizing: border-box;
            }}
            .btn-primary {{
                background: #2563eb;
                border: none;
                font-weight: bold;
                cursor: pointer;
            }}
            .btn-google {{
                background: white;
                color: #1e293b;
                border: none;
                font-weight: bold;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }}
            .hidden {{ display: none; }}
            .balance {{ font-size: 28px; font-weight: bold; color: #22c55e; margin: 10px 0; }}
            .status-badge {{ background: #ef4444; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
            .verified-badge {{ background: #22c55e; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <!-- LOGIN VIEW -->
            <div id="loginView" class="card">
                <h2>🔐 Secure Login</h2>
                <p style="color: #94a3b8; font-size: 14px;">Select Google account or enter email</p>
                <button class="btn-google" onclick="mockGoogleLogin()">
                    <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"/><path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.13 0-5.78-2.11-6.73-4.96H1.18v3.14C3.15 21.32 7.23 24 12 24z"/><path fill="#FBBC05" d="M5.27 14.24c-.25-.72-.38-1.49-.38-2.24s.13-1.52.38-2.24V6.62H1.18C.43 8.14 0 9.87 0 11.75s.43 3.61 1.18 5.13l4.09-2.64z"/><path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.23 0 3.15 2.68 1.18 6.62l4.09 3.14c.95-2.85 3.6-4.96 6.73-4.96z"/></svg>
                    Continue with Google
                </button>
                <input type="email" id="emailInput" placeholder="name@gmail.com">
                <button class="btn-primary" onclick="sendOtp()">Send OTP</button>
            </div>

            <!-- OTP VIEW -->
            <div id="otpView" class="card hidden">
                <h3>🔑 Enter OTP Code</h3>
                <p style="color: #94a3b8; font-size: 14px;">Check your email inbox for the real verification code.</p>
                <input type="text" id="otpInput" placeholder="6-digit code">
                <button class="btn-primary" onclick="verifyOtp()">Verify Code</button>
            </div>

            <!-- WALLET DASHBOARD VIEW -->
            <div id="dashboardView" class="card hidden">
                <h3>💼 INR Wallet Dashboard</h3>
                <p>Status: <span id="statusBadge" class="status-badge">Unverified</span></p>
                <div>Total Balance</div>
                <div class="balance" id="balanceDisplay">₹0.00</div>
                
                <hr style="border-color: #334155; margin: 15px 0;">
                
                <h4>🏦 Bank Account Details</h4>
                <input type="text" id="bankAccInput" placeholder="Bank Account Number">
                <input type="text" id="ifscInput" placeholder="IFSC Code (e.g., HDFC0001234)">
                <button class="btn-primary" onclick="saveBank()">Save Bank Details</button>

                <hr style="border-color: #334155; margin: 15px 0;">

                <h4>💸 Withdraw Funds</h4>
                <input type="number" id="withdrawAmountInput" placeholder="Amount in INR">
                <button class="btn-primary" style="background: #22c55e;" onclick="withdraw()">Withdraw Money</button>
            </div>
        </div>

        <script>
            let tg = window.Telegram.WebApp;
            tg.expand();
            let telegramId = {telegram_id};
            if (!telegramId && tg.initDataUnsafe && tg.initDataUnsafe.user) {{
                telegramId = tg.initDataUnsafe.user.id;
            }}

            let currentEmail = "";

            async function loadUserData() {{
                let res = await fetch(`/api/user?telegram_id=${{telegramId}}`);
                let data = await res.json();
                if (data.is_verified) {{
                    document.getElementById('loginView').classList.add('hidden');
                    document.getElementById('otpView').classList.add('hidden');
                    document.getElementById('dashboardView').classList.remove('hidden');
                    document.getElementById('balanceDisplay').innerText = `₹${{data.balance.toFixed(2)}}`;
                    document.getElementById('statusBadge').innerText = "Verified";
                    document.getElementById('statusBadge').className = "verified-badge";
                    if (data.bank_account) document.getElementById('bankAccInput').value = data.bank_account;
                    if (data.ifsc) document.getElementById('ifscInput').value = data.ifsc;
                }}
            }}

            function mockGoogleLogin() {{
                let email = prompt("Enter your Google Account email:", "Chsandeep829@gmail.com");
                if (email) {{
                    document.getElementById('emailInput').value = email;
                    sendOtp();
                }}
            }}

            async function sendOtp() {{
                currentEmail = document.getElementById('emailInput').value.trim();
                if (!currentEmail) {{ alert("Enter valid email"); return; }}
                let res = await fetch('/api/send-otp', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ telegram_id: telegramId, email: currentEmail }})
                }});
                let data = await res.json();
                if (data.success) {{
                    document.getElementById('loginView').classList.add('hidden');
                    document.getElementById('otpView').classList.remove('hidden');
                }} else {{
                    alert("Failed to send email. Check your SMTP configuration.");
                }}
            }}

            async function verifyOtp() {{
                let code = document.getElementById('otpInput').value.trim();
                let res = await fetch('/api/verify-otp', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ telegram_id: telegramId, code: code }})
                }});
                let data = await res.json();
                if (data.success) {{
                    alert("Verified successfully!");
                    loadUserData();
                }} else {{
                    alert("Invalid confirmation code.");
                }}
            }}

            async function saveBank() {{
                let bank_account = document.getElementById('bankAccInput').value.trim();
                let ifsc = document.getElementById('ifscInput').value.trim();
                let res = await fetch('/api/save-bank', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ telegram_id: telegramId, bank_account: bank_account, ifsc: ifsc }})
                }});
                let data = await res.json();
                if (data.success) {{ alert("Bank details updated!"); }}
            }}

            async function withdraw() {{
                let amount = parseFloat(document.getElementById('withdrawAmountInput').value);
                let res = await fetch('/api/withdraw', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ telegram_id: telegramId, amount: amount }})
                }});
                let data = await res.json();
                if (data.success) {{
                    alert(`Withdrawal of ₹${{amount}} successful!`);
                    loadUserData();
                }} else {{
                    alert(data.message || "Withdrawal failed.");
                }}
            }}

            loadUserData();
        </script>
    </body>
    </html>
    """

# --- API Endpoints for Web App ---
@app.get("/api/user")
async def api_user(telegram_id: int):
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (telegram_id, balance) VALUES (?, ?)", (telegram_id, 100.0))
    conn.commit()
    conn.close()
    
    user = get_user(telegram_id)
    return {
        "email": user[0],
        "is_verified": user[1],
        "balance": user[2],
        "bank_account": user[3],
        "ifsc": user[4]
    }

@app.post("/api/send-otp")
async def api_send_otp(request: Request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    email = data.get("email")
    code = str(random.randint(100000, 999999))

    success = send_otp_email(email, code)
    if success:
        conn = sqlite3.connect("bot_database.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET email = ?, confirmation_code = ? WHERE telegram_id = ?", (email, code, telegram_id))
        conn.commit()
        conn.close()
        return {"success": True}
    return {"success": False}

@app.post("/api/verify-otp")
async def api_verify_otp(request: Request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    code = data.get("code")

    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("SELECT confirmation_code FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()

    if row and row[0] == code:
        cursor.execute("UPDATE users SET is_verified = 1 WHERE telegram_id = ?", (telegram_id,))
        conn.commit()
        conn.close()
        return {"success": True}
    conn.close()
    return {"success": False}

@app.post("/api/save-bank")
async def api_save_bank(request: Request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    bank_account = data.get("bank_account")
    ifsc = data.get("ifsc").upper()

    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET bank_account = ?, ifsc = ? WHERE telegram_id = ?", (bank_account, ifsc, telegram_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.post("/api/withdraw")
async def api_withdraw(request: Request):
    data = await request.json()
    telegram_id = data.get("telegram_id")
    amount = float(data.get("amount"))

    user = get_user(telegram_id)
    balance = user[2]
    bank = user[3]

    if not bank:
        return {"success": False, "message": "Please add your bank account first."}
    if amount <= 0 or amount > balance:
        return {"success": False, "message": "Invalid amount or insufficient balance."}

    new_balance = balance - amount
    conn = sqlite3.connect("bot_database.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (new_balance, telegram_id))
    conn.commit()
    conn.close()
    return {"success": True}

# --- Telegram Bot Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    webapp_url = f"{WEBHOOK_URL.replace('/webhook', '')}/webapp?telegram_id={user_id}"
    
    keyboard = [[InlineKeyboardButton("🚀 Open Indian Payments Dashboard", web_app=WebAppInfo(url=webapp_url))]]
    await update.message.reply_text(
        "🇮🇳 **Welcome to Indian Payments Bot**\n\nClick below to securely log in, link your bank, and manage your INR wallet balance inside the web app:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

telegram_app.add_handler(CommandHandler("start", start))

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
