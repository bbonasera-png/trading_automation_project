# =====================================
# ig_trading.py — versione finale 2025
# =====================================

from __future__ import annotations

import os
import time
import inspect
from typing import Any, Dict, Optional

from trading_ig import IGService  # pacchetto: trading-ig (requirements.txt)


# ========= ENV =========
IG_USERNAME = os.getenv("IG_USERNAME", "").strip()
IG_PASSWORD = os.getenv("IG_PASSWORD", "").strip()
IG_API_KEY  = os.getenv("IG_API_KEY", "").strip()
IG_ACC_TYPE = os.getenv("IG_ACC_TYPE", "DEMO").strip().upper()  # DEMO | LIVE

if IG_ACC_TYPE not in {"DEMO", "LIVE"}:
    IG_ACC_TYPE = "DEMO"

# ========= IGService singleton + TTL login =========
_IG: Optional[IGService] = None
_LAST_LOGIN_TS: float = 0.0
_LOGIN_TTL_SEC = 60 * 20  # rinnova sessione ogni 20 minuti


def _new_ig() -> IGService:
    """Crea una nuova sessione IG."""
    if not (IG_USERNAME and IG_PASSWORD and IG_API_KEY):
        raise RuntimeError(
            "Missing IG credentials: set IG_USERNAME, IG_PASSWORD, IG_API_KEY"
        )
    ig = IGService(
        username=IG_USERNAME,
        password=IG_PASSWORD,
        api_key=IG_API_KEY,
        acc_type=IG_ACC_TYPE,  # 'DEMO' o 'LIVE'
    )
    ig.create_session()
    return ig


def _ensure_ig() -> IGService:
    """Assicura che la sessione IG sia valida e viva."""
    global _IG, _LAST_LOGIN_TS
    now = time.time()
    if _IG is None:
        _IG = _new_ig()
        _LAST_LOGIN_TS = now
        return _IG
    if now - _LAST_LOGIN_TS > _LOGIN_TTL_SEC:
        try:
            _IG.fetch_accounts()  # ping leggero
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


# ========= API principale =========
def place_order(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Esegue un ordine su IG (apertura o chiusura) in modo dinamico,
    adattandosi alla versione installata di trading-ig.
    """
    ig = _ensure_ig()

    epic = _get(data, "epic")
    if not epic:
        raise ValueError("Missing 'epic'")

    direction = (_get(data, "direction", "BUY") or "BUY").upper()
    size = float(_get(data, "size", 1))
    order_type = (_get(data, "order_type", "MARKET") or "MARKET").upper()

    # parametri opzionali
    expiry = _get(data, "expiry", "-")
    force_open = _to_bool(_get(data, "force_open", True))
    guaranteed_stop = _to_bool(_get(data, "guaranteed_stop", False))
    level = _get(data, "level")
    limit_distance = _get(data, "limit_distance")
    limit_level = _get(data, "limit_level")
    quote_id = _get(data, "quote_id")
    stop_distance = _get(data, "stop_distance")
    stop_level = _get(data, "stop_level")
    trailing_stop = _to_bool(_get(data, "trailing_stop", False))
    trailing_inc = _get(data, "trailing_stop_increment")
    currency_code = _get(data, "currency_code", "EUR")
    time_in_force = _get(data, "time_in_force")
    good_till_date = _get(data, "good_till_date")

    # === Costruzione dinamica ===
    func = ig.create_open_position
    sig = inspect.signature(func)
    param_names = [p.name for p in sig.parameters.values()]

    # Mappa valori disponibili
    value_map = {
        "currency_code": currency_code,
        "direction": direction,
        "epic": epic,
        "expiry": expiry,
        "force_open": force_open,
        "guaranteed_stop": guaranteed_stop,
        "level": level,
        "limit_distance": limit_distance,
        "limit_level": limit_level,
        "order_type": order_type,
        "quote_id": quote_id,
        "size": size,
        "stop_distance": stop_distance,
        "stop_level": stop_level,
        "time_in_force": time_in_force,
        "good_till_date": good_till_date,
        "trailing_stop": trailing_stop,
        "trailing_stop_increment": trailing_inc,
    }

    # Costruisci la lista degli argomenti nel giusto ordine, solo quelli supportati
    args = [value_map.get(name, None) for name in param_names]

    # Controllo base
    if order_type == "LIMIT" and "level" in param_names and level is None:
        raise ValueError("For LIMIT orders, 'level' is required")

    try:
        resp = func(*args)
        body = getattr(resp, "body", None) if hasattr(resp, "body") else None
        return {
            "status": "success",
            "status_code": getattr(resp, "status_code", None),
            "dealReference": (body or {}).get("dealReference")
            if isinstance(body, dict)
            else None,
            "raw": body if body is not None else str(resp),
        }
    except Exception as e:
        return {"status": "error", "error": type(e).__name__, "reason": str(e)}


# ========= Utility =========
def test_connection() -> Dict[str, Any]:
    """
    Verifica credenziali e sessione IG.
    """
    ig = _ensure_ig()
    try:
        accs = ig.fetch_accounts()
        body = accs.body if hasattr(accs, "body") else accs
        return {"ok": True, "accounts": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_markets(search: str) -> Dict[str, Any]:
    """
    Ricerca mercati per stringa (utile per trovare l'EPIC).
    """
    ig = _ensure_ig()
    try:
        res = ig.search_markets(search)
        body = res.body if hasattr(res, "body") else res
        return {"ok": True, "results": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    print("🔹 Test connessione IG...")
    print(test_connection())
