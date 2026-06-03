from __future__ import annotations

import threading
import time as time_module
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from src.features.daily_updates import run_daily_update, set_schedule_state

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
US_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ScheduledUpdateJob:
    key: str
    label: str
    reason: str
    markets: tuple[str, ...]
    timezone: ZoneInfo
    local_time: time
    weekday_only: bool = True


SCHEDULED_UPDATE_JOBS: tuple[ScheduledUpdateJob, ...] = (
    ScheduledUpdateJob(
        key="malaysia-open",
        label="Bursa Malaysia stock and ETF open scan",
        reason="scheduled_malaysia_open",
        markets=("malaysia", "malaysia_etf"),
        timezone=MY_TZ,
        local_time=time(9, 5),
    ),
    ScheduledUpdateJob(
        key="malaysia-close",
        label="Bursa Malaysia stock and ETF close scan",
        reason="scheduled_malaysia_close",
        markets=("malaysia", "malaysia_etf"),
        timezone=MY_TZ,
        local_time=time(17, 10),
    ),
    ScheduledUpdateJob(
        key="us-open",
        label="US stocks open scan",
        reason="scheduled_us_open",
        markets=("us",),
        timezone=US_TZ,
        local_time=time(9, 35),
    ),
    ScheduledUpdateJob(
        key="etf-open",
        label="US ETF open scan",
        reason="scheduled_etf_open",
        markets=("us_etf",),
        timezone=US_TZ,
        local_time=time(9, 45),
    ),
    ScheduledUpdateJob(
        key="us-close",
        label="US stocks close scan",
        reason="scheduled_us_close",
        markets=("us",),
        timezone=US_TZ,
        local_time=time(16, 10),
    ),
    ScheduledUpdateJob(
        key="etf-close",
        label="US ETF close scan",
        reason="scheduled_etf_close",
        markets=("us_etf",),
        timezone=US_TZ,
        local_time=time(16, 20),
    ),
    ScheduledUpdateJob(
        key="bitcoin-midnight",
        label="Bitcoin midnight scan",
        reason="scheduled_bitcoin_midnight",
        markets=("crypto",),
        timezone=MY_TZ,
        local_time=time(0, 0),
        weekday_only=False,
    ),
)

SCHEDULER_STARTED = False
SCHEDULER_LOCK = threading.Lock()


def start_daily_update_scheduler() -> None:
    global SCHEDULER_STARTED
    with SCHEDULER_LOCK:
        if SCHEDULER_STARTED:
            return
        SCHEDULER_STARTED = True

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()


def scheduler_loop() -> None:
    while True:
        upcoming = get_upcoming_jobs(limit=8)
        if not upcoming:
            time_module.sleep(300)
            continue

        next_event = upcoming[0]
        set_schedule_state(next_event=next_event, upcoming_events=upcoming)
        scheduled_at = datetime.fromisoformat(next_event["run_at_my_iso"])
        while datetime.now(MY_TZ) < scheduled_at:
            remaining = (scheduled_at - datetime.now(MY_TZ)).total_seconds()
            time_module.sleep(max(1, min(60, remaining)))

        job = get_scheduled_job(next_event["key"])
        if job:
            run_daily_update(reason=job.reason, markets=list(job.markets))


def get_scheduled_job(key: str) -> ScheduledUpdateJob | None:
    for job in SCHEDULED_UPDATE_JOBS:
        if job.key == key:
            return job
    return None


def get_upcoming_jobs(limit: int = 8, now: datetime | None = None) -> list[dict[str, Any]]:
    current = normalize_now(now)
    events = [format_schedule_event(job, next_run_for_job(job, current)) for job in SCHEDULED_UPDATE_JOBS]
    events.sort(key=lambda event: event["run_at_my_iso"])
    return events[:limit]


def get_due_jobs(now: datetime | None = None, tolerance_minutes: int = 12) -> list[ScheduledUpdateJob]:
    current = normalize_now(now)
    due = []
    for job in SCHEDULED_UPDATE_JOBS:
        job_now = current.astimezone(job.timezone)
        if job.weekday_only and job_now.weekday() >= 5:
            continue
        scheduled_today = datetime.combine(job_now.date(), job.local_time, tzinfo=job.timezone)
        minutes_after = (job_now - scheduled_today).total_seconds() / 60
        if 0 <= minutes_after <= tolerance_minutes:
            due.append(job)
    return due


def next_run_for_job(job: ScheduledUpdateJob, now: datetime | None = None) -> datetime:
    current = normalize_now(now).astimezone(job.timezone)
    for day_offset in range(0, 10):
        candidate_date = current.date() + timedelta(days=day_offset)
        if job.weekday_only and candidate_date.weekday() >= 5:
            continue
        candidate = datetime.combine(candidate_date, job.local_time, tzinfo=job.timezone)
        if candidate > current:
            return candidate
    return datetime.combine(current.date() + timedelta(days=10), job.local_time, tzinfo=job.timezone)


def format_schedule_event(job: ScheduledUpdateJob, run_at: datetime) -> dict[str, Any]:
    run_at_my = run_at.astimezone(MY_TZ)
    return {
        "key": job.key,
        "label": job.label,
        "reason": job.reason,
        "markets": list(job.markets),
        "run_at_my_iso": run_at_my.isoformat(),
        "run_at_exchange_iso": run_at.isoformat(),
        "my_time": run_at_my.strftime("%a, %d %b %Y %I:%M %p MYT"),
        "exchange_time": run_at.strftime("%a, %d %b %Y %I:%M %p %Z"),
    }


def normalize_now(now: datetime | None = None) -> datetime:
    current = now or datetime.now(MY_TZ)
    if current.tzinfo is None:
        return current.replace(tzinfo=MY_TZ)
    return current.astimezone(MY_TZ)
