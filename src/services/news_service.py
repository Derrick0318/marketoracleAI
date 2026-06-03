from __future__ import annotations

import email.utils
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import requests

from src.utils.error_handler import parse_error
from src.utils.number_utils import clamp, finite_float

POSITIVE_WORDS = {
    "beat",
    "beats",
    "bullish",
    "buy",
    "upgrade",
    "upgraded",
    "growth",
    "profit",
    "profits",
    "record",
    "surge",
    "surges",
    "rally",
    "gain",
    "gains",
    "strong",
    "outperform",
    "breakout",
    "positive",
    "approval",
    "approved",
    "partnership",
    "expansion",
}

NEGATIVE_WORDS = {
    "miss",
    "misses",
    "bearish",
    "sell",
    "downgrade",
    "downgraded",
    "loss",
    "losses",
    "slump",
    "falls",
    "fall",
    "plunge",
    "weak",
    "underperform",
    "lawsuit",
    "probe",
    "warning",
    "negative",
    "recession",
    "risk",
    "risks",
}


def fetch_rss_feed(url: str, source: str, limit: int = 10) -> dict[str, Any]:
    try:
        response = requests.get(url, timeout=5, headers={"User-Agent": "MarketOracleAI/1.0"})
        response.raise_for_status()
        root = ET.fromstring(response.text)
        items = [parse_rss_item(item, source) for item in root.findall(".//item")[:limit]]
        return {"data": [item for item in items if item["title"]]}
    except Exception as exc:
        return {"error": parse_error(exc), "data": []}


def parse_rss_item(item: ET.Element, source: str) -> dict[str, Any]:
    published_text = item.findtext("pubDate") or item.findtext("published") or ""
    published_at = parse_news_date(published_text)
    return {
        "title": (item.findtext("title") or "").strip(),
        "link": (item.findtext("link") or "").strip(),
        "source": source,
        "published_at": published_at.isoformat() if published_at else None,
    }


def parse_news_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def build_symbol_feed_urls(symbol: str, name: str, market: str) -> list[tuple[str, str]]:
    query_base = f"{name} {symbol} stock news today"
    if "Malaysia" in market:
        query_base = f"{name} {symbol} Bursa Malaysia stock news today"

    encoded_query = urllib.parse.quote_plus(query_base)
    google_region = "MY" if "Malaysia" in market else "US"
    google_lang = "en-MY" if "Malaysia" in market else "en-US"
    return [
        (
            f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={urllib.parse.quote(symbol)}&region=US&lang=en-US",
            "Yahoo Finance",
        ),
        (
            f"https://news.google.com/rss/search?q={encoded_query}+when:1d&hl={google_lang}&gl={google_region}&ceid={google_region}:en",
            "Google News",
        ),
        (f"https://www.bing.com/news/search?q={encoded_query}&format=rss", "Bing News"),
    ]


def build_market_feed_urls(market: str) -> list[tuple[str, str]]:
    queries = {
        "us": "US stock market news today earnings Nasdaq NYSE",
        "malaysia": "Bursa Malaysia stock market news today KLCI",
        "etf": "ETF market news today S&P 500 Nasdaq bond gold sector funds",
        "us_etf": "US ETF market news today S&P 500 Nasdaq bond gold sector funds",
        "malaysia_etf": "Bursa Malaysia ETF market news today KLCI gold bond ETF",
        "crypto": "Bitcoin price market news today",
        "all": "stock market news today US Malaysia Bitcoin",
    }
    normalized = market.lower()
    query = queries.get(normalized, queries["all"])
    encoded_query = urllib.parse.quote_plus(query)
    google_region = "MY" if normalized in {"malaysia", "malaysia_etf"} else "US"
    google_lang = "en-MY" if normalized in {"malaysia", "malaysia_etf"} else "en-US"
    return [
        (
            f"https://news.google.com/rss/search?q={encoded_query}+when:1d&hl={google_lang}&gl={google_region}&ceid={google_region}:en",
            "Google News",
        ),
        (f"https://www.bing.com/news/search?q={encoded_query}&format=rss", "Bing News"),
    ]


def collect_news_from_feeds(feeds: list[tuple[str, str]], limit: int) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for url, source in feeds:
        response = fetch_rss_feed(url, source=source, limit=limit)
        items.extend(response.get("data", []))
        if response.get("error"):
            errors.append({"source": source, "error": response["error"]})

    deduped = dedupe_news(items)
    deduped.sort(key=lambda item: item.get("published_at") or "", reverse=True)
    return {"data": deduped[:limit], "errors": errors}


def dedupe_news(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for item in items:
        key = (item.get("title") or "").lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def score_news_sentiment(items: list[dict[str, Any]]) -> dict[str, Any]:
    raw_score = 0
    scored_terms = 0
    for item in items:
        words = {
            word.strip(".,:;!?()[]{}\"'").lower()
            for word in item.get("title", "").split()
            if len(word.strip(".,:;!?()[]{}\"'")) > 2
        }
        positives = len(words.intersection(POSITIVE_WORDS))
        negatives = len(words.intersection(NEGATIVE_WORDS))
        raw_score += positives - negatives
        scored_terms += positives + negatives

    score = 0.0 if scored_terms == 0 else clamp(raw_score / scored_terms, -1, 1)
    label = "positive" if score > 0.2 else "negative" if score < -0.2 else "neutral"
    return {"score": finite_float(score, 3), "label": label}
