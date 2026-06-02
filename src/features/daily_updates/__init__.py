from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

from src.config.settings import UNIVERSE
from src.features.alerts import create_admin_alert
from src.features.news import get_market_news
from src.features.prediction import scan_symbols
from src.services.state_store_service import append_update_run, list_update_runs, save_daily_snapshot

UPDATE_LOCK = threading.Lock()
UPDATE_STATE: dict[str, Any] = {
    "running": False,
    "last_started_at": None,
    "last_finished_at": None,
    "next_run_at": None,
    "last_error": None,
}


def set_next_run_at(next_run_at: str) -> None:
    UPDATE_STATE["next_run_at"] = next_run_at


def get_update_status() -> dict[str, Any]:
    runs_response = list_update_runs(limit=12)
    runs = runs_response.get("data", [])
    return {
        **UPDATE_STATE,
        "latest_run": runs[0] if runs else None,
        "runs": runs,
        "universe_size": len(UNIVERSE),
        "schedule": "Every day at 12:00 AM while the app server is running",
    }


def run_daily_update(reason: str = "manual", limit: int | None = None) -> dict[str, Any]:
    if not UPDATE_LOCK.acquire(blocking=False):
        return {"status": "already_running", **get_update_status()}

    started_at = datetime.now().isoformat(timespec="seconds")
    UPDATE_STATE.update({"running": True, "last_started_at": started_at, "last_error": None})
    requested_limit = limit or len(UNIVERSE)

    try:
        create_admin_alert(
            "Daily data update started",
            f"Collecting fresh prices, AI forecasts, and news for {requested_limit} assets.",
            level="info",
        )
        scan_payload = scan_symbols(market="all", limit=requested_limit, refresh=True)
        market_news = {
            "all": get_market_news("all", limit=12),
            "us": get_market_news("us", limit=12),
            "malaysia": get_market_news("malaysia", limit=12),
            "crypto": get_market_news("crypto", limit=12),
        }
        finished_at = datetime.now().isoformat(timespec="seconds")
        actionable = [
            item for item in scan_payload["results"] if item.get("action") in {"BUY", "STRONG BUY", "SELL / AVOID", "REDUCE"}
        ]
        snapshot_payload = {
            "reason": reason,
            "started_at": started_at,
            "finished_at": finished_at,
            "scan": scan_payload,
            "market_news": market_news,
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
        }
        append_update_run(run_record)
        create_admin_alert(
            "Daily data update complete",
            (
                f"Updated {run_record['asset_count']} assets with {run_record['actionable_count']} "
                f"buy/sell alerts and {run_record['error_count']} errors."
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
        }
        append_update_run(run_record)
        UPDATE_STATE.update({"running": False, "last_finished_at": finished_at, "last_error": str(exc)})
        create_admin_alert("Daily data update failed", str(exc), level="danger")
        return run_record
    finally:
        UPDATE_LOCK.release()


def run_daily_update_async(reason: str = "manual", limit: int | None = None) -> bool:
    if UPDATE_STATE["running"]:
        return False
    thread = threading.Thread(target=run_daily_update, kwargs={"reason": reason, "limit": limit}, daemon=True)
    thread.start()
    return True
