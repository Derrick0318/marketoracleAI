from __future__ import annotations

from typing import Any

import pandas as pd
import yfinance as yf

from src.config.settings import MODEL_PERIOD
from src.utils.error_handler import parse_error
from src.utils.number_utils import finite_float


def get_fast_info(ticker: yf.Ticker) -> dict[str, Any]:
    wanted = [
        "currency",
        "last_price",
        "regular_market_price",
        "previous_close",
        "open",
        "day_high",
        "day_low",
        "market_cap",
        "ten_day_average_volume",
        "year_high",
        "year_low",
    ]
    data: dict[str, Any] = {}
    try:
        fast = ticker.fast_info
        for key in wanted:
            try:
                data[key] = fast.get(key)
            except Exception:
                data[key] = getattr(fast, key, None)
    except Exception:
        return data
    return data


def fetch_market_history(symbol: str, period: str = MODEL_PERIOD) -> dict[str, Any]:
    try:
        ticker = yf.Ticker(symbol)
        history = ticker.history(
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=False,
            raise_errors=False,
        )
        if history.empty:
            raise ValueError(f"No market history returned for {symbol}")

        history = history.rename(columns=lambda col: str(col).strip().lower().replace(" ", "_"))
        if "close" not in history:
            raise ValueError(f"No closing-price data returned for {symbol}")

        history["model_close"] = history.get("adj_close", history["close"]).fillna(history["close"])
        for column in ["open", "high", "low", "close", "model_close", "volume"]:
            if column not in history:
                history[column] = history["model_close"] if column != "volume" else 0
            history[column] = pd.to_numeric(history[column], errors="coerce")

        history = history.dropna(subset=["model_close"])
        if len(history) < 160:
            raise ValueError(f"Not enough daily history for {symbol}; need at least 160 rows")

        return {"data": {"ticker": ticker, "history": history, "fast_info": get_fast_info(ticker)}}
    except Exception as exc:
        return {"error": parse_error(exc)}


def get_current_price(fast_info: dict[str, Any], latest_close: float) -> float:
    fast_price = (
        fast_info.get("last_price")
        or fast_info.get("regular_market_price")
        or fast_info.get("previous_close")
        or latest_close
    )
    return float(fast_price) if finite_float(fast_price) is not None else latest_close


def fetch_live_quote(symbol: str) -> dict[str, Any]:
    try:
        ticker = yf.Ticker(symbol)
        fast_info = get_fast_info(ticker)
        fallback = ticker.history(period="1mo", interval="1d", raise_errors=False)
        latest_close = float(fallback["Close"].dropna().iloc[-1]) if not fallback.empty else 0
        price = get_current_price(fast_info, latest_close)
        previous_close = fast_info.get("previous_close")
        if finite_float(previous_close) is None and len(fallback) >= 2:
            previous_close = float(fallback["Close"].dropna().iloc[-2])

        previous_close = float(previous_close) if finite_float(previous_close) is not None else None
        change = price - previous_close if previous_close else None
        change_pct = (change / previous_close) * 100 if previous_close and change is not None else None

        return {
            "data": {
                "symbol": symbol,
                "price": finite_float(price, 4),
                "previous_close": finite_float(previous_close, 4),
                "change": finite_float(change, 4),
                "change_pct": finite_float(change_pct, 2),
                "open": finite_float(fast_info.get("open"), 4),
                "day_high": finite_float(fast_info.get("day_high"), 4),
                "day_low": finite_float(fast_info.get("day_low"), 4),
                "currency": fast_info.get("currency"),
                "source": "Yahoo Finance via yfinance",
            }
        }
    except Exception as exc:
        return {"error": parse_error(exc)}
