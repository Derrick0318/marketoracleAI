from __future__ import annotations

from datetime import datetime
from typing import Any

from src.services.news_service import (
    build_market_feed_urls,
    build_symbol_feed_urls,
    collect_news_from_feeds,
    score_news_sentiment,
)
from src.utils.symbol_utils import get_symbol_meta


def get_symbol_news(symbol: str, limit: int = 12) -> dict[str, Any]:
    meta = get_symbol_meta(symbol)
    feeds = build_symbol_feed_urls(symbol=symbol, name=meta["name"], market=meta["market"])
    collected = collect_news_from_feeds(feeds=feeds, limit=limit)
    sentiment = score_news_sentiment(collected["data"])
    return {
        "symbol": symbol,
        "name": meta["name"],
        "market": meta["market"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [source for _, source in feeds],
        "sentiment": sentiment,
        "items": collected["data"],
        "errors": collected["errors"],
    }


def get_empty_symbol_news(symbol: str) -> dict[str, Any]:
    meta = get_symbol_meta(symbol)
    return {
        "symbol": symbol,
        "name": meta["name"],
        "market": meta["market"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [],
        "sentiment": {"score": 0, "label": "neutral"},
        "items": [],
        "errors": [],
    }


def get_market_news(market: str = "all", limit: int = 24) -> dict[str, Any]:
    feeds = build_market_feed_urls(market)
    collected = collect_news_from_feeds(feeds=feeds, limit=limit)
    sentiment = score_news_sentiment(collected["data"])
    return {
        "market": market,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources": [source for _, source in feeds],
        "sentiment": sentiment,
        "items": collected["data"],
        "errors": collected["errors"],
    }
