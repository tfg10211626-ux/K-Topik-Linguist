from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import azure.cognitiveservices.speech as speechsdk

from ktl_backend.config import (
    get_azure_speech_key,
    get_azure_speech_region,
    get_speech_url,
    load_backend_env,
)


def _speech_config_eval() -> speechsdk.SpeechConfig:
    load_backend_env()
    key = get_azure_speech_key()
    if not key:
        raise RuntimeError(
            "Azure Speech 金鑰未設定（請在 .env 設定 AZURE_SPEECH_KEY 或 SPEECH_KEY 後重啟 Flask。）"
        )
    endpoint = (get_speech_url() or "").strip()
    try:
        if endpoint:
            return speechsdk.SpeechConfig(subscription=key, endpoint=endpoint)
        region = (get_azure_speech_region() or "").strip()
        if not region:
            raise RuntimeError(
                "Azure Speech 區域未設定（請在 .env 設定 AZURE_SPEECH_REGION 或 SPEECH_REGION；"
                "若已設定 SPEECH_URL 則可省略區域。）"
            )
        return speechsdk.SpeechConfig(subscription=key, region=region)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Azure Speech 設定失敗: {exc}") from exc


def _convert_audio_to_wav_16k_mono(src: Path, dst_wav: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError(
            "伺服器未安裝 ffmpeg，無法將錄音轉成 WAV 以供發音評分。"
            "請安裝 ffmpeg 或改送 WAV 格式。"
        )
    try:
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(src),
                "-ar",
                "16000",
                "-ac",
                "1",
                str(dst_wav),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("音訊轉檔逾時") from exc
    except Exception as exc:
        raise RuntimeError(f"音訊轉檔失敗: {exc}") from exc
    if proc.returncode != 0 or not dst_wav.is_file():
        err = (proc.stderr or proc.stdout or "").strip() or f"exit={proc.returncode}"
        raise RuntimeError(f"ffmpeg 轉檔失敗: {err[:500]}")


def _ensure_wav_for_assessment(upload_path: Path) -> tuple[Path, bool]:
    """回傳 (wav_path, should_delete_wav)。若上傳已是 16k mono wav 可直接使用。"""
    suffix = upload_path.suffix.lower()
    if suffix == ".wav":
        return upload_path, False
    fd, tmp_name = tempfile.mkstemp(suffix=".wav", prefix="ktl_pa_")
    try:
        os.close(fd)
    except OSError:
        pass
    tmp = Path(tmp_name)
    try:
        _convert_audio_to_wav_16k_mono(upload_path, tmp)
    except Exception:
        if tmp.is_file():
            tmp.unlink(missing_ok=True)
        raise
    return tmp, True


def assess_korean_pronunciation(*, audio_path: Path, reference_text: str) -> dict[str, Any]:
    """
    使用 Azure Speech Pronunciation Assessment 評估韓語發音與流利度。
    回傳 accuracy_score、prosody_score（0–100，實取 FluencyScore，與前端欄位名相容）；失敗時拋出例外。
    """
    ref = (reference_text or "").strip()
    if not ref:
        raise ValueError("reference_text 不可為空")

    wav_path: Path | None = None
    delete_wav = False
    try:
        wav_path, delete_wav = _ensure_wav_for_assessment(audio_path)
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"準備音訊檔失敗: {exc}") from exc

    try:
        speech_config = _speech_config_eval()
        speech_config.speech_recognition_language = "ko-KR"

        audio_config = speechsdk.audio.AudioConfig(filename=str(wav_path))

        pronunciation_config = speechsdk.PronunciationAssessmentConfig(
            reference_text=ref,
            grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
            granularity=speechsdk.PronunciationAssessmentGranularity.FullText,
            enable_miscue=True,
        )
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config
        )
        try:
            pronunciation_config.apply_to(recognizer)
        except Exception as exc:
            try:
                recognizer.close()
            except Exception:
                pass
            raise RuntimeError(f"無法套用發音評估設定: {exc}") from exc

        try:
            result = recognizer.recognize_once()
        except Exception as exc:
            raise RuntimeError(f"Azure 辨識請求失敗: {exc}") from exc
        finally:
            try:
                recognizer.close()
            except Exception:
                pass

        if result.reason != speechsdk.ResultReason.RecognizedSpeech:
            if result.reason == speechsdk.ResultReason.Canceled:
                details = speechsdk.CancellationDetails(result)
                msg = (details.error_details or "").strip() or "辨識已取消"
                raise RuntimeError(f"Azure Speech 取消: {msg}")
            raise RuntimeError(f"Azure Speech 辨識未成功: reason={result.reason}")

        raw_json = result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
        if not raw_json:
            raise RuntimeError("Azure 未回傳 JSON 評分結果")

        try:
            detail = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"解析 Azure JSON 失敗: {exc}") from exc

        nbest = detail.get("NBest")
        if not isinstance(nbest, list) or not nbest:
            raise RuntimeError("Azure 回傳缺少 NBest")

        first = nbest[0]
        if not isinstance(first, dict):
            raise RuntimeError("Azure NBest 格式異常")

        pa = first.get("PronunciationAssessment")
        if not isinstance(pa, dict):
            raise RuntimeError("Azure 回傳缺少 PronunciationAssessment")

        acc = pa.get("AccuracyScore")
        flu = pa.get("FluencyScore")
        try:
            accuracy_score = float(acc) if acc is not None else 0.0
        except (TypeError, ValueError):
            accuracy_score = 0.0
        try:
            prosody_score = float(flu) if flu is not None else 0.0
        except (TypeError, ValueError):
            prosody_score = 0.0

        return {
            "accuracy_score": max(0.0, min(100.0, accuracy_score)),
            "prosody_score": max(0.0, min(100.0, prosody_score)),
        }
    finally:
        if delete_wav and wav_path is not None and wav_path.is_file():
            try:
                wav_path.unlink()
            except OSError:
                pass
