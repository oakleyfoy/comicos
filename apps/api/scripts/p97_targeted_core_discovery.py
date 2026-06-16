"""Targeted ComicVine search for missing core runs (universe row only, dry-run default).

Usage:
  python scripts/p97_targeted_core_discovery.py
  python scripts/p97_targeted_core_discovery.py --title "Uncanny X-Men"
  python scripts/p97_targeted_core_discovery.py --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p97_comicvine_rate_budget import (  # noqa: E402
    DEFAULT_MAX_REQUESTS_PER_HOUR,
    DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
    DEFAULT_PAUSE_HOURS_ON_420,
    ComicVineRateBudget,
)
from app.services.p97_comicvine_universe_discovery_service import (  # noqa: E402
    ComicVineUniverseDiscoveryClient,
)
from app.services.p97_targeted_core_discovery import (  # noqa: E402
    apply_targeted_core_discoveries,
    build_targeted_discovery_plans,
    missing_core_report_labels,
)
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _format_plan(plan, *, dry_run: bool) -> list[str]:
    lines = [
        f"Core run: {plan.report_label}",
        f"  Expected publisher: {plan.expected_publisher}",
        f"  Needs discovery: {'YES' if plan.missing_from_universe else 'NO'}",
    ]
    if not plan.candidates:
        lines.append("  Candidates: (none)")
        return lines

    lines.append("  Candidates:")
    for candidate in plan.candidates[:10]:
        lines.append(
            f"    id={candidate.volume_id} | {candidate.name!r} | "
            f"publisher={candidate.publisher!r} | issues={candidate.count_of_issues} | "
            f"start={candidate.start_year} | publisher_match="
            f"{'YES' if candidate.publisher_match else 'NO'}"
        )

    selected = plan.selected
    if selected is None:
        return lines

    lines.extend(
        [
            "",
            "Candidate found",
            f"Volume: {selected.name}",
            f"Publisher: {selected.publisher or 'Unknown'}",
            f"Issue Count: {selected.count_of_issues or 0}",
            f"Start Year: {selected.start_year}",
            f"Volume ID: {selected.volume_id}",
            f"Would insert: {'YES' if plan.missing_from_universe else 'NO'}",
        ]
    )
    if dry_run and plan.missing_from_universe:
        lines.append("Apply required (--apply).")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="P97 targeted core volume discovery")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--title", default=None, help="Single core run label to search")
    parser.add_argument("--apply", action="store_true", help="Insert universe rows only")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--search-limit", type=int, default=30)
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    dry_run = not args.apply

    with Session(engine) as session:
        labels = [args.title] if args.title else missing_core_report_labels(session)
        if args.title and args.title not in labels:
            labels = [args.title]

        budget = ComicVineRateBudget(
            session,
            max_requests_per_hour=DEFAULT_MAX_REQUESTS_PER_HOUR,
            min_seconds_between_requests=DEFAULT_MIN_SECONDS_BETWEEN_REQUESTS,
            pause_hours_on_420=DEFAULT_PAUSE_HOURS_ON_420,
        )
        client = ComicVineUniverseDiscoveryClient(session, budget)
        plans = build_targeted_discovery_plans(
            session,
            client,
            labels=labels,
            search_limit=args.search_limit,
        )

        if args.json:
            payload = {
                "dry_run": dry_run,
                "plans": [
                    {
                        "report_label": p.report_label,
                        "expected_publisher": p.expected_publisher,
                        "missing_from_universe": p.missing_from_universe,
                        "selected": asdict(p.selected) if p.selected else None,
                        "candidates": [asdict(c) for c in p.candidates],
                    }
                    for p in plans
                ],
            }
            if args.apply:
                payload["applied"] = [
                    {
                        "report_label": r.report_label,
                        "volume_id": r.volume_id,
                        "action": r.action,
                        "inserted": r.inserted,
                    }
                    for r in apply_targeted_core_discoveries(session, client, plans)
                ]
            print(json.dumps(payload, indent=2, default=str))
            return 0

        print(f"Mode: {'DRY-RUN' if dry_run else 'APPLY'}")
        print("")
        if not plans:
            print("No core runs need discovery.")
            return 0

        for plan in plans:
            for line in _format_plan(plan, dry_run=dry_run):
                print(line)
            print("")

        if args.apply:
            results = apply_targeted_core_discoveries(session, client, plans)
            if not results:
                print("No universe rows inserted (already present or no candidates).")
            else:
                print("Applied universe discovery:")
                for result in results:
                    print(
                        f"  {result.report_label}: volume_id={result.volume_id} "
                        f"({result.action})"
                    )
        elif any(p.missing_from_universe and p.selected for p in plans):
            print("Dry-run complete. Re-run with --apply to insert universe rows only.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
