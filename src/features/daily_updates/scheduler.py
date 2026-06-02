from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta

from src.features.daily_updates import run_daily_update, set_next_run_at

SCHEDULER_STARTED = False
SCHEDULER_LOCK = threading.Lock()


def next_midnight(now: datetime | None = None) -> datetime:
    current = now or datetime.now()
    tomorrow = current.date() + timedelta(days=1)
    return datetime.combine(tomorrow, datetime.min.time())


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
        scheduled_at = next_midnight()
        set_next_run_at(scheduled_at.isoformat(timespec="seconds"))
        while datetime.now() < scheduled_at:
            remaining = (scheduled_at - datetime.now()).total_seconds()
            time.sleep(max(1, min(60, remaining)))
        run_daily_update(reason="scheduled_midnight")
