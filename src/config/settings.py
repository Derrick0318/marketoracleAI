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

ETF_ASSETS = [
    {"symbol": "VOO", "name": "Vanguard S&P 500 ETF", "market": "ETF"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "market": "ETF"},
    {"symbol": "IVV", "name": "iShares Core S&P 500 ETF", "market": "ETF"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "market": "ETF"},
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "market": "ETF"},
    {"symbol": "DIA", "name": "SPDR Dow Jones Industrial Average ETF", "market": "ETF"},
    {"symbol": "IWM", "name": "iShares Russell 2000 ETF", "market": "ETF"},
    {"symbol": "SCHD", "name": "Schwab US Dividend Equity ETF", "market": "ETF"},
    {"symbol": "VYM", "name": "Vanguard High Dividend Yield ETF", "market": "ETF"},
    {"symbol": "VNQ", "name": "Vanguard Real Estate ETF", "market": "ETF"},
    {"symbol": "VEA", "name": "Vanguard FTSE Developed Markets ETF", "market": "ETF"},
    {"symbol": "VWO", "name": "Vanguard FTSE Emerging Markets ETF", "market": "ETF"},
    {"symbol": "EFA", "name": "iShares MSCI EAFE ETF", "market": "ETF"},
    {"symbol": "EEM", "name": "iShares MSCI Emerging Markets ETF", "market": "ETF"},
    {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "market": "ETF"},
    {"symbol": "TLT", "name": "iShares 20+ Year Treasury Bond ETF", "market": "ETF"},
    {"symbol": "IEF", "name": "iShares 7-10 Year Treasury Bond ETF", "market": "ETF"},
    {"symbol": "SHY", "name": "iShares 1-3 Year Treasury Bond ETF", "market": "ETF"},
    {"symbol": "GLD", "name": "SPDR Gold Shares", "market": "ETF"},
    {"symbol": "SLV", "name": "iShares Silver Trust", "market": "ETF"},
    {"symbol": "XLK", "name": "Technology Select Sector SPDR Fund", "market": "ETF"},
    {"symbol": "XLF", "name": "Financial Select Sector SPDR Fund", "market": "ETF"},
    {"symbol": "XLE", "name": "Energy Select Sector SPDR Fund", "market": "ETF"},
    {"symbol": "XLV", "name": "Health Care Select Sector SPDR Fund", "market": "ETF"},
    {"symbol": "XLY", "name": "Consumer Discretionary Select Sector SPDR Fund", "market": "ETF"},
    {"symbol": "XLP", "name": "Consumer Staples Select Sector SPDR Fund", "market": "ETF"},
    {"symbol": "XLI", "name": "Industrial Select Sector SPDR Fund", "market": "ETF"},
]

CRYPTO_ASSETS = [
    {"symbol": "BTC-USD", "name": "Bitcoin", "market": "Crypto"},
]

UNIVERSE = US_STOCKS + MALAYSIA_STOCKS + ETF_ASSETS + CRYPTO_ASSETS
SYMBOL_META = {item["symbol"].upper(): item for item in UNIVERSE}
ETF_SYMBOLS = {item["symbol"].upper() for item in ETF_ASSETS}
