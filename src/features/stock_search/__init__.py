from __future__ import annotations

from typing import Any

from src.config.settings import UNIVERSE
from src.services.stock_search_service import search_yahoo_finance


def search_stocks(query: str, limit: int = 12) -> dict[str, Any]:
    clean_query = query.strip()
    if not clean_query:
        return {"query": query, "results": []}

    local_results = search_local_universe(clean_query)
    remaining = max(0, limit - len(local_results))
    remote_response = search_yahoo_finance(clean_query, limit=limit) if remaining else {"data": []}
    merged = merge_results(local_results, remote_response.get("data", []))
    return {
        "query": query,
        "results": merged[:limit],
        "source_note": "Local configured universe first, Yahoo Finance fallback second.",
        "remote_error": remote_response.get("error"),
    }


def search_local_universe(query: str) -> list[dict[str, str]]:
    lowered = query.lower()
    ranked = []
    for item in UNIVERSE:
        if item["market"] == "Crypto":
            continue
        symbol = item["symbol"].lower()
        name = item["name"].lower()
        if lowered not in symbol and lowered not in name:
            continue
        score = score_match(lowered, symbol, name)
        ranked.append(({**item, "source": "Configured universe"}, score))
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return [item for item, _ in ranked]


def score_match(query: str, symbol: str, name: str) -> int:
    if query == symbol or query == name:
        return 100
    if symbol.startswith(query):
        return 85
    if name.startswith(query):
        return 75
    if query in symbol:
        return 60
    if query in name:
        return 50
    return 0


def merge_results(local_results: list[dict[str, str]], remote_results: list[dict[str, str]]) -> list[dict[str, str]]:
    merged = []
    seen = set()
    for item in [*local_results, *remote_results]:
        symbol = item["symbol"].upper()
        if symbol in seen:
            continue
        seen.add(symbol)
        merged.append({**item, "symbol": symbol})
    return merged
