import razorpay
from fastapi import FastAPI, Request, HTTPException
import requests

app = FastAPI()

# Your Razorpay Account Credentials (Get from Razorpay Dashboard)
RAZORPAY_KEY_ID = "rzp_test_your_key_id"
RAZORPAY_KEY_SECRET = "your_key_secret"
client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Mock Database of Registered Client Developers
# API Key -> Client Bot Webhook URL for fulfillment notifications
REGISTERED_DEVELOPERS = {
    "client_dev_unique_api_key_123": {
        "developer_name": "John Doe",
        "webhook_url": "http://localhost:5001/fulfillment-webhook"
    }
}

@app.post("/create-payment-link")
async def create_payment_link(data: dict):
    api_key = data.get("api_key")
    telegram_user_id = data.get("telegram_user_id")
    amount = data.get("amount")
    description = data.get("description", "Telegram Bot Service")

    # Validate Developer API Key
    if api_key not in REGISTERED_DEVELOPERS:
        raise HTTPException(status_code=401, detail="Invalid or Unauthorized API Key")

    try:
        # Create Razorpay Payment Link (Supports UPI, GPay, PhonePe, Paytm, Cards, Netbanking)
        payment_link_request = {
            "amount": int(float(amount) * 100),  # Amount in paisa (e.g., ₹199 = 19900)
            "currency": "INR",
            "description": description,
            "customer": {
                "name": f"Telegram User {telegram_user_id}",
                "email": "customer@telegram.placeholder",
                "contact": "9999999999"
            },
            "notify": {"sms": False, "email": False},
            "reminder_enable": False,
            "notes": {
                "telegram_user_id": str(telegram_user_id),
                "api_key": api_key
            }
        }
        
        response = client.payment_link.create(payment_link_request)
        return {
            "status": "success",
            "payment_url": response["short_url"],
            "order_id": response["id"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/razorpay-webhook")
async def razorpay_webhook(request: Request):
    event_data = await request.json()
    
    # Check if payment is successfully completed by the user
    if event_data.get("event") == "payment_link.paid":
        payment_entity = event_data["payload"]["payment_link"]["entity"]
        notes = payment_entity.get("notes", {})
        telegram_user_id = notes.get("telegram_user_id")
        api_key = notes.get("api_key")
        
        # Locate the developer to notify their bot
        developer = REGISTERED_DEVELOPERS.get(api_key)
        if developer and developer.get("webhook_url"):
            fulfillment_payload = {
                "telegram_user_id": telegram_user_id,
                "status": "paid"
            }
            try:
                requests.post(developer["webhook_url"], json=fulfillment_payload)
            except Exception as ex:
                print(f"Failed to dispatch fulfillment webhook to client bot: {ex}")
                
    return {"status": "received"}
