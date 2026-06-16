"""P98 — Generate the major publisher action queue (planning only, no imports).

Writes data/p98/major_publisher_action_queue.json sorted by descending priority.

Examples:
  python scripts/p98_generate_major_publisher_action_queue.py
  python scripts/p98_generate_major_publisher_action_queue.py --publisher Marvel --top 500
  python scripts/p98_generate_major_publisher_action_queue.py --out data/p98/marvel_queue.json
"""

from __future__ import annotations

import argparse
import json
import os

from p98_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.services.p98_skeleton_gap_service import build_action_queue  # noqa: E402
from p97_db import describe_database_url, get_p97_engine, resolve_p97_database_url  # noqa: E402

DEFAULT_OUT = "data/p98/major_publisher_action_queue.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="P98 major publisher action queue generator")
    parser.add_argument("--publisher", type=str, default=None)
    parser.add_argument("--top", type=int, default=None)
    parser.add_argument("--out", type=str, default=DEFAULT_OUT)
    parser.add_argument("--database-url", type=str, default=None)
    args = parser.parse_args()

    database_url = resolve_p97_database_url(args.database_url)
    engine = get_p97_engine(database_url)
    with Session(engine) as session:
        rows = build_action_queue(session, publisher=args.publisher, top=args.top)

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)

    print(f"(database: {describe_database_url(database_url)})")
    print(f"Wrote {len(rows)} action queue rows -> {args.out}")
    actions: dict[str, int] = {}
    for row in rows:
        actions[row["recommended_action"]] = actions.get(row["recommended_action"], 0) + 1
    for action, count in sorted(actions.items()):
        print(f"  {action}: {count}")


if __name__ == "__main__":
    main()
