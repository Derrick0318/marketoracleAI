from __future__ import annotations

from datetime import datetime
from typing import Any

from src.features.market_status import get_market_status
from src.services.market_data_service import fetch_live_quote
from src.utils.symbol_utils import clean_symbol, get_symbol_meta, infer_currency


def get_live_quote(symbol: str) -> dict[str, Any]:
    clean = clean_symbol(symbol)
    meta = get_symbol_meta(clean)
    response = fetch_live_quote(clean)
    if response.get("error"):
        raise ValueError(response["error"])

    quote = response["data"]
    currency = quote.get("currency") or infer_currency(clean)
    return {
        **quote,
        "name": meta["name"],
        "market": meta["market"],
        "currency": currency,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "market_status": get_market_status(clean),
        "freshness_note": "Free Yahoo Finance data can be exchange-delayed; US equities are often delayed, BTC is usually near real time.",
    }
