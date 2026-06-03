from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import types

from ktl_backend.config import get_gemini_api_key
from services.gemini_json import parse_json_text
from services.gemini_rate_limit import enforce_gemini_request_limit, raise_gemini_rate_limit_if_needed

PROCESS_WORD_GEMINI_MODEL = "gemini-3.1-flash-lite"


def build_process_word_prompt(word: str, scenario: str, topik_level_zh: str) -> str:
    return f"""你是一位韓劇編劇與語言老師。請根據以下要求產出 JSON 格式數據：
a. 請幫我生成一句包含 {word} 的韓劇台詞，務必使用{word}。

風格為：{scenario}，請注意句子風格需與情境高度一致。

難度為：Topik {topik_level_zh}。

字數不超過 50 個字，適時加入標點符號。
b. 請注意，需要生成與風格一致的語尾變化。
c. 針對生成的句子提出「重點單字＆語法」（總共不要超過 2 個，並以數字列點呈現;此段請用分隔線與上面的造句分割）。
d. 請不要生成超過我要求的東西，僅回傳 JSON 格式如下：（中文翻譯和重點單字文法中間需要空一行）
{{"sentence": "...", "translation": "...", "analysis": ["...", "...", "..."]}}

【輸出規則】僅輸出一個 JSON 物件；禁止 Markdown、禁止程式碼區塊（禁止 ```）、禁止任何 JSON 以外的文字。"""


def _parse_and_normalize_payload(raw_text: str) -> dict[str, Any]:
    data = parse_json_text(raw_text)
    if not isinstance(data, dict):
        raise ValueError("Gemini returned non-object JSON")

    sentence = data.get("sentence")
    translation = data.get("translation")
    analysis = data.get("analysis")

    if not isinstance(sentence, str) or not sentence.strip():
        raise ValueError("Invalid response: missing or empty sentence")

    trans_out = translation.strip() if isinstance(translation, str) else ""
    analysis_out: list[str] = []
    if isinstance(analysis, list):
        for item in analysis[:3]:
            if isinstance(item, str) and item.strip():
                analysis_out.append(item.strip())
            elif item is not None:
                analysis_out.append(str(item).strip())

    return {
        "sentence": sentence.strip(),
        "translation": trans_out,
        "analysis": analysis_out,
    }


def generate_process_word_response(
    *,
    word: str,
    scenario: str,
    topik_level_zh: str,
) -> dict[str, Any]:
    api_key = get_gemini_api_key()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured（請在 backend/.env 的 GEMINI_API_KEY= 右側貼上金鑰、"
            "儲存檔案後重啟 Flask；若已貼上仍出現此訊息，表示目前存到磁碟的值仍為空。另可設 GOOGLE_API_KEY。）"
        )

    client = genai.Client(api_key=api_key)
    model_name = PROCESS_WORD_GEMINI_MODEL
    prompt = build_process_word_prompt(word, scenario, topik_level_zh)
    enforce_gemini_request_limit(model_name)
    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.7,
            ),
        )
    except Exception as exc:
        raise_gemini_rate_limit_if_needed(exc)
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    raw = (getattr(resp, "text", None) or "").strip()
    if not raw:
        raise RuntimeError("Empty response from Gemini")

    return _parse_and_normalize_payload(raw)
