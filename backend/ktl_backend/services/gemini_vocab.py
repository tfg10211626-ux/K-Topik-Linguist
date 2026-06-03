from __future__ import annotations

import base64
import json
from typing import Any

from pydantic import ValidationError

from ktl_backend.config import get_gemini_api_key, get_gemini_model
from ktl_backend.schemas.vocab import (
    GeminiVocabPayload,
    GenerateVocabRequest,
    GenerateVocabResponse,
    VoicePayload,
)
from services.gemini_rate_limit import GeminiRateLimitError, enforce_gemini_request_limit


class GeminiInvocationError(Exception):
    """Raised when Gemini returns unusable output or the SDK errors."""


def _decode_optional_audio(req: GenerateVocabRequest) -> tuple[bytes | None, str | None]:
    if not req.recording_base64:
        return None, None
    raw_b64 = req.recording_base64.strip()
    if raw_b64.startswith("data:") and "," in raw_b64:
        raw_b64 = raw_b64.split(",", 1)[1]
    try:
        audio_bytes = base64.b64decode(raw_b64, validate=False)
    except (ValueError, TypeError) as exc:
        raise ValueError("recording_base64 is not valid base64") from exc
    mime = (req.recording_mime_type or "audio/webm").strip()
    return audio_bytes, mime


def _build_instruction_prompt(req: GenerateVocabRequest) -> str:
    return (
        "你是韓語教學助理，輸出必須是 JSON（不要 Markdown），並嚴格符合 schema。\n"
        "Schema：\n"
        "{\n"
        '  "transcript": string | null,\n'
        '  "vocab": [\n'
        "    {\n"
        '      "word": string,\n'
        '      "meaning": string,\n'
        '      "example_kr": string,\n'
        '      "example_cn": string\n'
        "    }\n"
        "  ],\n"
        '  "sentences": [\n'
        "    { \"kr\": string, \"cn\": string }\n"
        "  ]\n"
        "}\n"
        "規則：\n"
        "- vocab 至少 5 個、至多 12 個；挑選與情境最相關、符合難度的詞彙。\n"
        "- 若提供錄音，transcript 請填寫你從錄音辨識出的韓文內容（聽不清楚可給部分並簡短說明）。\n"
        "- sentences 可給 0~3 組與情境相關的短句（韓＋中）。\n"
        "- 全部文字：繁體中文翻譯與解釋；韓文句子維持韓文。\n"
        "\n"
        f"情境（context）：{req.context}\n"
        f"TOPIK 難度（topik_level）：{req.topik_level}\n"
    )


def _parse_json_payload(text: str) -> GeminiVocabPayload:
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GeminiInvocationError("Gemini returned non-JSON output") from exc
    if not isinstance(data, dict):
        raise GeminiInvocationError("Gemini JSON root must be an object")
    try:
        return GeminiVocabPayload.model_validate(data)
    except ValidationError as exc:
        raise GeminiInvocationError(f"Gemini JSON failed validation: {exc}") from exc


def generate_vocab_via_gemini(req: GenerateVocabRequest) -> GenerateVocabResponse:
    from google import genai
    from google.genai import types

    api_key = get_gemini_api_key()
    if not api_key:
        raise GeminiInvocationError("GEMINI_API_KEY is not configured")

    audio_bytes, audio_mime = _decode_optional_audio(req)

    client = genai.Client(api_key=api_key)
    model_name = get_gemini_model()
    prompt = _build_instruction_prompt(req)

    contents: list[Any]
    if audio_bytes:
        contents = [
            prompt,
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type=audio_mime or "audio/webm",
            ),
        ]
    else:
        contents = [prompt]

    try:
        enforce_gemini_request_limit(model_name)
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
    except GeminiRateLimitError as exc:
        raise GeminiInvocationError(str(exc)) from exc
    except Exception as exc:
        raise GeminiInvocationError(f"Gemini request failed: {exc}") from exc

    raw_text = getattr(response, "text", None)
    if not raw_text:
        finish_reason = None
        try:
            cand = response.candidates[0]
            finish_reason = getattr(cand, "finish_reason", None)
            if finish_reason is not None:
                finish_reason = getattr(finish_reason, "name", finish_reason)
        except (AttributeError, IndexError, TypeError):
            finish_reason = None
        raise GeminiInvocationError(
            "Gemini returned empty content"
            + (f" (finish_reason={finish_reason})" if finish_reason else "")
        )

    payload = _parse_json_payload(raw_text)
    return GenerateVocabResponse(
        vocab=payload.vocab,
        transcript=payload.transcript,
        sentences=payload.sentences,
        voice=VoicePayload(
            recording_received=bool(audio_bytes),
            note=None,
        ),
    )
