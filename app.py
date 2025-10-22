from flask import Flask, request, jsonify
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
import os
from ig_trading import place_order  # riusa la tua funzione
# opzionale: semplice deduplicatore in memoria
from time import time

load_dotenv()
app = Flask(__name__)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # imposta su Render

class AlertPayload(BaseModel):
    epic: str
    direction: str = Field(pattern="^(BUY|SELL)$")
    size: float = 1
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT)$")
    # opzionali
    currency_code: str | None = None
    expiry: str | None = None
    level: float | None = None
    limit_distance: float | None = None
    limit_level: float | None = None
    stop_distance: float | None = None
    stop_level: float | None = None
    trailing_stop: bool | None = None
    trailing_stop_increment: float | None = None
    # id per idempotenza (consigliato in TradingView: {{alert_id}})
    alert_id: str | None = None
    ts: float | None = None  # timestamp lato TV

_recent_ids: dict[str, float] = {}

@app.get("/health")
def health():
    return {"ok": True}, 200

@app.post("/webhook")
def webhook():
    # semplice segreto via header
    if WEBHOOK_SECRET and request.headers.get("X-Webhook-Secret") != WEBHOOK_SECRET:
        return jsonify({"status": "error", "message": "unauthorized"}), 401

    try:
        payload = AlertPayload.model_validate(request.json or {})
    except ValidationError as ve:
        return jsonify({"status": "error", "message": ve.errors()}), 400

    # idempotenza best-effort
    if payload.alert_id:
        now = time()
        last = _recent_ids.get(payload.alert_id)
        if last and now - last < 600:
            return jsonify({"status": "ok", "message": "duplicate ignored"}), 200
        _recent_ids[payload.alert_id] = now

    try:
        resp = place_order(payload.model_dump(exclude_none=True))
        return jsonify({"status": "success", "response": resp}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # per test locale: FLASK_RUN_PORT o 5050
    port = int(os.getenv("PORT", "5050"))
    app.run(host="0.0.0.0", port=port)
