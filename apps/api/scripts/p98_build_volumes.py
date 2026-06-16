"""P98-02 — build universe_volume rows linked to publishers."""

from __future__ import annotations

import argparse
import json

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.universe.universe_volume_service import build_volumes_from_discovered_universe  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build master universe volumes (P98-02)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    engine = get_p97_engine(resolve_p97_database_url())
    with Session(engine) as session:
        stats = build_volumes_from_discovered_universe(session)
    if args.json:
        print(json.dumps(stats))
    else:
        print(f"Volumes in universe: {stats['volumes']} (created={stats['created']}, updated={stats['updated']})")


if __name__ == "__main__":
    main()
