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
- AI ranking tabs: use the newest stored scan snapshot when available, then retrain only when you press Refresh or when a scheduled collector runs.
- Scheduled collector: Bursa Malaysia stocks and Malaysia ETFs at 9:05 AM and 5:10 PM MYT on weekdays.
- Scheduled collector: US stocks at 9:35 AM and 4:10 PM New York time on weekdays.
- Scheduled collector: US ETFs at 9:45 AM and 4:20 PM New York time on weekdays.
- Scheduled collector: Bitcoin at 12:00 AM MYT daily.
- Prediction target: the next regular-session closing price after the latest downloaded daily candle.

## Environment Variables

Set these in `.env.local` for local development and in Vercel Project Settings for deployment:

- `ADMIN_USERNAME`: admin panel username.
- `ADMIN_PASSWORD`: admin panel password.
- `FLASK_SECRET_KEY`: a long random value for admin login sessions.
- `SUPABASE_URL`: Supabase project URL, when using Supabase.
- `SUPABASE_SERVICE_ROLE_KEY` or `SUPABASE_SECRET_KEY`: Supabase secret/service role key, server-side only.
- `CRON_SECRET`: optional secret for the scheduled Vercel update endpoint.

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
