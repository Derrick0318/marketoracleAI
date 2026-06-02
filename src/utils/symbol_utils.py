from __future__ import annotations

from typing import Any

from src.config.settings import CRYPTO_ASSETS, ETF_ASSETS, ETF_SYMBOLS, MALAYSIA_STOCKS, SYMBOL_META, UNIVERSE, US_STOCKS


def clean_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def infer_market(symbol: str) -> str:
    clean = clean_symbol(symbol)
    if clean in ETF_SYMBOLS:
        return "ETF"
    if clean.endswith(".KL"):
        return "Malaysia"
    if clean in {"BTC-USD", "ETH-USD"}:
        return "Crypto"
    return "US"


def infer_currency(symbol: str, fast_info: dict[str, Any] | None = None) -> str:
    if fast_info:
        currency = fast_info.get("currency")
        if currency:
            return str(currency)
    if symbol.endswith(".KL"):
        return "MYR"
    return "USD"


def get_symbol_meta(symbol: str) -> dict[str, str]:
    clean = clean_symbol(symbol)
    return SYMBOL_META.get(clean, {"symbol": clean, "name": clean, "market": infer_market(clean)})


def get_universe(market: str) -> list[dict[str, str]]:
    normalized = market.lower()
    if normalized == "us":
        return US_STOCKS
    if normalized in {"malaysia", "my", "kl"}:
        return MALAYSIA_STOCKS
    if normalized in {"etf", "etfs", "fund", "funds"}:
        return ETF_ASSETS
    if normalized in {"crypto", "bitcoin"}:
        return CRYPTO_ASSETS
    return UNIVERSE
