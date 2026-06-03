from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from elevenlabs import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.types import VoiceSettings

from ktl_backend.config import get_elevenlabs_api_key, load_backend_env

ELEVEN_MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT_MP3 = "mp3_44100_128"
# eleven_multilingual_v2 VoiceSettings.speed 目前 API 限制約 [0.7, 1.2]（見 invalid_voice_settings）。
_SPEED_MIN = 0.7
_SPEED_MAX = 1.2


@dataclass(frozen=True)
class _ScenarioVoice:
    voice_id: str
    speed: float
    stability: float
    similarity_boost: float
    style: float


# 情境 → Voice 與參數（Speed, Stability, Similarity, Style；後三者為 0–100，轉成 API 0–1）
_SCENARIO_VOICES: dict[str, _ScenarioVoice] = {
    "浪漫愛情": _ScenarioVoice(
        voice_id="aiUUgjHa4mpHf6UenZuf",
        speed=0.85,
        stability=0.30,
        similarity_boost=0.70,
        style=0.20,
    ),
    "嚴肅史劇": _ScenarioVoice(
        voice_id="gmRUMzXYROUiUpOrXA0z",
        speed=0.90,
        stability=0.30,
        similarity_boost=0.50,
        style=0.25,
    ),
    "狗血八點檔": _ScenarioVoice(
        voice_id="8jHHF8rMqMlg8if2mOUe",
        speed=0.9,
        stability=0.12,
        similarity_boost=0.35,
        style=0.80,
    ),
}

_DEFAULT_SCENARIO = "浪漫愛情"


def public_error_from_elevenlabs(exc: BaseException) -> tuple[str, int]:
    """回傳（給使用者看的短訊息, HTTP 狀態碼）；勿把 ApiError 的 headers／body 原樣丟給前端。"""
    if isinstance(exc, ApiError):
        status = exc.status_code or 502
        body = exc.body
        code_hint = ""
        blob = ""
        if isinstance(body, dict):
            detail = body.get("detail")
            if isinstance(detail, dict):
                code_hint = str(detail.get("code") or "").strip()
            blob = str(body).lower()
        elif body is not None:
            blob = str(body).lower()
        if status == 402 or code_hint == "paid_plan_required" or "paid_plan_required" in blob:
            return (
                "示範語音需 ElevenLabs 付費方案：免費帳戶無法透過 API 使用部分語音庫聲音，請至官網升級後再試。",
                402,
            )
        if status == 401:
            return ("ElevenLabs API 金鑰無效或未授權，請檢查 ELEVENLABS_API_KEY。", 401)
        if status == 429:
            return ("ElevenLabs 請求過於頻繁，請稍後再試。", 429)
        if status == 400:
            return ("ElevenLabs 無法處理此示範語音請求。", 400)
        return (f"ElevenLabs 服務錯誤（HTTP {status}）。", status if 400 <= status < 600 else 502)
    return (_non_api_elevenlabs_user_message(exc), 502)


def _non_api_elevenlabs_user_message(exc: BaseException) -> str:
    """非 ApiError 時避免把 traceback／dict repr 丟給前端。"""
    msg = str(exc).strip()
    low = msg.lower()
    if any(
        x in low
        for x in (
            "traceback",
            "file \"",
            "headers:",
            "status_code",
            "'detail'",
            "apierror",
        )
    ):
        return "示範語音產生失敗，請稍後再試。"
    if len(msg) > 160:
        return "示範語音產生失敗，請稍後再試。"
    return msg or "示範語音產生失敗。"


def _clamp_speed(speed: float) -> float:
    return max(_SPEED_MIN, min(_SPEED_MAX, float(speed)))


def resolve_scenario_voice(scenario: str) -> _ScenarioVoice:
    s = (scenario or "").strip() or _DEFAULT_SCENARIO
    return _SCENARIO_VOICES.get(s, _SCENARIO_VOICES[_DEFAULT_SCENARIO])


def sentence_demo_cache_key(*, scenario: str, sentence: str) -> str:
    """MD5（UTF-8）快取鍵：含模型、voice、數值參數、情境、句子，避免參數變更誤用舊檔。"""
    cfg = resolve_scenario_voice(scenario)
    scen = (scenario or "").strip() or _DEFAULT_SCENARIO
    text = (sentence or "").strip()
    spd = _clamp_speed(cfg.speed)
    raw = (
        f"{ELEVEN_MODEL_ID}|{cfg.voice_id}|{spd:.6g}|{cfg.stability:.6g}|"
        f"{cfg.similarity_boost:.6g}|{cfg.style:.6g}|{scen}|{text}"
    )
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _bytes_from_convert(client: ElevenLabs, **kwargs: object) -> bytes:
    stream = client.text_to_speech.convert(**kwargs)
    return b"".join(stream)


def synthesize_scenario_sentence_to_path(
    *,
    scenario: str,
    sentence: str,
    output_path: Path,
) -> None:
    load_backend_env()
    api_key = get_elevenlabs_api_key()
    if not api_key:
        raise RuntimeError(
            "ELEVENLABS_API_KEY is not configured（請在 backend/.env 設定後重啟 Flask。）"
        )
    text = (sentence or "").strip()
    if not text:
        raise ValueError("empty sentence for ElevenLabs TTS")

    cfg = resolve_scenario_voice(scenario)
    # 不在模組層建立 client，避免金鑰／連線狀態留在全域；每次呼叫新建實例。
    client = ElevenLabs(api_key=api_key)
    vs = VoiceSettings(
        stability=cfg.stability,
        similarity_boost=cfg.similarity_boost,
        style=cfg.style,
        speed=_clamp_speed(cfg.speed),
    )
    audio = _bytes_from_convert(
        client,
        voice_id=cfg.voice_id,
        text=text,
        model_id=ELEVEN_MODEL_ID,
        output_format=OUTPUT_FORMAT_MP3,
        voice_settings=vs,
    )
    if not audio:
        raise RuntimeError("ElevenLabs returned empty audio")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".mp3", prefix="el11_", dir=str(output_path.parent)
    )
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        tmp_p.write_bytes(audio)
        os.replace(tmp_p, output_path)
    except Exception:
        tmp_p.unlink(missing_ok=True)
        raise


def ensure_sentence_demo_audio_url(
    *,
    scenario: str,
    sentence: str,
    static_audio_dir: Path,
) -> str | None:
    """
    以 MD5 檔名快取於 static_audio_dir/elevenlabs/{md5}.mp3。
    已存在且非空則不重複呼叫 ElevenLabs；回傳 /static/audio/elevenlabs/{md5}.mp3。
    """
    text = (sentence or "").strip()
    if not text:
        return None
    if not get_elevenlabs_api_key():
        return None

    h = sentence_demo_cache_key(scenario=scenario, sentence=text)
    cache_root = static_audio_dir / "elevenlabs"
    cache_root.mkdir(parents=True, exist_ok=True)
    out_path = cache_root / f"{h}.mp3"

    try:
        if out_path.is_file() and out_path.stat().st_size > 0:
            return f"/static/audio/elevenlabs/{h}.mp3"
        synthesize_scenario_sentence_to_path(
            scenario=scenario, sentence=text, output_path=out_path
        )
    except Exception:
        try:
            if out_path.is_file() and out_path.stat().st_size == 0:
                out_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    if not out_path.is_file() or out_path.stat().st_size == 0:
        return None
    return f"/static/audio/elevenlabs/{h}.mp3"
