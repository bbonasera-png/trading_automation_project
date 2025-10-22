from trading_ig import IGService
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential
import os

load_dotenv()

USERNAME = os.getenv("IG_USERNAME")
PASSWORD = os.getenv("IG_PASSWORD")
API_KEY = os.getenv("IG_API_KEY")
ACC_TYPE = (os.getenv("IG_ACC_TYPE", "DEMO") or "DEMO").upper()  # "DEMO" | "LIVE"

_ig = None

def _get_ig():
    global _ig
    if _ig is None:
        _ig = IGService(USERNAME, PASSWORD, API_KEY, ACC_TYPE)
        _ig.create_session()
    return _ig

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def place_order(data: dict):
    ig = _get_ig()

    epic = data.get("epic")
    direction = (data.get("direction") or "BUY").upper()
    size = float(data.get("size") or 1)
    order_type = (data.get("order_type") or "MARKET").upper()

    currency_code = data.get("currency_code", "USD")
    expiry = data.get("expiry", "-")
    force_open = bool(data.get("force_open", True))
    level = data.get("level")
    limit_distance = data.get("limit_distance")
    limit_level = data.get("limit_level")
    quote_id = data.get("quote_id")
    stop_distance = data.get("stop_distance", 10.0)
    stop_level = data.get("stop_level")
    trailing_stop = data.get("trailing_stop", False)
    trailing_stop_increment = data.get("trailing_stop_increment")

    return ig.create_open_position(
        epic=epic,
        expiry=expiry,
        direction=direction,
        size=size,
        order_type=order_type,
        level=level,
        limit_distance=limit_distance,
        limit_level=limit_level,
        stop_distance=stop_distance,
        stop_level=stop_level,
        guaranteed_stop=False,
        trailing_stop=trailing_stop,
        trailing_stop_increment=trailing_stop_increment,
        force_open=force_open,
        currency_code=currency_code,
        quote_id=quote_id
    )
