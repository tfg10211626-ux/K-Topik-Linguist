from __future__ import annotations

import re
from collections import deque
from pathlib import Path

from pypdf import PdfReader

from ktl_backend.config import project_root
from ktl_backend.schemas.vocab_book import VocabAdvancedBackupDocument, VocabAdvancedBackupRow

# Allow `2101시행 ...` (no space after digits) and regular spaced rows.
_ENG_START = re.compile(r"^(\d+(?:-\S+)?)\s*(.+)$")
_HANGUL = re.compile(r"[가-힣]")
_KOR_LINE_HEAD = re.compile(r"^[가-힣ㄱ-ㅎ]")
_JUNK_KOR = re.compile(r"^[−\-\s]+$")


def _merge_eng_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    current: str | None = None
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if _ENG_START.match(ln):
            if current is not None:
                merged.append(current)
            current = ln
            continue
        if current is None:
            continue
        current += " " + ln
    if current is not None:
        merged.append(current)
    return merged


def _split_eng_kor(
    page_lines: list[str],
    *,
    allow_vocab_marker: bool = True,
) -> tuple[list[str], list[str]]:
    raw = [ln.rstrip() for ln in page_lines]

    vocab_idx = None
    if allow_vocab_marker:
        vocab_idx = next((idx for idx, ln in enumerate(raw) if ln.strip() == "Vocab"), None)
    if vocab_idx is not None:
        eng_raw = raw[:vocab_idx]
        kor_raw = raw[vocab_idx + 1 :]
    else:
        start = 0
        for idx, ln in enumerate(raw):
            if _ENG_START.match(ln.strip()):
                start = idx
                break
        body = raw[start:]
        kor_start: int | None = None
        for idx, ln in enumerate(body):
            text = ln.strip()
            if not text:
                continue
            if _ENG_START.match(text):
                continue
            # Korean vocabulary rows start with Hangul; embedded Hangul in English
            # gloss lines still begins with a digit (e.g. 2101시행 …).
            if _KOR_LINE_HEAD.match(text):
                kor_start = idx
                break
        if kor_start is None:
            return [], []
        eng_raw = body[:kor_start]
        kor_raw = body[kor_start:]

    eng_lines = _merge_eng_lines(eng_raw)
    kor_lines: list[str] = []
    for ln in kor_raw:
        text = ln.strip()
        if not text:
            continue
        if not _HANGUL.search(text):
            continue
        if _JUNK_KOR.fullmatch(text):
            continue
        kor_lines.append(text)
    return eng_lines, kor_lines


def _gloss_from_eng_line(line: str) -> str:
    text = line.strip()
    match = _ENG_START.match(text)
    if not match:
        return text
    return match.group(2).strip()


def _split_kor_usage(line: str) -> tuple[str, str]:
    parts = line.split()
    if not parts:
        return "", ""
    head = parts[0]
    tail = " ".join(parts[1:]).strip()
    return head, tail


def parse_advanced_backup(reader: PdfReader, *, source_path: Path) -> VocabAdvancedBackupDocument:
    """
    Pair entries across PDF pages using FIFO queues.

    English blocks often finish before Korean on the same page; Korean rows continue on
    the next page while PyPDF preserves reading order column-by-column.
    """
    eng_queue: deque[str] = deque()
    kor_queue: deque[str] = deque()
    rows: list[VocabAdvancedBackupRow] = []

    for page in reader.pages:
        lines = (page.extract_text() or "").splitlines()
        eng_lines, kor_lines = _split_eng_kor(lines, allow_vocab_marker=True)
        eng_queue.extend(eng_lines)
        kor_queue.extend(kor_lines)
        while eng_queue and kor_queue:
            eng = eng_queue.popleft()
            kor = kor_queue.popleft()
            gloss_en = _gloss_from_eng_line(eng)
            word_kr, usage_kr = _split_kor_usage(kor)
            if not word_kr:
                continue
            rows.append(
                VocabAdvancedBackupRow.model_validate(
                    {
                        "等級": "高級",
                        "韓文單字": word_kr,
                        "英文意思": gloss_en,
                        "常見用法": usage_kr,
                    },
                )
            )

    if eng_queue:
        print(f"[advanced] warning: unmatched English fragments ({len(eng_queue)})")
    if kor_queue:
        print(f"[advanced] warning: unmatched Korean fragments ({len(kor_queue)})")

    try:
        rel = source_path.resolve().relative_to(project_root().resolve())
    except ValueError:
        rel = source_path
    return VocabAdvancedBackupDocument(
        source_relative_path=str(rel).replace("\\", "/"),
        entries=rows,
    )
