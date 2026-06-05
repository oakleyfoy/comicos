"""Regenerate docs/LOCG_2026_BACKFILL_CERTIFICATION_REPORT.md from capture artifacts."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CAPTURE_ROOT = REPO_ROOT / "data" / "locg_browser_capture"
OUT_PATH = REPO_ROOT / "docs" / "LOCG_2026_BACKFILL_CERTIFICATION_REPORT.md"

NON_CLEAN_TERMINAL_PASS = {
    "2026-01-14",
    "2026-01-28",
    "2026-04-08",
    "2026-04-22",
    "2026-04-29",
    "2026-05-06",
}


def wednesdays(start: date, end: date) -> list[str]:
    d = start
    while d.weekday() != 2:
        d += timedelta(days=1)
    out: list[str] = []
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out


def n(x: object, default: int | float = 0) -> int | float:
    return default if x is None else x  # type: ignore[return-value]


def load_week(week: str) -> dict:
    cert_path = CAPTURE_ROOT / week / "locg_capture_certification.json"
    c = json.loads(cert_path.read_text(encoding="utf-8"))
    comp, pers = c["completeness"], c["persistence"]
    sk = pers.get("variant_skipped_reason_counts") or {}
    rt = c.get("runtime") or {}
    pra = comp.get("proof_run_assessment") or {}
    has_queue = bool(
        comp.get("final_parent_issue_queue_count") or pra.get("parent_issue_queue_count")
    )
    pq = int(
        n(
            comp.get("final_parent_issue_queue_count")
            or pra.get("parent_issue_queue_count")
            or pers.get("detail_pages_succeeded")
        )
    )
    vq = int(
        n(
            comp.get("final_variant_queue_count")
            or pra.get("variant_queue_count")
            or pers.get("list_variants_persisted")
        )
    )
    dom_p = int(n(comp.get("parent_issue_rows")))
    dom_v = int(n(comp.get("variant_rows")))
    ok_p = int(n(pers.get("detail_pages_succeeded")))
    dp = int(n(comp.get("duplicate_parent_li_rows"), n(pra.get("duplicate_parent_li_rows"))))
    dv = int(n(comp.get("duplicate_variant_li_rows"), n(pra.get("duplicate_variant_li_rows"))))
    incomplete = bool(dom_p and ok_p < dom_p and not (dp or dv))
    return {
        "week": week,
        "passed": bool(c.get("passed")),
        "has_queue_cert": has_queue,
        "li": int(n(comp.get("total_li_issue_rows"))),
        "parents": pq,
        "variants": vq,
        "dom_parents": dom_p,
        "dom_variants": dom_v,
        "parent_details_ok": ok_p,
        "skip_mp": int(n(sk.get("skipped_missing_parent"))),
        "v_fail": int(n(sk.get("variant_upsert_failure"))),
        "cf": int(n(rt.get("cloudflare_wait_count"))),
        "runtime_s": float(n(rt.get("total_runtime_seconds"))),
        "dup_p": dp,
        "dup_v": dv,
        "lighter": bool(pra.get("legitimately_lighter_release_week")),
        "warnings": c.get("warnings") or [],
        "non_clean": week in NON_CLEAN_TERMINAL_PASS,
        "incomplete_legacy": incomplete,
    }


def markdown_table(rows: list[dict]) -> str:
    lines = [
        "| Week | Cert | Schema | List `<li>` | Parents (queue) | Variants (queue) | Runtime (s) | CF | Notes |",
        "|------|------|--------|-------------|-----------------|------------------|-------------|----|-------|",
    ]
    for r in rows:
        notes: list[str] = []
        if r["dup_p"] or r["dup_v"]:
            notes.append(f"dup DOM +{r['dup_p']}/+{r['dup_v']}")
        if r["lighter"]:
            notes.append("lighter week")
        if r["non_clean"]:
            notes.append("non-clean shell exit")
        if not r["has_queue_cert"]:
            notes.append("legacy cert JSON")
        if r["incomplete_legacy"]:
            notes.append(f"INCOMPLETE dom_parents={r['dom_parents']} ok={r['parent_details_ok']}")
        if r["warnings"]:
            notes.append("warning")
        schema = "queue v1" if r["has_queue_cert"] else "legacy"
        status = "PASS" if r["passed"] else "FAIL"
        note_cell = "; ".join(notes) if notes else "—"
        lines.append(
            f"| {r['week']} | {status} | {schema} | {r['li']} | {r['parents']} | {r['variants']} | "
            f"{r['runtime_s']:.1f} | {r['cf']} | {note_cell} |"
        )
    return "\n".join(lines)


def main() -> None:
    rows = [load_week(w) for w in wednesdays(date(2026, 1, 7), date(2026, 8, 26))]
    rt_sum = sum(r["runtime_s"] for r in rows)
    dup_weeks = [r for r in rows if r["dup_p"] or r["dup_v"]]
    lighter = [r["week"] for r in rows if r["lighter"]]
    non_clean = [r["week"] for r in rows if r["non_clean"] and r["passed"]]
    incomplete = [r for r in rows if r["incomplete_legacy"]]
    queue_weeks = [r for r in rows if r["has_queue_cert"]]

    body = f"""# LoCG 2026 backfill — cumulative certification report

**Window:** Wednesday release weeks **2026-01-07** through **2026-08-26** (34 weeks).  
**Source of truth:** `data/locg_browser_capture/<date>/locg_capture_certification.json` (gitignored on disk; paths referenced for local reproduction).  
**Certification model:** LoCG-Certified-v1 queue coverage (`detail_pages_succeeded == final_parent_issue_queue_count`, variants persisted to `final_variant_queue_count`). Older artifacts without queue fields are labeled **legacy** below.

## Executive summary

| Metric | Value |
|--------|------:|
| Weeks with certification artifact | {len(rows)} |
| Weeks `passed: true` | {sum(1 for r in rows if r['passed'])} |
| Weeks `passed: false` | {sum(1 for r in rows if not r['passed'])} |
| Weeks with queue-based cert fields | {len(queue_weeks)} |
| Total parent issues (queue or persisted succeeded) | {sum(r['parents'] for r in rows)} |
| Total variants (queue or persisted) | {sum(r['variants'] for r in rows)} |
| `skipped_missing_parent` (sum) | {sum(r['skip_mp'] for r in rows)} |
| `variant_upsert_failure` (sum) | {sum(r['v_fail'] for r in rows)} |
| Cloudflare wait events (sum) | {sum(r['cf'] for r in rows)} |
| HTTP 429 count in cert artifacts | *not stored* (operational logs: 0 across backfill) |
| Total certified runtime (sum of `total_runtime_seconds`) | {rt_sum:.1f} s (~{rt_sum / 3600:.2f} h) |
| Average runtime per week | {rt_sum / len(rows):.1f} s (~{rt_sum / len(rows) / 60:.1f} min) |

## Data quality notes

### Duplicate DOM `<li>` rows (queue coverage still passed)

"""
    for r in dup_weeks:
        body += (
            f"- **{r['week']}:** duplicate parent `{r['dup_p']}`, variant `{r['dup_v']}` "
            f"(queue parents `{r['parents']}`, variants `{r['variants']}`).\n"
        )
    if not dup_weeks:
        body += "- None in window.\n"

    body += "\n### Lighter release weeks (assessment flag)\n\n"
    if lighter:
        for w in lighter:
            r = next(x for x in rows if x["week"] == w)
            body += f"- **{w}:** `{r['li']}` list rows, `{r['parents']}` parents, `{r['variants']}` variants.\n"
    else:
        body += "- None flagged.\n"

    body += "\n### Non-clean terminal exit but artifact PASS\n\n"
    body += (
        "Shell exit `4294967295` (force-stop) or missing JSON footer after certification; "
        "artifacts on disk remain authoritative.\n\n"
    )
    for w in non_clean:
        body += f"- {w}\n"

    body += "\n### Legacy / incomplete captures (artifact `passed` but parent gap)\n\n"
    if incomplete:
        for r in incomplete:
            body += (
                f"- **{r['week']}:** DOM parents `{r['dom_parents']}`, "
                f"detail succeeded `{r['parent_details_ok']}` — **recapture recommended** under queue v1.\n"
            )
    else:
        body += "- None detected (excluding duplicate-DOM weeks where queue cert passed).\n"

    body += "\n## Per-week detail\n\n"
    body += markdown_table(rows)
    june_remediation_done = all(
        r["passed"] and r["has_queue_cert"]
        for r in rows
        if r["week"] in ("2026-06-10", "2026-06-17")
    )
    body += "\n\n## Operational follow-ups\n\n"
    if june_remediation_done and not incomplete:
        body += (
            "1. **June 2026 remediation:** complete — **2026-06-10** and **2026-06-17** queue-v1 PASS "
            "(see [LOCG_REMEDIATION_TASK_2026-06-10_17.md](LOCG_REMEDIATION_TASK_2026-06-10_17.md)).\n"
        )
    else:
        body += (
            "1. **Remediation (open):** [LOCG_REMEDIATION_TASK_2026-06-10_17.md](LOCG_REMEDIATION_TASK_2026-06-10_17.md) "
            "until incomplete weeks are recaptured.\n"
        )
    body += (
        "2. Post-cert crosswalk: capture script skips `rebuild_external_catalog_crosswalk` by default; "
        "use `--run-crosswalk` only when needed (`--skip-crosswalk` in backfill docs).\n"
        "3. Post-cert CLI: default path omits `per_issue_timings` from stdout JSON; use `--timing-table` for full dumps.\n"
        "4. Regenerate this file: `python scripts/generate_locg_2026_backfill_certification_report.py` from `apps/api`.\n"
    )

    OUT_PATH.write_text(body, encoding="utf-8")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
