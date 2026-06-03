from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, jsonify, request

from ktl_backend.auth_routes import get_session_user
from ktl_backend.supabase_db import (
    _MEMBER_VOCABULARY_TABLE,
    cloud_sync_available,
    supabase_configured,
    user_authenticated_client,
)

vocabulary_bp = Blueprint("vocabulary", __name__, url_prefix="/api/vocabulary")


def _api_error_message(exc: Exception) -> str:
    message = getattr(exc, "message", None)
    if isinstance(message, dict):
        text = str(message.get("message") or message)
        if "duplicate" in text.lower() or "unique" in text.lower() or "23505" in text:
            text += (
                ". Run docs/supabase_fix_constraints.sql in Supabase SQL Editor "
                "(remove UNIQUE on vocabulary alone; keep user_id+vocabulary)."
            )
        if "row-level security" in text.lower():
            text += ". Re-run docs/supabase_rls.sql and use anon key (eyJ...) in .env."
        hint = message.get("hint")
        return f"{text} (hint: {hint})" if hint else text
    if message:
        return str(message)
    return str(exc)


def _is_duplicate_error(exc: Exception) -> bool:
    text = _api_error_message(exc).lower()
    return "duplicate" in text or "unique" in text or "23505" in text


def _require_cloud_user() -> tuple[Any, int] | None:
    if not get_session_user():
        return jsonify({"error": "login required"}), 401
    if not supabase_configured():
        return jsonify({"error": "Supabase is not configured"}), 503
    if not cloud_sync_available():
        return jsonify({"error": "cloud sync unavailable; sign in again"}), 503
    return None


def _row_to_item(row: dict[str, Any]) -> dict[str, Any]:
    created = row.get("created_at")
    saved_at = created.isoformat() if hasattr(created, "isoformat") else str(created or "")
    return {
        "id": row.get("id"),
        "word": str(row.get("vocabulary") or ""),
        "meaningZh": str(row.get("meaning") or ""),
        "dramaLineKo": str(row.get("sentence") or ""),
        "sentenceStyle": str(row.get("sentence_style") or ""),
        "savedAt": saved_at,
    }


def _item_to_row(user_id: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "vocabulary": str(item.get("word") or "").strip(),
        "meaning": str(item.get("meaningZh") or ""),
        "sentence": str(item.get("dramaLineKo") or ""),
        "sentence_style": str(item.get("sentenceStyle") or ""),
    }


def _list_rows(client: Any, user_id: str) -> list[dict[str, Any]]:
    result = (
        client.table(_MEMBER_VOCABULARY_TABLE)
        .select("id,vocabulary,meaning,sentence,sentence_style,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data if isinstance(result.data, list) else []


def _parse_incoming(raw_items: list[Any]) -> dict[str, dict[str, Any]]:
    incoming: dict[str, dict[str, Any]] = {}
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        word = str(raw.get("word") or "").strip()
        if not word or word in incoming:
            continue
        incoming[word] = raw
    return incoming


def _upsert_batch(client: Any, user_id: str, incoming: dict[str, dict[str, Any]]) -> None:
    rows = [_item_to_row(user_id, item) for item in incoming.values() if item]
    if not rows:
        return
    try:
        client.table(_MEMBER_VOCABULARY_TABLE).upsert(
            rows,
            on_conflict="user_id,vocabulary",
        ).execute()
        return
    except Exception as exc:
        if "on_conflict" not in _api_error_message(exc).lower():
            current_app.logger.warning("batch upsert fallback: %s", _api_error_message(exc))

    existing_rows = _list_rows(client, user_id)
    existing_by_word = {
        str(row.get("vocabulary") or ""): row for row in existing_rows if row.get("vocabulary")
    }
    for item in incoming.values():
        _save_item(client, user_id, item, existing_by_word)


def _save_item(
    client: Any,
    user_id: str,
    item: dict[str, Any],
    existing_by_word: dict[str, dict[str, Any]],
) -> None:
    row = _item_to_row(user_id, item)
    word = row["vocabulary"]
    if not word:
        return
    payload = {
        "meaning": row["meaning"],
        "sentence": row["sentence"],
        "sentence_style": row["sentence_style"],
    }
    prev = existing_by_word.get(word)
    if prev and prev.get("id") is not None:
        result = (
            client.table(_MEMBER_VOCABULARY_TABLE)
            .update(payload)
            .eq("id", prev["id"])
            .eq("user_id", user_id)
            .execute()
        )
        if not (result.data if isinstance(result.data, list) else []):
            raise RuntimeError(f"update failed for vocabulary={word!r}")
        return
    try:
        client.table(_MEMBER_VOCABULARY_TABLE).insert(row).execute()
    except Exception as exc:
        if not _is_duplicate_error(exc):
            raise
        result = (
            client.table(_MEMBER_VOCABULARY_TABLE)
            .update(payload)
            .eq("user_id", user_id)
            .eq("vocabulary", word)
            .execute()
        )
        if not (result.data if isinstance(result.data, list) else []):
            raise RuntimeError(
                f"duplicate vocabulary {word!r} but not owned by current user; "
                "run docs/supabase_fix_constraints.sql"
            )


def _sync_items(
    client: Any,
    user_id: str,
    incoming: dict[str, dict[str, Any]],
    *,
    replace: bool,
) -> list[dict[str, Any]]:
    existing_rows = _list_rows(client, user_id)
    existing_by_word = {
        str(row.get("vocabulary") or ""): row for row in existing_rows if row.get("vocabulary")
    }
    if replace:
        remove_words = [
            word
            for word, prev in existing_by_word.items()
            if word not in incoming and prev.get("id") is not None
        ]
        if remove_words:
            client.table(_MEMBER_VOCABULARY_TABLE).delete().eq("user_id", user_id).in_(
                "vocabulary", remove_words
            ).execute()

    _upsert_batch(client, user_id, incoming)
    return _list_rows(client, user_id)


@vocabulary_bp.route("/favorites", methods=["GET", "OPTIONS"])
def list_favorites() -> tuple[Any, int]:
    if request.method == "OPTIONS":
        return "", 204
    blocked = _require_cloud_user()
    if blocked:
        return blocked
    try:
        client, user_id = user_authenticated_client()
        items = [_row_to_item(row) for row in _list_rows(client, user_id)]
        return jsonify({"items": items}), 200
    except PermissionError:
        return jsonify({"error": "cloud sync unavailable; sign in again"}), 503
    except Exception as exc:
        current_app.logger.warning("list_favorites failed: %s", _api_error_message(exc))
        return jsonify({"error": _api_error_message(exc)}), 502


@vocabulary_bp.route("/favorites", methods=["POST"])
def upsert_favorite() -> tuple[Any, int]:
    blocked = _require_cloud_user()
    if blocked:
        return blocked
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400
    word = str(body.get("word") or "").strip()
    if not word:
        return jsonify({"error": "word is required"}), 400
    try:
        client, user_id = user_authenticated_client()
        rows = _sync_items(client, user_id, {word: body}, replace=False)
        items = [_row_to_item(r) for r in rows]
        return jsonify({"ok": True, "items": items, "count": len(items)}), 200
    except PermissionError:
        return jsonify({"error": "cloud sync unavailable; sign in again"}), 503
    except Exception as exc:
        current_app.logger.warning("upsert_favorite failed: %s", _api_error_message(exc))
        return jsonify({"error": _api_error_message(exc)}), 502


@vocabulary_bp.route("/favorites", methods=["DELETE"])
def delete_favorite() -> tuple[Any, int]:
    blocked = _require_cloud_user()
    if blocked:
        return blocked
    word = (request.args.get("word") or "").strip()
    if not word:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            word = str(body.get("word") or "").strip()
    if not word:
        return jsonify({"error": "word is required"}), 400
    try:
        client, user_id = user_authenticated_client()
        client.table(_MEMBER_VOCABULARY_TABLE).delete().eq("user_id", user_id).eq(
            "vocabulary", word
        ).execute()
        items = [_row_to_item(r) for r in _list_rows(client, user_id)]
        return jsonify({"ok": True, "items": items, "count": len(items)}), 200
    except PermissionError:
        return jsonify({"error": "cloud sync unavailable; sign in again"}), 503
    except Exception as exc:
        current_app.logger.warning("delete_favorite failed: %s", _api_error_message(exc))
        return jsonify({"error": _api_error_message(exc)}), 502


@vocabulary_bp.route("/favorites/sync", methods=["POST", "OPTIONS"])
def sync_favorites() -> tuple[Any, int]:
    if request.method == "OPTIONS":
        return "", 204
    blocked = _require_cloud_user()
    if blocked:
        return blocked
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "JSON body required"}), 400
    raw_items = body.get("items")
    if not isinstance(raw_items, list):
        return jsonify({"error": "items array required"}), 400
    replace = body.get("replace") is True
    try:
        client, user_id = user_authenticated_client()
        incoming = _parse_incoming(raw_items)
        rows = _sync_items(client, user_id, incoming, replace=replace)
        items = [_row_to_item(r) for r in rows]
        if len(items) < len(incoming):
            current_app.logger.warning(
                "sync partial: sent=%s saved=%s user=%s",
                len(incoming),
                len(items),
                user_id,
            )
        return jsonify({"ok": True, "items": items, "count": len(items)}), 200
    except PermissionError:
        return jsonify({"error": "cloud sync unavailable; sign in again"}), 503
    except Exception as exc:
        current_app.logger.warning("sync_favorites failed: %s", _api_error_message(exc))
        return jsonify({"error": _api_error_message(exc)}), 502
