from __future__ import annotations

import csv
from pathlib import Path

from ktl_backend.config import project_root
from ktl_backend.schemas.datasets import KdramaLineItem, KdramaLinesDocument


def _normalize_kr(value: str) -> str:
    return value.replace("\ufeff", "").replace("\u00a0", " ").strip()


def read_kdrama_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.reader(handle))


def parse_kdrama_lines_rows(rows: list[list[str]]) -> list[KdramaLineItem]:
    if len(rows) < 2:
        raise ValueError("CSV must include a header and at least one data row")

    header = [cell.strip() for cell in rows[0]]
    if len(header) < 2:
        raise ValueError("Expected at least two columns (類型, 韓文台詞)")

    lines_out: list[KdramaLineItem] = []
    for index, row in enumerate(rows[1:], start=1):
        if len(row) < 2:
            continue
        category_zh = row[0].strip()
        line_kr = _normalize_kr(row[1])
        if not line_kr:
            continue
        line_id = f"kdl_{index:05d}"
        lines_out.append(
            KdramaLineItem(
                id=line_id,
                category_zh=category_zh,
                line_kr=line_kr,
            )
        )

    if not lines_out:
        raise ValueError("No K-drama lines parsed from CSV")

    return lines_out


def build_kdrama_lines_document(source_path: Path) -> KdramaLinesDocument:
    rows = read_kdrama_csv_rows(source_path)
    lines = parse_kdrama_lines_rows(rows)
    try:
        rel = source_path.resolve().relative_to(project_root().resolve())
    except ValueError:
        rel = source_path
    return KdramaLinesDocument(
        source_relative_path=str(rel).replace("\\", "/"),
        lines=lines,
    )
