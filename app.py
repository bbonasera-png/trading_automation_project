# app.py — TradingView → IG Bridge (Render)
from __future__ import annotations

import os
import traceback
from flask import Flask, request, jsonify

# Funzioni IG (nel tuo ig_trading.py)
from ig_trading import place_order, test_connection, list_markets

app = Flask(__name__)

# ========= CONFIG =========
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
APP_BUILD = "2025-10-23_ig-bridge_v3"

# ========= UTILS =========
def _is_authorized(req, body: dict | None) -> bool:
    """
    Autorizzazione semplice: accetta il secret via header o via body.
    """
    header_secret = req.headers.get("X-Webhook-Secret")
    body_secret = None
    if isinstance(body, dict):
        body_secret = body.get("secret")
    if not WEBHOOK_SECRET:
        return True  # se non è impostato, non bloccare (sconsigliato in prod)
    return header_secret == WEBHOOK_SECRET or body_secret == WEBHOOK_SECRET


# ========= ROOT / HEALTH / VERSION =========
@app.get("/")
def index():
    return jsonify({"status": "ok", "service": "TradingView → IG Bridge"}), 200


@app.get("/health")
def health():
    return jsonify({"ok": True}), 200


@app.get("/__version")
def __version():
    return jsonify({"build": APP_BUILD}), 200


# ========= TEST IG =========
@app.get("/test_ig")
def test_ig():
    # supporta secret via header o querystring
    header_secret = request.headers.get("X-Webhook-Secret")
    qs_secret = request.args.get("secret")
    if WEBHOOK_SECRET and (header_secret != WEBHOOK_SECRET and qs_secret != WEBHOOK_SECRET):
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    try:
        res = test_connection()
        return (jsonify(res), 200) if res.get("ok") else (jsonify(res), 500)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ========= SEARCH EPIC =========
@app.get("/search")
def search():
    # secret via header o querystring
    header_secret = request.headers.get("X-Webhook-Secret")
    qs_secret = request.args.get("secret")
    if WEBHOOK_SECRET and (header_secret != WEBHOOK_SECRET and qs_secret != WEBHOOK_SECRET):
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": False, "error": "missing q"}), 400
    try:
        res = list_markets(q)
        return (jsonify(res), 200) if res.get("ok") else (jsonify(res), 500)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ========= WEBHOOK (TradingView) =========
@app.post("/webhook")
def webhook():
    # 1) Parse JSON
    try:
        data = request.get_json(force=True, silent=False)
        if not isinstance(data, dict):
            raise ValueError("Body must be a JSON object")
    except Exception:
        return jsonify({"status": "error", "message": "invalid json"}), 400

    # 2) Auth
    if not _is_authorized(request, data):
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    # 3) (Opzionale) Mapping action -> parametri IG
    #    Consente ai Pine di inviare {"action":"CLOSE_LONG"} senza specificare direction/force_open.
    action = (data.get("action") or "").upper()
    if action == "OPEN":
        # per OPEN pretendiamo sempre direction
        if "direction" not in data:
            return jsonify({"status": "error", "message": "direction required for action=OPEN"}), 400
    elif action == "CLOSE_LONG":
        data["direction"] = "SELL"
        data["force_open"] = False
        data.setdefault("order_type", "MARKET")
    elif action == "CLOSE_SHORT":
        data["direction"] = "BUY"
        data["force_open"] = False
        data.setdefault("order_type", "MARKET")
    # Se non c'è 'action', usiamo direttamente quello che arriva (direction/order_type/etc.)

    # 4) Esecuzione ordine IG
    try:
        resp = place_order(data)
        # resp è un dict del tipo:
        # {"status":"success","status_code":..., "dealReference":..., "raw":...}  OPPURE {"status":"error",...}
        return jsonify({"status": "success", "response": resp}), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500


# ========= MAIN (solo per run locale) =========
if __name__ == "__main__":
    # Render usa gunicorn (startCommand), ma questo aiuta nei test locali:
    port = int(os.getenv("PORT", "10000"))  # su Render è 10000
    app.run(host="0.0.0.0", port=port)
