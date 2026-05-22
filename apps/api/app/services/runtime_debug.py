import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit

from app.core.config import Settings
from app.schemas.debug import RuntimeDebugResponse

PROCESS_STARTED_AT = datetime.now(timezone.utc)
SENSITIVE_QUERY_TOKENS = ("key", "password", "passwd", "pwd", "secret", "token")


def _mask_sensitive_query_values(query: str) -> str:
    if not query:
        return query

    pairs = parse_qsl(query, keep_blank_values=True)
    safe_parts: list[str] = []
    for key, value in pairs:
        safe_value = (
            "***"
            if any(token in key.lower() for token in SENSITIVE_QUERY_TOKENS)
            else value
        )
        safe_parts.append(f"{quote(key, safe='')}={quote(safe_value, safe='*')}")

    return "&".join(safe_parts)


def mask_url_secret(url: str) -> str:
    split_result = urlsplit(url)
    safe_query = _mask_sensitive_query_values(split_result.query)

    if split_result.username is None and split_result.password is None:
        return urlunsplit(
            (
                split_result.scheme,
                split_result.netloc,
                split_result.path,
                safe_query,
                split_result.fragment,
            )
        )

    hostname = split_result.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"

    host_and_port = hostname
    if split_result.port is not None:
        host_and_port = f"{host_and_port}:{split_result.port}"

    username = "" if split_result.username is None else split_result.username
    password = "***" if split_result.password is not None else None

    auth = username
    if password is not None:
        auth = f"{auth}:{password}"

    safe_netloc = f"{auth}@{host_and_port}"
    return urlunsplit(
        (
            split_result.scheme,
            safe_netloc,
            split_result.path,
            safe_query,
            split_result.fragment,
        )
    )


def _get_git_commit(cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            cwd=cwd,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None

    commit = result.stdout.strip()
    return commit or None


def build_runtime_debug_response(settings: Settings) -> RuntimeDebugResponse:
    cwd = Path.cwd()

    return RuntimeDebugResponse(
        app_name=settings.app_name,
        environment=settings.app_env,
        database_url_safe=mask_url_secret(settings.database_url),
        redis_url_safe=mask_url_secret(settings.redis_url),
        pid=os.getpid(),
        cwd=str(cwd),
        started_at=PROCESS_STARTED_AT,
        git_commit=_get_git_commit(cwd),
    )
