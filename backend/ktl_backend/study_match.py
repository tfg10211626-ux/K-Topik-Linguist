from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from ktl_backend.config import project_root

_STUDY_TOKEN_RE = re.compile(r"[가-힣]+")


@lru_cache(maxsize=1)
def study_suffixes() -> tuple[str, ...]:
    path = project_root() / "data" / "shared" / "study_suffixes.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return ()
    return tuple(str(item).strip() for item in raw if str(item).strip())


def slice_study_context(text: str, start: int, end: int) -> str:
    stop_chars = ".!?\n。！？"
    left = 0
    right = len(text)

    for idx in range(max(0, start - 1), -1, -1):
        if text[idx] in stop_chars:
            left = idx + 1
            break

    for idx in range(min(len(text), end), len(text)):
        if text[idx] in stop_chars:
            right = idx
            break

    return re.sub(r"\s+", " ", text[left:right]).strip()


def match_study_vocab(text: str, entries: list[dict[str, Any]], max_matches: int = 20) -> list[dict[str, Any]]:
    meaning_by_word: dict[str, str] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        word = row.get("韓文單字")
        meaning = row.get("中文意思")
        if not isinstance(word, str) or not isinstance(meaning, str):
            continue
        word_clean = word.strip()
        meaning_clean = meaning.strip()
        if not word_clean or not meaning_clean or word_clean in meaning_by_word:
            continue
        meaning_by_word[word_clean] = meaning_clean

    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    suffixes = study_suffixes()
    for token in _STUDY_TOKEN_RE.finditer(text):
        token_text = token.group(0).strip()
        if not token_text:
            continue
        surface = token_text if token_text in meaning_by_word else ""
        if not surface:
            for suffix in suffixes:
                if len(token_text) <= len(suffix) or not token_text.endswith(suffix):
                    continue
                candidate = token_text[: -len(suffix)]
                if candidate in meaning_by_word:
                    surface = candidate
                    break
        if not surface or surface in seen:
            continue
        meaning = meaning_by_word.get(surface)
        if not meaning:
            continue
        seen.add(surface)
        matches.append(
            {
                "surface": surface,
                "word": surface,
                "meaning_zh": meaning,
                "context_kr": slice_study_context(text, token.start(), token.end()),
            }
        )
        if len(matches) >= max_matches:
            break
    return matches
