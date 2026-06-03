from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from src.features.market_status import get_market_status
from src.features.prediction.trade_planner import (
    build_signal_notes,
    build_trade_plan,
    compute_confidence,
    compute_score,
    determine_action,
)
from src.services.market_data_service import get_current_price
from src.utils.number_utils import finite_float, pct
from src.utils.symbol_utils import infer_currency


def build_prediction_result(
    symbol: str,
    meta: dict[str, str],
    history: pd.DataFrame,
    fast_info: dict[str, Any],
    features: pd.DataFrame,
    atr_series: pd.Series,
    model_output: dict[str, Any],
    news_payload: dict[str, Any],
) -> dict[str, Any]:
    close = history["model_close"]
    latest_close = float(close.iloc[-1])
    current_price = get_current_price(fast_info, latest_close)
    currency = infer_currency(symbol, fast_info)
    predicted_return = float(model_output["predicted_return"])
    predicted_close = latest_close * (1 + predicted_return)
    predicted_change_vs_current = (predicted_close / current_price) - 1
    context = build_market_context(history, features, atr_series)

    sentiment = news_payload["sentiment"]
    validation = model_output["validation"]
    confidence = compute_confidence(
        predicted_return=predicted_return,
        validation=validation,
        atr_pct=context["atr_pct"],
        agreement=model_output["agreement"],
        sentiment_score=float(sentiment["score"] or 0),
        dispersion=float(model_output.get("dispersion") or 0),
    )
    predicted_change_pct = predicted_change_vs_current * 100
    action = determine_action(predicted_change_pct, confidence, validation["direction_accuracy_pct"], context["atr_pct"], context["rsi"])
    trade_plan = build_trade_plan(action, current_price, predicted_close, context["support"], context["resistance"], context["atr"], currency)
    risk_reward = calculate_risk_reward(current_price, trade_plan)
    latest_date = pd.Timestamp(history.index[-1]).strftime("%Y-%m-%d")
    horizon_label = f"Next close after {latest_date}"
    score = compute_score(predicted_change_pct, confidence, validation, context["trend_score"], float(sentiment["score"] or 0), context["atr_pct"])

    return {
        "symbol": symbol,
        "name": meta["name"],
        "market": meta["market"],
        "currency": currency,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "latest_history_date": latest_date,
        "target": "Predicted next regular-session closing price",
        "target_horizon": horizon_label,
        "current_price": finite_float(current_price, 4),
        "latest_model_close": finite_float(latest_close, 4),
        "predicted_close": finite_float(predicted_close, 4),
        "predicted_return_from_latest_close_pct": pct(predicted_return),
        "predicted_change_from_current_pct": finite_float(predicted_change_pct, 2),
        "direction": "UP" if predicted_change_vs_current >= 0 else "DOWN",
        "action": action,
        "confidence_pct": finite_float(confidence, 1),
        "score": finite_float(score, 2),
        "risk_reward": finite_float(risk_reward, 2),
        "risk": build_risk_payload(context),
        "trade_plan": trade_plan,
        "validation": format_validation(validation),
        "models": model_output["models"],
        "model_name": model_output.get("model_label", "Gradient Boosting + Random Forest Ensemble"),
        "model_profile": model_output.get("profile", "full"),
        "model_agreement_pct": finite_float(model_output["agreement"] * 100, 1),
        "model_dispersion_pct": finite_float(float(model_output.get("dispersion") or 0) * 100, 3),
        "sentiment": sentiment,
        "market_status": get_market_status(symbol),
        "news": news_payload,
        "signals": build_signal_notes(predicted_return * 100, context["rsi"], context["trend_score"], sentiment, validation, model_output["agreement"]),
        "chart": build_chart_payload(history, predicted_close, horizon_label),
    }


def build_market_context(history: pd.DataFrame, features: pd.DataFrame, atr_series: pd.Series) -> dict[str, Any]:
    close = history["model_close"]
    latest_close = float(close.iloc[-1])
    latest_features = features.tail(1).iloc[0]
    rsi = float(latest_features.get("rsi_14", 50)) if pd.notna(latest_features.get("rsi_14", 50)) else 50
    atr = float(atr_series.dropna().iloc[-1]) if not atr_series.dropna().empty else latest_close * 0.02
    sma20 = close.rolling(20).mean().iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    sma100 = close.rolling(100).mean().iloc[-1]
    trend_score = (1 if latest_close > sma20 else -1) + (1 if sma20 > sma50 else -1) + (1 if sma50 > sma100 else -1)
    return {
        "rsi": rsi,
        "atr": atr,
        "atr_pct": atr / latest_close if latest_close else 0.02,
        "support": float(history["low"].rolling(20).min().dropna().iloc[-1]),
        "resistance": float(history["high"].rolling(20).max().dropna().iloc[-1]),
        "trend_score": trend_score,
    }


def calculate_risk_reward(current_price: float, trade_plan: dict[str, Any]) -> float | None:
    if not trade_plan["stop_loss"] or current_price <= trade_plan["stop_loss"]:
        return None
    risk = current_price - trade_plan["stop_loss"]
    reward = trade_plan["take_profit"] - current_price
    return reward / risk if risk > 0 else None


def build_risk_payload(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "atr": finite_float(context["atr"], 4),
        "atr_pct": pct(context["atr_pct"]),
        "support_20d": finite_float(context["support"], 4),
        "resistance_20d": finite_float(context["resistance"], 4),
        "rsi_14": finite_float(context["rsi"], 1),
    }


def format_validation(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "rows": validation["rows"],
        "mae_pct": finite_float(validation["mae_pct"], 2),
        "rmse_pct": finite_float(validation["rmse_pct"], 2),
        "direction_accuracy_pct": finite_float(validation["direction_accuracy_pct"], 1),
    }


def build_chart_payload(history: pd.DataFrame, predicted_close: float, horizon_label: str) -> dict[str, Any]:
    tail = history.tail(90)
    return {
        "dates": [pd.Timestamp(index).strftime("%Y-%m-%d") for index in tail.index],
        "open": [finite_float(value, 4) for value in tail["open"].tolist()],
        "high": [finite_float(value, 4) for value in tail["high"].tolist()],
        "low": [finite_float(value, 4) for value in tail["low"].tolist()],
        "close": [finite_float(value, 4) for value in tail["model_close"].tolist()],
        "prediction": {"label": horizon_label, "price": finite_float(predicted_close, 4)},
    }


def compact_result(result: dict[str, Any]) -> dict[str, Any]:
    compact = dict(result)
    compact.pop("chart", None)
    compact.pop("models", None)
    compact["news"] = {
        "count": len(result["news"]["items"]),
        "sources": result["news"]["sources"],
        "errors": result["news"]["errors"],
    }
    return compact
