# ig_trading.py
from __future__ import annotations

import os
import time
import inspect
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
    """Tenta la conferma tramite dealReference (se presente)."""
    if not deal_ref:
        return {"ok": False, "error": "NoDealRef"}
    try:
        conf = ig.fetch_deal_by_deal_reference(deal_ref)
        body = conf.body if hasattr(conf, "body") else conf
        return {"ok": True, "confirm": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ========= API principale =========
def place_order(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Esegue OPEN / CLOSE_LONG / CLOSE_SHORT.
    Costruisce gli argomenti in base alla *firma reale* della tua versione di trading-ig,
    evitando mismatch “17/18/19 args”.
    """
    ig = _ensure_ig()

    action     = (_get(data, "action", "OPEN") or "OPEN").upper()
    epic       = _get(data, "epic")
    if not epic:
        return {"status": "error", "reason": "Missing 'epic'"}

    direction  = _get(data, "direction")
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
    expiry             = _get(data, "expiry", "-")

    # Normalizzazione CLOSE_* -> ordine opposto + force_open=False
    if action in {"CLOSE_LONG", "CLOSE_SHORT"}:
        direction = "SELL" if action == "CLOSE_LONG" else "BUY"
        force_open = False
        if order_type == "LIMIT" and level is None:
            return {"status": "error", "reason": "For CLOSE with LIMIT, 'level' is required"}
    else:
        if not direction:
            return {"status": "error", "reason": "Missing 'direction' for OPEN"}
        direction = direction.upper()
        force_open = _to_bool(_get(data, "force_open", True))
        if order_type == "LIMIT" and level is None:
            return {"status": "error", "reason": "For LIMIT orders, 'level' is required"}

    # Dizionario “sorgente” con i nomi *nostri* normalizzati
    avail = {
        "epic": epic,
        "expiry": expiry,
        "direction": direction,
        "size": size,
        "level": level,
        "order_type": order_type,
        "time_in_force": time_in_force,
        "limit_distance": limit_distance,
        "limit_level": limit_level,
        "stop_distance": stop_distance,
        "stop_level": stop_level,
        "guaranteed_stop": bool(guaranteed_stop),
        "trailing_stop": bool(trailing_stop),
        "trailing_stop_increment": trailing_increment,
        "force_open": bool(force_open),
        "currency_code": currency_code,
        "good_till_date": good_till_date,
        "quote_id": quote_id,
    }

    # Possibili alias dei nomi param nelle varie versioni del client
    name_map = {
        "deal_direction": "direction",
        "dealOrderType": "order_type",
        "deal_order_type": "order_type",
    }

    # ===== Costruzione argomenti in base alla firma reale =====
    sig = inspect.signature(IGService.create_open_position)
    params = [p for p in list(sig.parameters.values())[1:]]  # skip 'self'

    # Parametri posizionali nell’ordine esatto della firma
    args_pos = []
    for p in params:
        pname = p.name
        src_key = name_map.get(pname, pname)  # mappa eventuali alias
        args_pos.append(avail.get(src_key, None))

    # Prova posizionale
    try:
        ig_resp = ig.create_open_position(*args_pos)
    except Exception as e:
        # Fallback: keyword strettamente filtrate ai soli nomi presenti nella firma
        try:
            allowed = []
            for p in params:
                pname = p.name
                src_key = name_map.get(pname, pname)
                if src_key in avail and avail[src_key] is not None:
                    allowed.append((pname, avail[src_key]))
            ig_resp = ig.create_open_position(**dict(allowed))
        except Exception as e2:
            return {
                "status": "error",
                "error": "CreateOpenPositionFailed",
                "reason": f"{e} || {e2}",
            }

    # ----- Conferma tramite dealReference -----
    body = ig_resp.body if hasattr(ig_resp, "body") else ig_resp
    status_code = getattr(ig_resp, "status_code", None)
    deal_ref = None
    if isinstance(body, dict):
        deal_ref = body.get("dealReference") or body.get("deal_reference")

    confirm = _confirm_by_ref(ig, deal_ref)

    out = {
        "status": "success",
        "status_code": status_code,
        "dealReference": deal_ref,
        "raw": body,
    }
    if confirm.get("ok"):
        out["confirm"] = confirm["confirm"]
    else:
        out["confirm"] = {"error": confirm.get("error")}
    return out


# ========= Utility =========
def test_connection() -> Dict[str, Any]:
    """Verifica credenziali e sessione IG."""
    ig = _ensure_ig()
    try:
        accs = ig.fetch_accounts()
        body = accs.body if hasattr(accs, "body") else accs
        return {"ok": True, "accounts": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_markets(search: str) -> Dict[str, Any]:
    """Ricerca mercati per stringa (utile per trovare l'EPIC)."""
    ig = _ensure_ig()
    try:
        res = ig.search_markets(search)
        body = res.body if hasattr(res, "body") else res
        return {"ok": True, "results": body}
    except Exception as e:
        return {"ok": False, "error": str(e)}