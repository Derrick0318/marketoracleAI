from __future__ import annotations

from typing import Any

import requests

from src.utils.error_handler import parse_error

YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
US_EXCHANGES = {"NMS", "NGM", "NCM", "NYQ", "ASE", "PCX", "PNK"}


def search_yahoo_finance(query: str, limit: int = 12) -> dict[str, Any]:
    try:
        response = requests.get(
            YAHOO_SEARCH_URL,
            params={"q": query, "quotesCount": limit, "newsCount": 0},
            timeout=6,
            headers={"User-Agent": "MarketOracleAI/1.0"},
        )
        response.raise_for_status()
        return {"data": normalize_yahoo_quotes(response.json().get("quotes", []))}
    except Exception as exc:
        return {"error": parse_error(exc), "data": []}


def normalize_yahoo_quotes(quotes: list[dict[str, Any]]) -> list[dict[str, str]]:
    results = []
    for quote in quotes:
        symbol = str(quote.get("symbol") or "").upper()
        name = quote.get("shortname") or quote.get("longname") or symbol
        quote_type = quote.get("quoteType")
        exchange = quote.get("exchange")
        market = infer_search_market(symbol, exchange, quote_type)
        if quote_type not in {"EQUITY", "ETF", "INDEX"} or market not in {"US", "Malaysia", "ETF", "Index"}:
            continue
        results.append({"symbol": symbol, "name": str(name), "market": market, "source": "Yahoo Finance"})
    return results


def infer_search_market(symbol: str, exchange: str | None, quote_type: str | None = None) -> str:
    if quote_type == "INDEX":
        return "Index"
    if quote_type == "ETF" and exchange in US_EXCHANGES:
        return "ETF"
    if symbol.endswith(".KL") or exchange == "KLS":
        return "Malaysia"
    if "." not in symbol and exchange in US_EXCHANGES:
        return "US"
    return "Other"
