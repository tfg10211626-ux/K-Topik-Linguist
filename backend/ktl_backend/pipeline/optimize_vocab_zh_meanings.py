"""Optimize 中文意思 in TOPIK vocab JSON files (cleanup + Gemini batch rewrite)."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from ktl_backend.config import get_gemini_api_key, load_backend_env, project_root

HANGUL_RE = re.compile(r"[가-힣]")
DIGIT_RE = re.compile(r"\d")
TRAILING_NUM_RE = re.compile(r"\s+\d+\s*$")
ATTACHED_NUM_RE = re.compile(r"([\u4e00-\u9fff])[0-9]+")
SEP_RE = re.compile(r"[，,、；;]+")

# Korean number / day words → fixed zh (TOPIK 初級常見)
KO_NUMERAL_ZH: dict[str, str] = {
    "영": "零",
    "일": "一",
    "이": "二",
    "삼": "三",
    "사": "四",
    "오": "五",
    "육": "六",
    "칠": "七",
    "팔": "八",
    "구": "九",
    "십": "十",
    "백": "百",
    "천": "千",
    "만": "萬",
    "하나": "一",
    "둘": "二",
    "셋": "三",
    "넷": "四",
    "다섯": "五",
    "여섯": "六",
    "일곱": "七",
    "여덟": "八",
    "아홉": "九",
    "열": "十",
    "스물": "二十",
    "서른": "三十",
    "마흔": "四十",
    "쉰": "五十",
    "예순": "六十",
    "일흔": "七十",
    "여든": "八十",
    "아흔": "九十",
    "첫째": "第一",
    "둘째": "第二",
    "셋째": "第三",
    "넷째": "第四",
    "다섯째": "第五",
    "사흘": "三天",
    "나흘": "四天",
    "닷새": "五天",
    "엿새": "六天",
    "이레": "七天",
    "여드레": "八天",
    "아흐레": "九天",
    "열흘": "十天",
}

# Hard overrides after model pass (word_kr → zh)
WORD_OVERRIDE_ZH: dict[str, str] = {
    "가슴": "胸部；內心",
    "가요": "歌謠",
    "간장": "醬油",
    "글씨": "字跡；字體",
    "글자": "文字；字",
    "노래방": "卡拉 OK",
    "디브이디": "DVD",
    "티셔츠": "T 恤",
    "들": "（量詞）場、段",
    "방송": "廣播；播出",
    "거스름돈": "找零",
    "가능": "可能；可行性",
    "가늘다": "細的；薄的",
    "가리키다": "指向；指明",
    "가사": "歌詞；（家庭）家事",
    "골치가": "頭痛；麻煩",
    "메다": "揹、背負",
}

GEMINI_MODEL = "gemini-3.1-flash-lite"
BATCH_SIZE = 80


def _dedupe_parts(text: str) -> str:
    parts = [p.strip() for p in SEP_RE.split(text) if p.strip()]
    seen: list[str] = []
    for p in parts:
        if p not in seen:
            seen.append(p)
    return "、".join(seen)


def preclean_meaning(word_kr: str, meaning: str) -> str:
    if word_kr in KO_NUMERAL_ZH:
        return KO_NUMERAL_ZH[word_kr]
    m = meaning.strip()
    m = TRAILING_NUM_RE.sub("", m)
    m = ATTACHED_NUM_RE.sub(r"\1", m)
    m = re.sub(r"\s*～\s*[^、，,\s]*", "", m)
    m = re.sub(r"\s+\d+\s*～\s*[^、，,\s]*", "", m)
    m = HANGUL_RE.sub("", m).strip()
    m = _dedupe_parts(m)
    return m


def _needs_fix(meaning: str) -> bool:
    if not meaning.strip():
        return True
    if HANGUL_RE.search(meaning):
        return True
    if DIGIT_RE.search(meaning):
        return True
    if re.search(r"(.+)\\1", meaning.replace("、", "").replace("，", "")):
        return True
    return False


def validate_zh(meaning: str) -> bool:
    if not meaning or len(meaning) > 48:
        return False
    if HANGUL_RE.search(meaning):
        return False
    if DIGIT_RE.search(meaning):
        return False
    return True


def build_prompt(level_zh: str, items: list[dict[str, str]]) -> str:
    return f"""你是韓語教材編輯。請優化下列 TOPIK {level_zh} 單字的「中文意思」（繁體中文、台灣用語）。

規則：
1. 僅輸出 JSON 陣列，每項 {{"w":"韓文單字","zh":"中文意思"}}，w 必須與輸入完全一致。
2. 禁止韓文諺文、禁止阿拉伯數字（數詞用中文，如「五」「十天」）。
3. 刪除重複釋義；多義用頓號「、」連接；每義簡潔（通常 2–12 字）。
4. 用書面、教材用語；避免過白話（如「包包」→「包」）、避免錯譯與贅語。
5. 動詞/形容詞用自然中文（如「靠近」「教導」）；專有名詞用台灣慣用譯名，必要時括號簡註。
6. 若 cur 已正確可微調，勿憑空添加無關義項。

輸入：
{json.dumps(items, ensure_ascii=False)}"""


def gemini_batch(
    client: genai.Client,
    level_zh: str,
    items: list[dict[str, str]],
) -> dict[str, str]:
    prompt = build_prompt(level_zh, items)
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.15,
        ),
    )
    raw = (getattr(resp, "text", None) or "").strip()
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError("expected JSON array")
    out: dict[str, str] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        w = row.get("w")
        zh = row.get("zh")
        if isinstance(w, str) and isinstance(zh, str) and w.strip() and zh.strip():
            out[w.strip()] = zh.strip()
    return out


def optimize_file(
    path: Path,
    *,
    dry_run: bool = False,
    sleep_s: float = 0.25,
) -> dict[str, int]:
    load_backend_env()
    api_key = get_gemini_api_key()
    if not api_key:
        raise SystemExit("GEMINI_API_KEY not configured")

    doc = json.loads(path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = doc["entries"]
    level_zh = str(doc.get("summary_level") or entries[0].get("等級") or "初級")

    client = genai.Client(api_key=api_key)
    stats = {"total": len(entries), "updated": 0, "override": 0, "fallback": 0}

    for start in range(0, len(entries), BATCH_SIZE):
        batch_entries = entries[start : start + BATCH_SIZE]
        payload = [
            {
                "w": e["韓文單字"],
                "cur": preclean_meaning(str(e["韓文單字"]), str(e.get("中文意思") or "")),
            }
            for e in batch_entries
        ]
        mapping: dict[str, str] = {}
        for attempt in range(3):
            try:
                mapping = gemini_batch(client, level_zh, payload)
                break
            except Exception:
                time.sleep(1.0 * (attempt + 1))
        time.sleep(sleep_s)

        for e in batch_entries:
            w = str(e["韓文單字"]).strip()
            old = str(e.get("中文意思") or "")
            cleaned = preclean_meaning(w, old)
            new = mapping.get(w, cleaned)
            new = preclean_meaning(w, new)
            if w in WORD_OVERRIDE_ZH:
                new = WORD_OVERRIDE_ZH[w]
                stats["override"] += 1
            if not validate_zh(new):
                new = cleaned if validate_zh(cleaned) else (KO_NUMERAL_ZH.get(w) or cleaned)
                stats["fallback"] += 1
            new = _dedupe_parts(new)
            if new != old:
                stats["updated"] += 1
            e["中文意思"] = new

        print(f"  {path.name}: {min(start + BATCH_SIZE, len(entries))}/{len(entries)}")

    if not dry_run:
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize 中文意思 in vocab JSON files.")
    parser.add_argument(
        "--file",
        choices=("beginner", "intermediate", "both"),
        default="both",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    zh_dir = project_root() / "data" / "processed" / "vocab_books"
    files: list[Path] = []
    if args.file in ("beginner", "both"):
        files.append(zh_dir / "topik_vol_beginner.zh.v1.json")
    if args.file in ("intermediate", "both"):
        files.append(zh_dir / "topik_vol_intermediate.zh.v1.json")

    for fp in files:
        if not fp.is_file():
            raise SystemExit(f"Missing: {fp}")
        print(f"Optimizing {fp} ...")
        stats = optimize_file(fp, dry_run=args.dry_run)
        print(f"Done {fp.name}: {stats}")


if __name__ == "__main__":
    main()
