from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from ktl_backend.config import get_gemini_api_key, load_backend_env
from services.gemini_json import parse_json_text
from services.gemini_rate_limit import (
    GeminiRateLimitError,
    enforce_gemini_request_limit,
    raise_gemini_rate_limit_if_needed,
)

GEMINI_EVAL_PRIMARY_MODEL = "gemini-3-flash"
_GEMINI_EVAL_FALLBACK_MODELS: tuple[str, ...] = ("gemini-3.1-flash-lite",)


def _build_director_prompt(*, sentence: str, scenario: str) -> str:
    s = (sentence or "").strip()
    scen = (scenario or "").strip() or "（未指定）"
    return f"""你是一位獲獎無數的「毒舌韓劇導演」。現在你要審核演員的試鏡帶。 我會提供：1. 劇本原文(生成的句子) 2. 劇本情境 3. 使用者的錄音檔。
你的任務：
1 聽他的聲音，針對「語調起伏」與「情感張力」給予最無情的點評。
2 評分標準：如果聽起來像在背書，直接給低分（但不要給低於50分）；如果有入戲、聲音夠大，就給80分以上。
3 輸出格式為 JSON，包含：
◦ score_acting: 演戲分數 (50-100)
◦ feedback_acting: 演技評價（毒舌風格，不超過兩句話）

劇本原文：{s}
劇本情境：{scen}

【輸出規則】僅輸出一個 JSON 物件；禁止 Markdown、禁止程式碼區塊（禁止 ```）、禁止任何 JSON 以外的文字。"""


def _parse_acting_json(raw_text: str) -> dict[str, Any]:
    data = parse_json_text(raw_text)
    if not isinstance(data, dict):
        raise ValueError("Gemini 回傳非 JSON 物件")

    score_raw = data.get("score_acting")
    feedback_raw = data.get("feedback_acting")

    try:
        score_acting = int(float(score_raw))
    except (TypeError, ValueError):
        raise ValueError("score_acting 無效") from None
    score_acting = max(0, min(100, score_acting))

    if not isinstance(feedback_raw, str) or not feedback_raw.strip():
        raise ValueError("feedback_acting 缺失或空白")
    feedback_acting = feedback_raw.strip()
    if len(feedback_acting) > 400:
        feedback_acting = feedback_acting[:400]

    return {"score_acting": score_acting, "feedback_acting": feedback_acting}


def _gemini_eval_models() -> tuple[str, ...]:
    ordered: list[str] = []
    for name in (GEMINI_EVAL_PRIMARY_MODEL, *_GEMINI_EVAL_FALLBACK_MODELS):
        model_name = str(name or "").strip()
        if model_name and model_name not in ordered:
            ordered.append(model_name)
    return tuple(ordered)


def evaluate_acting_multimodal(
    *,
    audio_path: Path,
    mime_type: str,
    sentence: str,
    scenario: str,
) -> dict[str, Any]:
    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY 未設定（請在 backend/.env 設定 GEMINI_API_KEY 或 GOOGLE_API_KEY 後重啟 Flask。）"
        )

    load_backend_env()
    client = genai.Client(api_key=api_key)

    prompt = _build_director_prompt(sentence=sentence, scenario=scenario)
    mt = (mime_type or "application/octet-stream").strip() or "application/octet-stream"

    last_err: Exception | None = None
    for model_name in _gemini_eval_models():
        try:
            uploaded = client.files.upload(
                file=str(audio_path),
                config=types.UploadFileConfig(mime_type=mt),
            )
        except Exception as exc:
            raise_gemini_rate_limit_if_needed(exc)
            last_err = exc
            continue

        try:
            enforce_gemini_request_limit(model_name)
            resp = client.models.generate_content(
                model=model_name,
                contents=[prompt, uploaded],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.75,
                ),
            )
        except GeminiRateLimitError:
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                pass
            raise
        except Exception as exc:
            try:
                raise_gemini_rate_limit_if_needed(exc)
            finally:
                try:
                    client.files.delete(name=uploaded.name)
                except Exception:
                    pass
            last_err = exc
            continue

        try:
            client.files.delete(name=uploaded.name)
        except Exception:
            pass

        raw = (getattr(resp, "text", None) or "").strip()
        if not raw:
            last_err = RuntimeError("Gemini 回傳空白")
            continue

        try:
            return _parse_acting_json(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            last_err = exc
            continue

    if last_err is not None:
        raise RuntimeError(f"Gemini 演技講評失敗: {last_err}") from last_err
    raise RuntimeError("Gemini 演技講評失敗")
