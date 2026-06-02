from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.utils.symbol_utils import infer_market

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
US_TZ = ZoneInfo("America/New_York")


def get_market_status(symbol: str, now: datetime | None = None) -> dict[str, Any]:
    market = infer_market(symbol)
    current_my = (now or datetime.now(tz=MY_TZ)).astimezone(MY_TZ)
    if market == "Crypto":
        return build_crypto_status(current_my)
    if market == "Malaysia":
        return build_session_status(
            market="Malaysia",
            exchange="Bursa Malaysia",
            timezone=MY_TZ,
            current_my=current_my,
            sessions=[(time(9, 0), time(12, 30)), (time(14, 30), time(17, 0))],
            hours_label="9:00 AM-12:30 PM and 2:30 PM-5:00 PM MYT",
            source_note="Regular Bursa equity session estimate; public holidays, special sessions, and trading halts are not checked.",
        )
    return build_session_status(
        market="US",
        exchange="NYSE/Nasdaq",
        timezone=US_TZ,
        current_my=current_my,
        sessions=[(time(9, 30), time(16, 0))],
        hours_label="9:30 AM-4:00 PM New York time",
        source_note="Regular US equity core session estimate; exchange holidays, early closes, and trading halts are not checked.",
    )


def build_crypto_status(current_my: datetime) -> dict[str, Any]:
    return {
        "market": "Crypto",
        "exchange": "Crypto spot market",
        "is_open": True,
        "session": "24/7",
        "status_label": "OPEN",
        "note": "Bitcoin trades 24/7. Liquidity can still change sharply around major market sessions and news.",
        "my_time": format_dt(current_my),
        "exchange_time": format_dt(current_my),
        "exchange_timezone": "Asia/Kuala_Lumpur",
        "regular_hours": "24 hours daily",
        "next_event_label": "Always open",
        "next_event_my_time": None,
        "next_event_exchange_time": None,
        "next_event_my_iso": None,
        "next_event_exchange_iso": None,
    }


def build_session_status(
    market: str,
    exchange: str,
    timezone: ZoneInfo,
    current_my: datetime,
    sessions: list[tuple[time, time]],
    hours_label: str,
    source_note: str,
) -> dict[str, Any]:
    exchange_now = current_my.astimezone(timezone)
    is_open = is_weekday(exchange_now.date()) and any(is_within_session(exchange_now, start, end) for start, end in sessions)
    next_label, next_event = find_next_event(exchange_now, sessions, is_open)
    event_my = next_event.astimezone(MY_TZ) if next_event else None

    return {
        "market": market,
        "exchange": exchange,
        "is_open": is_open,
        "session": "Regular session" if is_open else "Closed",
        "status_label": "OPEN" if is_open else "CLOSED",
        "note": source_note,
        "my_time": format_dt(current_my),
        "exchange_time": format_dt(exchange_now),
        "exchange_timezone": str(timezone),
        "regular_hours": hours_label,
        "next_event_label": next_label,
        "next_event_my_time": format_dt(event_my) if event_my else None,
        "next_event_exchange_time": format_dt(next_event) if next_event else None,
        "next_event_my_iso": event_my.isoformat() if event_my else None,
        "next_event_exchange_iso": next_event.isoformat() if next_event else None,
    }


def is_weekday(value: date) -> bool:
    return value.weekday() < 5


def is_within_session(value: datetime, start: time, end: time) -> bool:
    return start <= value.time() < end


def find_next_event(exchange_now: datetime, sessions: list[tuple[time, time]], is_open: bool) -> tuple[str, datetime | None]:
    if is_open:
        for _, end in sessions:
            close_dt = exchange_now.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
            if exchange_now < close_dt:
                return "Closes", close_dt

    for day_offset in range(0, 8):
        candidate_date = exchange_now.date() + timedelta(days=day_offset)
        if not is_weekday(candidate_date):
            continue
        for start, _ in sessions:
            open_dt = datetime.combine(candidate_date, start, tzinfo=exchange_now.tzinfo)
            if open_dt > exchange_now:
                return "Opens", open_dt
    return "Next session unavailable", None


def format_dt(value: datetime) -> str:
    return value.strftime("%a, %d %b %Y %I:%M %p %Z")
