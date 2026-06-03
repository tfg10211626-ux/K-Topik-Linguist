from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Literal

from ktl_backend.config import project_root
from ktl_backend.schemas.datasets import TopikAbilityIndicatorsDocument, TopikLevelBlock

_SERIES_TOKENS = ("TOPIK I", "TOPIK II")


def _user_level_from_level_label(level_label: str) -> Literal["初級", "中級", "高級"]:
    """Map official 급수 labels (e.g. 3級) to coarse learner tiers."""
    match = re.search(r"[1-6]", level_label)
    if not match:
        raise ValueError(f"Cannot parse TOPIK level digit from: {level_label!r}")
    step = int(match.group())
    if step in (1, 2):
        return "初級"
    if step in (3, 4):
        return "中級"
    if step in (5, 6):
        return "高級"
    raise ValueError(f"Unsupported TOPIK level digit in: {level_label!r}")


def _normalize_text(value: str) -> str:
    cleaned = value.replace("\ufeff", "").replace("\u00a0", " ").replace("\u2028", "\n")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    return cleaned.strip()


def _split_bullets(indicators_text: str) -> list[str]:
    """
    Split ability indicators into bullet strings.

    Source CSV may wrap a single bullet across multiple physical lines; continuation
    lines do not start with '-', so they are appended to the previous bullet.
    """
    bullets: list[str] = []
    current: str | None = None
    for raw_line in indicators_text.splitlines():
        line = _normalize_text(raw_line)
        if not line:
            continue
        if line.startswith("-"):
            if current is not None:
                bullets.append(current)
            current = line
            continue
        if current is None:
            continue
        joiner = "" if current.endswith(("」", ")", "）")) else " "
        current = f"{current}{joiner}{line}"
    if current is not None:
        bullets.append(current)
    return bullets


def _pad_row(row: list[str], width: int) -> list[str]:
    if len(row) >= width:
        return row[:width]
    return row + [""] * (width - len(row))


def parse_topik_ability_csv_rows(rows: list[list[str]]) -> list[TopikLevelBlock]:
    if len(rows) < 2:
        raise ValueError("CSV must include a header and at least one data row")

    blocks: list[TopikLevelBlock] = []
    current_series = ""

    for row in rows[1:]:
        col0, col1, col2 = _pad_row(row, 3)
        col0 = col0.strip()
        col1 = col1.strip()
        col2 = _normalize_text(col2)

        if col0 in _SERIES_TOKENS:
            current_series = col0

        if not col1 or not col2:
            continue

        if not current_series:
            raise ValueError(f"Missing TOPIK series before row: {row!r}")

        indicators_text = col2
        blocks.append(
            TopikLevelBlock(
                series=current_series,
                level_label=col1,
                user_level=_user_level_from_level_label(col1),
                indicators_text=indicators_text,
                indicators_bullets=_split_bullets(indicators_text),
            )
        )

    if not blocks:
        raise ValueError("No TOPIK level rows parsed from CSV")

    return blocks


def read_topik_ability_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def build_topik_ability_document(source_path: Path) -> TopikAbilityIndicatorsDocument:
    rows = read_topik_ability_csv(source_path)
    levels = parse_topik_ability_csv_rows(rows)
    try:
        rel = source_path.resolve().relative_to(project_root().resolve())
    except ValueError:
        rel = source_path
    return TopikAbilityIndicatorsDocument(
        source_relative_path=str(rel).replace("\\", "/"),
        levels=levels,
    )
