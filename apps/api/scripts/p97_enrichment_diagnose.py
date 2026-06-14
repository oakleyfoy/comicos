from __future__ import annotations

import argparse
import json
import os
import sys

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.services.catalog_bulk_enrichment_selection import collect_enrichment_diagnostics  # noqa: E402
from p97_db import (  # noqa: E402
    DEFAULT_P97_DATABASE_URL,
    describe_database_url,
    ensure_p97_env_loaded,
    get_p97_engine,
    resolve_p97_database_url,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose P97 enrichment DB URL and ready-cover selection (read-only)",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override database URL (default: same resolution as progress_watch / enrichment CLIs)",
    )
    parser.add_argument("--json", action="store_true", help="Print diagnostics as JSON")
    parser.add_argument("--batch-limit", type=int, default=10, help="Simulated batch limit for selection counts")
    args = parser.parse_args()

    ensure_p97_env_loaded()
    getenv_before_settings = os.environ.get("DATABASE_URL")
    settings_url = get_settings().database_url
    resolved = resolve_p97_database_url(args.database_url)

    meta = {
        "cwd": os.getcwd(),
        "os_getenv_DATABASE_URL": getenv_before_settings,
        "settings_database_url": settings_url,
        "resolved_p97_database_url": resolved,
        "resolved_database_host_db": describe_database_url(resolved),
        "default_p97_database_url": DEFAULT_P97_DATABASE_URL,
        "progress_watch_would_use": os.environ.get("DATABASE_URL") or DEFAULT_P97_DATABASE_URL,
    }

    try:
        engine = get_p97_engine(resolved)
        with Session(engine) as session:
            diagnostics = collect_enrichment_diagnostics(session, batch_limit=args.batch_limit)
    except Exception as exc:
        print(f"ERROR: database connection failed: {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps({**meta, "error": str(exc)}, indent=2))
        else:
            print("connection_error:", exc)
            for key, value in meta.items():
                print(f"{key}={value}")
        return 1

    payload = {**meta, **diagnostics}
    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print("P97 Enrichment Diagnostics")
        print("=" * 40)
        for key, value in meta.items():
            print(f"{key}={value}")
        print("-" * 40)
        print(f"total_catalog_images={diagnostics['total_catalog_images']}")
        print(f"ready_by_progress_watch_definition={diagnostics['ready_by_progress_watch_definition']}")
        print(f"ready_by_download_status_only={diagnostics['ready_by_download_status_only']}")
        print(
            "ready_by_selector_definition_before_path_filter="
            f"{diagnostics['ready_by_selector_definition_before_path_filter']}"
        )
        print(f"missing_fingerprints_before_path_filter={diagnostics['missing_fingerprints_before_path_filter']}")
        print(f"missing_ocr_before_path_filter={diagnostics['missing_ocr_before_path_filter']}")
        print(f"ready_with_resolvable_path_sampled={diagnostics['ready_with_resolvable_path_sampled']}")
        print(f"selected_for_fingerprint_batch={diagnostics['selected_for_fingerprint_batch']}")
        print(f"selected_for_ocr_batch={diagnostics['selected_for_ocr_batch']}")
        print("distinct_image_type:")
        for name, count in diagnostics["distinct_image_type"]:
            print(f"  {name!r}: {count}")
        print("distinct_download_status:")
        for name, count in diagnostics["distinct_download_status"]:
            print(f"  {name!r}: {count}")
        print("sample_ready_cover_rows:")
        print(json.dumps(diagnostics["sample_ready_cover_rows"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
