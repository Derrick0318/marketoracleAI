from __future__ import annotations

import concurrent.futures as futures
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.features.market_status import get_market_status
from src.services.market_data_service import fetch_live_quote
from src.services.state_store_service import append_market_price_events, list_market_price_events
from src.utils.number_utils import finite_float
from src.utils.symbol_utils import clean_symbol, get_symbol_meta, get_universe

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
US_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")
MAX_PRICE_EVENT_WORKERS = 8


def record_market_price_events(scan_payload: dict[str, Any], reason: str) -> dict[str, Any]:
    symbols = unique_scan_symbols(scan_payload)
    if not symbols:
        return {"stored_count": 0, "records": [], "errors": []}

    event_mode = infer_event_mode(reason)
    return record_price_events_for_symbols(symbols=symbols, reason=reason, event_mode=event_mode)


def record_today_market_price_events(markets: list[str] | None = None, reason: str = "manual_today_price_catchup") -> dict[str, Any]:
    symbols = unique_market_symbols(markets or ["all"])
    return record_price_events_for_symbols(symbols=symbols, reason=reason, event_mode="seed_today")


def record_price_events_for_symbols(symbols: list[str], reason: str, event_mode: str) -> dict[str, Any]:
    if not symbols:
        return {"stored_count": 0, "event_mode": event_mode, "records": [], "errors": []}

    records: list[dict[str, Any]] = []
    errors: list[str] = []

    with futures.ThreadPoolExecutor(max_workers=min(MAX_PRICE_EVENT_WORKERS, len(symbols))) as executor:
        future_map = {executor.submit(build_records_for_symbol, symbol, reason, event_mode): symbol for symbol in symbols}
        for future in futures.as_completed(future_map):
            symbol = future_map[future]
            try:
                symbol_records = future.result()
                if symbol_records:
                    records.extend(symbol_records)
            except Exception as exc:
                errors.append(f"{symbol}: {exc}")

    response = append_market_price_events(records)
    if response.get("error"):
        errors.append(response["error"])
    return {
        "stored_count": len(response.get("data") or records),
        "event_mode": event_mode,
        "records": records[:40],
        "errors": errors[:20],
    }


def unique_market_symbols(markets: list[str]) -> list[str]:
    seen: set[str] = set()
    symbols: list[str] = []
    for market in markets:
        for item in get_universe(market):
            symbol = clean_symbol(str(item.get("symbol") or ""))
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            symbols.append(symbol)
    return symbols


def unique_scan_symbols(scan_payload: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    symbols: list[str] = []
    for result in scan_payload.get("results", []):
        symbol = clean_symbol(str(result.get("symbol") or ""))
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def infer_event_mode(reason: str) -> str:
    text = reason.lower()
    if "open" in text:
        return "open"
    if "close" in text:
        return "close"
    if "bitcoin" in text or "crypto" in text:
        return "crypto_daily"
    if "reset" in text:
        return "seed_today"
    return "snapshot"


def build_records_for_symbol(symbol: str, reason: str, event_mode: str) -> list[dict[str, Any]]:
    quote_response = fetch_live_quote(symbol)
    if quote_response.get("error"):
        raise RuntimeError(quote_response["error"])
    quote = quote_response.get("data") or {}
    meta = get_symbol_meta(symbol)

    if event_mode == "seed_today":
        return build_seed_records(symbol, meta, quote, reason)

    return [build_price_event_record(symbol, meta, quote, reason, event_mode)]


def build_seed_records(symbol: str, meta: dict[str, str], quote: dict[str, Any], reason: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    exchange_tz = exchange_timezone(symbol, meta)
    exchange_today = datetime.now(exchange_tz).date().isoformat()
    latest_history_date = str(quote.get("latest_history_date") or "")
    has_today_history = latest_history_date == exchange_today

    if numeric(quote.get("open")) is not None or (has_today_history and numeric(quote.get("latest_history_open")) is not None):
        records.append(build_price_event_record(symbol, meta, quote, reason, "open"))

    if meta.get("market") == "Crypto":
        records.append(build_price_event_record(symbol, meta, quote, reason, "crypto_daily"))
        return records

    status = get_market_status(symbol)
    if not status.get("is_open") and has_today_history and numeric(quote.get("latest_history_close")) is not None:
        records.append(build_price_event_record(symbol, meta, quote, reason, "close"))

    return records


def build_price_event_record(
    symbol: str,
    meta: dict[str, str],
    quote: dict[str, Any],
    reason: str,
    event_type: str,
) -> dict[str, Any]:
    captured_at = datetime.now(MY_TZ).isoformat(timespec="seconds")
    exchange_tz = exchange_timezone(symbol, meta)
    trading_date = trading_date_for_event(event_type, quote, exchange_tz)
    open_price = numeric(quote.get("open")) or numeric(quote.get("latest_history_open"))
    latest_price = numeric(quote.get("price"))
    latest_history_close = numeric(quote.get("latest_history_close"))
    close_price = latest_history_close if event_type in {"close", "crypto_daily"} else None
    event_price = choose_event_price(event_type, open_price, close_price, latest_price)

    return {
        "unique_key": f"{symbol}:{trading_date}:{event_type}",
        "captured_at": captured_at,
        "trading_date": trading_date,
        "event_type": event_type,
        "event_reason": reason,
        "symbol": symbol,
        "name": meta.get("name", symbol),
        "market": meta.get("market"),
        "price": finite_float(event_price, 4),
        "open_price": finite_float(open_price, 4),
        "close_price": finite_float(close_price, 4),
        "latest_price": finite_float(latest_price, 4),
        "previous_close": finite_float(quote.get("previous_close"), 4),
        "day_high": finite_float(quote.get("day_high"), 4),
        "day_low": finite_float(quote.get("day_low"), 4),
        "currency": quote.get("currency"),
        "source": quote.get("source", "Yahoo Finance via yfinance"),
        "exchange_timezone": str(exchange_tz),
        "metadata": {
            "latest_history_date": quote.get("latest_history_date"),
            "latest_history_open": quote.get("latest_history_open"),
            "latest_history_close": quote.get("latest_history_close"),
        },
    }


def choose_event_price(event_type: str, open_price: float | None, close_price: float | None, latest_price: float | None) -> float | None:
    if event_type == "open":
        return open_price or latest_price
    if event_type in {"close", "crypto_daily"}:
        return close_price or latest_price
    return latest_price or close_price or open_price


def trading_date_for_event(event_type: str, quote: dict[str, Any], exchange_tz: ZoneInfo) -> str:
    if event_type in {"close", "crypto_daily"} and quote.get("latest_history_date"):
        return str(quote["latest_history_date"])
    return datetime.now(exchange_tz).date().isoformat()


def exchange_timezone(symbol: str, meta: dict[str, str]) -> ZoneInfo:
    market = str(meta.get("market") or "")
    if symbol.endswith(".KL") or "Malaysia" in market:
        return MY_TZ
    if market == "Crypto":
        return UTC_TZ
    return US_TZ


def build_market_price_event_report(days: int = 2, limit: int = 120) -> dict[str, Any]:
    response = list_market_price_events(days=days, limit=limit)
    if response.get("error"):
        return empty_event_report(days, response["error"])

    events = response.get("data") or []
    open_events = [event for event in events if event.get("event_type") == "open"]
    close_events = [event for event in events if event.get("event_type") == "close"]
    crypto_events = [event for event in events if event.get("event_type") == "crypto_daily"]
    latest_event = events[0] if events else None
    today = datetime.now(MY_TZ).date().isoformat()
    today_events = [event for event in events if event.get("trading_date") == today]
    return {
        "days": days,
        "generated_at": datetime.now(MY_TZ).isoformat(timespec="seconds"),
        "event_count": len(events),
        "today_count": len(today_events),
        "open_count": len(open_events),
        "close_count": len(close_events),
        "crypto_count": len(crypto_events),
        "latest_event": latest_event,
        "events": events[:limit],
        "error": None,
    }


def empty_event_report(days: int, error: str | None = None) -> dict[str, Any]:
    return {
        "days": days,
        "generated_at": datetime.now(MY_TZ).isoformat(timespec="seconds"),
        "event_count": 0,
        "today_count": 0,
        "open_count": 0,
        "close_count": 0,
        "crypto_count": 0,
        "latest_event": None,
        "events": [],
        "error": error,
    }


def numeric(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed
