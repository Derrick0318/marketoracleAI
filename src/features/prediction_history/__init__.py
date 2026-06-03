from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd

from src.services.market_data_service import fetch_bulk_market_histories
from src.services.state_store_service import append_prediction_records, list_prediction_records, update_prediction_record
from src.utils.number_utils import finite_float


def store_scan_predictions(scan_payload: dict[str, Any], reason: str = "daily_update") -> dict[str, Any]:
    records = [build_prediction_record(result, reason) for result in scan_payload.get("results", [])]
    records = [record for record in records if record]
    response = append_prediction_records(records)
    return {"stored_count": len(response.get("data") or records), "error": response.get("error")}


def build_prediction_record(result: dict[str, Any], reason: str) -> dict[str, Any] | None:
    symbol = result.get("symbol")
    target_after_date = result.get("latest_history_date")
    if not symbol or not target_after_date:
        return None

    generated_at = result.get("generated_at") or datetime.now().isoformat(timespec="seconds")
    prediction_date = parse_date(generated_at) or datetime.now().date().isoformat()
    unique_key = f"{symbol}:{target_after_date}"
    return {
        "unique_key": unique_key,
        "prediction_date": prediction_date,
        "generated_at": generated_at,
        "symbol": symbol,
        "name": result.get("name"),
        "market": result.get("market"),
        "action": result.get("action"),
        "direction": result.get("direction"),
        "current_price": result.get("current_price"),
        "latest_model_close": result.get("latest_model_close"),
        "predicted_close": result.get("predicted_close"),
        "predicted_change_pct": result.get("predicted_change_from_current_pct"),
        "confidence_pct": result.get("confidence_pct"),
        "model_profile": result.get("model_profile", "fast"),
        "model_name": result.get("model_name"),
        "target_after_date": target_after_date,
        "evaluation_status": "pending",
        "metadata": {
            "reason": reason,
            "target_horizon": result.get("target_horizon"),
            "forecast_window": result.get("forecast_window"),
            "direction_probability_up_pct": result.get("direction_probability_up_pct"),
            "direction_probability_down_pct": result.get("direction_probability_down_pct"),
            "validation": result.get("validation"),
            "risk": result.get("risk"),
            "risk_reward": result.get("risk_reward"),
        },
    }


def evaluate_pending_predictions(days: int = 14) -> dict[str, Any]:
    response = list_prediction_records(days=days, limit=1000, status="pending")
    if response.get("error"):
        return {"evaluated_count": 0, "correct_count": 0, "pending_count": 0, "errors": [response["error"]]}

    records = response.get("data") or []
    symbols = sorted({record["symbol"] for record in records if record.get("symbol")})
    histories = fetch_bulk_market_histories(symbols) if symbols else {}
    evaluated_count = 0
    correct_count = 0
    errors: list[str] = []

    for record in records:
        symbol = record.get("symbol")
        unique_key = record.get("unique_key")
        history_response = histories.get(symbol or "")
        if not symbol or not unique_key or not history_response:
            continue
        if history_response.get("error"):
            errors.append(f"{symbol}: {history_response['error']}")
            continue

        evaluation = evaluate_record_against_history(record, history_response["data"]["history"])
        if not evaluation:
            continue

        update_response = update_prediction_record(unique_key, evaluation)
        if update_response.get("error"):
            errors.append(f"{symbol}: {update_response['error']}")
            continue

        evaluated_count += 1
        if evaluation["direction_correct"]:
            correct_count += 1

    return {
        "evaluated_count": evaluated_count,
        "correct_count": correct_count,
        "pending_count": max(0, len(records) - evaluated_count),
        "errors": errors[:12],
    }


def evaluate_record_against_history(record: dict[str, Any], history: pd.DataFrame) -> dict[str, Any] | None:
    target_after_date = parse_date(record.get("target_after_date"))
    if not target_after_date:
        return None

    future_rows = history[history.index.map(lambda index: pd.Timestamp(index).date().isoformat() > target_after_date)]
    if future_rows.empty:
        return None

    target_date = pd.Timestamp(future_rows.index[0]).date().isoformat()
    actual_close = float(future_rows["model_close"].iloc[0])
    base_price = numeric(record.get("current_price")) or numeric(record.get("latest_model_close"))
    predicted_close = numeric(record.get("predicted_close"))
    if not base_price or not predicted_close:
        return None

    actual_change_pct = ((actual_close / base_price) - 1) * 100
    actual_direction = "UP" if actual_change_pct >= 0 else "DOWN"
    direction_correct = actual_direction == record.get("direction")
    price_error = actual_close - predicted_close
    price_error_pct = abs(price_error / actual_close) * 100 if actual_close else None
    return {
        "target_date": target_date,
        "actual_close": finite_float(actual_close, 4),
        "actual_change_pct": finite_float(actual_change_pct, 2),
        "actual_direction": actual_direction,
        "direction_correct": direction_correct,
        "price_error": finite_float(price_error, 4),
        "price_error_pct": finite_float(price_error_pct, 2),
        "evaluation_status": "correct" if direction_correct else "wrong",
        "evaluated_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_prediction_accuracy_report(days: int = 10) -> dict[str, Any]:
    response = list_prediction_records(days=days, limit=1000)
    if response.get("error"):
        return empty_report(days, response["error"])

    records = response.get("data") or []
    evaluated = [record for record in records if record.get("direction_correct") is not None]
    correct = [record for record in evaluated if record.get("direction_correct") is True]
    pending = [record for record in records if record.get("evaluation_status") == "pending"]
    errors = [numeric(record.get("price_error_pct")) for record in evaluated if numeric(record.get("price_error_pct")) is not None]
    return {
        "days": days,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "record_count": len(records),
        "evaluated_count": len(evaluated),
        "correct_count": len(correct),
        "wrong_count": len(evaluated) - len(correct),
        "pending_count": len(pending),
        "accuracy_pct": finite_float((len(correct) / len(evaluated)) * 100, 1) if evaluated else None,
        "avg_price_error_pct": finite_float(sum(errors) / len(errors), 2) if errors else None,
        "daily": build_daily_summary(records),
        "records": records[:160],
        "error": None,
    }


def run_prediction_audit(days: int = 10) -> dict[str, Any]:
    evaluation = evaluate_pending_predictions(days=max(days + 5, 14))
    report = build_prediction_accuracy_report(days=days)
    report["evaluation"] = evaluation
    return report


def build_daily_summary(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("prediction_date") or "Unknown")].append(record)

    summary = []
    for day, day_records in sorted(grouped.items(), reverse=True):
        evaluated = [record for record in day_records if record.get("direction_correct") is not None]
        correct = [record for record in evaluated if record.get("direction_correct") is True]
        summary.append(
            {
                "date": day,
                "record_count": len(day_records),
                "evaluated_count": len(evaluated),
                "correct_count": len(correct),
                "pending_count": len([record for record in day_records if record.get("evaluation_status") == "pending"]),
                "accuracy_pct": finite_float((len(correct) / len(evaluated)) * 100, 1) if evaluated else None,
            }
        )
    return summary[:10]


def empty_report(days: int, error: str | None = None) -> dict[str, Any]:
    return {
        "days": days,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "record_count": 0,
        "evaluated_count": 0,
        "correct_count": 0,
        "wrong_count": 0,
        "pending_count": 0,
        "accuracy_pct": None,
        "avg_price_error_pct": None,
        "daily": [],
        "records": [],
        "error": error,
    }


def parse_date(value: Any) -> str | None:
    if not value:
        return None
    try:
        return pd.Timestamp(value).date().isoformat()
    except Exception:
        return None


def numeric(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed
