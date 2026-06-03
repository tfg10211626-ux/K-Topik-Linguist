from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

GEMINI_RATE_LIMIT_MESSAGE = "目前測試人數過多，請稍後再試"
GEMINI_BUSY_MESSAGE = "系統忙線中，請稍後再試"
_RATE_LIMIT_WINDOW_SECONDS = 60.0
_RATE_LIMIT_MAX_REQUESTS = 14
_RATE_LIMITED_MODELS = frozenset({"gemini-3.1-flash-lite"})
_GLOBAL_COOLDOWN_SECONDS = 60.0

_request_times_by_model: dict[str, deque[float]] = defaultdict(deque)
_request_times_lock = Lock()
_cooldown_lock = Lock()
_cooldown_until = 0.0


class GeminiRateLimitError(RuntimeError):
    """Raised when the local per-model Gemini request budget is exhausted."""


def _normalize_model_name(model_name: str) -> str:
    normalized = str(model_name or "").strip().lower()
    if normalized.startswith("models/"):
        normalized = normalized.split("/", 1)[1]
    return normalized


def _extract_status_code(exc: BaseException) -> int | None:
    for attr_name in ("status_code", "code"):
        candidate = getattr(exc, attr_name, None)
        if callable(candidate):
            try:
                candidate = candidate()
            except Exception:
                candidate = None
        if isinstance(candidate, int):
            return candidate
        value = getattr(candidate, "value", None)
        if isinstance(value, int):
            return value
    return None


def is_gemini_rate_limited_exception(exc: BaseException) -> bool:
    status_code = _extract_status_code(exc)
    if status_code == 429:
        return True

    exc_type_name = type(exc).__name__.lower()
    if exc_type_name in {"toomanyrequests", "resourceexhausted"}:
        return True

    message = str(exc or "").lower()
    return "429" in message or "resource_exhausted" in message or "too many requests" in message


def activate_gemini_cooldown(seconds: float = _GLOBAL_COOLDOWN_SECONDS) -> None:
    global _cooldown_until
    now = monotonic()
    with _cooldown_lock:
        _cooldown_until = max(_cooldown_until, now + max(0.0, seconds))


def raise_gemini_rate_limit_if_needed(exc: BaseException) -> None:
    if not is_gemini_rate_limited_exception(exc):
        return
    activate_gemini_cooldown()
    raise GeminiRateLimitError(GEMINI_BUSY_MESSAGE) from exc


def enforce_gemini_request_limit(model_name: str) -> None:
    normalized = _normalize_model_name(model_name)

    now = monotonic()
    with _cooldown_lock:
        if _cooldown_until > now:
            raise GeminiRateLimitError(GEMINI_BUSY_MESSAGE)

    if normalized not in _RATE_LIMITED_MODELS:
        return

    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    with _request_times_lock:
        timestamps = _request_times_by_model[normalized]
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()
        if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
            raise GeminiRateLimitError(GEMINI_RATE_LIMIT_MESSAGE)
        timestamps.append(now)
