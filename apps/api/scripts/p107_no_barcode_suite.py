"""P107 no-barcode recognition benchmark suite.

Usage:
  cd apps/api
  python scripts/p107_no_barcode_suite.py
  python scripts/p107_no_barcode_suite.py --manifest data/p107/no_barcode_manifest.csv --limit 4
  python scripts/p107_no_barcode_suite.py --json-out data/p107/last_run.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.p107_no_barcode_recognition_service import (  # noqa: E402
    P107_MANIFEST_DEFAULT,
    load_p107_manifest,
    run_p107_benchmark,
)


def _print_summary(report: dict) -> None:
    print("P107 No Barcode Recognition Suite")
    print(f"  manifest: {report.get('manifest_path')}")
    print(f"  rows: {report.get('rows')}")
    print(f"  benchmark_hits: {report.get('benchmark_hits')}")
    print(f"  auto_match_decisions: {report.get('auto_match_decisions')}")
    print(f"  barcode_skipped: {report.get('barcode_skipped')}")
    print(f"  missing_images: {report.get('missing_images')}")
    for ev in report.get("evaluations") or []:
        row = ev.get("manifest_row") or {}
        rec = ev.get("recognition") or {}
        best = rec.get("best_match") or {}
        print(
            f"  - {row.get('image_path')}: decision={rec.get('decision')} "
            f"confidence={rec.get('confidence')} hit={ev.get('benchmark_hit')} "
            f"best={best.get('series')} #{best.get('issue_number')}"
        )
        if rec.get("error"):
            print(f"      error: {rec.get('error')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run P107 no-barcode benchmark manifest")
    parser.add_argument("--manifest", type=Path, default=P107_MANIFEST_DEFAULT)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.manifest.is_file():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    load_p107_manifest(args.manifest)
    engine = get_engine()
    with Session(engine) as session:
        report = run_p107_benchmark(session, manifest_path=args.manifest, limit=args.limit)

    _print_summary(report)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"Wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
