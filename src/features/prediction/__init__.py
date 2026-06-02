from __future__ import annotations

import concurrent.futures as futures
import time
from copy import deepcopy
from datetime import datetime
from typing import Any

from src.config.settings import CACHE_TTL_SECONDS, MAX_SCAN_WORKERS
from src.features.alerts import record_prediction_alert
from src.features.news import get_symbol_news
from src.features.prediction.feature_engineering import build_feature_frame
from src.features.prediction.formatter import build_prediction_result, compact_result
from src.features.prediction.model_trainer import train_and_predict
from src.services.market_data_service import fetch_market_history
from src.utils.symbol_utils import clean_symbol, get_symbol_meta, get_universe

PREDICTION_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def analyze_symbol(symbol: str, refresh: bool = False) -> dict[str, Any]:
    clean = clean_symbol(symbol)
    cached = PREDICTION_CACHE.get(clean)
    if cached and not refresh and (time.time() - cached[0] < CACHE_TTL_SECONDS):
        return deepcopy(cached[1])

    meta = get_symbol_meta(clean)
    market_response = fetch_market_history(clean)
    if market_response.get("error"):
        raise ValueError(market_response["error"])

    market_data = market_response["data"]
    history = market_data["history"]
    fast_info = market_data["fast_info"]
    features, target_return, atr_series = build_feature_frame(history)
    model_output = train_and_predict(features, target_return)
    news_payload = get_symbol_news(clean, limit=12)

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
    result["alert"] = record_prediction_alert(result)
    PREDICTION_CACHE[clean] = (time.time(), deepcopy(result))
    return result


def scan_symbols(market: str, limit: int, refresh: bool = False) -> dict[str, Any]:
    symbols = [item["symbol"] for item in get_universe(market)][:limit]
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    with futures.ThreadPoolExecutor(max_workers=min(MAX_SCAN_WORKERS, max(1, len(symbols)))) as executor:
        future_map = {executor.submit(analyze_symbol, symbol, refresh): symbol for symbol in symbols}
        for future in futures.as_completed(future_map):
            symbol = future_map[future]
            try:
                results.append(compact_result(future.result()))
            except Exception as exc:
                errors.append({"symbol": symbol, "error": str(exc)})

    results.sort(key=lambda item: item.get("score") or -999, reverse=True)
    return {
        "market": market,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": results,
        "errors": errors,
    }
