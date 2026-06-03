from __future__ import annotations

import concurrent.futures as futures
import time
from copy import deepcopy
from datetime import datetime
from typing import Any

from src.config.settings import CACHE_TTL_SECONDS, FAST_MODEL_PERIOD, MAX_SCAN_WORKERS, MODEL_PERIOD, SNAPSHOT_SCAN_TTL_SECONDS
from src.features.alerts import record_prediction_alert
from src.features.news import get_empty_symbol_news, get_symbol_news
from src.features.prediction.feature_engineering import build_feature_frame
from src.features.prediction.formatter import build_prediction_result, compact_result
from src.features.prediction.model_trainer import train_and_predict
from src.services.market_data_service import fetch_bulk_market_histories, fetch_market_history
from src.services.state_store_service import list_daily_snapshots
from src.utils.symbol_utils import clean_symbol, get_symbol_meta, get_universe

PREDICTION_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
SCAN_CACHE: dict[tuple[str, int, str], tuple[float, dict[str, Any]]] = {}


def analyze_symbol(
    symbol: str,
    refresh: bool = False,
    include_news: bool = True,
    record_alert: bool = True,
    market_response: dict[str, Any] | None = None,
    fast_model: bool = False,
) -> dict[str, Any]:
    clean = clean_symbol(symbol)
    profile = "fast" if fast_model else "full"
    cached = PREDICTION_CACHE.get((clean, profile))
    if cached and not refresh and (time.time() - cached[0] < CACHE_TTL_SECONDS):
        result = deepcopy(cached[1])
        if include_news and not result.get("news_loaded"):
            result = attach_symbol_news(clean, result, profile)
        if record_alert and not result.get("alert"):
            result["alert"] = record_prediction_alert(result)
            PREDICTION_CACHE[(clean, profile)] = (time.time(), deepcopy(result))
        return result

    meta = get_symbol_meta(clean)
    market_response = market_response or fetch_market_history(clean)
    if market_response.get("error"):
        fallback_response = fetch_market_history(clean)
        if fallback_response.get("error"):
            raise ValueError(market_response["error"])
        market_response = fallback_response

    market_data = market_response["data"]
    history = market_data["history"]
    fast_info = market_data["fast_info"]
    features, target_return, atr_series = build_feature_frame(history)
    model_output = train_and_predict(features, target_return, fast=fast_model)
    news_payload = get_symbol_news(clean, limit=12) if include_news else get_empty_symbol_news(clean)

    result = build_prediction_result(
        symbol=clean,
        meta=meta,
        history=history,
        fast_info=fast_info,
        features=features,
        atr_series=atr_series,
        model_output=model_output,
        news_payload=news_payload,
    )
    result["news_loaded"] = include_news
    result["alert"] = record_prediction_alert(result) if record_alert else None
    PREDICTION_CACHE[(clean, profile)] = (time.time(), deepcopy(result))
    return result


def attach_symbol_news(symbol: str, result: dict[str, Any], profile: str) -> dict[str, Any]:
    result = deepcopy(result)
    result["news"] = get_symbol_news(symbol, limit=12)
    result["sentiment"] = result["news"]["sentiment"]
    result["news_loaded"] = True
    PREDICTION_CACHE[(symbol, profile)] = (time.time(), deepcopy(result))
    return result


def scan_symbols(
    market: str,
    limit: int,
    refresh: bool = False,
    include_news: bool = False,
    record_alerts: bool = True,
    fast_model: bool = True,
) -> dict[str, Any]:
    profile = "fast" if fast_model else "full"
    cache_key = (market.lower(), limit, profile)
    cached_scan = SCAN_CACHE.get(cache_key)
    if cached_scan and not refresh and (time.time() - cached_scan[0] < CACHE_TTL_SECONDS):
        payload = deepcopy(cached_scan[1])
        payload["cached"] = True
        return payload
    if not refresh:
        snapshot_scan = get_recent_snapshot_scan(market=market, limit=limit, profile=profile)
        if snapshot_scan:
            return snapshot_scan

    symbols = [item["symbol"] for item in get_universe(market)][:limit]
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    history_period = FAST_MODEL_PERIOD if fast_model else MODEL_PERIOD
    bulk_market_data = fetch_bulk_market_histories(symbols, period=history_period)

    with futures.ThreadPoolExecutor(max_workers=min(MAX_SCAN_WORKERS, max(1, len(symbols)))) as executor:
        future_map = {
            executor.submit(
                analyze_symbol,
                symbol,
                refresh,
                include_news,
                record_alerts,
                bulk_market_data.get(symbol),
                fast_model,
            ): symbol
            for symbol in symbols
        }
        for future in futures.as_completed(future_map):
            symbol = future_map[future]
            try:
                results.append(compact_result(future.result()))
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})

    results.sort(key=lambda item: item.get("score") or -999, reverse=True)
    payload = {
        "market": market,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cached": False,
        "results": results,
        "errors": errors,
    }
    SCAN_CACHE[cache_key] = (time.time(), deepcopy(payload))
    return payload


def get_recent_snapshot_scan(market: str, limit: int, profile: str) -> dict[str, Any] | None:
    snapshots_response = list_daily_snapshots(limit=24)
    if snapshots_response.get("error"):
        return None

    normalized_market = market.lower()
    allowed_symbols = {item["symbol"].upper() for item in get_universe(normalized_market)}
    merged_results: list[dict[str, Any]] = []
    merged_errors: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()

    for snapshot in snapshots_response.get("data", []):
        payload = snapshot.get("payload") or {}
        scan = payload.get("scan") or {}
        generated_at = scan.get("generated_at") or payload.get("finished_at") or snapshot.get("created_at")
        if not scan or not is_recent_snapshot(generated_at):
            continue

        selected_scan = select_snapshot_scan(scan, normalized_market, allowed_symbols)
        if not selected_scan:
            continue
        if snapshot_missing_forecast_fields(selected_scan):
            continue

        for item in selected_scan.get("results", []):
            symbol = str(item.get("symbol") or "").upper()
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)
            merged_results.append(item)

        for error in selected_scan.get("errors", []):
            symbol = str(error.get("symbol") or "").upper()
            if normalized_market == "all" or symbol in allowed_symbols:
                merged_errors.append(error)

        if normalized_market not in {"all", "etf"}:
            break

    expected_results = min(limit, len(allowed_symbols))
    if len(merged_results) < expected_results:
        return None

    merged_results.sort(key=lambda item: item.get("score") or -999, reverse=True)
    payload = {
        "market": market,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "snapshot_generated_at": generated_at,
        "cached": True,
        "snapshot": True,
        "results": merged_results[:limit],
        "errors": merged_errors,
    }
    SCAN_CACHE[(market.lower(), limit, profile)] = (time.time(), deepcopy(payload))
    return payload


def snapshot_missing_forecast_fields(scan: dict[str, Any]) -> bool:
    results = scan.get("results") or []
    if not results:
        return True
    return any(
        item.get("forecast_window") is None
        or item.get("direction_probability_up_pct") is None
        or item.get("direction_probability_down_pct") is None
        for item in results
    )


def select_snapshot_scan(scan: dict[str, Any], market: str, allowed_symbols: set[str]) -> dict[str, Any] | None:
    market_scans = scan.get("market_scans") or {}
    if market in market_scans:
        return market_scans[market]

    results = scan.get("results") or []
    errors = scan.get("errors") or []
    if market != "all":
        results = [item for item in results if str(item.get("symbol") or "").upper() in allowed_symbols]
        errors = [item for item in errors if str(item.get("symbol") or "").upper() in allowed_symbols]

    if not results:
        return None
    return {"results": results, "errors": errors}


def is_recent_snapshot(value: Any) -> bool:
    parsed = parse_snapshot_datetime(value)
    if not parsed:
        return False
    return (datetime.now() - parsed).total_seconds() <= SNAPSHOT_SCAN_TTL_SECONDS


def parse_snapshot_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed
    except Exception:
        return None
