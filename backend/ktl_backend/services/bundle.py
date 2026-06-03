from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ktl_backend.config import data_processed_root


def _index_path(schema_version: str) -> Path:
    safe = schema_version.replace("/", "").replace("..", "")
    return data_processed_root() / "index" / f"terms_{safe}.json"


def build_vocab_bundle(term_ids: list[str], *, schema_version: str = "v1") -> dict[str, Any]:
    """
    Load minimal fields for LLM prompts from `processed/index/terms_{schema}.json`.

    Token-efficiency goal: return only requested ids; omit corpus-sized payloads.
    """
    path = _index_path(schema_version)
    if not path.is_file():
        return {"schema_version": schema_version, "terms": {}}

    raw = json.loads(path.read_text(encoding="utf-8"))
    by_id: dict[str, Any] = raw.get("terms", {}) if isinstance(raw, dict) else {}
    selected: dict[str, Any] = {}
    for term_id in term_ids:
        if term_id in by_id:
            selected[term_id] = by_id[term_id]
    return {"schema_version": schema_version, "terms": selected}
