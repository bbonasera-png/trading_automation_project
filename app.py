from __future__ import annotations
import os
import traceback
from flask import Flask, request, jsonify
from ig_trading import place_order, test_connection, list_markets, _ensure_ig

app = Flask(__name__)

# ==========================
# Config / Secret
# ==========================
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "tv_ig_2025_secret!")

# ==========================
# Root
# ==========================
@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "IG Trading Webhook is running 🚀"
    })


# ==========================
# MAIN WEBHOOK
# ==========================
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        # Legge il JSON dal body
        data = request.get_json(force=True)
        if not data:
            return jsonify({"status": "error", "reason": "No JSON payload"}), 400

        # Verifica il secret dal body
        secret = data.get("secret", "")
        if secret != WEBHOOK_SECRET:
            return jsonify({"status": "forbidden"}), 403

        # Invio ordine IG
        resp = place_order(data)
        return jsonify({"status": "success", "response": resp})

    except Exception as e:
        return jsonify({
            "status": "error",
            "exc": e.__class__.__name__,
            "reason": str(e),
            "trace": traceback.format_exc(),
        }), 500


# ==========================
# DEBUG ENDPOINT
# ==========================
@app.route("/debug", methods=["POST"])
def debug():
    data = request.get_json(force=True)
    return jsonify({
        "env_secret": WEBHOOK_SECRET,
        "body_secret": data.get("secret", ""),
        "full_body": data
    })


# ==========================
# TEST IG CONNECTION
# ==========================
@app.route("/test_ig", methods=["GET"])
def test_ig():
    try:
        secret = request.args.get("secret", "")
        if secret != WEBHOOK_SECRET:
            return jsonify({"status": "forbidden"}), 403

        result = test_connection()
        if not result.get("ok"):
            return jsonify({
                "status": "error",
                "exc": "IGException",
                "message": "test_ig failed",
                "trace": result.get("error", "unknown")
            }), 500
        return jsonify({"status": "success", "response": result})

    except Exception as e:
        return jsonify({
            "status": "error",
            "exc": e.__class__.__name__,
            "message": str(e),
            "trace": traceback.format_exc(),
        }), 500


# ==========================
# LIST MARKETS (search)
# ==========================
@app.route("/markets", methods=["GET"])
def markets():
    try:
        secret = request.args.get("secret", "")
        if secret != WEBHOOK_SECRET:
            return jsonify({"status": "forbidden"}), 403

        search = request.args.get("search", "")
        if not search:
            return jsonify({"status": "error", "message": "missing search"}), 400

        result = list_markets(search)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "status": "error",
            "exc": e.__class__.__name__,
            "message": "markets failed",
            "trace": traceback.format_exc(),
        }), 500


# ==========================
# MARKET DETAILS (EPIC info)
# ==========================
@app.route("/market_details", methods=["GET"])
def market_details():
    try:
        secret = request.args.get("secret", "")
        if secret != WEBHOOK_SECRET:
            return jsonify({"status": "forbidden"}), 403

        epic = request.args.get("epic")
        if not epic:
            return jsonify({"status": "error", "message": "missing epic"}), 400

        ig = _ensure_ig()
        details = ig.fetch_market_by_epic(epic)
        body = details.body if hasattr(details, "body") else details
        return jsonify({"status": "success", "details": body})

    except Exception as e:
        return jsonify({
            "status": "error",
            "exc": e.__class__.__name__,
            "reason": str(e),
            "trace": traceback.format_exc(),
        }), 500


# ==========================
# Entry point
# ==========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)