"""Exercise the public password-authentication journey against a running API.

Run after starting the API and applying migrations:

    uv run python scripts/smoke_auth.py
"""

from __future__ import annotations

import argparse
import json
import secrets
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request_json(
    method: str,
    url: str,
    payload: Mapping[str, object] | None = None,
    access_token: str | None = None,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if access_token is not None:
        headers["Authorization"] = f"Bearer {access_token}"
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())
    except HTTPError as error:
        message = error.read().decode(errors="replace")
        raise RuntimeError(
            f"{method} {url} returned {error.code}: {message}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach {url}: {error.reason}") from error


def require_status(actual: int, expected: int, action: str) -> None:
    if actual != expected:
        raise RuntimeError(f"{action} returned {actual}; expected {expected}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    suffix = secrets.token_hex(6)
    email = f"smoke-{suffix}@example.com"
    password = "a-strong-smoke-password"

    status, registered = request_json(
        "POST",
        f"{base_url}/auth/register",
        {"username": f"smoke_{suffix}", "email": email, "password": password},
    )
    require_status(status, 201, "registration")

    status, logged_in = request_json(
        "POST", f"{base_url}/auth/login", {"email": email, "password": password}
    )
    require_status(status, 200, "login")

    status, user = request_json(
        "GET", f"{base_url}/auth/me", access_token=logged_in["access_token"]
    )
    require_status(status, 200, "protected current-user request")
    if user.get("email") != email:
        raise RuntimeError("current-user response did not match the registered account")

    status, refreshed = request_json(
        "POST",
        f"{base_url}/auth/refresh",
        {"refresh_token": registered["refresh_token"]},
    )
    require_status(status, 200, "refresh")

    status, _ = request_json(
        "POST",
        f"{base_url}/auth/logout",
        {"refresh_token": refreshed["refresh_token"]},
    )
    require_status(status, 200, "logout")
    print("Auth smoke journey passed: register -> login -> me -> refresh -> logout")


if __name__ == "__main__":
    main()
