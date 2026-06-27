"""Sync-only benchmark (no hydration downloads)."""
from __future__ import annotations

import time

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p104_cover_hydration_service import sync_cover_assets_batch  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> None:
    sync_limit = 5000
    engine = get_p97_engine(resolve_p97_database_url(None))
    t0 = time.perf_counter()
    with Session(engine, expire_on_commit=False) as session:
        result = sync_cover_assets_batch(session, sync_limit=sync_limit)
    elapsed = time.perf_counter() - t0
    d = result.to_dict()
    ipm = (result.catalog_issues_scanned / elapsed * 60.0) if elapsed > 0 else 0.0
    print(f"sync_limit={sync_limit}")
    print(f"elapsed_sec={elapsed:.2f}")
    print(f"issues_per_minute={ipm:.0f}")
    print(f"created={result.created}")
    print(f"updated={result.updated}")
    print(f"scanned={result.catalog_issues_scanned}")
    print(f"timing={d.get('timing')}")
    print(f"bottleneck={d.get('timing_bottleneck')}")


if __name__ == "__main__":
    main()
