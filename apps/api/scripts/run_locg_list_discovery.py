"""Run list discovery only (pagination + discovery_report.json)."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    page_date = date.fromisoformat(args.date)
    from app.services.external_catalog.locg_browser import calendar_url_slash_format
    from app.services.external_catalog.locg_list_discovery import (
        discover_release_list_in_browser,
        print_verification_summary,
        save_discovery_report,
        validate_discovery_threshold,
    )

    list_url = calendar_url_slash_format(page_date)
    out_dir = Path(ROOT).parent.parent / "data" / "locg_browser_capture" / page_date.isoformat()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright required", file=sys.stderr)
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        context = browser.new_context()
        page = context.new_page()
        try:
            html, audit = discover_release_list_in_browser(
                page, context, page_date=page_date, list_url=list_url
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "list_page_full.html").write_text(html, encoding="utf-8")
            save_discovery_report(audit, out_dir / "discovery_report.json")
            print_verification_summary(audit)
            validate_discovery_threshold(audit)
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
