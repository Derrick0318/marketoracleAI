from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, render_template, request, url_for
from dotenv import load_dotenv

load_dotenv(".env.local")

from src.features.admin_auth import (
    admin_credentials_ready,
    admin_required,
    sign_in_admin,
    sign_out_admin,
    validate_admin_credentials,
)
from src.features.alerts import get_alerts, read_alert
from src.features.assistant import answer_market_question
from src.features.daily_updates import get_update_status, run_daily_update, run_daily_update_async
from src.features.daily_updates.scheduler import get_due_jobs, get_upcoming_jobs, start_daily_update_scheduler
from src.features.live_quotes import get_live_quote
from src.features.market_status import get_market_status
from src.features.news import get_market_news, get_symbol_news
from src.features.prediction import analyze_symbol, scan_symbols
from src.features.prediction_history import build_prediction_accuracy_report, run_prediction_audit
from src.features.stock_search import search_stocks
from src.services.state_store_service import get_database_status
from src.utils.number_utils import as_jsonable, clamp
from src.utils.symbol_utils import clean_symbol


app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "market-oracle-local-dev-session-key"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("VERCEL") == "1",
)
if os.getenv("VERCEL") != "1":
    start_daily_update_scheduler()


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/admin")
@admin_required
def admin() -> str:
    return render_template("admin.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if not admin_credentials_ready():
            error = "Admin login is not configured yet."
        elif validate_admin_credentials(username, password):
            sign_in_admin(username)
            next_url = request.args.get("next") or url_for("admin")
            if not next_url.startswith("/"):
                next_url = url_for("admin")
            return redirect(next_url)
        else:
            error = "Wrong username or password."

    return render_template("admin_login.html", error=error)


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    sign_out_admin()
    return redirect(url_for("admin_login"))


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

    payload = scan_symbols(
        market=market,
        limit=int(clamp(limit, 1, 40)),
        refresh=refresh,
        include_news=False,
        record_alerts=False,
    )
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


@app.route("/api/assistant", methods=["POST"])
def market_assistant():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get("symbol") or ""
    question = payload.get("question") or ""
    language = payload.get("language") or "en"
    try:
        return jsonify(as_jsonable(answer_market_question(symbol=symbol, question=question, language=language)))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 422


@app.route("/api/market-status/<path:symbol>")
def market_status(symbol: str):
    return jsonify(as_jsonable(get_market_status(clean_symbol(symbol))))


@app.route("/api/alerts")
@admin_required
def alerts():
    try:
        limit = int(request.args.get("limit", "80"))
    except ValueError:
        limit = 80
    unread_only = request.args.get("unread") == "1"
    return jsonify(as_jsonable({"alerts": get_alerts(limit=int(clamp(limit, 1, 200)), unread_only=unread_only)}))


@app.route("/api/alerts/<alert_id>/read", methods=["POST"])
@admin_required
def alert_read(alert_id: str):
    try:
        return jsonify(as_jsonable({"alert": read_alert(alert_id)}))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 422


@app.route("/api/admin/status")
@admin_required
def admin_status():
    return jsonify(as_jsonable(get_update_status()))


@app.route("/api/admin/database-status")
@admin_required
def admin_database_status():
    return jsonify(as_jsonable(get_database_status()))


@app.route("/api/admin/run-update", methods=["POST"])
@admin_required
def admin_run_update():
    limit_value = request.args.get("limit")
    market_value = request.args.get("market")
    limit = None
    if limit_value:
        try:
            limit = int(clamp(int(limit_value), 1, 40))
        except ValueError:
            limit = None
    markets = [market_value] if market_value else None
    started = run_daily_update_async(reason="manual_admin", limit=limit, markets=markets)
    return jsonify(as_jsonable({"started": started, "status": get_update_status()}))


@app.route("/api/admin/prediction-accuracy")
@admin_required
def admin_prediction_accuracy():
    try:
        days = int(request.args.get("days", "10"))
    except ValueError:
        days = 10
    return jsonify(as_jsonable(build_prediction_accuracy_report(days=int(clamp(days, 1, 30)))))


@app.route("/api/admin/evaluate-predictions", methods=["POST"])
@admin_required
def admin_evaluate_predictions():
    try:
        days = int(request.args.get("days", "10"))
    except ValueError:
        days = 10
    return jsonify(as_jsonable(run_prediction_audit(days=int(clamp(days, 1, 30)))))


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
    market = request.args.get("market")
    markets = [market] if market else None
    result = run_daily_update(reason="vercel_cron", limit=int(clamp(limit, 1, 40)), markets=markets)
    return jsonify(as_jsonable(result))


@app.route("/api/admin/cron-check")
def admin_cron_check():
    expected = os.getenv("CRON_SECRET")
    auth_header = request.headers.get("Authorization", "")
    query_secret = request.args.get("secret")
    if expected and auth_header != f"Bearer {expected}" and query_secret != expected:
        return jsonify({"error": "Unauthorized cron request"}), 401

    due_jobs = get_due_jobs()
    if not due_jobs:
        return jsonify(
            as_jsonable(
                {
                    "status": "skipped",
                    "message": "No market update is due in this cron window.",
                    "upcoming": get_upcoming_jobs(limit=6),
                }
            )
        )

    results = []
    for job in due_jobs:
        results.append(run_daily_update(reason=f"vercel_{job.reason}", markets=list(job.markets)))
    return jsonify(as_jsonable({"status": "ran", "jobs": [job.key for job in due_jobs], "results": results}))


@app.route("/api/health")
def health():
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
