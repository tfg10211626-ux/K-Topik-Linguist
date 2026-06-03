from __future__ import annotations

import argparse
import json
from pathlib import Path

from pypdf import PdfReader

from ktl_backend.config import data_processed_root, project_root
from ktl_backend.pipeline.vocab_pdf_advanced import parse_advanced_backup
from ktl_backend.pipeline.vocab_pdf_vol import parse_vol_backup
from ktl_backend.pipeline.vocab_translate import translate_advanced_backup, translate_vol_backup


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(payload, "model_dump"):
        text = json.dumps(payload.model_dump(mode="json", by_alias=True), ensure_ascii=False, indent=2) + "\n"
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert vocabulary PDFs to English backups and Traditional Chinese JSON.")
    parser.add_argument(
        "--only",
        choices=("all", "beginner", "intermediate", "advanced"),
        default="all",
        help="Limit conversion to a single PDF family.",
    )
    parser.add_argument(
        "--no-translate",
        action="store_true",
        help="Only write English backup JSON (skip machine translation to zh-TW).",
    )
    args = parser.parse_args()

    root = project_root()
    backup_dir = data_processed_root() / "vocab_books" / "english_backup"
    zh_dir = data_processed_root() / "vocab_books"

    jobs: list[tuple[str, Path, Path, Path]] = []
    if args.only in ("all", "beginner"):
        jobs.append(
            (
                "beginner",
                root / "data" / "raw" / "vocab_books" / "TOPIK-VOL-初級.pdf",
                backup_dir / "vol_beginner.en.v1.json",
                zh_dir / "topik_vol_beginner.zh.v2.json",
            )
        )
    if args.only in ("all", "intermediate"):
        jobs.append(
            (
                "intermediate",
                root / "data" / "raw" / "vocab_books" / "TOPIK-VOL-中級.pdf",
                backup_dir / "vol_intermediate.en.v1.json",
                zh_dir / "topik_vol_intermediate.zh.v2.json",
            )
        )
    if args.only in ("all", "advanced"):
        jobs.append(
            (
                "advanced",
                root / "data" / "raw" / "vocab_books" / "TOPIK 高級單字.pdf",
                backup_dir / "advanced.en.v1.json",
                zh_dir / "topik_advanced.zh.v2.json",
            )
        )

    for kind, src, backup_path, zh_path in jobs:
        if not src.is_file():
            raise SystemExit(f"Missing PDF: {src}")
        reader = PdfReader(str(src))
        if kind in ("beginner", "intermediate"):
            level_zh = "初級" if kind == "beginner" else "中級"
            backup_doc = parse_vol_backup(reader, summary_level_zh=level_zh, source_path=src)
            _write_json(backup_path, backup_doc)
            print(f"Wrote backup {backup_path} ({len(backup_doc.entries)} entries)")
            if not args.no_translate:
                zh_doc = translate_vol_backup(backup_doc)
                _write_json(zh_path, zh_doc)
                print(f"Wrote zh {zh_path} ({len(zh_doc.entries)} entries)")
        else:
            backup_doc = parse_advanced_backup(reader, source_path=src)
            _write_json(backup_path, backup_doc)
            print(f"Wrote backup {backup_path} ({len(backup_doc.entries)} entries)")
            if not args.no_translate:
                zh_doc = translate_advanced_backup(backup_doc)
                _write_json(zh_path, zh_doc)
                print(f"Wrote zh {zh_path} ({len(zh_doc.entries)} entries)")


if __name__ == "__main__":
    main()
