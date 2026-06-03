from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import azure.cognitiveservices.speech as speechsdk

from ktl_backend.config import (
    get_speech_key,
    get_speech_region,
    get_speech_url,
    load_backend_env,
)

VOICE_NAME = "ko-KR-SunHiNeural"


def _build_ssml(*, word: str, sentence: str) -> str:
    w = escape(word.strip())
    s = escape(sentence.strip())
    return (
        f"<speak version='1.0' xml:lang='ko-KR'>"
        f"<voice name='{VOICE_NAME}'>{w}<break time='1000ms'/>{s}</voice>"
        f"</speak>"
    )


def _speech_config() -> speechsdk.SpeechConfig:
    load_backend_env()
    key = get_speech_key()
    if not key:
        raise RuntimeError(
            "SPEECH_KEY is not configured（請在 backend/.env 設定 SPEECH_KEY 後重啟 Flask。）"
        )
    endpoint = (get_speech_url() or "").strip()
    if endpoint:
        return speechsdk.SpeechConfig(subscription=key, endpoint=endpoint)
    region = (get_speech_region() or "").strip()
    if not region:
        raise RuntimeError(
            "SPEECH_REGION is not configured（未設定 SPEECH_URL 時必須提供 SPEECH_REGION。）"
        )
    return speechsdk.SpeechConfig(subscription=key, region=region)


def synthesize_word_sentence_mp3(*, word: str, sentence: str, output_path: Path) -> None:
    """Synthesize Korean TTS (word, 1s pause, sentence) to MP3 via SSML; writes bytes to output_path."""
    try:
        speech_config = _speech_config()
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Azure Speech config failed: {exc}") from exc

    speech_config.speech_synthesis_voice_name = VOICE_NAME
    speech_config.set_speech_synthesis_output_format(
        speechsdk.SpeechSynthesisOutputFormat.Audio48Khz192KBitRateMonoMp3
    )

    ssml = _build_ssml(word=word, sentence=sentence)
    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=None)

    try:
        result = synthesizer.speak_ssml_async(ssml).get()
    except Exception as exc:
        raise RuntimeError(f"Azure Speech synthesis request failed: {exc}") from exc

    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        audio = result.audio_data
        if not audio:
            raise RuntimeError("Azure Speech returned empty audio")
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio)
        except OSError as exc:
            raise RuntimeError(f"Failed to write audio file: {exc}") from exc
        return

    if result.reason == speechsdk.ResultReason.Canceled:
        details = speechsdk.CancellationDetails(result)
        err = (details.error_details or "").strip() or "Speech synthesis canceled"
        raise RuntimeError(f"Azure Speech canceled: {err}")

    raise RuntimeError(f"Azure Speech synthesis failed: reason={result.reason}")
