from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# --- Beginner / Intermediate (VOL PDFs) --------------------------------------

class VocabVolBackupRow(BaseModel):
    """English gloss preserved for auditing / regeneration."""

    model_config = ConfigDict(populate_by_name=True)

    level: str = Field(alias="等級")
    word_kr: str = Field(alias="韓文單字")
    gloss_en: str = Field(alias="英文意思")


class VocabVolBackupDocument(BaseModel):
    schema_version: str = "vocab_vol_en_backup_v1"
    source_relative_path: str
    summary_level: str
    entries: list[VocabVolBackupRow]


class VocabVolZhRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    level: str = Field(alias="等級")
    word_kr: str = Field(alias="韓文單字")
    meaning_zh: str = Field(alias="中文意思")


class VocabVolZhDocument(BaseModel):
    schema_version: str = "vocab_vol_zh_v2"
    source_relative_path: str
    summary_level: str
    entries: list[VocabVolZhRow]


# --- Advanced (STT-style PDF) -------------------------------------------------

class VocabAdvancedBackupRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    level: str = Field(alias="等級")
    word_kr: str = Field(alias="韓文單字")
    gloss_en: str = Field(alias="英文意思")
    usage_kr: str = Field(
        alias="常見用法",
        description="PDF 內韓文用法／例句片段（與單字重複的提示語可能同列）",
    )


class VocabAdvancedBackupDocument(BaseModel):
    schema_version: str = "vocab_advanced_en_backup_v1"
    source_relative_path: str
    summary_level: str = "高級"
    entries: list[VocabAdvancedBackupRow]


class VocabAdvancedZhRow(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    level: str = Field(alias="等級")
    word_kr: str = Field(alias="韓文單字")
    meaning_zh: str = Field(alias="中文意思")
    usage_kr: str = Field(alias="常見用法")
    usage_zh: str = Field(alias="例句中文")


class VocabAdvancedZhDocument(BaseModel):
    schema_version: str = "vocab_advanced_zh_v2"
    source_relative_path: str
    summary_level: str = "高級"
    entries: list[VocabAdvancedZhRow]
