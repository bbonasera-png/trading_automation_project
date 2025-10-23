# ig_trading.py — versione FIX (positional args IG API)
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional
from trading_ig import IGService  # libreria: trading-ig

# ======================
# CONFIGURAZIONE AMBIENTE
# ======================
IG_USERNAME = os.getenv("IG_USERNAME", "").strip()
IG_PASSWORD = os.getenv("IG_PASSWORD", "").strip()
IG_API_KEY  = os.getenv("IG_API_KEY", "").strip()
IG_ACC_TYPE = os.getenv("IG_ACC_TYPE", "DEMO").strip().upper()

if IG_ACC_TYPE not in {"DEMO", "LIVE"}:
    IG_ACC_TYPE = "DEMO"

_IG: Optional[IGService] = None
_LAST_LOGIN_TS = 0.0
_LOGIN_TTL_SEC = 60 * 20  # 20 minuti

# ======================
# CONNESSIONE IG
# ======================
def _new_ig() -> IGService:
    if not (IG_USERNAME and IG_PASSWORD and IG_API_KEY):
        raise RuntimeError("Missing IG credentials: set IG_USERNAME, IG_PASSWORD, IG_API_KEY")

    ig = IGService(
        username=IG_USERNAME,
        password=IG_PASSWORD,
        api_key=IG_API_KEY,
        acc_type=IG_ACC_TYPE
    )
    ig.create_session()
    return ig


def _ensure_ig() -> IGService:
    """Crea o rinnova la sessione IG se scaduta"""
    global _IG, _LAST_LOGIN_TS
    now = time.time()

    if _IG is None:
        _IG = _new_ig()
        _LAST_LOGIN_TS = now
        return _IG

    if now - _LAST_LOGIN_TS > _LOGIN_TTL_SEC:
        try:
            _IG.fetch_accounts()
            _LAST_LOGIN_TS = now
        except Exception:
            _IG = _new_ig()
            _LAST_LOGIN_TS = now
    return _IG

# ======================
# FUNZIONE PRINCIPALE
# ======================
def place_order(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Esegue un ordine su IG (apertura o chiusura posizione).
    Esempio payload:
      {
        "epic": "CS.D.EURUSD.MINI.IP",
        "direction": "BUY",
        "size": 1,
        "order_type": "MARKET",
        "force_open": true
      }
    """
    ig = _ensure_ig()

    epic = data.get("epic")
    direction = data.get("direction", "BUY").upper()
    size = float(data.get("size", 1))
    order_type = data.get("order_type", "MARKET").upper()

    # Default parametri opzionali
    expiry = data.get("expiry", "-")
    force_open = bool(data.get("force_open", True))
    guaranteed_stop = bool(data.get("guaranteed_stop", False))
    level = data.get("level", None)
    limit_distance = data.get("limit_distance", None)
    limit_level = data.get("limit_level", None)
    quote_id = data.get("quote_id", None)
    stop_distance = data.get("stop_distance", None)
    stop_level = data.get("stop_level", None)
    time_in_force = data.get("time_in_force", None)
    good_till_date = data.get("good_till_date", None)
    trailing_stop = data.get("trailing_stop", False)
    trailing_inc = data.get("trailing_stop_increment", None)
    currency_code = data.get("currency_code", "EUR")

    # === Chiamata IG con argomenti POSIZIONALI ===
    try:
        resp = ig.create_open_position(
            currency_code,
            direction,
            epic,
            expiry,
            force_open,
            guaranteed_stop,
            level,
            limit_distance,
            limit_level,
            order_type,
            quote_id,
            size,
            stop_distance,
            stop_level,
            time_in_force,
            good_till_date,
            trailing_stop,
            trailing_inc,
        )

        body = getattr(resp, "body", None)
        return {
            "status": "success",
            "status_code": getattr(resp, "status_code", None),
            "dealReference": (body or {}).get("dealReference") if isinstance(body, dict) else None,
            "raw": body if body is not None else str(resp)
        }

    except Exception as e:
        return {"status": "error", "error": type(e).__name__, "reason": str(e)}

# ======================
# FUNZIONI DI SUPPORTO
# ======================
def test_connection() -> Dict[str, Any]:
    """Verifica credenziali e connessione IG"""
    try:
        ig = _ensure_ig()
        accs = ig.fetch_accounts()
        return {"ok": True, "accounts": accs.body if hasattr(accs, "body") else accs}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_markets(search: str) -> Dict[str, Any]:
    """Ricerca mercati per nome o simbolo"""
    try:
        ig = _ensure_ig()
        res = ig.search_markets(search)
        return {"ok": True, "results": res.body if hasattr(res, "body") else res}
    except Exception as e:
        return {"ok": False, "error": str(e)}
