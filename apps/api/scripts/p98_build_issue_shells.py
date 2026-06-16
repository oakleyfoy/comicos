"""P98-03/04 — issue + UNKNOWN variant shells from catalog mapping."""

from __future__ import annotations

import argparse
import json

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.universe.universe_issue_service import build_issue_shells_from_catalog  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build universe issue shells from catalog (P98-03)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    engine = get_p97_engine(resolve_p97_database_url())
    with Session(engine) as session:
        stats = build_issue_shells_from_catalog(session)
    if args.json:
        print(json.dumps(stats))
    else:
        print(
            "Issue shells: "
            f"created={stats['issues_created']} updated={stats['issues_updated']} "
            f"variants_linked={stats['variants_linked']}"
        )


if __name__ == "__main__":
    main()
