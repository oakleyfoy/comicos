"""Discovery + spreadsheet cert only (no DB)."""
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.external_catalog.locg_browser import calendar_url_slash_format
from app.services.external_catalog.locg_list_discovery import (
    discover_release_list_in_browser,
    save_discovery_report,
)
from app.services.external_catalog.locg_spreadsheet_certification import (
    certify_against_spreadsheet,
    save_certification_report,
)

out = Path(ROOT).parent.parent / "data" / "locg_browser_capture" / "2026-06-10"
out.mkdir(parents=True, exist_ok=True)
started = time.perf_counter()
from playwright.sync_api import sync_playwright

list_url = calendar_url_slash_format(date(2026, 6, 10))
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    ctx = browser.new_context()
    page = ctx.new_page()
    html, audit = discover_release_list_in_browser(page, ctx, page_date=date(2026, 6, 10), list_url=list_url)
    ctx.close()
    browser.close()

save_discovery_report(audit, out / "discovery_report.json")
(out / "list_page.html").write_text(html, encoding="utf-8")
cert = certify_against_spreadsheet(
    html=html,
    page_date=date(2026, 6, 10),
    audit_total_li=audit.total_li_issue_rows,
    audit_parent=audit.parent_issue_rows,
    audit_variant=audit.variant_rows,
    audit_other=audit.other_release_rows,
    list_variants_persisted=0,
)
save_certification_report(cert, out / "spreadsheet_certification.json")
runtime = round(time.perf_counter() - started, 3)
print(
    json.dumps(
        {
            "total_li_issue_rows": audit.total_li_issue_rows,
            "parent_issue_rows": audit.parent_issue_rows,
            "variant_rows": audit.variant_rows,
            "other_release_rows": audit.other_release_rows,
            "extend_calls": audit.pagination_extend_calls,
            "list_variants_found": audit.final_variant_queue_count,
            "list_variants_persisted": 0,
            "spreadsheet_expected": cert.spreadsheet_expected_count,
            "spreadsheet_found": cert.spreadsheet_title_count,
            "spreadsheet_missing": len(cert.missing_from_discovery),
            "spreadsheet_match_percent": cert.match_percent,
            "certification_passed": cert.passed,
            "total_runtime": runtime,
        },
        indent=2,
    )
)
