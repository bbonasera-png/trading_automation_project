
# Trading Automation Project

Sistema completo per ricevere alert da TradingView e inviare ordini automatici a IG Markets tramite webhook.

## 📦 Struttura del progetto

```
trading_automation_project/
├── app.py                  # Web server Flask per ricevere alert
├── ig_trading.py           # Funzioni per interagire con IG
├── utils.py                # Funzioni di supporto
├── .env                    # Variabili d'ambiente
├── requirements.txt        # Dipendenze
└── README.md               # Istruzioni
```

## ⚙️ Setup locale

1. Clona il progetto
2. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```
3. Compila il file `.env` con le tue credenziali IG
4. Avvia il server:
   ```bash
   python app.py
   ```

## 🚀 Deploy su Render

1. Crea un nuovo servizio web su [Render](https://render.com)
2. Carica tutti i file del progetto
3. Imposta le variabili d'ambiente come da `.env`
4. Il server sarà disponibile per ricevere webhook da TradingView

## 📩 Esempio di alert da TradingView

Configura TradingView per inviare alert al tuo endpoint:

```
https://tuo-server-render.com/webhook
```

Esempio di payload:
```json
{
  "epic": "CS.D.EURUSD.MINI.IP",
  "direction": "BUY",
  "size": 1,
  "order_type": "MARKET"
}
```
