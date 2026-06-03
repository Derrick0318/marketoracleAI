from __future__ import annotations

from typing import Any

from src.features.prediction import analyze_symbol
from src.utils.symbol_utils import clean_symbol


def answer_market_question(symbol: str, question: str, language: str = "en") -> dict[str, Any]:
    clean = clean_symbol(symbol or "")
    if not clean:
        return {"error": "Choose a stock first."}

    lang = "zh" if str(language).lower().startswith("zh") else "en"
    data = analyze_symbol(clean, refresh=False, include_news=True, record_alert=False, fast_model=False)
    answer = build_chinese_answer(data, question) if lang == "zh" else build_english_answer(data, question)
    return {
        "symbol": data["symbol"],
        "name": data["name"],
        "language": lang,
        "question": question,
        "answer": answer,
        "action": data["action"],
        "confidence_pct": data["confidence_pct"],
        "generated_at": data["generated_at"],
    }


def build_english_answer(data: dict[str, Any], question: str) -> str:
    verdict = english_verdict(data["action"])
    price = format_price(data["current_price"], data["currency"])
    predicted = format_price(data["predicted_close"], data["currency"])
    move = signed_pct(data["predicted_change_from_current_pct"])
    confidence = data.get("confidence_pct") or 0
    validation = (data.get("validation") or {}).get("direction_accuracy_pct") or 0
    classifier_accuracy = (data.get("validation") or {}).get("classifier_direction_accuracy_pct") or validation
    forecast = data.get("forecast_window") or {}
    plan = data.get("trade_plan") or {}
    risk = data.get("risk") or {}
    signals = data.get("signals") or []
    sentiment = ((data.get("sentiment") or {}).get("label") or "neutral").lower()

    lines = [
        f"For {data['name']} ({data['symbol']}), the model says: {verdict}",
        f"Now: {price}. Predicted next regular-session close: {predicted} ({data['direction']} {move}). Confidence: {confidence:.1f}%, backtest direction accuracy: {validation:.1f}%, classifier accuracy: {classifier_accuracy:.1f}%.",
        f"Timing window: {forecast.get('horizon_text', 'No duration estimate available.')} Probability UP {data.get('direction_probability_up_pct', 50):.1f}%, DOWN {data.get('direction_probability_down_pct', 50):.1f}%.",
        buy_sentence(data["action"], plan),
        f"Sell/exit plan: {plan.get('sell_text', 'No sell plan available.')}",
        f"Risk check: RSI {risk.get('rsi_14', 'N/A')}, ATR {risk.get('atr_pct', 'N/A')}%, news sentiment {sentiment}.",
    ]
    if question:
        lines.append(f"Your question was: {question.strip()}")
    if signals:
        lines.append(f"Why: {' '.join(signals[:3])}")
    lines.append("Use this as research only, not personal financial advice. Confirm market status, volume, news, and your own risk limit before buying.")
    return "\n\n".join(lines)


def build_chinese_answer(data: dict[str, Any], question: str) -> str:
    verdict = chinese_verdict(data["action"])
    price = format_price(data["current_price"], data["currency"])
    predicted = format_price(data["predicted_close"], data["currency"])
    move = signed_pct(data["predicted_change_from_current_pct"])
    confidence = data.get("confidence_pct") or 0
    validation = (data.get("validation") or {}).get("direction_accuracy_pct") or 0
    classifier_accuracy = (data.get("validation") or {}).get("classifier_direction_accuracy_pct") or validation
    forecast = data.get("forecast_window") or {}
    plan = data.get("trade_plan") or {}
    risk = data.get("risk") or {}
    sentiment = chinese_sentiment((data.get("sentiment") or {}).get("label"))
    signals = translate_signal_notes(data.get("signals") or [])

    buy_plan, sell_plan = chinese_plan_sentences(data["action"], plan, data["currency"])
    duration = forecast.get("estimated_days", "N/A")
    day_unit = "天" if forecast.get("day_unit") == "calendar day" else "个交易日"
    direction_text = "上涨" if forecast.get("direction") == "UP" else "下跌"
    lines = [
        f"关于 {data['name']}（{data['symbol']}），模型结论：{verdict}",
        f"当前价格：{price}。预测下一个正常交易日收盘价：{predicted}（{data['direction']} {move}）。信心：{confidence:.1f}%，方向回测准确率：{validation:.1f}%。",
        f"预测时间：大约 {duration} {day_unit}{direction_text}；上涨概率 {data.get('direction_probability_up_pct', 50):.1f}%，下跌概率 {data.get('direction_probability_down_pct', 50):.1f}%，分类器准确率 {classifier_accuracy:.1f}%。",
        buy_plan,
        sell_plan,
        f"风险检查：RSI {risk.get('rsi_14', 'N/A')}，ATR {risk.get('atr_pct', 'N/A')}%，新闻情绪：{sentiment}。",
    ]
    if question:
        lines.append(f"你的问题：{question.strip()}")
    if signals:
        lines.append(f"原因：{' '.join(signals[:3])}")
    lines.append("这只是研究参考，不是个人投资建议。买入前请再确认市场是否开盘、成交量、最新新闻和你自己的风险承受能力。")
    return "\n\n".join(lines)


def english_verdict(action: str) -> str:
    if action == "STRONG BUY":
        return "can buy only with risk control; signal is strong."
    if action == "BUY":
        return "can buy, preferably near the buy zone or on confirmed strength."
    if action in {"SELL / AVOID", "REDUCE"}:
        return "do not buy now; risk is elevated."
    return "wait/watch; do not rush the buy."


def buy_sentence(action: str, plan: dict[str, Any]) -> str:
    buy_text = plan.get("buy_text", "No buy plan available.")
    if action in {"BUY", "STRONG BUY"}:
        return f"Buy timing: {buy_text}"
    if action in {"SELL / AVOID", "REDUCE"}:
        return f"Buy timing: not attractive now. {buy_text}"
    return f"Buy timing: wait for confirmation. {buy_text}"


def chinese_verdict(action: str) -> str:
    return {
        "STRONG BUY": "可以考虑买入，但一定要控制风险",
        "BUY": "可以买入/关注买点",
        "WATCH": "等待观察，暂时不要急",
        "SELL / AVOID": "现在不适合买入",
        "REDUCE": "偏弱，建议避免新买入或减仓",
    }.get(action, action)


def chinese_buy_sentence(action: str, plan: dict[str, Any]) -> str:
    buy_text = plan.get("buy_text", "暂时没有买入计划。")
    if action in {"BUY", "STRONG BUY"}:
        return f"买入时机：{buy_text}"
    if action in {"SELL / AVOID", "REDUCE"}:
        return f"买入时机：现在不理想。{buy_text}"
    return f"买入时机：先等待确认。{buy_text}"


def chinese_plan_sentences(action: str, plan: dict[str, Any], currency: str) -> tuple[str, str]:
    entry_low = format_price(plan.get("entry_low"), currency)
    entry_high = format_price(plan.get("entry_high"), currency)
    breakout = format_price(plan.get("breakout_entry"), currency)
    stop = format_price(plan.get("stop_loss"), currency)
    target = format_price(plan.get("take_profit"), currency)
    if action in {"BUY", "STRONG BUY"}:
        buy = f"买入时机：可以等回调到 {entry_low}-{entry_high}，或放量突破 {breakout} 后再买。"
    elif action in {"SELL / AVOID", "REDUCE"}:
        buy = f"买入时机：现在不理想，至少等价格重新站上 {breakout} 后再考虑。"
    else:
        buy = f"买入时机：先观察 {entry_low}-{entry_high} 区域，突破 {breakout} 后信号会更好。"
    sell = f"卖出/止盈计划：目标可看 {target} 附近；若跌破 {stop}，要控制风险。"
    return buy, sell


def chinese_sentiment(label: str | None) -> str:
    return {"positive": "偏正面", "negative": "偏负面", "neutral": "中性"}.get(str(label or "").lower(), "中性")


def translate_signal_notes(signals: list[str]) -> list[str]:
    translated = []
    for signal in signals:
        translated.append(
            signal.replace("Next-close model forecast:", "下一个收盘模型预测：")
            .replace("Trend stack is bullish.", "趋势偏强。")
            .replace("Trend stack is weak.", "趋势偏弱。")
            .replace("Trend stack is mixed.", "趋势混合。")
            .replace("RSI is hot.", "RSI 偏高。")
            .replace("RSI is near oversold.", "RSI 接近超卖。")
            .replace("RSI is balanced.", "RSI 平衡。")
            .replace("Backtest direction accuracy:", "方向回测准确率：")
            .replace("Model agreement:", "模型一致性：")
            .replace("News sentiment overlay is", "新闻情绪为")
        )
    return translated


def format_price(value: Any, currency: str) -> str:
    try:
        return f"{float(value):,.4f} {currency}"
    except (TypeError, ValueError):
        return f"N/A {currency}"


def signed_pct(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"
