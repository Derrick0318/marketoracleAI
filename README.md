# Market Oracle AI

A local web-based research dashboard for US stocks, Malaysia stocks, and Bitcoin.

## What It Does

- Fetches fresh daily market data with `yfinance`.
- Trains a per-symbol AI ensemble using gradient boosting and random forest models.
- Predicts the next regular-session closing price after the latest downloaded candle.
- Shows current price, predicted close, predicted up/down direction, confidence, validation accuracy, buy zone, sell target, and stop level.
- Adds a lightweight Yahoo Finance headline sentiment overlay.
- Shows a live selected-symbol quote panel that polls every 30 seconds.

## Update Schedule

- Live price: refreshes every 30 seconds in the browser.
- AI prediction: retrains every 10 minutes per symbol, or immediately when you press Refresh.
- Prediction target: the next regular-session closing price after the latest downloaded daily candle.

## Run

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Notes

This is an educational research system, not personalized financial advice. Markets can move for reasons the model cannot see, including earnings, macro news, liquidity shocks, filings, and geopolitical events.
