"""Run July forward LoCG capture weeks and print summary metrics."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATES = ("2026-07-08", "2026-07-15", "2026-07-22", "2026-07-29")
DATA_ROOT = ROOT.parent.parent / "data" / "locg_browser_capture"


def _load_week(date: str) -> dict:
    cert_path = DATA_ROOT / date / "locg_capture_certification.json"
    if not cert_path.is_file():
        return {"date": date, "error": f"missing {cert_path}"}
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    comp = cert.get("completeness") or {}
    persist = cert.get("persistence") or {}
    runtime = cert.get("runtime") or {}
    skip = persist.get("variant_skipped_reason_counts") or {}
    throttle = runtime.get("adaptive_throttle") or {}
    return {
        "date": date,
        "certification_passed": cert.get("passed"),
        "total_li_issue_rows": comp.get("total_li_issue_rows"),
        "parent_issue_rows": comp.get("parent_issue_rows"),
        "variant_rows": comp.get("variant_rows"),
        "list_variants_found": persist.get("list_variants_found"),
        "list_variants_persisted": persist.get("list_variants_persisted"),
        "skipped_missing_parent": skip.get("skipped_missing_parent", 0),
        "variant_upsert_failure": skip.get("variant_upsert_failure", 0),
        "parent_details_processed": persist.get("detail_pages_succeeded"),
        "avg_parent_detail_seconds": runtime.get("average_parent_detail_seconds"),
        "total_runtime": runtime.get("total_runtime_seconds"),
        "cloudflare_wait_count": runtime.get("cloudflare_wait_count")
        or throttle.get("cloudflare_wait_count"),
        "429_count": throttle.get("rate_limit_429_count", 0),
    }


def main() -> int:
    env = os.environ.copy()
    if not env.get("DATABASE_URL", "").strip():
        print("error: DATABASE_URL required", file=sys.stderr)
        return 1
    script = ROOT / "scripts" / "capture_locg_date_details_browser.py"
    for date in DATES:
        print(f"\n========== capture {date} ==========", flush=True)
        rc = subprocess.call(
            [
                sys.executable,
                str(script),
                "--production",
                "--email",
                "ofoy@att.net",
                "--date",
                date,
                "--headful",
                "--save-raw",
                "--adaptive-delay",
                "--skip-crosswalk",
            ],
            cwd=str(ROOT),
            env=env,
        )
        if rc != 0:
            print(f"capture failed for {date} exit={rc}", file=sys.stderr)
            return rc
    rows = [_load_week(d) for d in DATES]
    out = DATA_ROOT.parent.parent / "docs" / "LOCG_JULY_2026_CAPTURE_VALIDATION.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\n--- July forward validation ---", flush=True)
    for r in rows:
        print(r, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
