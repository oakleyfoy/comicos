"""Run August 2026 LoCG forward capture weeks and print summary metrics."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATES = ("2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26")
DATA_ROOT = ROOT.parent.parent / "data" / "locg_browser_capture"
DOCS = ROOT.parent.parent / "docs"


def _load_week(date: str) -> dict:
    cert_path = DATA_ROOT / date / "locg_capture_certification.json"
    if not cert_path.is_file():
        return {"date": date, "error": f"missing {cert_path}"}
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    comp = cert.get("completeness") or {}
    persist = cert.get("persistence") or {}
    runtime = cert.get("runtime") or {}
    skip = persist.get("variant_skipped_reason_counts") or {}
    assessment = comp.get("proof_run_assessment") or {}
    throttle = runtime.get("adaptive_throttle") or {}
    notes = []
    if assessment.get("legitimately_lighter_release_week"):
        notes.append("lighter week")
    for w in cert.get("warnings") or []:
        if "lighter release week" in w:
            notes.append("lighter week (warning)")
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
        "proof_run_assessment": assessment,
        "warnings": cert.get("warnings"),
        "failure_reasons": cert.get("failure_reasons"),
        "notes": "; ".join(dict.fromkeys(notes)) if notes else "",
    }


def _write_markdown(rows: list[dict]) -> None:
    lines = [
        "# LoCG August 2026 forward capture validation",
        "",
        "```bash",
        "cd apps/api",
        "export DATABASE_URL=postgresql+pg8000://postgres:postgres@localhost:5433/comic_os",
        "python scripts/capture_locg_date_details_browser.py \\",
        "  --production --email ofoy@att.net \\",
        "  --date YYYY-MM-DD --headful --save-raw --adaptive-delay --skip-crosswalk",
        "```",
        "",
        "## Summary",
        "",
        "| Week | Certification | Rows | Parents | Variants | Persisted | Runtime (s) | Notes |",
        "|------|---------------|------|---------|----------|-----------|-------------|-------|",
    ]
    all_pass = True
    for r in rows:
        if r.get("error"):
            all_pass = False
            lines.append(f"| {r['date']} | ERROR | — | — | — | — | — | {r['error']} |")
            continue
        passed = r.get("certification_passed")
        if not passed:
            all_pass = False
        cert = "**PASS**" if passed else "**FAIL**"
        lines.append(
            f"| {r['date']} | {cert} | {r.get('total_li_issue_rows')} | "
            f"{r.get('parent_issue_rows')} | {r.get('variant_rows')} | "
            f"{r.get('list_variants_persisted')} | {r.get('total_runtime')} | "
            f"{r.get('notes', '')} |"
        )
    lines.extend(
        [
            "",
            f"**August forward gate:** {'**4/4 certified**' if all_pass else 'incomplete — see per-week detail'}",
            "",
        ]
    )
    for r in rows:
        if r.get("error"):
            continue
        lines.extend(
            [
                f"### {r['date']}",
                "",
                f"- certification_passed: {r.get('certification_passed')}",
                f"- total_li_issue_rows: {r.get('total_li_issue_rows')}",
                f"- parent_issue_rows: {r.get('parent_issue_rows')}",
                f"- variant_rows: {r.get('variant_rows')}",
                f"- list_variants_found / persisted: {r.get('list_variants_found')} / {r.get('list_variants_persisted')}",
                f"- skipped_missing_parent: {r.get('skipped_missing_parent')}",
                f"- variant_upsert_failure: {r.get('variant_upsert_failure')}",
                f"- parent_details_processed: {r.get('parent_details_processed')}",
                f"- avg_parent_detail_seconds: {r.get('avg_parent_detail_seconds')}",
                f"- total_runtime: {r.get('total_runtime')}",
                f"- cloudflare_wait_count: {r.get('cloudflare_wait_count')}",
                f"- 429_count: {r.get('429_count')}",
                f"- proof_run_assessment: `{json.dumps(r.get('proof_run_assessment'), default=str)}`",
                "",
            ]
        )
        if r.get("failure_reasons"):
            lines.append(f"- failure_reasons: {r['failure_reasons']}")
            lines.append("")
        if r.get("warnings"):
            lines.append(f"- warnings: {r['warnings']}")
            lines.append("")
    path = DOCS / "LOCG_AUGUST_2026_CAPTURE_VALIDATION.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    (DOCS / "LOCG_AUGUST_2026_CAPTURE_VALIDATION.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )


def main() -> int:
    if not os.environ.get("DATABASE_URL", "").strip():
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
            ],
            cwd=str(ROOT),
            env=os.environ.copy(),
        )
        if rc != 0:
            print(f"capture failed for {date} exit={rc}", file=sys.stderr)
            rows = [_load_week(d) for d in DATES]
            _write_markdown(rows)
            return rc
    rows = [_load_week(d) for d in DATES]
    _write_markdown(rows)
    print("\n--- August forward validation ---", flush=True)
    for r in rows:
        print(json.dumps(r, indent=2, default=str), flush=True)
    return 0 if all(r.get("certification_passed") for r in rows if not r.get("error")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
