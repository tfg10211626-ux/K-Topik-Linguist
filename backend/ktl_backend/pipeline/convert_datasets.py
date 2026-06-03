from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel

from ktl_backend.config import data_processed_root, project_root
from ktl_backend.pipeline.kdrama_lines_csv import build_kdrama_lines_document
from ktl_backend.pipeline.topik_rules_csv import build_topik_ability_document
from ktl_backend.schemas.datasets import KdramaLinesDocument, TopikAbilityIndicatorsDocument


def _write_json(path: Path, doc: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(doc.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")


def default_paths() -> dict[str, tuple[Path, Path]]:
    root = project_root()
    return {
        "topik_rules": (
            root / "data" / "raw" / "rules" / "TOPIK分級能力指標.csv",
            root / "data" / "processed" / "rules" / "topik_ability_indicators.v1.json",
        ),
        "kdrama_lines": (
            root / "data" / "raw" / "script_lines" / "K-drama-lines.csv",
            root / "data" / "processed" / "script_lines" / "k_drama_lines.v1.json",
        ),
    }


def convert_topik_rules(source: Path, destination: Path | None = None) -> Path:
    doc: TopikAbilityIndicatorsDocument = build_topik_ability_document(source)
    out = destination or (
        data_processed_root() / "rules" / "topik_ability_indicators.v1.json"
    )
    _write_json(out, doc)
    return out


def convert_kdrama_lines(source: Path, destination: Path | None = None) -> Path:
    doc: KdramaLinesDocument = build_kdrama_lines_document(source)
    out = destination or (
        data_processed_root() / "script_lines" / "k_drama_lines.v1.json"
    )
    _write_json(out, doc)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert raw CSV datasets to processed JSON.")
    parser.add_argument(
        "--only",
        choices=("all", "topik_rules", "kdrama_lines"),
        default="all",
        help="Which dataset to convert",
    )
    args = parser.parse_args()

    paths = default_paths()
    written: list[Path] = []

    if args.only in ("all", "topik_rules"):
        src, dst = paths["topik_rules"]
        if not src.is_file():
            raise SystemExit(f"Missing source file: {src}")
        written.append(convert_topik_rules(src, dst))

    if args.only in ("all", "kdrama_lines"):
        src, dst = paths["kdrama_lines"]
        if not src.is_file():
            raise SystemExit(f"Missing source file: {src}")
        written.append(convert_kdrama_lines(src, dst))

    for path in written:
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
