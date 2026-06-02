from __future__ import annotations

import os

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

load_dotenv(".env.local")

from src.features.alerts import get_alerts, read_alert
from src.features.daily_updates import get_update_status, run_daily_update, run_daily_update_async
from src.features.daily_updates.scheduler import start_daily_update_scheduler
from src.features.live_quotes import get_live_quote
from src.features.market_status import get_market_status
from src.features.news import get_market_news, get_symbol_news
from src.features.prediction import analyze_symbol, scan_symbols
from src.features.stock_search import search_stocks
from src.utils.number_utils import as_jsonable, clamp
from src.utils.symbol_utils import clean_symbol


app = Flask(__name__)
start_daily_update_scheduler()


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/admin")
def admin() -> str:
    return render_template("admin.html")


@app.route("/api/universe")
def universe():
    from src.config.settings import UNIVERSE

    return jsonify({"symbols": UNIVERSE})


@app.route("/api/search")
def stock_search():
    query = request.args.get("q", "")
    try:
        limit = int(request.args.get("limit", "12"))
    except ValueError:
        limit = 12
    return jsonify(as_jsonable(search_stocks(query=query, limit=int(clamp(limit, 1, 25)))))


@app.route("/api/analyze/<path:symbol>")
def analyze(symbol: str):
    refresh = request.args.get("refresh") == "1"
    try:
        return jsonify(as_jsonable(analyze_symbol(symbol, refresh=refresh)))
    except Exception as exc:
        return jsonify({"symbol": clean_symbol(symbol), "error": str(exc)}), 422


@app.route("/api/scan")
def scan():
    market = request.args.get("market", "all")
    refresh = request.args.get("refresh") == "1"
    try:
        limit = int(request.args.get("limit", "18"))
    except ValueError:
        limit = 18

    payload = scan_symbols(market=market, limit=int(clamp(limit, 1, 40)), refresh=refresh)
    return jsonify(as_jsonable(payload))


@app.route("/api/news")
def market_news():
    market = request.args.get("market", "all")
    try:
        limit = int(request.args.get("limit", "24"))
    except ValueError:
        limit = 24

    payload = get_market_news(market=market, limit=int(clamp(limit, 4, 50)))
    return jsonify(as_jsonable(payload))


@app.route("/api/news/<path:symbol>")
def symbol_news(symbol: str):
    try:
        limit = int(request.args.get("limit", "12"))
    except ValueError:
        limit = 12

    payload = get_symbol_news(symbol=clean_symbol(symbol), limit=int(clamp(limit, 4, 30)))
    return jsonify(as_jsonable(payload))


@app.route("/api/quote/<path:symbol>")
def live_quote(symbol: str):
    try:
        payload = get_live_quote(clean_symbol(symbol))
        return jsonify(as_jsonable(payload))
    except Exception as exc:
        return jsonify({"symbol": clean_symbol(symbol), "error": str(exc)}), 422


@app.route("/api/market-status/<path:symbol>")
def market_status(symbol: str):
    return jsonify(as_jsonable(get_market_status(clean_symbol(symbol))))


@app.route("/api/alerts")
def alerts():
    try:
        limit = int(request.args.get("limit", "80"))
    except ValueError:
        limit = 80
    unread_only = request.args.get("unread") == "1"
    return jsonify(as_jsonable({"alerts": get_alerts(limit=int(clamp(limit, 1, 200)), unread_only=unread_only)}))


@app.route("/api/alerts/<alert_id>/read", methods=["POST"])
def alert_read(alert_id: str):
    try:
        return jsonify(as_jsonable({"alert": read_alert(alert_id)}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 422


@app.route("/api/admin/status")
def admin_status():
    return jsonify(as_jsonable(get_update_status()))


@app.route("/api/admin/run-update", methods=["POST"])
def admin_run_update():
    limit_value = request.args.get("limit")
    limit = None
    if limit_value:
        try:
            limit = int(clamp(int(limit_value), 1, 40))
        except ValueError:
            limit = None
    started = run_daily_update_async(reason="manual_admin", limit=limit)
    return jsonify(as_jsonable({"started": started, "status": get_update_status()}))


@app.route("/api/admin/cron-update")
def admin_cron_update():
    expected = os.getenv("CRON_SECRET")
    auth_header = request.headers.get("Authorization", "")
    query_secret = request.args.get("secret")
    if expected and auth_header != f"Bearer {expected}" and query_secret != expected:
        return jsonify({"error": "Unauthorized cron request"}), 401

    try:
        limit = int(request.args.get("limit", "33"))
    except ValueError:
        limit = 33
    result = run_daily_update(reason="vercel_cron", limit=int(clamp(limit, 1, 40)))
    return jsonify(as_jsonable(result))


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
