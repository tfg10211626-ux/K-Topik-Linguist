from __future__ import annotations

import os
from typing import Any

from flask import Blueprint, jsonify, redirect, request, session

from ktl_backend.google_auth import (
    build_authorize_url,
    exchange_code_for_tokens,
    google_oauth_configured,
    new_oauth_state,
    verify_id_token,
)
from ktl_backend.supabase_db import (
    clear_supabase_session,
    cloud_sync_available,
    ensure_member_row,
    sign_in_with_google_id_token,
    store_supabase_session,
    supabase_configured,
    user_authenticated_client,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")

_SESSION_USER_KEY = "auth_user"


def get_session_user() -> dict[str, Any] | None:
    raw = session.get(_SESSION_USER_KEY)
    if not isinstance(raw, dict):
        return None
    sub = str(raw.get("id") or "").strip()
    if not sub:
        return None
    return raw


def _public_user(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "email": raw.get("email"),
        "displayName": raw.get("displayName"),
        "avatarUrl": raw.get("avatarUrl"),
    }


def _oauth_redirect_uri() -> str:
    explicit = (os.getenv("GOOGLE_OAUTH_REDIRECT_URI") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    root = request.url_root.rstrip("/")
    return f"{root}/api/auth/google/callback"


def _auth_success_redirect() -> str:
    target = (os.getenv("KTL_AUTH_SUCCESS_REDIRECT") or "/index.html").strip()
    if target.startswith("http://") or target.startswith("https://"):
        return target
    if not target.startswith("/"):
        target = "/" + target
    return target


@auth_bp.route("/google", methods=["GET"])
def auth_google_start() -> Any:
    if not google_oauth_configured():
        return jsonify({"error": "Google OAuth is not configured on the server"}), 503
    state = new_oauth_state()
    session["oauth_state"] = state
    url = build_authorize_url(redirect_uri=_oauth_redirect_uri(), state=state)
    return redirect(url)


@auth_bp.route("/google/callback", methods=["GET"])
def auth_google_callback() -> Any:
    if not google_oauth_configured():
        return jsonify({"error": "Google OAuth is not configured on the server"}), 503

    err = request.args.get("error")
    if err:
        return jsonify({"error": f"Google OAuth denied: {err}"}), 400

    state = request.args.get("state") or ""
    expected = session.pop("oauth_state", None)
    if not expected or state != expected:
        return jsonify({"error": "invalid OAuth state"}), 400

    code = request.args.get("code")
    if not isinstance(code, str) or not code.strip():
        return jsonify({"error": "missing OAuth code"}), 400

    redirect_uri = _oauth_redirect_uri()
    try:
        tokens = exchange_code_for_tokens(code=code.strip(), redirect_uri=redirect_uri)
        id_token = tokens.get("id_token")
        if not isinstance(id_token, str) or not id_token.strip():
            raise RuntimeError("missing id_token in Google response")
        claims = verify_id_token(id_token.strip())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502

    google_sub = str(claims.get("sub") or "").strip()
    if not google_sub:
        return jsonify({"error": "Google account id missing"}), 502

    session[_SESSION_USER_KEY] = {
        "id": google_sub,
        "email": str(claims.get("email") or "") or None,
        "displayName": str(claims.get("name") or "") or None,
        "avatarUrl": str(claims.get("picture") or "") or None,
    }

    if supabase_configured():
        try:
            sb = sign_in_with_google_id_token(id_token.strip())
            store_supabase_session(
                access_token=sb["access_token"],
                refresh_token=sb["refresh_token"],
                user_id=sb["user_id"],
            )
            client, user_id = user_authenticated_client()
            ensure_member_row(
                client,
                user_id,
                email=str(claims.get("email") or "") or None,
            )
        except Exception:
            clear_supabase_session()

    return redirect(_auth_success_redirect() + "?auth=1")


@auth_bp.route("/me", methods=["GET", "OPTIONS"])
def auth_me() -> tuple[Any, int]:
    if request.method == "OPTIONS":
        return "", 204
    user = get_session_user()
    if not user:
        return jsonify({"loggedIn": False, "user": None, "cloudSync": False}), 200
    return jsonify(
        {
            "loggedIn": True,
            "user": _public_user(user),
            "cloudSync": cloud_sync_available(),
        }
    ), 200


@auth_bp.route("/logout", methods=["POST", "OPTIONS"])
def auth_logout() -> tuple[Any, int]:
    if request.method == "OPTIONS":
        return "", 204
    session.pop(_SESSION_USER_KEY, None)
    session.pop("oauth_state", None)
    clear_supabase_session()
    return jsonify({"ok": True}), 200
