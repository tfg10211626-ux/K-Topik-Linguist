from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ktl_backend.config import data_processed_root, get_gemini_api_key
from services.gemini_json import parse_json_text
from services.gemini_rate_limit import (
    GeminiRateLimitError,
    enforce_gemini_request_limit,
    raise_gemini_rate_limit_if_needed,
)

LOGGER = logging.getLogger(__name__)
EXAM_GEMINI_MODEL = "gemini-2.5-flash"
ABILITY_INDICATOR_PATH = data_processed_root() / "rules" / "topik_ability_indicators.v1.json"
CACHE_ROOT = data_processed_root() / "exam" / "generated"
_RNG = secrets.SystemRandom()

_LEVEL_DIR_BY_ZH = {
    "初級": "beginner",
    "中級": "intermediate",
    "高級": "advanced",
}

_QUESTION_TYPE_META: dict[str, dict[str, Any]] = {
    "vocabulary": {
        "label_zh": "單字",
        "seed_questions": [
            {
                "prompt": "下列何者最接近「감사하다」的意思？",
                "options": ["擔心", "感謝", "等待", "比較"],
                "answer": 1,
            },
            {
                "prompt": "下列何者最接近「약속」的意思？",
                "options": ["約定", "習慣", "地點", "聲音"],
                "answer": 0,
            },
            {
                "prompt": "下列何者最接近「도서관」的意思？",
                "options": ["教室", "餐廳", "圖書館", "醫院"],
                "answer": 2,
            },
            {
                "prompt": "下列何者最接近「필요하다」的意思？",
                "options": ["需要", "結束", "借用", "相信"],
                "answer": 0,
            },
            {
                "prompt": "下列何者最接近「빠르다」的意思？",
                "options": ["昂貴", "緩慢", "快速", "乾淨"],
                "answer": 2,
            },
            {
                "prompt": "下列何者最接近「조용하다」的意思？",
                "options": ["安靜", "熱鬧", "寒冷", "忙碌"],
                "answer": 0,
            },
            {
                "prompt": "下列何者最接近「지하철」的意思？",
                "options": ["公車", "計程車", "地鐵", "飛機"],
                "answer": 2,
            },
            {
                "prompt": "下列何者最接近「준비하다」的意思？",
                "options": ["休息", "準備", "離開", "回家"],
                "answer": 1,
            },
            {
                "prompt": "下列何者最接近「시장」的意思？",
                "options": ["市場", "校長", "機場", "船長"],
                "answer": 0,
            },
            {
                "prompt": "下列何者最接近「연습」的意思？",
                "options": ["休假", "搬家", "練習", "參觀"],
                "answer": 2,
            },
        ],
    },
    "grammar": {
        "label_zh": "文法",
        "seed_questions": [
            {
                "prompt": "請選出最自然的一句：저는 친구__ 영화를 봤어요.",
                "options": ["와", "를", "에서", "보다"],
                "answer": 0,
            },
            {
                "prompt": "請選出最自然的一句：비가 오__ 우산을 가져가세요.",
                "options": ["는데", "니까", "보다", "처럼"],
                "answer": 1,
            },
            {
                "prompt": "請選出最自然的一句：오늘은 어제__ 덜 추워요.",
                "options": ["마다", "처럼", "보다", "까지"],
                "answer": 2,
            },
            {
                "prompt": "請選出最自然的一句：숙제를 다 한 __ 텔레비전을 봤어요.",
                "options": ["부터", "후에", "만큼", "보다"],
                "answer": 1,
            },
            {
                "prompt": "請選出最自然的一句：한국어를 잘하고 싶어서 매일 __.",
                "options": ["연습해요", "연습이에요", "연습보다", "연습부터"],
                "answer": 0,
            },
            {
                "prompt": "請選出最自然的一句：시간이 없__ 택시를 탔어요.",
                "options": ["고", "는데", "어서", "마다"],
                "answer": 2,
            },
            {
                "prompt": "請選出最自然的一句：주말에는 집에서 푹 __ 싶어요.",
                "options": ["쉬고", "쉬는", "쉬다", "쉬어서"],
                "answer": 0,
            },
            {
                "prompt": "請選出最自然的一句：이 책은 생각보다 __ 읽어요.",
                "options": ["쉽게", "쉽다", "쉬운", "쉬어서"],
                "answer": 0,
            },
            {
                "prompt": "請選出最自然的一句：수업이 끝나면 바로 집에 __ 거예요.",
                "options": ["가요", "가고", "갈", "가서"],
                "answer": 2,
            },
            {
                "prompt": "請選出最自然的一句：내일 시험이 있어서 오늘은 일찍 __.",
                "options": ["자요", "잘", "자는", "자서"],
                "answer": 0,
            },
        ],
    },
}


class ExamQuestionError(Exception):
    """Raised when exam question generation fails."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_path(level_zh: str, question_type: str) -> Path:
    level_dir = _LEVEL_DIR_BY_ZH.get(level_zh, "unknown")
    return CACHE_ROOT / level_dir / f"{question_type}.json"


def _question_key(question: dict[str, Any]) -> str:
    prompt = str(question.get("prompt", "")).strip()
    options = [str(option).strip() for option in question.get("options", [])]
    return json.dumps({"prompt": prompt, "options": options}, ensure_ascii=False, sort_keys=True)


def _normalize_answer(raw: Any) -> int:
    if isinstance(raw, bool):
        raise ExamQuestionError("Invalid answer index")
    if isinstance(raw, int):
        answer = raw
    elif isinstance(raw, str):
        token = raw.strip().upper()
        if token.isdigit():
            answer = int(token)
        elif token in {"A", "B", "C", "D"}:
            answer = ord(token) - ord("A")
        else:
            raise ExamQuestionError("Invalid answer index")
    else:
        raise ExamQuestionError("Invalid answer index")
    if answer < 0 or answer > 3:
        raise ExamQuestionError("Answer index out of range")
    return answer


def _normalize_question(question: Any) -> dict[str, Any]:
    if not isinstance(question, dict):
        raise ExamQuestionError("Question item must be an object")

    prompt = question.get("prompt")
    options = question.get("options")
    answer = question.get("answer")

    if not isinstance(prompt, str) or not prompt.strip():
        raise ExamQuestionError("Question prompt is missing")
    if not isinstance(options, list) or len(options) != 4:
        raise ExamQuestionError("Question options must contain exactly 4 items")

    normalized_options: list[str] = []
    for option in options:
        if not isinstance(option, str) or not option.strip():
            raise ExamQuestionError("Question option is missing")
        normalized_options.append(option.strip())

    return {
        "prompt": prompt.strip(),
        "options": normalized_options,
        "answer": _normalize_answer(answer),
    }


def _parse_gemini_questions(raw_text: str, expected_count: int) -> list[dict[str, Any]]:
    try:
        data = parse_json_text(raw_text)
    except json.JSONDecodeError as exc:
        raise ExamQuestionError("Gemini returned non-JSON output") from exc

    if isinstance(data, dict):
        rows = data.get("questions")
    else:
        rows = data

    if not isinstance(rows, list):
        raise ExamQuestionError("Gemini JSON must contain questions array")
    if len(rows) != expected_count:
        raise ExamQuestionError("Gemini returned unexpected question count")

    normalized = [_normalize_question(row) for row in rows]
    return normalized


def _pick_questions(bank: list[dict[str, Any]], count: int, prefix: str) -> list[dict[str, Any]]:
    if count <= 0 or not bank:
        return []

    shuffled = bank[:]
    _RNG.shuffle(shuffled)
    picked: list[dict[str, Any]] = []
    for index in range(count):
        template = shuffled[index % len(shuffled)]
        picked.append(
            {
                "id": f"{prefix}-{index + 1}",
                "prompt": template["prompt"],
                "options": list(template["options"]),
                "answer": template["answer"],
            }
        )
    return picked


def _shuffle_questions(questions: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    shuffled = [dict(question) for question in questions]
    _RNG.shuffle(shuffled)
    for index, question in enumerate(shuffled, start=1):
        question["id"] = f"{prefix}-{index}"
    return shuffled


def _load_cached_questions(level_zh: str, question_type: str) -> list[dict[str, Any]]:
    path = _cache_path(level_zh, question_type)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    rows = data.get("questions")
    if not isinstance(rows, list):
        return []

    normalized: list[dict[str, Any]] = []
    for row in rows:
        try:
            normalized.append(_normalize_question(row))
        except ExamQuestionError:
            continue
    return normalized


def _save_generated_questions(level_zh: str, question_type: str, questions: list[dict[str, Any]]) -> None:
    path = _cache_path(level_zh, question_type)
    existing = _load_cached_questions(level_zh, question_type)
    merged = existing[:]
    seen = {_question_key(question) for question in merged}

    for question in questions:
        key = _question_key(question)
        if key in seen:
            continue
        merged.append(
            {
                "prompt": question["prompt"],
                "options": list(question["options"]),
                "answer": question["answer"],
            }
        )
        seen.add(key)

    merged = merged[-200:]
    payload = {
        "level": level_zh,
        "question_type": question_type,
        "question_type_label": _QUESTION_TYPE_META[question_type]["label_zh"],
        "updated_at": _utc_now(),
        "questions": merged,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_ability_indicators() -> dict[str, Any]:
    if not ABILITY_INDICATOR_PATH.is_file():
        raise ExamQuestionError(f"Ability indicators file not found: {ABILITY_INDICATOR_PATH}")
    try:
        data = json.loads(ABILITY_INDICATOR_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ExamQuestionError("Failed to read ability indicators") from exc
    if not isinstance(data, dict):
        raise ExamQuestionError("Ability indicators JSON root must be an object")
    return data


def _select_level_indicators(level_zh: str, ability_doc: dict[str, Any]) -> list[dict[str, Any]]:
    levels = ability_doc.get("levels")
    if not isinstance(levels, list):
        return []
    return [
        row
        for row in levels
        if isinstance(row, dict) and str(row.get("user_level", "")).strip() == level_zh
    ]


def _build_user_prompt(level_zh: str, question_type: str, count: int) -> str:
    question_meta = _QUESTION_TYPE_META[question_type]
    ability_doc = _load_ability_indicators()
    level_indicators = _select_level_indicators(level_zh, ability_doc)
    reference_examples = question_meta["seed_questions"][:2]
    return (
        "請只輸出一個 JSON 物件，禁止 Markdown、禁止說明文字、禁止程式碼區塊。\n"
        "輸出格式必須完全符合：\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "prompt": string,\n'
        '      "options": [string, string, string, string],\n'
        '      "answer": 0\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "規則：\n"
        f"- questions 陣列長度必須剛好是 {count}。\n"
        "- 每題必須只有 4 個選項，且只有 1 個正確答案。\n"
        "- answer 必須是 0 到 3 的整數。\n"
        "- 題幹請用繁體中文；韓文單字、句子、助詞與語尾可以保留韓文。\n"
        f"- 本次題型：{question_meta['label_zh']}。\n"
        f"- 本次程度：{level_zh}。\n"
        "- 單字題請以詞義、語境、近義辨析為主；文法題請以助詞、語尾、連接語尾、句型搭配為主。\n"
        "- 嚴格依照提供的能力指標出題，不可超出該程度。\n"
        "- 選項要有干擾性，但不能有多個正解。\n"
        "- 不要重複題目。\n"
        "- 請仿照真正的Topik出題方式及對應難度，不要直接輸出考古題原文，請根據考古題的出題邏輯，生成『類似難度』的題目。\n"
        "- 題目跟選項都必須是全韓文，不要出現中文。\n"
        "\n"
        #"目前前端既有題型邏輯參考：\n"
        #f"{json.dumps(reference_examples, ensure_ascii=False, indent=2)}\n"
        "\n"
        "能力指標來源：data/processed/rules/topik_ability_indicators.v1.json\n"
        "本次可參考的分級資料：\n"
        f"{json.dumps(level_indicators, ensure_ascii=False, indent=2)}"
    )


def _generate_single_type_questions(
    *,
    level_zh: str,
    question_type: str,
    count: int,
) -> tuple[list[dict[str, Any]], str]:
    from google import genai
    from google.genai import types

    api_key = get_gemini_api_key()
    if not api_key:
        raise ExamQuestionError("GEMINI_API_KEY is not configured")

    question_type_label = _QUESTION_TYPE_META[question_type]["label_zh"]
    system_prompt = (
        "你是一位 TOPIK 出題官。"
        f"請參考提供的考古題邏輯，根據{question_type_label}{count}題出題。"
        "必須嚴格遵守分級標準。"
    )
    user_prompt = _build_user_prompt(level_zh, question_type, count)

    client = genai.Client(api_key=api_key)

    try:
        enforce_gemini_request_limit(EXAM_GEMINI_MODEL)
        response = client.models.generate_content(
            model=EXAM_GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                temperature=0.9,
            ),
        )
    except GeminiRateLimitError:
        raise
    except Exception as exc:
        raise_gemini_rate_limit_if_needed(exc)
        raise ExamQuestionError(f"Gemini request failed: {exc}") from exc

    raw_text = (getattr(response, "text", None) or "").strip()
    if not raw_text:
        raise ExamQuestionError("Gemini returned empty content")

    questions = _parse_gemini_questions(raw_text, count)
    _save_generated_questions(level_zh, question_type, questions)
    return _pick_questions(questions, count, question_type), "gemini"


def _fallback_single_type_questions(
    *,
    level_zh: str,
    question_type: str,
    count: int,
) -> tuple[list[dict[str, Any]], str]:
    cached = _load_cached_questions(level_zh, question_type)
    if cached:
        return _pick_questions(cached, count, question_type), "cache"
    seed = _QUESTION_TYPE_META[question_type]["seed_questions"]
    return _pick_questions(seed, count, question_type), "seed"


def _get_single_type_questions(
    *,
    level_zh: str,
    question_type: str,
    count: int,
) -> tuple[list[dict[str, Any]], str]:
    try:
        return _generate_single_type_questions(level_zh=level_zh, question_type=question_type, count=count)
    except GeminiRateLimitError:
        raise
    except Exception as exc:
        LOGGER.warning(
            "Exam question generation failed; falling back. level=%s type=%s error=%s",
            level_zh,
            question_type,
            exc,
        )
        return _fallback_single_type_questions(level_zh=level_zh, question_type=question_type, count=count)


def generate_exam_questions_response(
    *,
    level_zh: str,
    question_type: str,
    count: int,
) -> dict[str, Any]:
    if question_type not in {"vocabulary", "grammar", "mixed"}:
        raise ExamQuestionError("Unsupported question type")
    if count <= 0:
        raise ExamQuestionError("Question count must be positive")

    if question_type in {"vocabulary", "grammar"}:
        questions, source = _get_single_type_questions(
            level_zh=level_zh,
            question_type=question_type,
            count=count,
        )
        return {
            "level": level_zh,
            "question_type": question_type,
            "source": source,
            "questions": questions,
        }

    vocab_count = (count + 1) // 2
    grammar_count = count // 2
    vocab_questions, vocab_source = _get_single_type_questions(
        level_zh=level_zh,
        question_type="vocabulary",
        count=vocab_count,
    )
    grammar_questions, grammar_source = _get_single_type_questions(
        level_zh=level_zh,
        question_type="grammar",
        count=grammar_count,
    )
    mixed_questions = _shuffle_questions(vocab_questions + grammar_questions, "mixed")
    return {
        "level": level_zh,
        "question_type": question_type,
        "source": f"vocabulary:{vocab_source},grammar:{grammar_source}",
        "questions": mixed_questions,
    }
