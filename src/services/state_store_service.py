from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime
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

STORE_LOCK = threading.RLock()


def supabase_config() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        return None
    return url, key


def get_database_status() -> dict[str, Any]:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
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
            missing.append("SUPABASE_SERVICE_ROLE_KEY")
        status["message"] = f"Using local JSON fallback. Missing Vercel env var(s): {', '.join(missing)}."
        return status

    if not url.startswith("https://") or ".supabase.co" not in url:
        status["message"] = "SUPABASE_URL does not look like a Supabase project URL."
        return status

    checks = {
        "app_alerts": check_supabase_table("app_alerts"),
        "update_runs": check_supabase_table("update_runs"),
        "daily_snapshots": check_supabase_table("daily_snapshots"),
    }
    status["tables"] = checks
    failed = {table: result for table, result in checks.items() if not result["ok"]}
    if failed:
        status["message"] = "Supabase env vars exist, but one or more tables cannot be read."
        return status

    status["ok"] = True
    status["message"] = "Supabase is connected and all required tables are readable."
    return status


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
    return {"alerts": [], "update_runs": []}


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
