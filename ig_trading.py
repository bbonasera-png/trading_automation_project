# ig_trading.py
from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from trading_ig import IGService
from trading_ig.config import config
from trading_ig.exceptions import IGException

# ======= Lettura ENV =======
IG_USERNAME = os.getenv("IG_USERNAME", "")
IG_PASSWORD = os.getenv("IG_PASSWORD", "")
IG_API_KEY  = os.getenv("IG_API_KEY", "")
IG_ACC_TYPE = os.getenv("IG_ACC_TYPE", "DEMO").upper().strip()  # DEMO o LIVE

if IG_ACC_TYPE not in {"DEMO", "LIVE"}:
    IG_ACC_TYPE = "DEMO"

# ======= Singleton IGService =======
_IG: Optional[IGService] = None
_LAST_LOGIN_TS: float = 0.0
_LOGIN_TTL = 60 * 20  # rifai login ogni 20 minuti

def _new_ig() -> IGService:
    """
    Crea una nuova sessione IGService.
    """
    if not (IG_USERNAME and IG_PASSWORD and IG_API_KEY):
        raise RuntimeError("IG credentials missing: set IG_USERNAME, IG_PASSWORD, IG_API_KEY")

    ig = IGService(
        username=IG_USERNAME,
        password=IG_PASSWORD,
        api_key=IG_API_KEY,
        acc_type=IG_ACC_TYPE  # 'DEMO' o 'LIVE'
    )
    ig.create_session()
    # opzionale: se hai più conti, potresti dover fare ig.switch_account(accountId, defaultAccount)
    return ig

def _ensure_ig() -> IGService:
    """
    Ritorna un IGService attivo, rifacendo il login se scaduto.
    """
    global _IG, _LAST_LOGIN_TS
    now = time.time()
    if _IG is None:
        _IG = _new_ig()
        _LAST_LOGIN_TS = now
        return _IG

    if (now - _LAST_LOGIN_TS) > _LOGIN_TTL:
        try:
            # tenta una chiamata leggera per verificare la sessione
            _IG.fetch_accounts()
            _LAST_LOGIN_TS = now
        except Exception:
            # ri-crea sessione
            _IG = _new_ig()
            _LAST_LOGIN_TS = now
    return _IG

# ======= Utils =======
def _get(d: Dict[str, Any], key: str, default=None):
    v = d.get(key, default)
    return v if v not in ("", None) else default

def _coerce_bool(x: Any, default: bool = False) -> bool:
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

# ======= API Principale =======
def place_order(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Esegue un ordine su IG.
    `data` può contenere:
      epic (str)                      -> OBBLIGATORIO
      direction ('BUY'|'SELL')        -> OBBLIGATORIO per OPEN / per CLOSE lo decide chi chiama
      size (float)                    -> default 1
      order_type ('MARKET'|'LIMIT')   -> default 'MARKET'
      level (float)                   -> per ordini LIMIT
      limit_distance (float)          -> distanza TP
      limit_level (float)             -> livello TP
      stop_distance (float)           -> distanza SL
      stop_level (float)              -> livello SL
      trailing_stop (bool)
      trailing_stop_increment (float)
      force_open (bool)               -> default True (OPEN); per chiusure usare False
      currency_code (str)             -> es. 'EUR', 'USD'
      expiry (str)                    -> default '-' (rolling)
      quote_id (str)                  -> opzionale
    Ritorna il payload di risposta IG o un dict con 'error'.
    """
    ig = _ensure_ig()

    epic        = _get(data, "epic")
    if not epic:
        raise ValueError("Missing 'epic'")

    direction   = _get(data, "direction")  # BUY / SELL
    size        = float(_get(data, "size", 1))
    order_type  = (_get(data, "order_type", "MARKET") or "MARKET").upper()

    level               = _get(data, "level")  # float | None
    limit_distance      = _get(data, "limit_distance")
    limit_level         = _get(data, "limit_level")
    stop_distance       = _get(data, "stop_distance")
    stop_level          = _get(data, "stop_level")
    trailing_stop       = _coerce_bool(_get(data, "trailing_stop", False))
    trailing_increment  = _get(data, "trailing_stop_increment")
    force_open          = _coerce_bool(_get(data, "force_open", True))
    currency_code       = _get(data, "currency_code")
    expiry              = _get(data, "expiry", "-")
    quote_id            = _get(data, "quote_id")
    guaranteed_stop     = _coerce_bool(_get(data, "guaranteed_stop", False))

    if order_type not in {"MARKET", "LIMIT"}:
        raise ValueError("order_type must be MARKET or LIMIT")

    if order_type == "LIMIT" and level is None:
        # In assenza di 'level', IG rifiuta l'ordine LIMIT
        raise ValueError("For LIMIT orders, 'level' is required")

    # IG accetta o *distance* oppure *level* per TP/SL.
    # Se hai sia distance che level, IG di solito privilegia 'level'.
    kwargs = {
        "epic": epic,
        "expiry": expiry,
        "direction": direction,
        "size": size,
        "order_type": order_type,
        "level": level,  # None per MARKET
        "limit_distance": limit_distance,
        "limit_level": limit_level,
        "stop_distance": stop_distance,
        "stop_level": stop_level,
        "guaranteed_stop": guaranteed_stop,
        "time_in_force": None,               # opzionale
        "good_till_date": None,              # opzionale
        "trailing_stop": trailing_stop,
        "trailing_stop_increment": trailing_increment,
        "force_open": force_open,
        "currency_code": currency_code,
        "quote_id": quote_id,
    }

    # Pulisci None (alcune versioni dell'SDK gradiscono parametri assenti)
    clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        resp = ig.create_open_position(**clean_kwargs)
        # Normalizza risposta in dict serializzabile
        result = {
            "dealReference": getattr(resp, "body", {}).get("dealReference") if hasattr(resp, "body") else None,
            "status": getattr(resp, "status_code", None),
            "raw": getattr(resp, "body", None) if hasattr(resp, "body") else resp,
        }
        return result
    except IGException as e:
        # Errori noti IG
        return {"error": "IGException", "reason": str(e)}
    except Exception as e:
        return {"error": "Exception", "reason": str(e)}

# ======= Funzioni di utilità opzionali =======
def test_connection() -> Dict[str, Any]:
    """
    Verifica che le credenziali siano valide e restituisce qualche info conto.
    """
    ig = _ensure_ig()
    try:
        accs = ig.fetch_accounts()
        try:
            # trading_ig>=0.0.20: .body come dict
            body = accs.body if hasattr(accs, "body") else accs
        except Exception:
            body = accs
        return {"ok": True, "accounts": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def list_markets(search: str) -> Dict[str, Any]:
    """
    Ricerca mercati per stringa (utile per trovare l'EPIC).
    """
    ig = _ensure_ig()
    try:
        m = ig.search_markets(search)
        body = m.body if hasattr(m, "body") else m
        return {"ok": True, "results": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}
