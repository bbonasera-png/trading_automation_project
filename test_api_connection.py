
from trading_ig import IGService

# Inserisci qui le tue credenziali IG demo
USERNAME = "your_username"
PASSWORD = "your_password"
API_KEY = "your_api_key"
ACCOUNT_TYPE = "DEMO"

print("🔐 Test connessione API IG...")

try:
    ig_service = IGService(USERNAME, PASSWORD, API_KEY, ACCOUNT_TYPE)
    ig_service.create_session()
    print("✅ Connessione riuscita! La tua API key è valida.")
except Exception as e:
    print(f"❌ Errore nella connessione: {e}")
