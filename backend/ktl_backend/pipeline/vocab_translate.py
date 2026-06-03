from __future__ import annotations

import time

from deep_translator import GoogleTranslator

from ktl_backend.schemas.vocab_book import (
    VocabAdvancedBackupDocument,
    VocabAdvancedZhDocument,
    VocabAdvancedZhRow,
    VocabVolBackupDocument,
    VocabVolZhDocument,
    VocabVolZhRow,
)


def _translate_line(text: str, *, source: str, retries: int = 4) -> str:
    cleaned = text.strip()
    if not cleaned:
        return ""
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            return GoogleTranslator(source=source, target="zh-TW").translate(cleaned)
        except Exception as exc:
            last_exc = exc
            time.sleep(0.35 * (attempt + 1))
    raise RuntimeError(f"Translation failed after retries for: {cleaned[:120]}") from last_exc


def translate_vol_backup(doc: VocabVolBackupDocument) -> VocabVolZhDocument:
    cache_en: dict[str, str] = {}
    rows: list[VocabVolZhRow] = []
    for idx, row in enumerate(doc.entries):
        gloss = row.gloss_en
        if gloss not in cache_en:
            cache_en[gloss] = _translate_line(gloss, source="en")
            time.sleep(0.03)
        rows.append(
            VocabVolZhRow.model_validate(
                {
                    "等級": row.level,
                    "韓文單字": row.word_kr,
                    "中文意思": cache_en[gloss],
                },
            )
        )
        if idx % 200 == 0 and idx:
            time.sleep(0.05)
    return VocabVolZhDocument(
        source_relative_path=doc.source_relative_path,
        summary_level=doc.summary_level,
        entries=rows,
    )


def translate_advanced_backup(doc: VocabAdvancedBackupDocument) -> VocabAdvancedZhDocument:
    cache_en: dict[str, str] = {}
    cache_ko: dict[str, str] = {}
    rows: list[VocabAdvancedZhRow] = []
    for idx, row in enumerate(doc.entries):
        gloss = row.gloss_en
        if gloss not in cache_en:
            cache_en[gloss] = _translate_line(gloss, source="en")
            time.sleep(0.03)

        usage_kr = row.usage_kr.strip()
        if usage_kr:
            if usage_kr not in cache_ko:
                cache_ko[usage_kr] = _translate_line(usage_kr, source="ko")
                time.sleep(0.03)
            usage_zh = cache_ko[usage_kr]
        else:
            usage_zh = ""

        rows.append(
            VocabAdvancedZhRow.model_validate(
                {
                    "等級": row.level,
                    "韓文單字": row.word_kr,
                    "中文意思": cache_en[gloss],
                    "常見用法": row.usage_kr,
                    "例句中文": usage_zh,
                },
            )
        )
        if idx % 150 == 0 and idx:
            time.sleep(0.05)

    return VocabAdvancedZhDocument(
        source_relative_path=doc.source_relative_path,
        entries=rows,
    )
