from pydantic import BaseModel, Field, ValidationError
from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
from time import time
from ig_trading import place_order  # riusa la tua funzione

load_dotenv()
app = Flask(__name__)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

class AlertPayload(BaseModel):
    epic: str
    direction: str | None = Field(default=None, pattern="^(BUY|SELL)$")  # richiesto solo per OPEN
    size: float = 1
    order_type: str = Field(default="MARKET", pattern="^(MARKET|LIMIT)$")
    # opzionali IG
    currency_code: str | None = None
    expiry: str | None = None
    level: float | None = None
    limit_distance: float | None = None
    limit_level: float | None = None
    stop_distance: float | None = None
    stop_level: float | None = None
    trailing_stop: bool | None = None
    trailing_stop_increment: float | None = None
    # controllo flusso
    action: str = Field(default="OPEN", pattern="^(OPEN|CLOSE_LONG|CLOSE_SHORT)$")
    # meta
    alert_id: str | None = None
    ts: float | None = None
    secret: str | None = None  # per chi usa il secret nel body

_recent_ids: dict[str, float] = {}

@app.get("/health")
def health():
    return {"ok": True}, 200

@app.post("/webhook")
def webhook():
    req_json = request.get_json(silent=True) or {}

    # segreto: header o body
    header_secret = request.headers.get("X-Webhook-Secret")
    body_secret = req_json.get("secret")
    if WEBHOOK_SECRET:
        if header_secret != WEBHOOK_SECRET and body_secret != WEBHOOK_SECRET:
            return jsonify({"status": "error", "message": "unauthorized"}), 401

    # validazione
    try:
        payload = AlertPayload.model_validate(req_json)
    except ValidationError as ve:
        return jsonify({"status": "error", "message": ve.errors()}), 400

    # idempotenza semplice
    if payload.alert_id:
        now = time()
        last = _recent_ids.get(payload.alert_id)
        if last and now - last < 600:
            return jsonify({"status": "ok", "message": "duplicate ignored"}), 200
        _recent_ids[payload.alert_id] = now

    try:
        # routing: OPEN vs CLOSE
        data = payload.model_dump(exclude_none=True)

        if payload.action == "OPEN":
            resp = place_order(data)  # come già fai ora
        else:
            # CLOSE_LONG -> invia SELL con force_open=False
            # CLOSE_SHORT -> invia BUY  con force_open=False
            close_dir = "SELL" if payload.action == "CLOSE_LONG" else "BUY"
            close_payload = {
                "epic": payload.epic,
                "direction": close_dir,
                "size": payload.size,
                "order_type": payload.order_type,
                "force_open": False,        # <-- NETTING: chiude la posizione opposta
                "currency_code": data.get("currency_code", "USD"),
                "expiry": data.get("expiry", "-"),
                # opzionali: puoi passare livello o distanze se vuoi una chiusura LIMIT
            }
            resp = place_order(close_payload)

        return jsonify({"status": "success", "response": resp}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
