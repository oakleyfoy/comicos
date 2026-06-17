"""P98 — Generate missing major-publisher volume action queue (planning only).

Reads API discovery results and local comicvine_volume_universe gaps vs universe_volume.

Example:
  python scripts/p98_generate_missing_volume_action_queue.py --database-url "postgresql+pg8000://postgres:postgres@localhost:5433/comic_os"
"""

from __future__ import annotations

import argparse
import json
import os

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_missing_volume_discovery_service import (  # noqa: E402
    build_missing_volume_action_queue,
    default_missing_queue_path,
    default_results_path,
)
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="P98 missing volume action queue")
    parser.add_argument("--out", type=str, default=str(default_missing_queue_path()))
    parser.add_argument("--results", type=str, default=None, help="Discovery results JSON path")
    parser.add_argument("--skip-local-db", action="store_true")
    parser.add_argument("--database-url", type=str, default=None)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    results_path = default_results_path() if not args.results else default_results_path().parent / args.results
    if args.results:
        from pathlib import Path

        results_path = Path(args.results)

    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        rows = build_missing_volume_action_queue(
            session,
            results_path=results_path,
            include_local_db=not args.skip_local_db,
        )

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)

    print(f"(database: {describe_database_url(database_url)})")
    print(f"Wrote {len(rows)} rows -> {args.out}")
    actions: dict[str, int] = {}
    for row in rows:
        act = row.get("recommended_action") or "?"
        actions[act] = actions.get(act, 0) + 1
    for act, count in sorted(actions.items()):
        print(f"  {act}: {count}")


if __name__ == "__main__":
    main()
