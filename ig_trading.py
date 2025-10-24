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
    Apre/chiude ordini su IG e ritorna anche la deal confirmation (motivo REJECT/ACCEPT).
    Per CLOSE_LONG/CLOSE_SHORT inviare: {"action":"CLOSE_LONG"} o {"action":"CLOSE_SHORT"}.
    """
    ig = _ensure_ig()

    action = (_get(data, "action", "OPEN") or "OPEN").upper()

    # --- CLOSE handling (usa positions + close_working_order/close_position) ---
    if action in {"CLOSE_LONG", "CLOSE_SHORT"}:
        # chiusura semplificata: se hai una sola posizione su quell'epic, la chiude in senso opposto
        epic = _get(data, "epic")
        size = float(_get(data, "size", 1))
        if not epic:
            raise ValueError("Per CLOSE_* fornisci almeno 'epic'")

        try:
            # recupera posizioni aperte
            pos = ig.fetch_open_positions()
            body = pos.body if hasattr(pos, "body") else pos
            positions = []
            if isinstance(body, dict) and "positions" in body:
                positions = body["positions"]

            # trova posizione sull'EPIC richiesto
            pos_on_epic = None
            for p in positions:
                instr = p.get("market", {})
                deal = p.get("position", {})
                if instr.get("epic") == epic:
                    pos_on_epic = deal
                    break

            if not pos_on_epic:
                return {"status": "error", "reason": f"no open position on epic {epic}"}

            # direzione opposta per chiusura
            current_dir = pos_on_epic.get("direction")
            close_dir = "SELL" if current_dir == "BUY" else "BUY"

            # chiude a MARKET
            resp = ig.close_open_position(
                deal_id=pos_on_epic.get("dealId"),
                direction=close_dir,
                epic=epic,
                size=size,
                order_type="MARKET",
                level=None,
                time_in_force=None,
                limit_level=None,
                stop_level=None
            )

            # conferma
            body = resp.body if hasattr(resp, "body") else resp
            deal_ref = body.get("dealReference") if isinstance(body, dict) else None
            confirm_body = None
            if deal_ref:
                try:
                    confirm = ig.fetch_deal_by_deal_reference(deal_ref)
                    confirm_body = confirm.body if hasattr(confirm, "body") else confirm
                except Exception:
                    confirm_body = None

            return {
                "status": "success",
                "raw": body,
                "dealReference": deal_ref,
                "confirm": confirm_body,
            }
        except Exception as e:
            return {"status": "error", "error": e.__class__.__name__, "reason": str(e)}

    # --- OPEN handling ---
    epic       = _get(data, "epic")
    if not epic:
        raise ValueError("Missing 'epic'")

    direction  = (_get(data, "direction") or "").upper()   # BUY/SELL
    size       = float(_get(data, "size", 1))
    order_type = (_get(data, "order_type", "MARKET") or "MARKET").upper()

    # opzionali
    level              = _get(data, "level")
    limit_distance     = _get(data, "limit_distance")
    limit_level        = _get(data, "limit_level")
    stop_distance      = _get(data, "stop_distance")
    stop_level         = _get(data, "stop_level")
    guaranteed_stop    = _to_bool(_get(data, "guaranteed_stop", False))
    trailing_stop      = _to_bool(_get(data, "trailing_stop", False))
    trailing_increment = _get(data, "trailing_stop_increment")
    force_open         = _to_bool(_get(data, "force_open", True))
    currency_code      = _get(data, "currency_code", "EUR")
    expiry             = _get(data, "expiry", "-")
    quote_id           = _get(data, "quote_id")
    time_in_force      = _get(data, "time_in_force")
    good_till_date     = _get(data, "good_till_date")

    if order_type not in {"MARKET", "LIMIT"}:
        raise ValueError("order_type must be 'MARKET' or 'LIMIT'")
    if order_type == "LIMIT" and level is None:
        raise ValueError("For LIMIT orders, 'level' is required")

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
        "time_in_force": time_in_force,
        "good_till_date": good_till_date,
        "trailing_stop": trailing_stop,
        "trailing_stop_increment": trailing_increment,
        "force_open": force_open,
        "currency_code": currency_code,
        "quote_id": quote_id,
    }
    clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}

    try:
        resp = ig.create_open_position(**clean_kwargs)
        body = resp.body if hasattr(resp, "body") else resp
        deal_ref = body.get("dealReference") if isinstance(body, dict) else None

        # prova a leggere la conferma — qui esce il REJECT reason “vero”
        confirm_body = None
        if deal_ref:
            try:
                confirm = ig.fetch_deal_by_deal_reference(deal_ref)
                confirm_body = confirm.body if hasattr(confirm, "body") else confirm
            except Exception:
                confirm_body = None

        return {
            "status": "success",
            "status_code": getattr(resp, "status_code", None),
            "dealReference": deal_ref,
            "raw": body,
            "confirm": confirm_body,
        }
    except Exception as e:
        return {"status": "error", "error": e.__class__.__name__, "reason": str(e)}

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
