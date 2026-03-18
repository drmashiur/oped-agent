import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
chat_id = os.getenv("TELEGRAM_CHAT_ID")

url = f"https://api.telegram.org/bot{token}/sendMessage"
payload = {
    "chat_id": chat_id,
    "text": "Test message from my WSL2 op-ed agent."
}

r = requests.post(url, data=payload, timeout=30)
print(r.status_code)
print(r.text)
