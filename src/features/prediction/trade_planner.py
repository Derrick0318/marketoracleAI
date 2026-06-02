from __future__ import annotations

from typing import Any

from src.utils.number_utils import clamp, finite_float


def determine_action(predicted_change_pct: float, confidence: float, accuracy_pct: float, atr_pct: float, rsi: float) -> str:
    buy_threshold = max(0.55, min(2.5, atr_pct * 75))
    strong_buy_threshold = max(1.2, min(4.0, atr_pct * 120))
    sell_threshold = -max(0.65, min(2.75, atr_pct * 85))

    if predicted_change_pct >= strong_buy_threshold and confidence >= 68 and accuracy_pct >= 52 and rsi < 74:
        return "STRONG BUY"
    if predicted_change_pct >= buy_threshold and confidence >= 57 and rsi < 78:
        return "BUY"
    if predicted_change_pct <= sell_threshold and confidence >= 56:
        return "SELL / AVOID"
    if predicted_change_pct < -0.35:
        return "REDUCE"
    return "WATCH"


def compute_confidence(
    predicted_return: float,
    validation: dict[str, Any],
    atr_pct: float,
    agreement: float,
    sentiment_score: float,
    dispersion: float = 0,
) -> float:
    move_strength = clamp(abs(predicted_return) / max(validation["mae_pct"] / 100, atr_pct * 0.65, 0.006), 0, 1)
    accuracy_component = clamp((validation["direction_accuracy_pct"] - 47) / 18, 0, 1)
    stability_component = 1 - clamp(dispersion / max(validation["mae_pct"] / 100, atr_pct, 0.006), 0, 1)
    confidence = 34 + (31 * move_strength) + (22 * accuracy_component) + (10 * agreement) + (8 * stability_component)
    confidence += clamp(sentiment_score * (1 if predicted_return >= 0 else -1) * 5, -5, 5)
    return clamp(confidence, 5, 95)


def compute_score(
    predicted_change_pct: float,
    confidence: float,
    validation: dict[str, Any],
    trend_score: int,
    sentiment_score: float,
    atr_pct: float,
) -> float:
    return (
        predicted_change_pct * 3.2
        + confidence * 0.35
        + (validation["direction_accuracy_pct"] - 50) * 0.42
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
) -> list[str]:
    notes = [f"Next-close model forecast: {predicted_return_pct:+.2f}%."]
    notes.append("Trend stack is bullish." if trend_score >= 2 else "Trend stack is weak." if trend_score <= -2 else "Trend stack is mixed.")
    notes.append("RSI is hot." if rsi >= 72 else "RSI is near oversold." if rsi <= 35 else "RSI is balanced.")
    notes.append(f"Backtest direction accuracy: {validation['direction_accuracy_pct']:.1f}% across {validation['rows']} validation days.")
    notes.append(f"Model agreement: {agreement * 100:.0f}%. News sentiment overlay is {sentiment['label']}.")
    return notes
