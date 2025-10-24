# ig_trading.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from trading_ig import IGService


# ========= ENV =========
IG_USERNAME = os.getenv("IG_USERNAME", "").strip()
IG_PASSWORD = os.getenv("IG_PASSWORD", "").strip()
IG_API_KEY  = os.getenv("IG_API_KEY",  "").strip()
IG_ACC_TYPE = os.getenv("IG_ACC_TYPE", "DEMO").strip().upper()  # DEMO | LIVE
if IG_ACC_TYPE not in {"DEMO", "LIVE"}:
    IG_ACC_TYPE = "DEMO"

# ========= IGService singleton + TTL login =========
_IG: Optional[IGService] = None
_LAST_LOGIN_TS: float = 0.0
_LOGIN_TTL_SEC = 60 * 20  # 20 minuti


def _new_ig() -> IGService:
    if not (IG_USERNAME and IG_PASSWORD and IG_API_KEY):
        raise RuntimeError("Missing IG credentials: set IG_USERNAME, IG_PASSWORD, IG_API_KEY")
    ig = IGService(
        username=IG_USERNAME,
        password=IG_PASSWORD,
        api_key=IG_API_KEY,
        acc_type=IG_ACC_TYPE,
    )
    ig.create_session()
    return ig


def _ensure_ig() -> IGService:
    global _IG, _LAST_LOGIN_TS
    now = time.time()
    if _IG is None:
        _IG = _new_ig()
        _LAST_LOGIN_TS = now
        return _IG
    if now - _LAST_LOGIN_TS > _LOGIN_TTL_SEC:
        try:
            _IG.fetch_accounts()   # keep-alive
            _LAST_LOGIN_TS = now
        except Exception:
            _IG = _new_ig()
            _LAST_LOGIN_TS = now
    return _IG


# ========= Helpers =========
def _get(d: Dict[str, Any], key: str, default=None):
    v = d.get(key, default)
    return v if v not in ("", None) else default


def _to_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool):
        return x
    if isinstance(x, (int, float)):
        return bool(x)
    if isinstance(x, str):
        s = x.strip().lower()
        if s in {"true", "1", "yes", "y", "on"}:
            return True
        if s in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _confirm_by_ref(ig: IGService, deal_ref: Optional[str]) -> Dict[str, Any]:
    if not deal_ref:
        return {"error": "NoDealRef", "reason": "No dealReference returned"}
    try:
        conf = ig.fetch_deal_by_deal_reference(deal_ref)
        body = conf.body if hasattr(conf, "body") else conf
        # body tipicamente ha: dealReference, dealId, dealStatus, reason, reasonCode
        return {"ok": True, "confirm": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ========= API principale =========
def place_order(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Accetta payload dal webhook.

    Campi attesi:
      action: "OPEN" | "CLOSE_LONG" | "CLOSE_SHORT"   (default: OPEN)
      epic (str)                    OBBLIGATORIO
      direction ('BUY'|'SELL')      OBBLIGATORIO per OPEN
      size (float)                  default 1
      order_type ('MARKET'|'LIMIT') default 'MARKET'
      level (float)                 obbligatorio se LIMIT
      currency_code (str)           es. 'EUR'
      force_open (bool)             default True (OPEN). Per chiudere usare CLOSE_* che imposta force_open=False
      limit_distance / limit_level / stop_distance / stop_level
      guaranteed_stop (bool), trailing_stop (bool), trailing_stop_increment (float)
      time_in_force, good_till_date, quote_id (opzionali)
    """
    ig = _ensure_ig()

    action     = (_get(data, "action", "OPEN") or "OPEN").upper()
    epic       = _get(data, "epic")
    if not epic:
        raise ValueError("Missing 'epic'")

    direction  = _get(data, "direction")  # BUY | SELL
    size       = float(_get(data, "size", 1))
    order_type = (_get(data, "order_type", "MARKET") or "MARKET").upper()

    # livelli/parametri opzionali
    level              = _get(data, "level")
    limit_distance     = _get(data, "limit_distance")
    limit_level        = _get(data, "limit_level")
    stop_distance      = _get(data, "stop_distance")
    stop_level         = _get(data, "stop_level")
    guaranteed_stop    = _to_bool(_get(data, "guaranteed_stop", False))
    trailing_stop      = _to_bool(_get(data, "trailing_stop", False))
    trailing_increment = _get(data, "trailing_stop_increment")
    currency_code      = _get(data, "currency_code")
    time_in_force      = _get(data, "time_in_force")
    good_till_date     = _get(data, "good_till_date")
    quote_id           = _get(data, "quote_id")
    # su CFD rolling, IG usa tipicamente '-'
    expiry             = _get(data, "expiry", "-")

    # Normalizzazione CLOSE_* -> usa ordine opposto con force_open=False
    if action in {"CLOSE_LONG", "CLOSE_SHORT"}:
        # per CLOSE_LONG (chiudi long) inviamo SELL, per CLOSE_SHORT inviamo BUY
        direction = "SELL" if action == "CLOSE_LONG" else "BUY"
        # size: usa quella passata (per chiusure parziali) o 1 di default
        # force_open: deve essere False per chiudere
        force_open = False
        # l'order_type di default può essere MARKET; se vuoi LIMIT per chiusura, specifica level
        if order_type == "LIMIT" and level is None:
            return {"status": "error", "reason": "For CLOSE with LIMIT, 'level' is required"}
    else:
        # OPEN
        if not direction:
            return {"status": "error", "reason": "Missing 'direction' for OPEN"}
        force_open = _to_bool(_get(data, "force_open", True))
        if order_type == "LIMIT" and level is None:
            return {"status": "error", "reason": "For LIMIT orders, 'level' is required"}

    # Alcune versioni di trading-ig richiedono TUTTI gli argomenti POSIZIONALI (inclusi None).
    # Firma più comune storica (17 args posizionali):
    # epic, expiry, direction, size, level, order_type,
    # time_in_force, limit_distance, limit_level, stop_distance, stop_level,
    # guaranteed_stop, trailing_stop, trailing_stop_increment,
    # force_open, currency_code, quote_id
    args_17 = [
        epic,
        expiry,
        direction,
        size,
        level,
        order_type,
        time_in_force,
        limit_distance,
        limit_level,
        stop_distance,
        stop_level,
        bool(guaranteed_stop),
        bool(trailing_stop),
        trailing_increment,
        bool(force_open),
        currency_code,
        quote_id,
    ]

    # Alcune release inseriscono anche good_till_date come 18° posizionale
    args_18 = args_17[:-1] + [good_till_date, quote_id]

    resp = None
    last_err = None

    # Tentativo 1: 17 posizionali
    try:
        resp = ig.create_open_position(*args_17)
    except TypeError as e:
        last_err = e

    # Tentativo 2: 18 posizionali (con good_till_date)
    if resp is None:
        try:
            resp = ig.create_open_position(*args_18)
        except TypeError as e:
            last_err = e

    # Tentativo 3: fallback con keyword (per versioni più recenti che le accettano)
    if resp is None:
        try:
            resp = ig.create_open_position(
                epic=epic,
                expiry=expiry,
                direction=direction,
                size=size,
                level=level,
                order_type=order_type,
                time_in_force=time_in_force,
                limit_distance=limit_distance,
                limit_level=limit_level,
                stop_distance=stop_distance,
                stop_level=stop_level,
                guaranteed_stop=bool(guaranteed_stop),
                trailing_stop=bool(trailing_stop),
                trailing_stop_increment=trailing_increment,
                force_open=bool(force_open),
                currency_code=currency_code,
                good_till_date=good_till_date,
                quote_id=quote_id,
            )
        except Exception as e:
            # se qui fallisce, esci riportando l'ultimo TypeError “istruttivo”
            return {"status": "error", "error": e.__class__.__name__, "reason": str(e)}

    # Costruisci risposta + conferma
    try:
        body = resp.body if hasattr(resp, "body") else resp
        status_code = getattr(resp, "status_code", None)
        deal_ref = None
        if isinstance(body, dict):
            deal_ref = body.get("dealReference") or body.get("deal_reference")

        confirm = _confirm_by_ref(ig, deal_ref)

        return {
            "status": "success",
            "status_code": status_code,
            "dealReference": deal_ref,
            "raw": body,
            "confirm": confirm.get("confirm") if confirm.get("ok") else {"error": confirm.get("error")},
        }
    except Exception as e:
        return {"status": "error", "error": e.__class__.__name__, "reason": str(e)}


# ========= Utility =========
def test_connection() -> Dict[str, Any]:
    ig = _ensure_ig()
    try:
        accs = ig.fetch_accounts()
        body = accs.body if hasattr(accs, "body") else accs
        return {"ok": True, "accounts": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_markets(search: str) -> Dict[str, Any]:
    ig = _ensure_ig()
    try:
        res = ig.search_markets(search)
        body = res.body if hasattr(res, "body") else res
        return {"ok": True, "results": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}