from __future__ import annotations


def parse_error(error: Exception | str) -> str:
    if isinstance(error, str):
        return error
    if getattr(error, "message", None):
        return str(error.message)
    return str(error) or "An unexpected error occurred"
