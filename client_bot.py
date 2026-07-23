import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
from indian_pay import IndianPaymentGateway

logging.basicConfig(level=logging.INFO)

# Initialize your plug-and-play Indian Payment SDK with their developer API key
payment_gateway = IndianPaymentGateway(
    api_key="client_dev_unique_api_key_123", 
    backend_url="http://localhost:8000"
)

TELEGRAM_BOT_TOKEN = "YOUR_CLIENT_DEVELOPER_BOT_TOKEN_HERE"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💳 Pay ₹199 (UPI / GPay / Cards)", callback_data="buy_vip")]
    ]
    await update.message.reply_text(
        "Welcome! Click below to purchase VIP access using any Indian payment app:", 
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Generate dynamic payment link via your SDK
    payment_url = payment_gateway.generate_checkout_url(
        telegram_user_id=user_id, 
        amount=199, 
        description="Telegram Bot VIP Subscription"
    )
    
    if payment_url:
        keyboard = [[InlineKeyboardButton("👉 Click Here to Pay Securely", url=payment_url)]]
        await query.edit_message_text(
            text="Your secure payment link is ready. Complete your payment via UPI, PhonePe, Paytm, or Card:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(text="Could not process payment link right now. Try again later.")

if __name__ == "__main__":
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_checkout))
    
    print("Client Telegram Bot is running...")
    application.run_polling()
