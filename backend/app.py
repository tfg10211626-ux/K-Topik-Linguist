"""Flask entrypoint: `cd backend && flask --app app run` or `python app.py`."""

from __future__ import annotations

import os

# Before google.genai loads (via flask_app): gRPC + Werkzeug reloader fork() conflict.
os.environ.setdefault("GRPC_ENABLE_FORK_SUPPORT", "0")

from ktl_backend.config import load_backend_env

load_backend_env()

from ktl_backend.flask_app import app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG") == "1"
    # Reloader forks; skip it even when debug=1—restart manually after code changes.
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
