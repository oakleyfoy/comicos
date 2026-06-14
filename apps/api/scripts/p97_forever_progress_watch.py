from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from p97_bootstrap import API_ROOT, bootstrap_api_path

bootstrap_api_path()

DEFAULT_PROGRESS = API_ROOT / "data" / "p97" / "forever_catalog_progress.json"


def _fmt_count(value: int | float | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{int(value):,}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.1f}%"


def _load_progress(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: could not read progress file: {exc}", file=sys.stderr)
        return None


def format_dashboard(doc: dict) -> str:
    runtime_seconds = float(doc.get("runtime_seconds") or 0)
    hours = int(runtime_seconds // 3600)
    minutes = int((runtime_seconds % 3600) // 60)
    last_chunk = doc.get("last_chunk_result") or {}
    publisher_progress = doc.get("publisher_progress") or {}

    lines = [
        "P97 Forever Catalog Acquisition",
        "=" * 56,
        f"Mode: {doc.get('mode', '—')}",
        f"Updated: {doc.get('updated_at', '—')}",
        f"Runtime: {hours:02d}h {minutes:02d}m",
        f"Status: {doc.get('status', 'UNKNOWN')}",
        "",
        "Catalog",
        "-" * 56,
        f"Issues now:           {_fmt_count(doc.get('issues_now'))}",
        f"Issues added (run):   +{_fmt_count(doc.get('issues_added_this_run'))}",
        f"Images now:           {_fmt_count(doc.get('images_now'))}",
        f"Ready covers:         {_fmt_count(doc.get('ready_covers'))}",
        f"Pending covers:       {_fmt_count(doc.get('pending_covers'))}",
        f"Fingerprints:         {_fmt_count(doc.get('fingerprints'))}",
        f"OCR rows:             {_fmt_count(doc.get('ocr_rows'))}",
        "",
        "Goals",
        "-" * 56,
        f"150k progress:        {_fmt_pct(doc.get('goal_150k_progress_pct'))}  "
        f"(remaining {_fmt_count(doc.get('goal_150k_remaining'))})",
        f"200k progress:        {_fmt_pct(doc.get('goal_200k_progress_pct'))}  "
        f"(remaining {_fmt_count(doc.get('goal_200k_remaining'))})",
        "",
        "Current chunk",
        "-" * 56,
        f"Publisher:            {doc.get('current_publisher', '—')}",
        f"Offset:               {_fmt_count(doc.get('current_offset'))}",
        f"Chunk limit:          {_fmt_count(doc.get('current_chunk_limit'))}",
        f"Chunks this run:      {_fmt_count(doc.get('chunks_completed_this_run'))}",
        f"ComicVine sleep:      {doc.get('current_sleep_seconds', '—')}s",
        f"420 count (run):      {_fmt_count(doc.get('total_420_count_this_run'))}",
        f"Last success:         {doc.get('last_successful_chunk_at', '—')}",
        (
            f"Last chunk:           created={last_chunk.get('created', 0)} "
            f"updated={last_chunk.get('updated', 0)} "
            f"skipped={last_chunk.get('skipped', 0)} "
            f"failed={last_chunk.get('failed', 0)}"
        ),
        "",
        "Throughput",
        "-" * 56,
        f"Issues last hour:     +{_fmt_count(doc.get('issues_added_last_hour'))}",
        f"Avg issues/chunk:     {_fmt_count(doc.get('average_issues_per_chunk'))}",
        f"Est. time to 150k:    {doc.get('estimated_time_to_150k', 'UNKNOWN')}",
        "",
        "Publisher progress",
        "-" * 56,
    ]
    if not publisher_progress:
        lines.append("(no publisher stats yet)")
    else:
        for name in sorted(publisher_progress.keys()):
            row = publisher_progress[name]
            lines.append(
                f"{name:<14} offset={_fmt_count(row.get('offset'))} "
                f"chunks={row.get('chunks', 0)} "
                f"created={row.get('created', 0)} "
                f"updated={row.get('updated', 0)} "
                f"420s={row.get('420s', 0)} "
                f"status={row.get('status', '—')}"
            )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Live dashboard for P97 forever catalog acquisition (reads JSON only)"
    )
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=DEFAULT_PROGRESS,
        help="Path to forever_catalog_progress.json",
    )
    parser.add_argument(
        "--watch",
        type=int,
        metavar="SECONDS",
        help="Refresh every N seconds until Ctrl+C",
    )
    parser.add_argument("--json", action="store_true", help="Print raw progress JSON")
    args = parser.parse_args()

    def render_once() -> int:
        doc = _load_progress(args.progress_file)
        if doc is None:
            print(f"No progress file at {args.progress_file} (daemon not started yet?)")
            return 1
        if args.json:
            print(json.dumps(doc, indent=2))
        else:
            print(format_dashboard(doc))
        return 0

    if args.watch is not None:
        if args.watch <= 0:
            print("ERROR: --watch must be a positive integer.", file=sys.stderr)
            return 1
        try:
            while True:
                print(f"\n--- {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC ---")
                code = render_once()
                if code != 0:
                    return code
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0

    return render_once()


if __name__ == "__main__":
    raise SystemExit(main())
