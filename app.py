# app.py
from __future__ import annotations

import os
from flask import Flask, request, jsonify
from ig_trading import place_order  # riusa la tua funzione IG
import traceback

app = Flask(__name__)

# ========= CONFIG =========
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

# ========= ROOT =========
@app.route("/")
def index():
    return jsonify({"status": "ok", "service": "TradingView → IG Bridge"}), 200


# ========= HEALTH CHECK =========
@app.route("/health")
def health():
    return jsonify({"ok": True}), 200


# ========= WEBHOOK =========
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"status": "error", "message": "invalid json"}), 400

    # --- Autenticazione ---
    header_secret = request.headers.get("X-Webhook-Secret")
    body_secret = data.get("secret") if isinstance(data, dict) else None
    if WEBHOOK_SECRET and (header_secret != WEBHOOK_SECRET and body_secret != WEBHOOK_SECRET):
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    # --- Logica ordine ---
    try:
        response = place_order(data)
        return jsonify({"response": response, "status": "success"}), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500


# ========= TEST IG ENDPOINT =========
APP_BUILD = "2025-10-23_IG_test_v1"

@app.get("/__version")
def __version():
    return {"build": APP_BUILD}, 200


@app.get("/test_ig")
def test_ig():
    header_secret = request.headers.get("X-Webhook-Secret")
    qs_secret = request.args.get("secret")

    if WEBHOOK_SECRET and (header_secret != WEBHOOK_SECRET and qs_secret != WEBHOOK_SECRET):
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    try:
        from ig_trading import test_connection
        res = test_connection()
        return (jsonify(res), 200) if res.get("ok") else (jsonify(res), 500)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ========= MAIN =========
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
