from __future__ import annotations

from typing import Any

from src.utils.number_utils import clamp, finite_float


def determine_action(
    predicted_change_pct: float,
    confidence: float,
    accuracy_pct: float,
    atr_pct: float,
    rsi: float,
    direction_probability_up: float | None = None,
    classifier_accuracy_pct: float | None = None,
) -> str:
    buy_threshold = max(0.55, min(2.5, atr_pct * 75))
    strong_buy_threshold = max(1.2, min(4.0, atr_pct * 120))
    sell_threshold = -max(0.65, min(2.75, atr_pct * 85))
    up_probability = 0.5 if direction_probability_up is None else float(direction_probability_up)
    direction_accuracy = classifier_accuracy_pct if classifier_accuracy_pct is not None else accuracy_pct

    if predicted_change_pct >= strong_buy_threshold and confidence >= 70 and accuracy_pct >= 52 and direction_accuracy >= 51 and up_probability >= 0.58 and rsi < 74:
        return "STRONG BUY"
    if predicted_change_pct >= buy_threshold and confidence >= 59 and direction_accuracy >= 50 and up_probability >= 0.53 and rsi < 78:
        return "BUY"
    if predicted_change_pct <= sell_threshold and confidence >= 58 and direction_accuracy >= 50 and up_probability <= 0.47:
        return "SELL / AVOID"
    if predicted_change_pct < -0.35 and up_probability <= 0.51:
        return "REDUCE"
    return "WATCH"


def compute_confidence(
    predicted_return: float,
    validation: dict[str, Any],
    atr_pct: float,
    agreement: float,
    sentiment_score: float,
    dispersion: float = 0,
    direction_probability_up: float | None = None,
    classifier_accuracy_pct: float | None = None,
    high_confidence_accuracy_pct: float | None = None,
    high_confidence_count: int | None = None,
) -> float:
    move_strength = clamp(abs(predicted_return) / max(validation["mae_pct"] / 100, atr_pct * 0.65, 0.006), 0, 1)
    accuracy_component = clamp((validation["direction_accuracy_pct"] - 47) / 18, 0, 1)
    classifier_accuracy = classifier_accuracy_pct if classifier_accuracy_pct is not None else validation.get("classifier_direction_accuracy_pct")
    classifier_component = clamp(((classifier_accuracy or validation["direction_accuracy_pct"]) - 48) / 18, 0, 1)
    stability_component = 1 - clamp(dispersion / max(validation["mae_pct"] / 100, atr_pct, 0.006), 0, 1)
    up_probability = 0.5 if direction_probability_up is None else float(direction_probability_up)
    aligned_probability = up_probability if predicted_return >= 0 else 1 - up_probability
    probability_component = clamp((aligned_probability - 0.5) / 0.18, 0, 1)
    high_confidence_component = 0
    if high_confidence_count and high_confidence_count >= 8 and high_confidence_accuracy_pct is not None:
        high_confidence_component = clamp((high_confidence_accuracy_pct - 52) / 20, -0.4, 1)

    confidence = (
        30
        + (27 * move_strength)
        + (16 * accuracy_component)
        + (14 * classifier_component)
        + (12 * probability_component)
        + (7 * agreement)
        + (7 * stability_component)
        + (5 * high_confidence_component)
    )
    if aligned_probability < 0.5:
        confidence -= clamp((0.5 - aligned_probability) * 120, 0, 9)
    confidence += clamp(sentiment_score * (1 if predicted_return >= 0 else -1) * 5, -5, 5)
    return clamp(confidence, 5, 94)


def compute_score(
    predicted_change_pct: float,
    confidence: float,
    validation: dict[str, Any],
    trend_score: int,
    sentiment_score: float,
    atr_pct: float,
    direction_probability_up: float | None = None,
) -> float:
    up_probability = 0.5 if direction_probability_up is None else float(direction_probability_up)
    direction_edge = (up_probability - 0.5) if predicted_change_pct >= 0 else (0.5 - up_probability)
    return (
        predicted_change_pct * 3.2
        + confidence * 0.35
        + (validation["direction_accuracy_pct"] - 50) * 0.42
        + direction_edge * 28
        + (trend_score * 2.2)
        + (sentiment_score * 3.5)
        - min(12, atr_pct * 180)
    )


def build_trade_plan(
    action: str,
    current_price: float,
    predicted_close: float,
    support: float,
    resistance: float,
    atr: float,
    currency: str,
) -> dict[str, Any]:
    safe_atr = max(atr, current_price * 0.008)
    stop_loss = max(0.01, current_price - (1.45 * safe_atr))
    entry_low = max(0.01, min(support, current_price - (0.75 * safe_atr)))
    entry_high = max(entry_low, min(current_price, current_price - (0.15 * safe_atr)))
    breakout_entry = resistance + (0.1 * safe_atr)
    take_profit = max(predicted_close, resistance, current_price + (2 * (current_price - stop_loss)))

    if action in {"BUY", "STRONG BUY"}:
        buy_text = f"Wait for {entry_low:.2f}-{entry_high:.2f} {currency}, or buy strength above {breakout_entry:.2f} {currency}."
        sell_text = f"Take profit near {take_profit:.2f} {currency}; cut risk below {stop_loss:.2f} {currency}."
    elif action in {"SELL / AVOID", "REDUCE"}:
        buy_text = f"Avoid new buys until price reclaims {breakout_entry:.2f} {currency} with volume."
        sell_text = f"Reduce on rebounds toward {resistance:.2f} {currency}; risk is elevated below {stop_loss:.2f} {currency}."
    else:
        buy_text = f"Watch {entry_low:.2f}-{entry_high:.2f} {currency}; confirmation improves above {breakout_entry:.2f} {currency}."
        sell_text = f"Trim strength near {take_profit:.2f} {currency}; defensive stop below {stop_loss:.2f} {currency}."

    return {
        "buy_text": buy_text,
        "sell_text": sell_text,
        "entry_low": finite_float(entry_low, 4),
        "entry_high": finite_float(entry_high, 4),
        "breakout_entry": finite_float(breakout_entry, 4),
        "stop_loss": finite_float(stop_loss, 4),
        "take_profit": finite_float(take_profit, 4),
    }


def build_signal_notes(
    predicted_return_pct: float,
    rsi: float,
    trend_score: int,
    sentiment: dict[str, Any],
    validation: dict[str, Any],
    agreement: float,
    direction_probability_up: float | None = None,
    forecast_window: dict[str, Any] | None = None,
) -> list[str]:
    notes = [f"Next-close model forecast: {predicted_return_pct:+.2f}%."]
    if direction_probability_up is not None:
        notes.append(f"Direction classifier probability: UP {direction_probability_up * 100:.1f}%, DOWN {(1 - direction_probability_up) * 100:.1f}%.")
    notes.append("Trend stack is bullish." if trend_score >= 2 else "Trend stack is weak." if trend_score <= -2 else "Trend stack is mixed.")
    notes.append("RSI is hot." if rsi >= 72 else "RSI is near oversold." if rsi <= 35 else "RSI is balanced.")
    notes.append(f"Backtest direction accuracy: {validation['direction_accuracy_pct']:.1f}% across {validation['rows']} validation days.")
    if validation.get("classifier_direction_accuracy_pct") is not None:
        notes.append(f"Direction classifier backtest: {validation['classifier_direction_accuracy_pct']:.1f}%.")
    if validation.get("rolling_classifier_accuracy_pct") is not None:
        notes.append(f"Rolling time-split classifier accuracy: {validation['rolling_classifier_accuracy_pct']:.1f}%.")
    if forecast_window:
        notes.append(f"{forecast_window.get('horizon_text', '')}")
    notes.append(f"Model agreement: {agreement * 100:.0f}%. News sentiment overlay is {sentiment['label']}.")
    return notes
