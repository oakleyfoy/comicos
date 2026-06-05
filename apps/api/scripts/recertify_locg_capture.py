"""Re-run internal capture certification from saved discovery + list HTML."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.external_catalog.locg_capture_certification import (
    certify_locg_capture,
    save_capture_certification_artifacts,
)
from app.services.external_catalog.locg_list_discovery import ListDiscoveryAudit


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = parser.parse_args()
    page_date = date.fromisoformat(args.date)
    base = ROOT.parent.parent / "data" / "locg_browser_capture" / page_date.isoformat()
    discovery_path = base / "discovery_report.json"
    list_path = base / "list_page.html"
    variant_summary_path = base / "variant_persist_summary.json"
    if not discovery_path.is_file() or not list_path.is_file():
        print(json.dumps({"error": "missing discovery_report.json or list_page.html"}))
        return 1
    disc = json.loads(discovery_path.read_text(encoding="utf-8"))
    pag = disc.get("pagination") or {}
    audit = ListDiscoveryAudit(
        page_url=disc.get("page_url", ""),
        page_title=disc.get("page_title", ""),
        total_li_issue_rows=int(disc.get("total_li_issue_rows") or 0),
        parent_issue_rows=int(disc.get("parent_issue_rows") or 0),
        variant_rows=int(disc.get("variant_rows") or 0),
        other_release_rows=int(disc.get("other_release_rows") or 0),
        pagination_mechanism=pag.get("mechanism") or "",
        pagination_extend_calls=int(pag.get("extend_calls") or 0),
        pagination_extend_now=pag.get("extend_now"),
    )
    html = list_path.read_text(encoding="utf-8")
    old_cert = {}
    old_cert_path = base / "locg_capture_certification.json"
    if old_cert_path.is_file():
        old_cert = json.loads(old_cert_path.read_text(encoding="utf-8"))
    old_persist = old_cert.get("persistence") or {}
    skip = {}
    if variant_summary_path.is_file():
        skip = json.loads(variant_summary_path.read_text(encoding="utf-8"))
    old_runtime = old_cert.get("runtime") or {}
    cert = certify_locg_capture(
        page_date=page_date,
        final_url=audit.page_url
        or f"https://leagueofcomicgeeks.com/comics/new-comics/{page_date.year}/{page_date.month:02d}/{page_date.day:02d}",
        page_title=disc.get("page_title", ""),
        html=html,
        discovery_audit=audit,
        list_variants_found=int(old_persist.get("list_variants_found") or skip.get("found") or 0),
        list_variants_persisted=int(old_persist.get("list_variants_persisted") or skip.get("persisted") or 0),
        detail_pages_succeeded=int(old_persist.get("detail_pages_succeeded") or 0),
        detail_pages_attempted=int(old_persist.get("detail_pages_attempted") or 0),
        dry_run=False,
        parent_detail_seconds=None,
        total_runtime_seconds=float(old_runtime.get("total_runtime_seconds") or 0),
        variant_skipped_reason_counts=old_persist.get("variant_skipped_reason_counts") or skip,
    )
    if cert.passed and old_runtime.get("average_parent_detail_seconds"):
        cert.runtime["average_parent_detail_seconds"] = old_runtime["average_parent_detail_seconds"]
        cert.runtime["parent_detail_timing_count"] = old_runtime.get("parent_detail_timing_count")
    save_capture_certification_artifacts(
        report_dir=base,
        cert=cert,
        live_page_state=json.loads((base / "live_page_state_report.json").read_text(encoding="utf-8"))
        if (base / "live_page_state_report.json").is_file()
        else {},
        source_universe=json.loads((base / "source_universe_report.json").read_text(encoding="utf-8"))
        if (base / "source_universe_report.json").is_file()
        else {},
    )
    print(json.dumps(cert.to_dict(), indent=2))
    return 0 if cert.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
