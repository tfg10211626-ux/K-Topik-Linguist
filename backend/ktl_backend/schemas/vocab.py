from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class VocabItem(BaseModel):
    word: str = Field(description="韓文單字")
    meaning: str = Field(description="中文解釋")
    example_kr: str = Field(description="韓文例句")
    example_cn: str = Field(description="例句中文翻譯")


class SentencePair(BaseModel):
    kr: str
    cn: str


class VoicePayload(BaseModel):
    """Voice-related metadata; extend later with TTS URLs or MIME payloads."""

    recording_received: bool = False
    note: str | None = None


class GenerateVocabRequest(BaseModel):
    context: str = Field(description="情境／文本脈絡")
    topik_level: str = Field(description="TOPIK 難度（例如：初級／中級／高級或 I/II）")
    recording_base64: str | None = Field(default=None, description="選填：錄音 Base64（無 data: 前綴）")
    recording_mime_type: str | None = Field(
        default=None,
        description="選填：錄音 MIME，例如 audio/webm、audio/wav",
    )

    @field_validator("context")
    @classmethod
    def strip_context(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("context must not be empty")
        return cleaned


class GenerateVocabResponse(BaseModel):
    vocab: list[VocabItem]
    transcript: str | None = Field(default=None, description="若有錄音，可回傳轉錄文字")
    sentences: list[SentencePair] = Field(default_factory=list)
    voice: VoicePayload | None = None


class GeminiVocabPayload(BaseModel):
    """Strict JSON shape returned by Gemini (validated before mapping)."""

    vocab: list[VocabItem]
    transcript: str | None = None
    sentences: list[SentencePair] = Field(default_factory=list)
