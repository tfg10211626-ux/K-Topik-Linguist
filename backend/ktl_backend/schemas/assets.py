from __future__ import annotations

from pydantic import BaseModel, Field


class ContentRef(BaseModel):
    """Pointer to SSOT text stored under processed/script or processed/exam."""

    asset_type: str = Field(description="e.g. script, exam")
    asset_id: str
    span_start: int | None = None
    span_end: int | None = None


class TermRecord(BaseModel):
    """Normalized vocabulary row for processed JSON (internal storage)."""

    term_id: str
    word: str
    meaning: str
    example_kr: str
    example_cn: str
    example_id: str | None = None
    topik_level: str | None = None
    source: ContentRef | None = None
