# app.py
from __future__ import annotations

import os
from flask import Flask, request, jsonify

from ig_trading import test_connection, list_markets, place_order

app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "tv_ig_2025_secret!")

def _require_secret(req: request) -> tuple[bool, str | None]:
    hdr = req.headers.get("X-Webhook-Secret")
    if hdr is None or hdr != WEBHOOK_SECRET:
        return False, "unauthorized"
    return True, None

@app.get("/")
def root():
    return jsonify({"ok": True, "service": "ig-tv-webhook", "hint": "use /test_ig, /markets, /webhook"}), 200

@app.get("/__version")
def version():
    return jsonify({
        "service": "ig-tv-webhook",
        "version": os.getenv("RENDER_GIT_COMMIT", "local"),
        "env": {"IG_ACC_TYPE": os.getenv("IG_ACC_TYPE", "DEMO")}
    }), 200

@app.get("/test_ig")
def test_ig():
    ok, err = _require_secret(request)
    if not ok:
        return jsonify({"status": "error", "message": err}), 401
    return jsonify(test_connection()), 200

@app.get("/markets")
def markets():
    ok, err = _require_secret(request)
    if not ok:
        return jsonify({"status": "error", "message": err}), 401
    q = request.args.get("q") or request.args.get("search") or ""
    if not q:
        return jsonify({"status": "error", "message": "missing query param ?q="}), 400
    res = list_markets(q)
    return jsonify(res), 200

@app.post("/webhook")
def webhook():
    ok, err = _require_secret(request)
    if not ok:
        return jsonify({"status": "error", "message": err}), 401
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        return jsonify({"status": "error", "message": f"invalid json: {e}"}), 400

    try:
        resp = place_order(data)
        return jsonify({"status": "success", "response": resp}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)