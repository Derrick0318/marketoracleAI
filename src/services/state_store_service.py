from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import requests

from src.utils.error_handler import parse_error

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "daily_snapshots"
STATE_FILE = DATA_DIR / "admin_state.json"
MAX_ALERTS = 300
MAX_UPDATE_RUNS = 80
MAX_PREDICTION_RECORDS = 1400
MAX_MARKET_PRICE_EVENTS = 5000

STORE_LOCK = threading.RLock()


def supabase_config() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = supabase_secret_key()
    if not url or not key:
        return None
    return url, key


def supabase_secret_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SECRET_KEY", "")


def get_database_status() -> dict[str, Any]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = supabase_secret_key()
    status = {
        "storage_mode": "supabase" if url and key else "local_json",
        "supabase_url_present": bool(url),
        "supabase_key_present": bool(key),
        "supabase_url_preview": preview_url(url),
        "supabase_key_preview": preview_secret(key),
        "tables": {},
        "ok": False,
        "message": "",
    }

    if not url or not key:
        missing = []
        if not url:
            missing.append("SUPABASE_URL")
        if not key:
            missing.append("SUPABASE_SERVICE_ROLE_KEY or SUPABASE_SECRET_KEY")
        status["message"] = f"Using local JSON fallback. Missing Vercel env var(s): {', '.join(missing)}."
        return status

    if not url.startswith("https://") or ".supabase.co" not in url:
        status["message"] = "SUPABASE_URL does not look like a Supabase project URL."
        return status

    checks = {
        "app_alerts": check_supabase_table("app_alerts"),
        "update_runs": check_supabase_table("update_runs"),
        "daily_snapshots": check_supabase_table("daily_snapshots"),
        "prediction_records": check_supabase_table("prediction_records"),
        "market_price_events": check_supabase_table("market_price_events"),
    }
    status["tables"] = checks
    failed = {table: result for table, result in checks.items() if not result["ok"]}
    if failed:
        status["message"] = "Supabase env vars exist, but one or more tables cannot be read."
        return status

    status["ok"] = True
    status["message"] = "Supabase is connected and all required tables are readable."
    return status


def clear_collected_market_data() -> dict[str, Any]:
    if supabase_config():
        return clear_collected_market_data_supabase()

    cleared = {
        "app_alerts": 0,
        "update_runs": 0,
        "daily_snapshots": 0,
        "prediction_records": 0,
        "market_price_events": 0,
    }
    errors: list[str] = []

    with STORE_LOCK:
        state = read_state()
        cleared["app_alerts"] = len(state.get("alerts") or [])
        cleared["update_runs"] = len(state.get("update_runs") or [])
        cleared["prediction_records"] = len(state.get("prediction_records") or [])
        cleared["market_price_events"] = len(state.get("market_price_events") or [])
        response = write_state(default_state())
        if response.get("error"):
            errors.append(response["error"])

    try:
        if SNAPSHOT_DIR.exists():
            for path in SNAPSHOT_DIR.glob("*.json"):
                path.unlink()
                cleared["daily_snapshots"] += 1
    except Exception as exc:
        errors.append(parse_error(exc))

    return {
        "ok": not errors,
        "storage_mode": "local_json",
        "cleared": cleared,
        "errors": errors,
    }


def clear_collected_market_data_supabase() -> dict[str, Any]:
    tables = ["app_alerts", "update_runs", "daily_snapshots", "prediction_records", "market_price_events"]
    cleared = {table: "requested" for table in tables}
    errors: list[str] = []

    for table in tables:
        response = request_supabase(
            "DELETE",
            table,
            params={"id": "not.is.null"},
            headers=supabase_headers("return=minimal"),
        )
        if response.get("error"):
            errors.append(f"{table}: {response['error']}")
            cleared[table] = "failed"

    return {
        "ok": not errors,
        "storage_mode": "supabase",
        "cleared": cleared,
        "errors": errors,
    }


def preview_url(url: str) -> str | None:
    if not url:
        return None
    if len(url) <= 36:
        return url
    return f"{url[:28]}...{url[-12:]}"


def preview_secret(secret: str) -> str | None:
    if not secret:
        return None
    if len(secret) <= 12:
        return "***"
    return f"{secret[:6]}...{secret[-4:]}"


def check_supabase_table(table: str) -> dict[str, Any]:
    response = request_supabase("GET", table, params={"select": "id", "limit": "1"})
    if response.get("error"):
        return {"ok": False, "error": response["error"]}
    count = len(response.get("data") or [])
    return {"ok": True, "sample_count": count}


def supabase_headers(prefer: str | None = None) -> dict[str, str]:
    config = supabase_config()
    if not config:
        return {}
    _, key = config
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def supabase_rest_url(table: str) -> str:
    config = supabase_config()
    if not config:
        raise RuntimeError("Supabase is not configured")
    url, _ = config
    return f"{url}/rest/v1/{table}"


def request_supabase(method: str, table: str, **kwargs: Any) -> dict[str, Any]:
    try:
        response = requests.request(
            method,
            supabase_rest_url(table),
            headers=kwargs.pop("headers", supabase_headers()),
            timeout=10,
            **kwargs,
        )
        response.raise_for_status()
        if response.text:
            return {"data": response.json()}
        return {"data": None}
    except Exception as exc:
        return {"error": parse_error(exc)}


def default_state() -> dict[str, Any]:
    return {"alerts": [], "update_runs": [], "prediction_records": [], "market_price_events": []}


def read_state() -> dict[str, Any]:
    with STORE_LOCK:
        try:
            if not STATE_FILE.exists():
                return default_state()
            with STATE_FILE.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
            return {**default_state(), **state}
        except Exception:
            return default_state()


def write_state(state: dict[str, Any]) -> dict[str, Any]:
    with STORE_LOCK:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with STATE_FILE.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2)
            return {"data": deepcopy(state)}
        except Exception as exc:
            return {"error": parse_error(exc)}


def append_alert(alert: dict[str, Any]) -> dict[str, Any]:
    if supabase_config():
        return append_alert_supabase(alert)

    with STORE_LOCK:
        state = read_state()
        unique_key = alert.get("unique_key")
        if unique_key:
            for existing in state["alerts"]:
                if existing.get("unique_key") == unique_key:
                    return {"data": existing, "duplicate": True}

        normalized = {
            "id": str(uuid4()),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "read": False,
            **alert,
        }
        state["alerts"] = [normalized, *state["alerts"]][:MAX_ALERTS]
        response = write_state(state)
        if response.get("error"):
            return response
        return {"data": normalized, "duplicate": False}


def list_alerts(limit: int = 80, unread_only: bool = False) -> dict[str, Any]:
    if supabase_config():
        params = {"select": "*", "order": "created_at.desc", "limit": str(limit)}
        if unread_only:
            params["read"] = "eq.false"
        response = request_supabase("GET", "app_alerts", params=params)
        if response.get("error"):
            return response
        return {"data": response["data"] or []}

    state = read_state()
    alerts = state["alerts"]
    if unread_only:
        alerts = [alert for alert in alerts if not alert.get("read")]
    return {"data": alerts[:limit]}


def mark_alert_read(alert_id: str) -> dict[str, Any]:
    if supabase_config():
        response = request_supabase(
            "PATCH",
            "app_alerts",
            params={"id": f"eq.{alert_id}"},
            json={"read": True, "read_at": datetime.now().isoformat(timespec="seconds")},
            headers=supabase_headers("return=representation"),
        )
        if response.get("error"):
            return response
        data = response["data"] or []
        return {"data": data[0] if data else None}

    with STORE_LOCK:
        state = read_state()
        for alert in state["alerts"]:
            if alert["id"] == alert_id:
                alert["read"] = True
                alert["read_at"] = datetime.now().isoformat(timespec="seconds")
                response = write_state(state)
                if response.get("error"):
                    return response
                return {"data": alert}
        return {"error": "Alert not found"}


def append_update_run(run: dict[str, Any]) -> dict[str, Any]:
    if supabase_config():
        response = request_supabase(
            "POST",
            "update_runs",
            json=run,
            headers=supabase_headers("return=representation"),
        )
        if response.get("error"):
            return response
        data = response["data"] or []
        return {"data": data[0] if data else run}

    with STORE_LOCK:
        state = read_state()
        normalized = {"id": str(uuid4()), **run}
        state["update_runs"] = [normalized, *state["update_runs"]][:MAX_UPDATE_RUNS]
        response = write_state(state)
        if response.get("error"):
            return response
        return {"data": normalized}


def list_update_runs(limit: int = 20) -> dict[str, Any]:
    if supabase_config():
        response = request_supabase("GET", "update_runs", params={"select": "*", "order": "created_at.desc", "limit": str(limit)})
        if response.get("error"):
            return response
        return {"data": response["data"] or []}

    state = read_state()
    return {"data": state["update_runs"][:limit]}


def save_daily_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    if supabase_config():
        response = request_supabase(
            "POST",
            "daily_snapshots",
            json={
                "reason": payload.get("reason"),
                "started_at": payload.get("started_at"),
                "finished_at": payload.get("finished_at"),
                "payload": payload,
            },
            headers=supabase_headers("return=representation"),
        )
        if response.get("error"):
            return response
        data = response["data"] or []
        snapshot_id = data[0]["id"] if data else "created"
        return {"data": f"supabase:daily_snapshots:{snapshot_id}"}

    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        path = SNAPSHOT_DIR / f"market_snapshot_{stamp}.json"
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return {"data": str(path)}
    except Exception as exc:
        return {"error": parse_error(exc)}


def list_daily_snapshots(limit: int = 20) -> dict[str, Any]:
    if supabase_config():
        response = request_supabase(
            "GET",
            "daily_snapshots",
            params={"select": "created_at,reason,payload", "order": "created_at.desc", "limit": str(limit)},
        )
        if response.get("error"):
            return response
        return {"data": response.get("data") or []}

    try:
        if not SNAPSHOT_DIR.exists():
            return {"data": []}
        snapshots = []
        for path in sorted(SNAPSHOT_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            snapshots.append(
                {
                    "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
                    "reason": payload.get("reason"),
                    "payload": payload,
                    "path": str(path),
                }
            )
        return {"data": snapshots}
    except Exception as exc:
        return {"error": parse_error(exc)}


def append_market_price_events(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"data": []}

    if supabase_config():
        response = request_supabase(
            "POST",
            "market_price_events",
            params={"on_conflict": "unique_key"},
            json=records,
            headers=supabase_headers("return=representation,resolution=merge-duplicates"),
        )
        if response.get("error"):
            return response
        return {"data": response.get("data") or []}

    with STORE_LOCK:
        state = read_state()
        by_key = {record.get("unique_key"): record for record in state["market_price_events"] if record.get("unique_key")}
        for record in records:
            unique_key = record.get("unique_key")
            if not unique_key:
                continue
            existing = by_key.get(unique_key, {})
            by_key[unique_key] = {**existing, **record, "id": existing.get("id") or str(uuid4())}

        merged = sorted(by_key.values(), key=lambda item: item.get("captured_at") or item.get("created_at") or "", reverse=True)
        state["market_price_events"] = merged[:MAX_MARKET_PRICE_EVENTS]
        response = write_state(state)
        if response.get("error"):
            return response
        return {"data": records}


def list_market_price_events(
    days: int = 30,
    limit: int = 1000,
    event_types: list[str] | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()
    normalized_types = [item for item in (event_types or []) if item]

    if supabase_config():
        params = {
            "select": "*",
            "trading_date": f"gte.{cutoff}",
            "order": "trading_date.desc,captured_at.desc",
            "limit": str(limit),
        }
        if normalized_types:
            params["event_type"] = f"in.({','.join(normalized_types)})"
        if symbol:
            params["symbol"] = f"eq.{symbol}"
        response = request_supabase("GET", "market_price_events", params=params)
        if response.get("error"):
            return response
        return {"data": response.get("data") or []}

    state = read_state()
    events = [
        event
        for event in state["market_price_events"]
        if str(event.get("trading_date") or "") >= cutoff
        and (not normalized_types or event.get("event_type") in normalized_types)
        and (not symbol or event.get("symbol") == symbol)
    ]
    events.sort(key=lambda item: (item.get("trading_date") or "", item.get("captured_at") or ""), reverse=True)
    return {"data": events[:limit]}


def append_prediction_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    if not records:
        return {"data": []}

    if supabase_config():
        response = request_supabase(
            "POST",
            "prediction_records",
            params={"on_conflict": "unique_key"},
            json=records,
            headers=supabase_headers("return=representation,resolution=merge-duplicates"),
        )
        if response.get("error"):
            return response
        return {"data": response.get("data") or []}

    with STORE_LOCK:
        state = read_state()
        by_key = {record.get("unique_key"): record for record in state["prediction_records"] if record.get("unique_key")}
        for record in records:
            unique_key = record.get("unique_key")
            if not unique_key:
                continue
            existing = by_key.get(unique_key, {})
            by_key[unique_key] = {**existing, **record, "id": existing.get("id") or str(uuid4())}

        merged = sorted(by_key.values(), key=lambda item: item.get("generated_at") or item.get("created_at") or "", reverse=True)
        state["prediction_records"] = merged[:MAX_PREDICTION_RECORDS]
        response = write_state(state)
        if response.get("error"):
            return response
        return {"data": records}


def list_prediction_records(days: int = 10, limit: int = 1000, status: str | None = None) -> dict[str, Any]:
    cutoff = (datetime.now() - timedelta(days=days)).date().isoformat()

    if supabase_config():
        params = {
            "select": "*",
            "prediction_date": f"gte.{cutoff}",
            "order": "prediction_date.desc,generated_at.desc",
            "limit": str(limit),
        }
        if status:
            params["evaluation_status"] = f"eq.{status}"
        response = request_supabase("GET", "prediction_records", params=params)
        if response.get("error"):
            return response
        return {"data": response.get("data") or []}

    state = read_state()
    records = [
        record
        for record in state["prediction_records"]
        if str(record.get("prediction_date") or "") >= cutoff and (not status or record.get("evaluation_status") == status)
    ]
    records.sort(key=lambda item: (item.get("prediction_date") or "", item.get("generated_at") or ""), reverse=True)
    return {"data": records[:limit]}


def update_prediction_record(unique_key: str, updates: dict[str, Any]) -> dict[str, Any]:
    if supabase_config():
        response = request_supabase(
            "PATCH",
            "prediction_records",
            params={"unique_key": f"eq.{unique_key}"},
            json=updates,
            headers=supabase_headers("return=representation"),
        )
        if response.get("error"):
            return response
        data = response.get("data") or []
        return {"data": data[0] if data else None}

    with STORE_LOCK:
        state = read_state()
        for record in state["prediction_records"]:
            if record.get("unique_key") == unique_key:
                record.update(updates)
                response = write_state(state)
                if response.get("error"):
                    return response
                return {"data": record}
        return {"error": "Prediction record not found"}


def append_alert_supabase(alert: dict[str, Any]) -> dict[str, Any]:
    unique_key = alert.get("unique_key")
    if unique_key:
        existing = request_supabase("GET", "app_alerts", params={"select": "*", "unique_key": f"eq.{unique_key}", "limit": "1"})
        if existing.get("error"):
            return existing
        if existing.get("data"):
            return {"data": existing["data"][0], "duplicate": True}

    payload = {"read": False, **alert}
    response = request_supabase(
        "POST",
        "app_alerts",
        json=payload,
        headers=supabase_headers("return=representation"),
    )
    if response.get("error"):
        return response
    data = response["data"] or []
    return {"data": data[0] if data else payload, "duplicate": False}
