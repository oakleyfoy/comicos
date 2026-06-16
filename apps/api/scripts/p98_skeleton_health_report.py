"""P98 — skeleton health report (read-only)."""

from __future__ import annotations

import argparse
import json

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.universe.universe_health_service import compute_skeleton_health  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="P98 skeleton health report")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--database-url", type=str, default=None)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        health = compute_skeleton_health(session)

    if args.json:
        print(json.dumps(health.as_dict()))
        return

    print("P98 SKELETON HEALTH")
    print(f"(database: {describe_database_url(database_url)})")
    print(f"Publishers: {health.publishers}")
    print(f"Volumes: {health.volumes}")
    print(f"Issues: {health.issues}")
    print(f"Variants: {health.variants}")
    print(f"Issues without variants: {health.issues_without_variants}")
    print(f"Catalog-linked issues: {health.catalog_linked_issues}")
    print(f"Discovered-only issues: {health.discovered_only_issues}")
    print(f"Volume-only volumes: {health.volume_only_volumes}")


if __name__ == "__main__":
    main()
