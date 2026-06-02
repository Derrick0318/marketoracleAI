from __future__ import annotations

from typing import Any

from src.services.state_store_service import append_alert, list_alerts, mark_alert_read
from src.utils.number_utils import finite_float

ACTION_ALERTS = {"STRONG BUY", "BUY", "SELL / AVOID", "REDUCE"}


def get_alerts(limit: int = 80, unread_only: bool = False) -> list[dict[str, Any]]:
    response = list_alerts(limit=limit, unread_only=unread_only)
    if response.get("error"):
        raise ValueError(response["error"])
    return response["data"]


def read_alert(alert_id: str) -> dict[str, Any]:
    response = mark_alert_read(alert_id)
    if response.get("error"):
        raise ValueError(response["error"])
    return response["data"]


def create_admin_alert(title: str, body: str, level: str = "info", unique_key: str | None = None) -> dict[str, Any]:
    response = append_alert(
        {
            "type": "admin",
            "level": level,
            "title": title,
            "body": body,
            "source": "admin",
            "unique_key": unique_key,
        }
    )
    if response.get("error"):
        raise ValueError(response["error"])
    return response["data"]


def record_prediction_alert(result: dict[str, Any]) -> dict[str, Any] | None:
    action = result.get("action", "")
    if action not in ACTION_ALERTS:
        return None

    level = "buy" if "BUY" in action else "sell"
    predicted_move = finite_float(result.get("predicted_change_from_current_pct"), 2)
    confidence = finite_float(result.get("confidence_pct"), 1)
    move_text = f"{predicted_move:+.2f}%" if predicted_move is not None else "N/A"
    confidence_text = f"{confidence:.1f}%" if confidence is not None else "N/A"
    symbol = result["symbol"]
    unique_key = (
        f"signal:{symbol}:{action}:{result.get('latest_history_date')}:"
        f"{result.get('predicted_close')}:{confidence}"
    )
    response = append_alert(
        {
            "type": "signal",
            "level": level,
            "symbol": symbol,
            "market": result.get("market"),
            "action": action,
            "title": f"{symbol} {action}",
            "body": (
                f"{result.get('name')} triggered {action}. "
                f"Forecast move {move_text} with {confidence_text} confidence."
            ),
            "price": result.get("current_price"),
            "predicted_close": result.get("predicted_close"),
            "confidence_pct": confidence,
            "predicted_change_pct": predicted_move,
            "source": "prediction_model",
            "unique_key": unique_key,
        }
    )
    if response.get("error"):
        raise ValueError(response["error"])
    return response["data"]
