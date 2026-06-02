from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def finite_float(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def pct(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return finite_float(value * 100, digits)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def as_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: as_jsonable(val) for key, val in value.items()}
    if isinstance(value, list):
        return [as_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [as_jsonable(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return finite_float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if not isinstance(value, (str, bytes)) and value is not None:
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
    return value
