from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DOMAIN_DIRS: tuple[str, ...] = (
    "scripts",
    "script_lines",
    "past_papers",
    "vocab_books",
    "rules",
)


def project_root() -> Path:
    return _PROJECT_ROOT


def backend_root() -> Path:
    return _BACKEND_ROOT


def data_raw_root() -> Path:
    return project_root() / "data" / "raw"


def data_processed_root() -> Path:
    return project_root() / "data" / "processed"


def load_backend_env() -> None:
    """Load `.env`: project root then `backend/.env` (latter wins on duplicate keys)."""
    for path in (project_root() / ".env", backend_root() / ".env"):
        if path.is_file():
            load_dotenv(dotenv_path=path, override=True, encoding="utf-8-sig")


def get_gemini_api_key() -> str | None:
    load_backend_env()
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        key = os.getenv(name, "").strip()
        if key:
            return key
    return None


def get_gemini_model() -> str:
    load_backend_env()
    raw = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    return raw or DEFAULT_GEMINI_MODEL


def get_speech_key() -> str | None:
    load_backend_env()
    key = os.getenv("SPEECH_KEY", "").strip()
    return key or None


def get_speech_region() -> str | None:
    load_backend_env()
    region = os.getenv("SPEECH_REGION", "").strip()
    return region or None


def get_azure_speech_key() -> str | None:
    """Azure Speech：優先 AZURE_SPEECH_KEY，否則沿用 SPEECH_KEY。"""
    load_backend_env()
    for name in ("AZURE_SPEECH_KEY", "SPEECH_KEY"):
        key = os.getenv(name, "").strip()
        if key:
            return key
    return None


def get_azure_speech_region() -> str | None:
    """Azure Speech：優先 AZURE_SPEECH_REGION，否則沿用 SPEECH_REGION。"""
    load_backend_env()
    for name in ("AZURE_SPEECH_REGION", "SPEECH_REGION"):
        region = os.getenv(name, "").strip()
        if region:
            return region
    return None


def get_speech_url() -> str | None:
    """Optional custom endpoint URL; when set, used with SPEECH_KEY instead of region."""
    load_backend_env()
    url = os.getenv("SPEECH_URL", "").strip()
    return url or None


def get_elevenlabs_api_key() -> str | None:
    load_backend_env()
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    return key or None
