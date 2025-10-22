#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-https://your-service.onrender.com}"
SECRET_HEADER="${SECRET_HEADER:-changeme}"
curl -sS -X POST "$BASE_URL/webhook"   -H "Content-Type: application/json"   -H "X-Webhook-Secret: $SECRET_HEADER"   -d '{
    "epic": "CS.D.EURUSD.MINI.IP",
    "direction": "BUY",
    "size": 1,
    "order_type": "MARKET",
    "alert_id": "test-'"$(date +%s)"'",
    "ts": '"$(date +%s)"'
  }' | jq .
