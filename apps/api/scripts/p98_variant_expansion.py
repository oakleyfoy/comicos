"""P98-10 — expand UNKNOWN variant shells into concrete cover types."""

from __future__ import annotations

import argparse
import json

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session, select  # noqa: E402

from app.models.universe import UniverseIssue, UniverseVariant  # noqa: E402
from app.services.universe.universe_variant_service import (  # noqa: E402
    expand_variant_labels,
    promote_unknown_when_catalog_linked,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Expand universe variant shells (P98-10)")
    parser.add_argument("--issue-id", type=int, help="Single universe_issue id")
    parser.add_argument("--labels", nargs="+", default=["Cover A", "Cover B", "Newsstand", "Direct"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    engine = get_p97_engine(resolve_p97_database_url())
    with Session(engine) as session:
        if args.issue_id:
            issue_ids = [args.issue_id]
        else:
            issue_ids = [
                int(row.issue_id)
                for row in session.exec(select(UniverseVariant.issue_id).distinct()).all()
            ]
        created = 0
        for issue_id in issue_ids:
            rows = expand_variant_labels(session, issue_id=issue_id, labels=args.labels)
            created += len(rows)
            promote_unknown_when_catalog_linked(session, issue_id=issue_id)
        session.commit()
    stats = {"issues_touched": len(issue_ids), "variants_created": created}
    if args.json:
        print(json.dumps(stats))
    else:
        print(f"Expanded {stats['issues_touched']} issues; added {stats['variants_created']} variant shells.")


if __name__ == "__main__":
    main()
