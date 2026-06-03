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


def normalize_market_history(history: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if history.empty:
        raise ValueError(f"No market history returned for {symbol}")

    normalized = history.rename(columns=lambda col: str(col).strip().lower().replace(" ", "_"))
    if "close" not in normalized:
        raise ValueError(f"No closing-price data returned for {symbol}")

    normalized["model_close"] = normalized.get("adj_close", normalized["close"]).fillna(normalized["close"])
    for column in ["open", "high", "low", "close", "model_close", "volume"]:
        if column not in normalized:
            normalized[column] = normalized["model_close"] if column != "volume" else 0
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.dropna(subset=["model_close"])
    if len(normalized) < 160:
        raise ValueError(f"Not enough daily history for {symbol}; need at least 160 rows")
    return normalized


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
        history = normalize_market_history(history, symbol)
        return {"data": {"ticker": ticker, "history": history, "fast_info": get_fast_info(ticker)}}
    except Exception as exc:
        return {"error": parse_error(exc)}


def fetch_bulk_market_histories(symbols: list[str], period: str = MODEL_PERIOD) -> dict[str, dict[str, Any]]:
    if not symbols:
        return {}

    try:
        raw = yf.download(
            tickers=" ".join(symbols),
            period=period,
            interval="1d",
            auto_adjust=False,
            actions=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as exc:
        error = parse_error(exc)
        return {symbol: {"error": error} for symbol in symbols}

    responses: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        try:
            history = extract_bulk_history(raw, symbol, len(symbols))
            history = normalize_market_history(history, symbol)
            responses[symbol] = {"data": {"ticker": None, "history": history, "fast_info": {}}}
        except Exception as exc:
            responses[symbol] = {"error": parse_error(exc)}
    return responses


def extract_bulk_history(raw: pd.DataFrame, symbol: str, symbol_count: int) -> pd.DataFrame:
    if symbol_count == 1 or not isinstance(raw.columns, pd.MultiIndex):
        return raw.copy()

    if symbol in raw.columns.get_level_values(0):
        return raw[symbol].copy()

    try:
        return raw.xs(symbol, axis=1, level=1).copy()
    except Exception:
        return pd.DataFrame()


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
        latest_row = fallback.tail(1).iloc[0] if not fallback.empty else None
        latest_history_date = fallback.index[-1].date().isoformat() if not fallback.empty else None
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
                "latest_history_date": latest_history_date,
                "latest_history_open": finite_float(latest_row.get("Open") if latest_row is not None else None, 4),
                "latest_history_close": finite_float(latest_close, 4),
                "day_high": finite_float(fast_info.get("day_high"), 4),
                "day_low": finite_float(fast_info.get("day_low"), 4),
                "currency": fast_info.get("currency"),
                "source": "Yahoo Finance via yfinance",
            }
        }
    except Exception as exc:
        return {"error": parse_error(exc)}
