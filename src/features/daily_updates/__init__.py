from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from src.config.settings import UNIVERSE
from src.features.alerts import create_admin_alert
from src.features.news import get_market_news
from src.features.prediction import scan_symbols
from src.features.prediction_history import evaluate_pending_predictions, store_scan_predictions
from src.services.state_store_service import append_update_run, list_update_runs, save_daily_snapshot
from src.utils.symbol_utils import get_universe

UPDATE_LOCK = threading.Lock()
UPDATE_STATE: dict[str, Any] = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "next_run_at": None,
    "next_run_label": None,
    "next_run_markets": [],
    "schedule_events": [],
    "last_error": None,
}


def set_next_run_at(next_run_at: str) -> None:
    UPDATE_STATE["next_run_at"] = next_run_at


def set_schedule_state(next_event: dict[str, Any] | None, upcoming_events: list[dict[str, Any]] | None = None) -> None:
    UPDATE_STATE["next_run_at"] = next_event.get("run_at_my_iso") if next_event else None
    UPDATE_STATE["next_run_label"] = next_event.get("label") if next_event else None
    UPDATE_STATE["next_run_markets"] = next_event.get("markets", []) if next_event else []
    UPDATE_STATE["schedule_events"] = upcoming_events or []


def get_update_status() -> dict[str, Any]:
    ensure_schedule_state()
    runs_response = list_update_runs(limit=12)
    runs = runs_response.get("data", [])
    return {
        **UPDATE_STATE,
        "latest_run": runs[0] if runs else None,
        "runs": runs,
        "universe_size": len(UNIVERSE),
        "schedule": (
            "Market-session collector: Bursa 9:05 AM and 5:10 PM MYT on weekdays; "
            "US stocks 9:35 AM and 4:10 PM New York time on weekdays; "
            "US ETFs 9:45 AM and 4:20 PM New York time on weekdays; "
            "Malaysia ETFs follow the Bursa open and close scans; "
            "Bitcoin 12:00 AM MYT daily. Regular sessions only; holidays, early closes, and halts are not checked."
        ),
    }


def ensure_schedule_state() -> None:
    if UPDATE_STATE["schedule_events"]:
        return
    try:
        from src.features.daily_updates.scheduler import get_upcoming_jobs

        upcoming = get_upcoming_jobs(limit=8)
        set_schedule_state(next_event=upcoming[0] if upcoming else None, upcoming_events=upcoming)
    except Exception:
        return


def run_daily_update(reason: str = "manual", limit: int | None = None, markets: list[str] | None = None) -> dict[str, Any]:
    if not UPDATE_LOCK.acquire(blocking=False):
        return {"status": "already_running", **get_update_status()}

    started_at = datetime.now().isoformat(timespec="seconds")
    UPDATE_STATE.update({"running": True, "last_started_at": started_at, "last_error": None})
    selected_markets = normalize_update_markets(markets)
    market_label = ", ".join(format_market_label(market) for market in selected_markets)

    try:
        create_admin_alert(
            "Market data update started",
            f"Collecting fresh prices, AI forecasts, and buy/not-buy suggestions for {market_label}.",
            level="info",
        )
        scan_payload = scan_update_markets(selected_markets, limit=limit)
        market_news = {market: get_market_news(market, limit=12) for market in selected_markets}
        prediction_store = store_scan_predictions(scan_payload, reason=reason)
        prediction_audit = evaluate_pending_predictions(days=14)
        finished_at = datetime.now().isoformat(timespec="seconds")
        suggestion_counts = summarize_suggestions(scan_payload["results"])
        actionable = [item for item in scan_payload["results"] if is_actionable(item.get("action"))]
        snapshot_payload = {
            "reason": reason,
            "started_at": started_at,
            "finished_at": finished_at,
            "markets": selected_markets,
            "scan": scan_payload,
            "market_news": market_news,
            "prediction_store": prediction_store,
            "prediction_audit": prediction_audit,
        }
        snapshot_response = save_daily_snapshot(snapshot_payload)
        run_record = {
            "reason": reason,
            "status": "success",
            "started_at": started_at,
            "finished_at": finished_at,
            "asset_count": len(scan_payload["results"]),
            "error_count": len(scan_payload["errors"]),
            "actionable_count": len(actionable),
            "snapshot_path": snapshot_response.get("data"),
            "metadata": {
                "markets": selected_markets,
                "buy_count": suggestion_counts["buy"],
                "watch_count": suggestion_counts["watch"],
                "not_buy_count": suggestion_counts["not_buy"],
                "prediction_records_stored": prediction_store.get("stored_count", 0),
                "prediction_records_evaluated": prediction_audit.get("evaluated_count", 0),
                "prediction_records_correct": prediction_audit.get("correct_count", 0),
            },
        }
        append_update_run(run_record)
        create_admin_alert(
            "Market data update complete",
            (
                f"Updated {market_label}: {suggestion_counts['buy']} buy candidates, "
                f"{suggestion_counts['watch']} wait/watch, {suggestion_counts['not_buy']} do-not-buy, "
                f"{prediction_audit.get('evaluated_count', 0)} prediction checks, and {run_record['error_count']} errors."
            ),
            level="success",
        )
        UPDATE_STATE.update({"running": False, "last_finished_at": finished_at})
        return run_record
    except Exception as exc:
        finished_at = datetime.now().isoformat(timespec="seconds")
        run_record = {
            "reason": reason,
            "status": "failed",
            "started_at": started_at,
            "finished_at": finished_at,
            "asset_count": 0,
            "error_count": 1,
            "actionable_count": 0,
            "error": str(exc),
            "metadata": {"markets": selected_markets},
        }
        append_update_run(run_record)
        UPDATE_STATE.update({"running": False, "last_finished_at": finished_at, "last_error": str(exc)})
        create_admin_alert("Market data update failed", f"{market_label}: {exc}", level="danger")
        return run_record
    finally:
        UPDATE_LOCK.release()


def run_daily_update_async(reason: str = "manual", limit: int | None = None, markets: list[str] | None = None) -> bool:
    if UPDATE_STATE["running"]:
        return False
    thread = threading.Thread(target=run_daily_update, kwargs={"reason": reason, "limit": limit, "markets": markets}, daemon=True)
    thread.start()
    return True


def scan_update_markets(markets: list[str], limit: int | None = None) -> dict[str, Any]:
    scans: dict[str, Any] = {}
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for market in markets:
        market_limit = limit or len(get_universe(market))
        payload = scan_symbols(market=market, limit=market_limit, refresh=True)
        scans[market] = payload
        results.extend(payload.get("results", []))
        errors.extend(payload.get("errors", []))

    results.sort(key=lambda item: item.get("score") or -999, reverse=True)
    return {
        "market": ",".join(markets),
        "markets": markets,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "cached": False,
        "results": results,
        "errors": errors,
        "market_scans": scans,
    }


def normalize_update_markets(markets: list[str] | None) -> list[str]:
    if not markets:
        return ["all"]
    normalized = []
    for market in markets:
        clean = str(market).strip().lower()
        if clean in {"my", "kl"}:
            clean = "malaysia"
        if clean in {"bitcoin"}:
            clean = "crypto"
        if clean in {"us-etf", "usa_etf", "usa-etf"}:
            clean = "us_etf"
        if clean in {"my_etf", "my-etf", "malaysia-etf", "kl_etf", "kl-etf"}:
            clean = "malaysia_etf"
        if clean not in {"all", "us", "malaysia", "etf", "us_etf", "malaysia_etf", "crypto"}:
            continue
        if clean == "all":
            return ["all"]
        if clean not in normalized:
            normalized.append(clean)
    return normalized or ["all"]


def format_market_label(market: str) -> str:
    return {
        "all": "all configured assets",
        "us": "US stocks",
        "malaysia": "Malaysia stocks",
        "etf": "ETFs",
        "us_etf": "US ETFs",
        "malaysia_etf": "Malaysia ETFs",
        "crypto": "Bitcoin",
    }.get(market, market)


def summarize_suggestions(results: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"buy": 0, "watch": 0, "not_buy": 0}
    for item in results:
        action = str(item.get("action") or "").upper()
        if "BUY" in action:
            summary["buy"] += 1
        elif "SELL" in action or "REDUCE" in action or "AVOID" in action:
            summary["not_buy"] += 1
        else:
            summary["watch"] += 1
    return summary


def is_actionable(action: Any) -> bool:
    return str(action or "").upper() in {"BUY", "STRONG BUY", "SELL / AVOID", "REDUCE"}
