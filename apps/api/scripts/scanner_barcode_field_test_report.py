"""Summarize recent intake scanner barcode resolution events (field test).

Usage:
  cd apps/api
  python scripts/scanner_barcode_field_test_report.py --limit 100
  python scripts/scanner_barcode_field_test_report.py --limit 100 --json --out data/scanner/field_test_20260627.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from app.services.scanner_barcode_field_test_service import (  # noqa: E402
    ALL_BUCKETS,
    BUCKET_NO_GCD,
    default_field_test_log_path,
    load_recent_scanner_barcode_events,
    summarize_scanner_barcode_field_test,
)


def _default_json_out() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Path("data/scanner") / f"field_test_{stamp}.json"


def _print_text_summary(summary: dict) -> None:
    counts = summary.get("counts") or {}
    total = summary.get("total") or 0
    print(f"Scanner barcode field test summary (last {total} events)")
    print()
    for bucket in ALL_BUCKETS:
        print(f"  {bucket}: {counts.get(bucket, 0)}")
    print()
    no_gcd = (summary.get("buckets") or {}).get(BUCKET_NO_GCD) or []
    if no_gcd:
        print("unresolved_no_gcd_match details:")
        for row in no_gcd:
            exact = row.get("gcd_exact_hits") or []
            prefix = row.get("gcd_prefix_hits") or []
            print(f"  barcode={row.get('normalized_barcode')}")
            print(f"    GCD DB: {row.get('p106_gcd_database_path')}")
            print(f"    DB modified: {row.get('p106_gcd_database_modified_at')}")
            print(f"    exact hit count: {len(exact) if isinstance(exact, list) else 0}")
            print(f"    prefix hit count: {len(prefix) if isinstance(prefix, list) else 0}")
            print(f"    final reason: {row.get('final_reason') or row.get('gcd_lookup_final_reason')}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize scanner barcode field test JSONL log")
    parser.add_argument("--limit", type=int, default=100, help="Last N events to include")
    parser.add_argument("--log", type=str, default="", help="Override JSONL log path")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    parser.add_argument("--out", type=str, default="", help="Write JSON report to this path")
    args = parser.parse_args()

    log_path = Path(args.log).expanduser() if args.log.strip() else default_field_test_log_path()
    events = load_recent_scanner_barcode_events(log_path=log_path, limit=max(1, args.limit))
    summary = summarize_scanner_barcode_field_test(events)
    summary["log_path"] = str(log_path.resolve()) if log_path.exists() else str(log_path)
    summary["events"] = events

    if args.json or args.out.strip():
        out_path = Path(args.out).expanduser() if args.out.strip() else _default_json_out()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "log_path": summary["log_path"],
            "limit": args.limit,
            "counts": summary["counts"],
            "total": summary["total"],
            "events": events,
        }
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {out_path}")
        if args.json:
            json.dump(payload, sys.stdout, indent=2, default=str)
            print()
    else:
        _print_text_summary(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
