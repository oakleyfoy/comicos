"""Render web entrypoint: Alembic in a short-lived process, then exec uvicorn."""
from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    os.chdir(API_ROOT)
    sys.path.insert(0, str(API_ROOT))

    from app.db.startup_migrations import run_startup_migrations_subprocess, should_run_startup_migrations

    if should_run_startup_migrations():
        print("Running Alembic upgrade head (pre-uvicorn)...", flush=True)
        run_startup_migrations_subprocess(cwd=API_ROOT)
        print("Alembic upgrade complete", flush=True)

    port = os.environ.get("PORT", "8000")
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ],
    )


if __name__ == "__main__":
    main()
