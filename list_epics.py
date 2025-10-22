from trading_ig import IGService
import os

# ✅ Inserisci qui le tue credenziali IG oppure usa variabili d'ambiente
USERNAME = os.getenv("IG_USERNAME", "sefon13")
PASSWORD = os.getenv("IG_PASSWORD", "P1x3y013579??")
API_KEY = os.getenv("IG_API_KEY", "46a7e29c47e13899898265d16a78e35f693c2d87")
ACCOUNT_TYPE = "DEMO"  # Usa "LIVE" per account reali

print("🔐 Connessione in corso con l'API IG...")

# Crea la sessione IG
try:
    ig_service = IGService(USERNAME, PASSWORD, API_KEY, ACCOUNT_TYPE)
    ig_service.create_session()
    print("✅ Connessione riuscita.")
except Exception as e:
    print(f"❌ Errore nella connessione: {e}")
    exit()

# Recupera i nodi principali del mercato
print("🔍 Recupero nodi principali...")
try:
    navigation = ig_service.fetch_market_navigation()
    nodes = navigation.get("nodes", [])
    print(f"✅ Trovati {len(nodes)} nodi principali.")
except Exception as e:
    print(f"❌ Errore nel recupero dei nodi: {e}")
    exit()

# Funzione ricorsiva per estrarre strumenti da nodi

def fetch_epics(node_id):
    result = []
    try:
        sub_nodes = ig_service.fetch_market_navigation(node_id)
        for node in sub_nodes.get("nodes", []):
            if node["type"] == "MARKET":
                result.append({"epic": node["epic"], "name": node["name"]})
            elif node["type"] == "NODE":
                result.extend(fetch_epics(node["id"]))
    except Exception as e:
        print(f"⚠️ Errore nel nodo {node_id}: {e}")
    return result

# Estrai tutti gli strumenti disponibili
print("📦 Estrazione strumenti disponibili...")
all_epics = []
for node in nodes:
    all_epics.extend(fetch_epics(node["id"]))

print(f"✅ Trovati {len(all_epics)} strumenti disponibili nel tuo account demo IG.")
for epic in all_epics[:20]:
    print(f"{epic['epic']}: {epic['name']}")
