import requests

class IndianPaymentGateway:
    def __init__(self, api_key: str, backend_url: str = "http://localhost:8000"):
        self.api_key = api_key
        self.backend_url = backend_url

    def generate_checkout_url(self, telegram_user_id: int, amount: float, description: str) -> str:
        """Requests a secure UPI & Card payment link from your central backend."""
        payload = {
            "api_key": self.api_key,
            "telegram_user_id": telegram_user_id,
            "amount": amount,
            "description": description
        }
        
        try:
            response = requests.post(f"{self.backend_url}/create-payment-link", json=payload)
            if response.status_code == 200:
                return response.json().get("payment_url")
            else:
                raise Exception(response.json().get("detail", "Failed to generate link"))
        except Exception as e:
            print(f"Payment SDK Error: {e}")
            return None
