"""Deployment marker: backend git SHA, build time, runtime kind, and feature flags.

Used by /api/ops/build-info so we can prove which backend build is actually live and
which intake feature flags are active (full-cover follow-up, mobile capture, unsafe
fingerprint suppression).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Settings
from app.services.runtime_debug import PROCESS_STARTED_AT, _get_git_commit


def _detect_runtime_kind(settings: Settings) -> str:
    explicit = (settings.runtime_kind or "").strip()
    if explicit:
        return explicit
    if os.path.exists("/.dockerenv"):
        return "docker"
    if os.environ.get("KUBERNETES_SERVICE_HOST"):
        return "kubernetes"
    if os.environ.get("RENDER"):
        return "render"
    return "native"


def _resolve_build_sha(settings: Settings) -> str | None:
    configured = (settings.build_sha or "").strip()
    if configured:
        return configured
    env_sha = (
        os.environ.get("RENDER_GIT_COMMIT")
        or os.environ.get("GIT_COMMIT")
        or os.environ.get("SOURCE_VERSION")
        or ""
    ).strip()
    if env_sha:
        return env_sha
    return _get_git_commit(Path.cwd())


def _resolve_build_time(settings: Settings) -> str:
    configured = (settings.build_time or "").strip()
    if configured:
        return configured
    return PROCESS_STARTED_AT.astimezone(timezone.utc).isoformat()


def build_build_info(settings: Settings) -> dict:
    return {
        "service": "comic-os-api",
        "git_sha": _resolve_build_sha(settings),
        "build_time": _resolve_build_time(settings),
        "process_started_at": PROCESS_STARTED_AT.astimezone(timezone.utc).isoformat(),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "runtime": _detect_runtime_kind(settings),
        "environment": settings.app_env,
        "feature_flags": {
            "full_cover_followup_enabled": bool(settings.full_cover_followup_enabled),
            "mobile_capture_enabled": bool(settings.mobile_capture_enabled),
            "suppress_unsafe_fingerprint_enabled": bool(
                settings.suppress_unsafe_fingerprint_enabled
            ),
        },
    }
