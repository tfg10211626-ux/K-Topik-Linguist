from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class ManifestFileEntry(BaseModel):
    domain: Literal["scripts", "script_lines", "past_papers", "vocab_books", "rules"]
    relative_path: str
    sha256: str
    size_bytes: int
    suffix: str


class ManifestRun(BaseModel):
    run_id: str = Field(description="UTC ISO-8601 timestamp id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    pipeline_version: str = "ingest_v1"
    schema_version: str = "manifest_v1"
    files: list[ManifestFileEntry] = Field(default_factory=list)
