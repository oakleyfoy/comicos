"""P97-23A ComicVine universe discovery — volume metadata only (no issue import).

Paginates ComicVine ``volumes/`` and upserts into ``comicvine_volume_universe``.
Uses the existing P97 request ledger budget so acquisition is not starved or reconfigured.

Usage:
  python scripts/p97_discover_comicvine_universe.py
  python scripts/p97_discover_comicvine_universe.py --pages 5
  python scripts/p97_discover_comicvine_universe.py --offset 1200 --pages 10
  python scripts/p97_discover_comicvine_universe.py --until-complete
  python scripts/p97_discover_comicvine_universe.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session, func, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models.catalog_p97 import ComicVineVolumeUniverse  # noqa: E402
from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
    ComicVineRateBudget,
)
from app.services.p97_comicvine_universe_discovery_service import (  # noqa: E402
    ComicVineUniverseDiscoveryClient,
    discover_universe_batch,
    load_discovery_progress,
    save_discovery_progress,
    UniverseDiscoveryProgress,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

DATA_DIR = API_ROOT / "data" / "p97"
PROGRESS_FILE = DATA_DIR / "comicvine_universe_discovery_progress.json"
LOCK_FILE = DATA_DIR / "comicvine_universe_discovery.lock"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_lock(lock_path: Path = LOCK_FILE) -> bool:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if lock_path.is_file():
        try:
            existing = int(lock_path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            existing = 0
        if existing and _pid_alive(existing):
            return False
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock(lock_path: Path = LOCK_FILE) -> None:
    if not lock_path.is_file():
        return
    try:
        if int(lock_path.read_text(encoding="utf-8").strip() or "0") == os.getpid():
            lock_path.unlink(missing_ok=True)
    except (OSError, ValueError):
        pass


def _count_universe_volumes(session: Session) -> int:
    return int(session.exec(select(func.count()).select_from(ComicVineVolumeUniverse)).one())


def run_discovery(
    session: Session,
    *,
    offset: int | None,
    max_pages: int,
    until_complete: bool,
    progress_path: Path,
    client: ComicVineUniverseDiscoveryClient,
) -> dict:
    progress = load_discovery_progress(progress_path)
    if offset is not None:
        progress.offset = int(offset)
    if progress.list_endpoint_forbidden and progress.discovery_mode == "list":
        progress.discovery_mode = "search"
    start_offset = progress.offset
    start_mode = progress.discovery_mode
    progress.status = "running"
    progress.api_requests_this_run = 0
    progress.pages_fetched_this_run = 0
    progress.last_error = None
    save_discovery_progress(progress_path, progress)

    total_inserted = 0
    total_updated = 0
    total_pages = 0
    total_requests = 0
    complete = False
    throttled = False
    endpoint_forbidden = False
    last_error: str | None = None
    switched_to_search = False

    while True:
        batch = discover_universe_batch(
            session,
            client,
            progress,
            max_pages=1 if until_complete else max_pages,
        )
        total_inserted += batch.inserted
        total_updated += batch.updated
        total_pages += batch.pages_fetched
        total_requests += batch.api_requests
        if batch.number_of_total_results is not None:
            progress.number_of_total_results = batch.number_of_total_results
        if batch.switched_to_search:
            switched_to_search = True
        if batch.endpoint_forbidden:
            endpoint_forbidden = True
            last_error = batch.error
            break
        if batch.throttled:
            throttled = True
            last_error = batch.error
            break
        if batch.error:
            last_error = batch.error
            break
        if batch.complete:
            complete = True
            break
        if not until_complete:
            break

    progress.volumes_in_db = _count_universe_volumes(session)
    progress.api_requests_this_run = total_requests
    progress.pages_fetched_this_run = total_pages
    progress.last_error = last_error
    if endpoint_forbidden:
        progress.status = "endpoint_forbidden"
    elif throttled:
        progress.status = "paused_420"
    elif complete:
        progress.status = "complete"
    elif last_error:
        progress.status = "error"
    else:
        progress.status = "idle"
    save_discovery_progress(progress_path, progress)

    return {
        "discovery_mode": progress.discovery_mode,
        "discovery_mode_before": start_mode,
        "offset_before": start_offset,
        "offset_after": progress.offset,
        "search_bucket_index": progress.search_bucket_index,
        "search_query": progress.current_search_query(),
        "list_endpoint_forbidden": progress.list_endpoint_forbidden,
        "switched_to_search": switched_to_search,
        "pages_fetched": total_pages,
        "api_requests": total_requests,
        "inserted": total_inserted,
        "updated": total_updated,
        "volumes_in_db": progress.volumes_in_db,
        "number_of_total_results": progress.number_of_total_results,
        "complete": complete,
        "throttled": throttled,
        "endpoint_forbidden": endpoint_forbidden,
        "error": last_error,
        "status": progress.status,
    }


def format_summary(result: dict) -> str:
    lines = [
        "P97 COMICVINE UNIVERSE DISCOVERY",
        "=" * 52,
        f"{'Status':<26}{result.get('status', '—')}",
        f"{'Mode':<26}{result.get('discovery_mode', '—')}",
        f"{'Offset':<26}{result.get('offset_before')} → {result.get('offset_after')}",
        f"{'Pages this run':<26}{result.get('pages_fetched')}",
        f"{'API requests':<26}{result.get('api_requests')}",
        f"{'Inserted':<26}{result.get('inserted')}",
        f"{'Updated':<26}{result.get('updated')}",
        f"{'Volumes in DB':<26}{result.get('volumes_in_db')}",
        f"{'CV total results':<26}{result.get('number_of_total_results') or '—'}",
        f"{'Search bucket':<26}{result.get('search_bucket_index')}",
        f"{'Search query':<26}{result.get('search_query') or '—'}",
        f"{'List /volumes/ forbidden':<26}{result.get('list_endpoint_forbidden')}",
        f"{'Complete':<26}{result.get('complete')}",
    ]
    if result.get("error"):
        lines.append(f"{'Last error':<26}{result['error']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 ComicVine universe discovery (metadata only)")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--offset", type=int, default=None, help="Resume offset (default: progress file)")
    parser.add_argument("--pages", type=int, default=1, help="Max list pages to fetch this run")
    parser.add_argument("--until-complete", action="store_true", help="Fetch until ComicVine returns no rows")
    parser.add_argument("--progress-file", default=str(PROGRESS_FILE))
    parser.add_argument("--no-lock", action="store_true", help="Skip single-worker lock (not recommended)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-requests-per-hour", type=int, default=DEFAULT_MAX_REQUESTS_PER_HOUR)
    parser.add_argument("--min-seconds-between-requests", type=float, default=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS)
    parser.add_argument("--pause-hours-on-420", type=float, default=DEFAULT_PAUSE_HOURS_ON_420)
    args = parser.parse_args()

    if not args.no_lock and not acquire_lock():
        print("ERROR: another universe discovery worker holds the lock", file=sys.stderr)
        return 2

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    progress_path = Path(args.progress_file)
    settings = get_settings()
    cache_dir = Path(settings.catalog_storage_root) / "comicvine_http_cache"

    try:
        with Session(engine) as session:
            budget = ComicVineRateBudget(
                session,
                max_requests_per_hour=args.max_requests_per_hour,
                min_seconds_between_requests=args.min_seconds_between_requests,
                pause_hours_on_420=args.pause_hours_on_420,
            )
            client = ComicVineUniverseDiscoveryClient(
                session,
                budget,
                http_cache_dir=cache_dir,
            )
            result = run_discovery(
                session,
                offset=args.offset,
                max_pages=max(1, int(args.pages)),
                until_complete=bool(args.until_complete),
                progress_path=progress_path,
                client=client,
            )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if not args.no_lock:
            release_lock()

    if args.json:
        print(json.dumps(result, separators=(",", ":")))
    else:
        print(format_summary(result))
    return 0 if not result.get("error") and not result.get("endpoint_forbidden") else 1


if __name__ == "__main__":
    raise SystemExit(main())
