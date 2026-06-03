from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ktl_backend.config import load_backend_env

load_backend_env()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


def google_oauth_configured() -> bool:
    return bool((os.getenv("GOOGLE_CLIENT_ID") or "").strip() and (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip())


def build_authorize_url(*, redirect_uri: str, state: str) -> str:
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{_GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(*, code: str, redirect_uri: str) -> dict[str, Any]:
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    body = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        _GOOGLE_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google token exchange failed: {detail}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Google token response invalid")
    return payload


def verify_id_token(id_token: str) -> dict[str, Any]:
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    url = f"{_GOOGLE_TOKENINFO_URL}?{urllib.parse.urlencode({'id_token': id_token})}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            claims = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google id_token invalid: {detail}") from exc
    if not isinstance(claims, dict):
        raise RuntimeError("Google tokeninfo invalid")
    aud = str(claims.get("aud") or "")
    if client_id and aud != client_id:
        raise RuntimeError("Google id_token audience mismatch")
    sub = str(claims.get("sub") or "").strip()
    if not sub:
        raise RuntimeError("Google id_token missing sub")
    return claims


def new_oauth_state() -> str:
    return secrets.token_urlsafe(32)
