"""ComicVine endpoint diagnostic (P97-23A).

Uses the same User-Agent and request pattern as the catalog volume importer.

Usage:
  python scripts/p97_comicvine_endpoint_diagnostic.py
  python scripts/p97_comicvine_endpoint_diagnostic.py --volume-id 87154
  python scripts/p97_comicvine_endpoint_diagnostic.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.comicvine_importer_http import DEFAULT_DIAGNOSTIC_VOLUME_ID  # noqa: E402
from app.services.p97_comicvine_rate_budget import ComicVineRateBudget  # noqa: E402
from app.services.p97_comicvine_universe_discovery_service import (  # noqa: E402
    ComicVineUniverseDiscoveryClient,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def format_probe(report: dict) -> str:
    lines = [
        "P97 COMICVINE ENDPOINT DIAGNOSTIC",
        "=" * 52,
        f"{'Base URL':<26}{report.get('base_url', '—')}",
        f"{'User-Agent':<26}{(report.get('user_agent') or '—')[:52]}",
        f"{'Probe volume id':<26}{report.get('volume_id', '—')}",
        "",
    ]
    for key in ("volumes_list", "search_volumes", "volume_detail"):
        entry = report.get(key) or {}
        label = key.replace("_", " ")
        if entry.get("ok"):
            lines.append(
                f"{label}: OK (results={entry.get('result_count')}, "
                f"total={entry.get('number_of_total_results', '—')})"
            )
        else:
            lines.append(
                f"{label}: FAIL status={entry.get('status_code')} error={entry.get('error')}"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe ComicVine volume endpoints")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--volume-id", type=int, default=DEFAULT_DIAGNOSTIC_VOLUME_ID)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    cache_dir = None
    if settings.comicvine_http_cache_enabled:
        from pathlib import Path

        cache_dir = Path(settings.catalog_storage_root) / "comicvine_http_cache"

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)

    try:
        with Session(engine) as session:
            budget = ComicVineRateBudget(session)
            client = ComicVineUniverseDiscoveryClient(session, budget, http_cache_dir=cache_dir)
            report = client.probe_endpoints(volume_id=args.volume_id)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_probe(report))

    failed = [key for key in ("volumes_list", "search_volumes", "volume_detail") if not (report.get(key) or {}).get("ok")]
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
