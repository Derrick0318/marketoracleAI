from __future__ import annotations

CACHE_TTL_SECONDS = 600
MODEL_PERIOD = "5y"
MAX_SCAN_WORKERS = 8

US_STOCKS = [
    {"symbol": "NVDA", "name": "NVIDIA", "market": "US"},
    {"symbol": "MSFT", "name": "Microsoft", "market": "US"},
    {"symbol": "AAPL", "name": "Apple", "market": "US"},
    {"symbol": "AMZN", "name": "Amazon", "market": "US"},
    {"symbol": "GOOGL", "name": "Alphabet", "market": "US"},
    {"symbol": "META", "name": "Meta Platforms", "market": "US"},
    {"symbol": "TSLA", "name": "Tesla", "market": "US"},
    {"symbol": "AMD", "name": "Advanced Micro Devices", "market": "US"},
    {"symbol": "AVGO", "name": "Broadcom", "market": "US"},
    {"symbol": "NFLX", "name": "Netflix", "market": "US"},
    {"symbol": "JPM", "name": "JPMorgan Chase", "market": "US"},
    {"symbol": "V", "name": "Visa", "market": "US"},
    {"symbol": "COST", "name": "Costco", "market": "US"},
    {"symbol": "LLY", "name": "Eli Lilly", "market": "US"},
    {"symbol": "XOM", "name": "Exxon Mobil", "market": "US"},
    {"symbol": "PLTR", "name": "Palantir", "market": "US"},
]

MALAYSIA_STOCKS = [
    {"symbol": "1155.KL", "name": "Maybank", "market": "Malaysia"},
    {"symbol": "1023.KL", "name": "CIMB Group", "market": "Malaysia"},
    {"symbol": "1295.KL", "name": "Public Bank", "market": "Malaysia"},
    {"symbol": "5347.KL", "name": "Tenaga Nasional", "market": "Malaysia"},
    {"symbol": "5225.KL", "name": "IHH Healthcare", "market": "Malaysia"},
    {"symbol": "5183.KL", "name": "Petronas Chemicals", "market": "Malaysia"},
    {"symbol": "6947.KL", "name": "CelcomDigi", "market": "Malaysia"},
    {"symbol": "4863.KL", "name": "Telekom Malaysia", "market": "Malaysia"},
    {"symbol": "8869.KL", "name": "Press Metal", "market": "Malaysia"},
    {"symbol": "1961.KL", "name": "IOI Corporation", "market": "Malaysia"},
    {"symbol": "4677.KL", "name": "YTL Corporation", "market": "Malaysia"},
    {"symbol": "6742.KL", "name": "YTL Power", "market": "Malaysia"},
    {"symbol": "4065.KL", "name": "PPB Group", "market": "Malaysia"},
    {"symbol": "6033.KL", "name": "Petronas Gas", "market": "Malaysia"},
    {"symbol": "5819.KL", "name": "Hong Leong Bank", "market": "Malaysia"},
    {"symbol": "1066.KL", "name": "RHB Bank", "market": "Malaysia"},
]

CRYPTO_ASSETS = [
    {"symbol": "BTC-USD", "name": "Bitcoin", "market": "Crypto"},
]

UNIVERSE = US_STOCKS + MALAYSIA_STOCKS + CRYPTO_ASSETS
SYMBOL_META = {item["symbol"].upper(): item for item in UNIVERSE}
