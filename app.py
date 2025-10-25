# app.py
from __future__ import annotations

import os
import json
from typing import Any, Dict
from flask import Flask, request, jsonify

# Importa le funzioni del tuo modulo IG
from ig_trading import test_connection, list_markets, place_order

app = Flask(__name__)

SERVICE_NAME = os.getenv("SERVICE_NAME", "ig-tv-webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

def _json_error(message: str, status: int = 400, **extra):
    payload = {"status": "error", "message": message}
    if extra:
        payload.update(extra)
    resp = jsonify(payload)
    resp.status_code = status
    return resp

def _require_secret(req) -> Dict[str, Any] | None:
    """Verifica il secret in header."""
    hdr = req.headers.get("X-Webhook-Secret", "").strip()
    if not WEBHOOK_SECRET:
        # Servizio configurato male su Render
        return {"status": "error",
                "message": "WEBHOOK_SECRET is not set on server",
                "code": "MISSING_SERVER_SECRET"}
    if hdr != WEBHOOK_SECRET:
        return {"status": "error",
                "message": "unauthorized",
                "code": "UNAUTHORIZED"}
    return None

@app.errorhandler(404)
def _not_found(_e):
    return _json_error("not found", 404)

@app.errorhandler(405)
def _method_not_allowed(_e):
    return _json_error("method not allowed", 405)

@app.errorhandler(Exception)
def _unhandled(e):
    # Fai vedere eccezione per debug; in produzione potresti nasconderla
    return _json_error("internal error", 500, trace=str(e), exc=e.__class__.__name__)

@app.get("/")
def root():
    return jsonify({"ok": True, "service": SERVICE_NAME, "status": "ready"})

@app.get("/__version")
def version():
    return jsonify({
        "ok": True,
        "service": SERVICE_NAME,
        "python": os.getenv("PYTHON_VERSION", ""),
        "env": {
            "acc_type": os.getenv("IG_ACC_TYPE", ""),
        }
    })

@app.get("/test_ig")
def test_ig():
    sec = _require_secret(request)
    if sec:
        # 401 semanticamente più corretto
        return _json_error(sec["message"], 401, code=sec.get("code"))

    try:
        res = test_connection()
        return jsonify(res)
    except Exception as e:
        return _json_error("test_ig failed", 500, exc=e.__class__.__name__, trace=str(e))

@app.get("/markets")
def markets():
    sec = _require_secret(request)
    if sec:
        return _json_error(sec["message"], 401, code=sec.get("code"))

    q = request.args.get("search", "").strip()
    if not q:
        return _json_error("missing query param 'search'", 400)
    try:
        res = list_markets(q)
        return jsonify(res)
    except Exception as e:
        return _json_error("markets failed", 500, exc=e.__class__.__name__, trace=str(e))

@app.post("/webhook")
def webhook():
    sec = _require_secret(request)
    if sec:
        return _json_error(sec["message"], 401, code=sec.get("code"))

    # accetta JSON puro
    try:
        data = request.get_json(force=True, silent=False)
        if not isinstance(data, dict):
            return _json_error("invalid json payload", 400)
    except Exception as e:
        return _json_error("invalid json", 400, exc=e.__class__.__name__, trace=str(e))

    # chiama la logica ordine
    try:
        resp = place_order(data)
        # uniforma risposta
        return jsonify({"status": "success", "response": resp})
    except Exception as e:
        return _json_error("webhook failed", 500, exc=e.__class__.__name__, trace=str(e))

if __name__ == "__main__":
    # per esecuzione locale: python app.py
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))