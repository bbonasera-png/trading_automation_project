biagiobonasera@MacBook-Pro-di-Biagio trading_automation_project % curl -sS -X POST https://ig-tv-wbhook.onrender.com/webhook \
  -H 'Content-Type: application/json' \
  -H 'X-Webhook-Secret: tv_ig_2025_secret!' \
  -d '{
    "action":"OPEN",
    "epic":"CS.D.GBPCHF.CFD.IP",
    "direction":"BUY",
    "size":1,
    "order_type":"MARKET",
    "currency_code":"EUR"
  }' | jq
{
  "response": {
    "confirm": {
      "affectedDeals": [],
      "date": "2025-10-27T08:06:30.188",
      "dealId": "DIAAAAVGZED9SAK",
      "dealReference": "TBH4TM4YJKAT28R",
      "dealStatus": "REJECTED",
      "direction": "BUY",
      "epic": "CS.D.GBPCHF.CFD.IP",
      "expiry": null,
      "guaranteedStop": false,
      "level": null,
      "limitDistance": null,
      "limitLevel": null,
      "profit": null,
      "profitCurrency": null,
      "reason": "UNKNOWN",
      "size": null,
      "status": null,
      "stopDistance": null,
      "stopLevel": null,
      "trailingStop": false
    },
    "dealReference": "TBH4TM4YJKAT28R",
    "raw": {
      "affectedDeals": [],
      "date": "2025-10-27T08:06:30.188",
      "dealId": "DIAAAAVGZED9SAK",
      "dealReference": "TBH4TM4YJKAT28R",
      "dealStatus": "REJECTED",
      "direction": "BUY",
      "epic": "CS.D.GBPCHF.CFD.IP",
      "expiry": null,
      "guaranteedStop": false,
      "level": null,
      "limitDistance": null,
      "limitLevel": null,
      "profit": null,
      "profitCurrency": null,
      "reason": "UNKNOWN",
      "size": null,
      "status": null,
      "stopDistance": null,
      "stopLevel": null,
      "trailingStop": false
    },
    "status": "success",
    "status_code": null
  },
  "status": "success"
}
biagiobonasera@MacBook-Pro-di-Biagio trading_automation_project % 