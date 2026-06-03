from __future__ import annotations

import os
from typing import Any

from flask import session
from supabase import Client, create_client

from ktl_backend.config import load_backend_env

_SESSION_SUPABASE_KEY = "supabase_auth"

_MEMBER_TABLE = "Member"
_MEMBER_VOCABULARY_TABLE = "MemberVocabulary"


def _supabase_api_key() -> str:
    load_backend_env()
    for name in ("SUPABASE_ANON_KEY", "SUPABASE_KEY"):
        key = (os.getenv(name) or "").strip()
        if key:
            return key
    return ""


def supabase_configured() -> bool:
    load_backend_env()
    return bool((os.getenv("SUPABASE_URL") or "").strip() and _supabase_api_key())


def _anon_client() -> Client:
    load_backend_env()
    url = (os.getenv("SUPABASE_URL") or "").strip()
    key = _supabase_api_key()
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(url, key)


def _session_supabase() -> dict[str, Any] | None:
    raw = session.get(_SESSION_SUPABASE_KEY)
    return raw if isinstance(raw, dict) else None


def store_supabase_session(*, access_token: str, refresh_token: str, user_id: str) -> None:
    session[_SESSION_SUPABASE_KEY] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": user_id,
    }


def clear_supabase_session() -> None:
    session.pop(_SESSION_SUPABASE_KEY, None)


def sign_in_with_google_id_token(id_token: str) -> dict[str, str]:
    client = _anon_client()
    response = client.auth.sign_in_with_id_token({"provider": "google", "token": id_token})
    if not response or not response.session or not response.user:
        raise RuntimeError("Supabase sign-in returned no session")
    access = (response.session.access_token or "").strip()
    refresh = (response.session.refresh_token or "").strip()
    user_id = str(response.user.id or "").strip()
    if not access or not user_id:
        raise RuntimeError("Supabase session missing access token or user id")
    return {
        "access_token": access,
        "refresh_token": refresh,
        "user_id": user_id,
    }


def ensure_member_row(client: Client, user_id: str, *, email: str | None = None) -> None:
    existing = (
        client.table(_MEMBER_TABLE).select("id,email").eq("user_id", user_id).limit(1).execute()
    )
    rows = existing.data if isinstance(existing.data, list) else []
    if rows:
        if email and not str(rows[0].get("email") or "").strip():
            client.table(_MEMBER_TABLE).update({"email": email.strip()}).eq(
                "user_id", user_id
            ).execute()
        return
    payload: dict[str, Any] = {"user_id": user_id}
    if email:
        payload["email"] = email.strip()
    client.table(_MEMBER_TABLE).insert(payload).execute()


def user_authenticated_client() -> tuple[Client, str]:
    sb = _session_supabase()
    if not sb:
        raise PermissionError("not signed in to Supabase")
    access = str(sb.get("access_token") or "").strip()
    user_id = str(sb.get("user_id") or "").strip()
    if not access or not user_id:
        raise PermissionError("invalid Supabase session")
    client = _anon_client()
    client.postgrest.auth(access)
    return client, user_id


def cloud_sync_available() -> bool:
    return _session_supabase() is not None and supabase_configured()


def compact_vocabulary_ids(client: Client) -> None:
    """全表 id 重排為 1..N，下一筆插入為 MAX(id)+1（需先執行 docs/supabase_compact_vocabulary_ids.sql）。"""
    client.rpc("compact_member_vocabulary_ids").execute()
