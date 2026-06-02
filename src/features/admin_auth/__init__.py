from __future__ import annotations

import hmac
import os
from functools import wraps
from typing import Any, Callable

from flask import jsonify, redirect, request, session, url_for


ADMIN_SESSION_KEY = "market_oracle_admin"
ADMIN_USERNAME_KEY = "market_oracle_admin_username"


def get_admin_username() -> str:
    return os.getenv("ADMIN_USERNAME", "").strip()


def get_admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD", "")


def admin_credentials_ready() -> bool:
    return bool(get_admin_username() and get_admin_password())


def validate_admin_credentials(username: str, password: str) -> bool:
    expected_username = get_admin_username()
    expected_password = get_admin_password()
    if not expected_username or not expected_password:
        return False
    return hmac.compare_digest(username.strip(), expected_username) and hmac.compare_digest(password, expected_password)


def sign_in_admin(username: str) -> None:
    session.clear()
    session[ADMIN_SESSION_KEY] = True
    session[ADMIN_USERNAME_KEY] = username.strip()


def sign_out_admin() -> None:
    session.pop(ADMIN_SESSION_KEY, None)
    session.pop(ADMIN_USERNAME_KEY, None)


def is_admin_signed_in() -> bool:
    return session.get(ADMIN_SESSION_KEY) is True


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if is_admin_signed_in():
            return view(*args, **kwargs)

        if request.path.startswith("/api/"):
            return jsonify({"error": "Admin login required"}), 401

        next_url = request.full_path if request.query_string else request.path
        return redirect(url_for("admin_login", next=next_url))

    return wrapped
