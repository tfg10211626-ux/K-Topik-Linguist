from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from flask import Flask, abort, current_app, jsonify, request, send_from_directory, session

from ktl_backend.config import (
    data_processed_root,
    get_elevenlabs_api_key,
    load_backend_env,
    project_root,
)
from services.azure_eval_service import assess_korean_pronunciation
from services.azure_service import synthesize_word_sentence_mp3
from services.elevenlab_voice_service import (
    ensure_sentence_demo_audio_url,
    public_error_from_elevenlabs,
)
from services.gemini_eval_service import GEMINI_EVAL_PRIMARY_MODEL, evaluate_acting_multimodal
from services.exam_question_service import ExamQuestionError, generate_exam_questions_response
from services.gemini_rate_limit import (
    GEMINI_BUSY_MESSAGE,
    GeminiRateLimitError,
    enforce_gemini_request_limit,
)
from services.gemini_service import generate_process_word_response

from ktl_backend.auth_routes import auth_bp
from ktl_backend.vocabulary_routes import vocabulary_bp
from ktl_backend.study_match import match_study_vocab

load_backend_env()

STATIC_SITE_ROOT = project_root() / "static-site"
DATA_ROOT = project_root() / "data"

_LEVEL_ROWS: tuple[tuple[str, str, str], ...] = (
    ("beginner", "初級", "topik_vol_beginner.zh.v1.json"),
    ("intermediate", "中級", "topik_vol_intermediate.zh.v1.json"),
    ("advanced", "高級", "topik_advanced.zh.v1.json"),
)
_CANONICAL_BY_ALIAS: dict[str, str] = {}
for canon, zh, _fn in _LEVEL_ROWS:
    _CANONICAL_BY_ALIAS[canon] = canon
    _CANONICAL_BY_ALIAS[canon.lower()] = canon
    _CANONICAL_BY_ALIAS[zh] = canon
_ZH_BY_CANONICAL: dict[str, str] = {c: z for c, z, _ in _LEVEL_ROWS}
_FILE_BY_CANONICAL: dict[str, str] = {c: f for c, _, f in _LEVEL_ROWS}


def _validate_acting_audio(path: Path) -> tuple[bool, str]:
    """錄音過短、過小或無法解析時視為無效，不呼叫 Azure／Gemini/ElevenLabs。"""
    try:
        size = path.stat().st_size
    except OSError:
        return False, "請重新錄音"
    if size < 900:
        return False, "請重新錄音"
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return True, ""
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if proc.returncode != 0:
            return True, ""
        raw = (proc.stdout or "").strip()
        if not raw or raw == "N/A":
            return False, "請重新錄音"
        dur = float(raw)
        if dur != dur or dur < 0.35:
            return False, "請重新錄音"
    except (ValueError, subprocess.TimeoutExpired, OSError):
        return True, ""
    return True, ""


def _public_eval_service_error(service: str) -> str:
    if service == "azure":
        return "發音評分暫時不可用，請稍後再試。"
    if service == "gemini":
        return "演技講評暫時不可用，請稍後再試。"
    return "評分系統暫時不可用，請稍後再試。"


_DEFAULT_CORS_ORIGINS: frozenset[str] = frozenset(
    {
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:8080",
        "http://localhost:8080",
    }
)


def _cors_allowed_origins() -> set[str]:
    extra_raw = (os.getenv("KTL_CORS_ORIGINS") or "").strip()
    extra = {p.strip().rstrip("/") for p in extra_raw.split(",") if p.strip()} if extra_raw else set()
    return set(_DEFAULT_CORS_ORIGINS) | extra


_LOCAL_LOOPBACK = re.compile(r"^https?://(127\.0\.0\.1|localhost)(:\d+)?$")


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _session_cookie_samesite() -> str:
    raw = (os.getenv("KTL_SESSION_COOKIE_SAMESITE") or "Lax").strip().lower()
    if raw == "strict":
        return "Strict"
    if raw == "none":
        return "None"
    return "Lax"


def _origin_allowed(origin: str) -> bool:
    o = (origin or "").strip().rstrip("/")
    if not o:
        return False
    if o in _cors_allowed_origins():
        return True
    return bool(_LOCAL_LOOPBACK.match(o))


def _safe_rel_file(base: Path, rel: str) -> Path | None:
    rel = rel.strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None
    target = (base / rel).resolve()
    try:
        target.relative_to(base.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


def _normalize_level(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip()
    if not key:
        return None
    lower = key.lower()
    extras = {
        "topik1": "beginner",
        "topik2": "intermediate",
        "topik3": "advanced",
        "i": "beginner",
        "ii": "intermediate",
        "iii": "advanced",
    }
    return _CANONICAL_BY_ALIAS.get(key) or _CANONICAL_BY_ALIAS.get(lower) or extras.get(lower)


def _vocab_path(filename: str) -> Path:
    return data_processed_root() / "vocab_books" / filename


def _load_filtered_entries(canonical: str) -> tuple[str, str, list[dict[str, Any]]]:
    zh = _ZH_BY_CANONICAL[canonical]
    path = _vocab_path(_FILE_BY_CANONICAL[canonical])
    if not path.is_file():
        return zh, path.name, []
    doc = json.loads(path.read_text(encoding="utf-8"))
    rows = doc.get("entries")
    if not isinstance(rows, list):
        return zh, path.name, []
    filtered = [e for e in rows if isinstance(e, dict) and e.get("等級") == zh]
    return zh, path.name, filtered


def _pick_random_entries(entries: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    if k <= 0 or not entries:
        return []
    n = min(k, len(entries))
    rng = secrets.SystemRandom()
    return rng.sample(entries, n)


def _word_in_current_level(word: str, canonical: str) -> bool:
    if canonical not in _ZH_BY_CANONICAL:
        return False
    w = word.strip()
    _zh, _fn, entries = _load_filtered_entries(canonical)
    for row in entries:
        if not isinstance(row, dict):
            continue
        kr = row.get("韓文單字")
        if isinstance(kr, str) and kr.strip() == w:
            return True
    return False


def _find_word_level_zh(word: str) -> str | None:
    w = word.strip()
    root = data_processed_root() / "vocab_books"
    if not root.is_dir():
        return None
    for path in sorted(root.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rows = doc.get("entries")
        if not isinstance(rows, list):
            continue
        for e in rows:
            if not isinstance(e, dict):
                continue
            kr = e.get("韓文單字")
            if not isinstance(kr, str) or kr.strip() != w:
                continue
            lvl = e.get("等級")
            if isinstance(lvl, str) and lvl.strip():
                return lvl.strip()
    return None


def create_app() -> Flask:
    load_backend_env()
    app = Flask(__name__, static_folder=None)
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-set-flask-secret-key")
    app.register_blueprint(auth_bp)
    app.register_blueprint(vocabulary_bp)
    session_cookie_samesite = _session_cookie_samesite()
    app.config["SESSION_COOKIE_SAMESITE"] = session_cookie_samesite
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SECURE"] = (
        True
        if session_cookie_samesite == "None"
        else _env_flag("KTL_SESSION_COOKIE_SECURE", False)
    )

    @app.after_request
    def add_cors_headers(response: Any) -> Any:
        origin = (request.headers.get("Origin") or "").strip()
        if origin and _origin_allowed(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            req_headers = request.headers.get("Access-Control-Request-Headers")
            response.headers["Access-Control-Allow-Headers"] = (
                req_headers if req_headers else "Content-Type"
            )
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Vary"] = "Origin"
        return response

    @app.route("/api/set-level", methods=["POST", "OPTIONS"])
    def api_set_level() -> tuple[Any, int]:
        if request.method == "OPTIONS":
            return "", 204
        body = request.get_json(silent=True) or {}
        level_raw = body.get("level")
        include_entries = bool(body.get("include_entries"))
        canonical = _normalize_level(level_raw if isinstance(level_raw, str) else None)
        if canonical is None:
            return jsonify({"error": "invalid or missing level"}), 400

        zh_label, filename, entries = _load_filtered_entries(canonical)
        session["topik_level"] = canonical
        session["topik_level_zh"] = zh_label

        payload: dict[str, Any] = {
            "level": canonical,
            "summary_level": zh_label,
            "source_file": filename,
            "entry_count": len(entries),
        }
        if include_entries:
            payload["entries"] = entries
        return jsonify(payload), 200

    @app.route("/api/modes/script/word-picks", methods=["GET", "OPTIONS"])
    def api_script_word_picks() -> tuple[Any, int]:
        if request.method == "OPTIONS":
            return "", 204
        canonical = session.get("topik_level")
        if not isinstance(canonical, str) or canonical not in _ZH_BY_CANONICAL:
            return jsonify({"error": "no level in session; call POST /set-level first"}), 401

        zh_label, _filename, entries = _load_filtered_entries(canonical)
        chosen = _pick_random_entries(entries, 3)
        picks: list[dict[str, str]] = []
        for row in chosen:
            w = row.get("韓文單字")
            m = row.get("中文意思")
            if isinstance(w, str) and w.strip():
                picks.append(
                    {
                        "word_kr": w.strip(),
                        "meaning_zh": m.strip() if isinstance(m, str) else "",
                    }
                )
        return (
            jsonify(
                {
                    "level": canonical,
                    "summary_level": zh_label,
                    "picks": picks,
                }
            ),
            200,
        )

    @app.route("/api/modes/study/analyze", methods=["POST", "OPTIONS"])
    def api_study_analyze() -> tuple[Any, int]:
        if request.method == "OPTIONS":
            return "", 204
        canonical = session.get("topik_level")
        if not isinstance(canonical, str) or canonical not in _ZH_BY_CANONICAL:
            return jsonify({"error": "no level in session; call POST /api/set-level first"}), 401

        body = request.get_json(silent=True) or {}
        text_raw = body.get("text")
        if not isinstance(text_raw, str) or not text_raw.strip():
            return jsonify({"error": "missing or invalid text"}), 400

        text = text_raw.strip()
        zh_label, _filename, entries = _load_filtered_entries(canonical)
        matches = match_study_vocab(text, entries)
        return (
            jsonify(
                {
                    "level": canonical,
                    "summary_level": zh_label,
                    "match_count": len(matches),
                    "matches": matches,
                }
            ),
            200,
        )

    @app.route("/api/modes/exam/questions", methods=["POST", "OPTIONS"])
    def api_exam_questions() -> tuple[Any, int]:
        if request.method == "OPTIONS":
            return "", 204

        body = request.get_json(silent=True) or {}
        level_raw = body.get("level")
        question_type_raw = body.get("question_type")
        count_raw = body.get("count")

        canonical = _normalize_level(level_raw if isinstance(level_raw, str) else None)
        if canonical is None:
            canonical = session.get("topik_level") if isinstance(session.get("topik_level"), str) else None
        if canonical is None or canonical not in _ZH_BY_CANONICAL:
            return jsonify({"error": "invalid or missing level"}), 400

        question_type = question_type_raw.strip() if isinstance(question_type_raw, str) else ""
        if question_type not in {"vocabulary", "grammar", "mixed"}:
            return jsonify({"error": "invalid or missing question_type"}), 400

        if isinstance(count_raw, bool):
            return jsonify({"error": "invalid count"}), 400
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "invalid count"}), 400
        if count <= 0 or count > 30:
            return jsonify({"error": "count must be between 1 and 30"}), 400

        level_zh = _ZH_BY_CANONICAL[canonical]
        session["topik_level"] = canonical
        session["topik_level_zh"] = level_zh

        try:
            payload = generate_exam_questions_response(
                level_zh=level_zh,
                question_type=question_type,
                count=count,
            )
        except GeminiRateLimitError as exc:
            return jsonify({"error": str(exc)}), 429
        except ExamQuestionError as exc:
            return jsonify({"error": str(exc)}), 502
        except Exception as exc:
            current_app.logger.exception("exam question generation failed")
            return jsonify({"error": f"failed to prepare exam questions: {exc}"}), 500

        payload["summary_level"] = level_zh
        payload["level"] = canonical
        return jsonify(payload), 200

    @app.route("/process-word", methods=["POST", "OPTIONS"])
    def process_word() -> tuple[Any, int]:
        if request.method == "OPTIONS":
            return "", 204
        canonical = session.get("topik_level")
        if not isinstance(canonical, str) or canonical not in _ZH_BY_CANONICAL:
            return jsonify({"error": "no level in session; call POST /api/set-level first"}), 401

        body = request.get_json(silent=True) or {}
        word_raw = body.get("word")
        if not isinstance(word_raw, str) or not word_raw.strip():
            return jsonify({"error": "missing or invalid word"}), 400

        scenario_raw = body.get("scenario")
        scenario = (
            scenario_raw.strip()
            if isinstance(scenario_raw, str) and scenario_raw.strip()
            else "浪漫愛情"
        )

        word = word_raw.strip()
        zh_current = session.get("topik_level_zh")
        if not isinstance(zh_current, str) or not zh_current.strip():
            zh_current = _ZH_BY_CANONICAL.get(canonical, "")
        else:
            zh_current = zh_current.strip()

        level_warning: str | None = None
        if not _word_in_current_level(word, canonical):
            found_zh = _find_word_level_zh(word)
            if found_zh:
                level_warning = f"此單字並非{zh_current}單字，屬於{found_zh}單字。"
            else:
                level_warning = "等級外單字"

        try:
            result = generate_process_word_response(
                word=word,
                scenario=scenario,
                topik_level_zh=zh_current,
            )
        except GeminiRateLimitError as exc:
            payload = {"error": str(exc)}
            if level_warning:
                payload["level_warning"] = level_warning
            return jsonify(payload), 429
        except (RuntimeError, ValueError) as exc:
            payload: dict[str, Any] = {"error": str(exc)}
            if level_warning:
                payload["level_warning"] = level_warning
            return jsonify(payload), 502
        except Exception as exc:
            payload = {"error": f"Gemini request failed: {exc}"}
            if level_warning:
                payload["level_warning"] = level_warning
            return jsonify(payload), 502

        out: dict[str, Any] = dict(result)
        if level_warning:
            out["level_warning"] = level_warning

        audio_dir = STATIC_SITE_ROOT / "static" / "audio"
        filename = f"{uuid.uuid4().hex}.mp3"
        try:
            synthesize_word_sentence_mp3(
                word=word,
                sentence=out.get("sentence") if isinstance(out.get("sentence"), str) else "",
                output_path=audio_dir / filename,
            )
            out["audio_url"] = f"/static/audio/{filename}"
        except Exception:
            current_app.logger.exception("Azure TTS failed")

        try:
            skr = out.get("sentence") if isinstance(out.get("sentence"), str) else ""
            demo_url = ensure_sentence_demo_audio_url(
                scenario=scenario,
                sentence=skr,
                static_audio_dir=audio_dir,
            )
            if demo_url:
                out["sentence_demo_audio_url"] = demo_url
        except Exception:
            current_app.logger.exception("ElevenLabs sentence demo TTS failed")

        return jsonify(out), 200

    @app.route("/sentence-demo-audio", methods=["POST", "OPTIONS"])
    def sentence_demo_audio() -> tuple[Any, int]:
        if request.method == "OPTIONS":
            return "", 204
        canonical = session.get("topik_level")
        if not isinstance(canonical, str) or canonical not in _ZH_BY_CANONICAL:
            return jsonify({"error": "no level in session; call POST /api/set-level first"}), 401

        body = request.get_json(silent=True) or {}
        sentence_raw = body.get("sentence")
        if not isinstance(sentence_raw, str) or not sentence_raw.strip():
            return jsonify({"error": "missing or invalid sentence"}), 400

        scenario_raw = body.get("scenario")
        scenario = (
            scenario_raw.strip()
            if isinstance(scenario_raw, str) and scenario_raw.strip()
            else "浪漫愛情"
        )

        audio_dir = STATIC_SITE_ROOT / "static" / "audio"
        try:
            url = ensure_sentence_demo_audio_url(
                scenario=scenario,
                sentence=sentence_raw.strip(),
                static_audio_dir=audio_dir,
            )
        except Exception as exc:
            current_app.logger.exception("sentence-demo-audio failed")
            msg, code = public_error_from_elevenlabs(exc)
            return jsonify({"error": msg}), code
        if not url:
            if not get_elevenlabs_api_key():
                return jsonify({"error": "ELEVENLABS_API_KEY not configured"}), 503
            return jsonify({"error": "could not produce demo audio"}), 502
        return jsonify({"sentence_demo_audio_url": url}), 200

    @app.route("/evaluate-acting", methods=["POST", "OPTIONS"])
    def evaluate_acting() -> tuple[Any, int]:
        if request.method == "OPTIONS":
            return "", 204
        upload_path: Path | None = None
        try:
            if "audio" not in request.files:
                return jsonify({"error": "missing audio file"}), 400
            audio_file = request.files["audio"]
            if not audio_file or not getattr(audio_file, "filename", None):
                return jsonify({"error": "empty audio upload"}), 400

            sentence = (request.form.get("sentence") or "").strip()
            scenario_raw = request.form.get("scenario")
            scenario = (
                scenario_raw.strip()
                if isinstance(scenario_raw, str) and scenario_raw.strip()
                else "浪漫愛情"
            )
            if not sentence:
                return jsonify({"error": "missing or empty sentence"}), 400

            suffix = Path(str(audio_file.filename)).suffix.lower() or ".webm"
            if suffix not in {".webm", ".wav", ".mp3", ".ogg", ".m4a", ".mp4"}:
                suffix = ".webm"

            mime = (getattr(audio_file, "mimetype", None) or "").strip() or "application/octet-stream"
            if suffix == ".webm" and not mime.startswith("audio/"):
                mime = "audio/webm"

            fd, tmp_name = tempfile.mkstemp(suffix=suffix, prefix="ktl_eval_")
            try:
                os.close(fd)
            except OSError:
                pass
            upload_path = Path(tmp_name)
            try:
                audio_file.save(str(upload_path))
            except Exception as exc:
                return jsonify({"error": f"failed to save upload: {exc}"}), 500

            ok_audio, _audio_msg = _validate_acting_audio(upload_path)
            if not ok_audio:
                return (
                    jsonify(
                        {
                            "error": "請重新錄音",
                            "feedback_acting": "請重新錄音",
                            "accuracy_score": None,
                            "prosody_score": None,
                            "score_acting": None,
                            "average_total": None,
                            "azure_error": None,
                            "gemini_error": None,
                        }
                    ),
                    200,
                )

            try:
                enforce_gemini_request_limit(GEMINI_EVAL_PRIMARY_MODEL)
            except GeminiRateLimitError as exc:
                return jsonify({"error": str(exc)}), 429

            azure_out: dict[str, Any] | None = None
            gemini_out: dict[str, Any] | None = None
            azure_error: str | None = None
            gemini_error: str | None = None

            def _azure_task() -> dict[str, Any]:
                return assess_korean_pronunciation(audio_path=upload_path, reference_text=sentence)

            def _gemini_task() -> dict[str, Any]:
                return evaluate_acting_multimodal(
                    audio_path=upload_path,
                    mime_type=mime,
                    sentence=sentence,
                    scenario=scenario,
                )

            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    fut_a = pool.submit(_azure_task)
                    fut_g = pool.submit(_gemini_task)
                    try:
                        azure_out = fut_a.result()
                    except Exception:
                        azure_error = _public_eval_service_error("azure")
                        current_app.logger.exception("Azure pronunciation assessment failed")
                    try:
                        gemini_out = fut_g.result()
                    except Exception as exc:
                        gemini_error = (
                            str(exc)
                            if isinstance(exc, GeminiRateLimitError)
                            else _public_eval_service_error("gemini")
                        )
                        current_app.logger.exception("Gemini acting evaluation failed")
            except Exception:
                current_app.logger.exception("evaluate-acting runner failed")
                return jsonify({"error": _public_eval_service_error("")}), 500

            if gemini_error and gemini_error == GEMINI_BUSY_MESSAGE:
                return (
                    jsonify(
                        {
                            "error": gemini_error,
                            "accuracy_score": None,
                            "prosody_score": None,
                            "score_acting": None,
                            "feedback_acting": "",
                            "average_total": None,
                            "azure_error": None,
                            "gemini_error": gemini_error,
                        }
                    ),
                    429,
                )

            accuracy = (
                float(azure_out["accuracy_score"]) if isinstance(azure_out, dict) else None
            )
            prosody = float(azure_out["prosody_score"]) if isinstance(azure_out, dict) else None
            score_acting = (
                int(gemini_out["score_acting"]) if isinstance(gemini_out, dict) else None
            )
            feedback_acting = (
                str(gemini_out.get("feedback_acting", "")).strip()
                if isinstance(gemini_out, dict)
                else ""
            )

            parts: list[float] = []
            if accuracy is not None:
                parts.append(accuracy)
            if prosody is not None:
                parts.append(prosody)
            if score_acting is not None:
                parts.append(float(score_acting))
            average_total = round(sum(parts) / len(parts), 1) if parts else None

            status_code = 200 if parts else 502
            err_msg: str | None = None
            if not parts:
                err_msg = "目前無法完成評分，請稍後再試。"
            payload: dict[str, Any] = {
                "accuracy_score": accuracy,
                "prosody_score": prosody,
                "score_acting": score_acting,
                "feedback_acting": feedback_acting,
                "average_total": average_total,
                "azure_error": azure_error,
                "gemini_error": gemini_error,
            }
            if err_msg:
                payload["error"] = err_msg
            current_app.logger.info(
                "evaluate-acting status=%s accuracy=%s prosody=%s score_acting=%s "
                "azure_error=%s gemini_error=%s",
                status_code,
                accuracy,
                prosody,
                score_acting,
                azure_error,
                gemini_error,
            )
            return (
                jsonify(payload),
                status_code,
            )
        except Exception:
            current_app.logger.exception("evaluate-acting failed")
            return jsonify({"error": _public_eval_service_error("")}), 500
        finally:
            if upload_path is not None and upload_path.is_file():
                try:
                    upload_path.unlink()
                except OSError:
                    pass

    @app.get("/data/<path:rel>")
    def serve_data(rel: str) -> Any:
        if not _safe_rel_file(DATA_ROOT, rel):
            abort(404)
        return send_from_directory(DATA_ROOT, rel)

    @app.get("/static/<path:rel>")
    def serve_static_assets(rel: str) -> Any:
        if not _safe_rel_file(STATIC_SITE_ROOT / "static", rel):
            abort(404)
        if rel.lower().endswith(".mp3"):
            return send_from_directory(STATIC_SITE_ROOT / "static", rel, mimetype="audio/mpeg")
        return send_from_directory(STATIC_SITE_ROOT / "static", rel)

    @app.get("/")
    def serve_index() -> Any:
        return send_from_directory(STATIC_SITE_ROOT, "index.html")

    @app.get("/<path:rel>")
    def serve_static(rel: str) -> Any:
        if rel.startswith("api/") or rel.startswith("data/"):
            abort(404)
        if not _safe_rel_file(STATIC_SITE_ROOT, rel):
            abort(404)
        return send_from_directory(STATIC_SITE_ROOT, rel)

    return app


app = create_app()
