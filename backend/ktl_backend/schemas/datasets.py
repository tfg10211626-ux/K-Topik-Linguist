from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class TopikLevelBlock(BaseModel):
    series: str = Field(description="TOPIK I 或 TOPIK II")
    level_label: str = Field(description="例如：1級、2級")
    user_level: Literal["初級", "中級", "高級"] = Field(
        description="對應使用者難度：1–2 級為初級、3–4 級為中級、5–6 級為高級",
    )
    indicators_text: str = Field(description="原始能力指標全文（含換行）")
    indicators_bullets: list[str] = Field(
        default_factory=list,
        description="依行拆解，以 '-' 開頭的條列能力指標",
    )


class TopikAbilityIndicatorsDocument(BaseModel):
    schema_version: str = "topik_ability_indicators_v1.1"
    source_relative_path: str
    levels: list[TopikLevelBlock]


class KdramaLineItem(BaseModel):
    id: str
    category_zh: str = Field(description="台詞類型（中文標籤）")
    line_kr: str = Field(description="韓文台詞本文")


class KdramaLinesDocument(BaseModel):
    schema_version: str = "kdrama_lines_v1"
    source_relative_path: str
    lines: list[KdramaLineItem]
