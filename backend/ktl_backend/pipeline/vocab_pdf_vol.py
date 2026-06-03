from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from ktl_backend.config import project_root
from ktl_backend.schemas.vocab_book import VocabVolBackupDocument, VocabVolBackupRow

# Boundaries only when the serial number is followed by Korean script (avoids digits inside English gloss).
_VOL_ENTRY = re.compile(r"(\d+)\s+(?=[가-힣ㄱ-ㅎ])")


def _page_body_lines(page_text: str) -> list[str]:
    out: list[str] = []
    for ln in page_text.splitlines():
        s = ln.strip()
        if not s:
            continue
        if "TOPIK" in s and "Vocabulary" in s:
            continue
        if s.startswith("No.") and "한글" in s:
            continue
        out.append(s)
    return out


def parse_vol_backup(reader: PdfReader, *, summary_level_zh: str, source_path: Path) -> VocabVolBackupDocument:
    """Parse TOPIK-VOL style PDFs (two-column numbered 한글 + English gloss) into an English backup document."""
    triples: list[tuple[int, str, str]] = []
    for page in reader.pages:
        big = " ".join(_page_body_lines(page.extract_text() or ""))
        matches = list(_VOL_ENTRY.finditer(big))
        for index, m in enumerate(matches):
            serial = int(m.group(1))
            start = m.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(big)
            chunk = big[start:end].strip()
            parts = chunk.split(None, 1)
            if len(parts) < 2:
                continue
            word_kr, gloss_en = parts[0], parts[1].strip()
            triples.append((serial, word_kr, gloss_en))

    triples.sort(key=lambda item: item[0])
    rows = [
        VocabVolBackupRow.model_validate(
            {"等級": summary_level_zh, "韓文單字": word_kr, "英文意思": gloss_en},
        )
        for _serial, word_kr, gloss_en in triples
    ]
    try:
        rel = source_path.resolve().relative_to(project_root().resolve())
    except ValueError:
        rel = source_path
    return VocabVolBackupDocument(
        source_relative_path=str(rel).replace("\\", "/"),
        summary_level=summary_level_zh,
        entries=rows,
    )
