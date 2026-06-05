"""Inspect live LoCG browser page state vs spreadsheet (no normalization changes)."""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.external_catalog.locg_browser import calendar_url_slash_format
from app.services.external_catalog.locg_list_discovery import (
    LOCG_CAPTURE_LIST_VIEW,
    _block_params,
    apply_text_list_view,
    discover_release_list_in_browser,
)
from app.services.external_catalog.locg_spreadsheet_certification import (
    extract_list_row_titles,
    extract_parent_issue_titles,
    load_spreadsheet_titles,
)


def main() -> int:
    page_date = date(2026, 6, 10)
    list_url = calendar_url_slash_format(page_date)
    xlsx = ROOT.parent.parent / "data/locg_browser_capture/2026-06-10/6-10-26.xlsx"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright required", file=sys.stderr)
        return 1

    report: dict[str, object] = {"target_date": page_date.isoformat(), "requested_url": list_url}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        try:
            html, audit = discover_release_list_in_browser(
                page, context, page_date=page_date, list_url=list_url
            )
            report["final_url"] = page.url
            report["page_title"] = page.title()
            report["discovery_audit"] = {
                "total_li_issue_rows": audit.total_li_issue_rows,
                "parent_issue_rows": audit.parent_issue_rows,
                "variant_rows": audit.variant_rows,
                "pagination": audit.to_report_dict().get("pagination"),
            }

            date_heading = page.evaluate(
                """() => {
                    const h = document.querySelector('h1, .page-title, .releases-heading');
                    if (h) return h.innerText.trim();
                    const rel = document.querySelector('.releases-date, [class*="release"]');
                    if (rel) return rel.innerText.trim();
                    const block = document.querySelector('#comic-list-block');
                    return block ? block.getAttribute('data-date') : null;
                }"""
            )
            report["date_heading_visible"] = date_heading

            block_attrs = page.evaluate(
                """() => {
                    const b = document.querySelector('#comic-list-block');
                    if (!b) return null;
                    const out = {};
                    for (const a of b.attributes) {
                        if (a.name.startsWith('data-')) out[a.name] = a.value;
                    }
                    return out;
                }"""
            )
            report["comic_list_block_data_attrs"] = block_attrs
            report["api_block_params"] = _block_params(page)

            active_view = page.evaluate(
                """() => {
                    const active = document.querySelector('#options-issues .comic-toolbar-views.active');
                    return active ? active.getAttribute('data-view') : null;
                }"""
            )
            report["active_toolbar_view"] = active_view
            report["configured_capture_view"] = LOCG_CAPTURE_LIST_VIEW

            parent_titles_live = page.evaluate(
                """() => {
                    const titles = [];
                    const lis = document.querySelectorAll('#comic-list-issues li.issue');
                    for (const li of lis) {
                        if (li.getAttribute('data-parent') !== '0') continue;
                        const el = li.querySelector('[data-sorting]');
                        if (el) titles.push(el.getAttribute('data-sorting').trim());
                        else {
                            const a = li.querySelector('.title a, a.title');
                            if (a) titles.push(a.innerText.trim());
                        }
                        if (titles.length >= 25) break;
                    }
                    return titles;
                }"""
            )
            report["first_25_parent_titles_live_dom"] = parent_titles_live

            sheet = load_spreadsheet_titles(xlsx) if xlsx.is_file() else []
            report["first_25_spreadsheet_titles"] = sheet[:25]

            needle_batman = "Absolute Batman #21"
            needle_cat = "Absolute Catwoman #1"
            html_lower = html.lower()
            list_text = page.evaluate(
                "() => document.querySelector('#comic-list-issues')?.innerText || ''"
            )

            parents = extract_parent_issue_titles(html)
            all_rows = extract_list_row_titles(html)

            def contains_ci(hay: str, needle: str) -> bool:
                return needle.lower() in hay.lower()

            report["absolute_batman_21"] = {
                "in_parent_rows": any(contains_ci(t, needle_batman) for t in parents),
                "in_variant_or_all_rows": any(contains_ci(t, needle_batman) for t in all_rows),
                "in_list_inner_text": contains_ci(list_text, needle_batman),
                "in_raw_html": contains_ci(html, needle_batman),
                "parent_match_samples": [t for t in parents if "absolute batman" in t.lower()][:5],
            }
            report["absolute_catwoman_1_in_spreadsheet"] = any(
                contains_ci(t, needle_cat) for t in sheet
            )
            report["absolute_catwoman_1_in_spreadsheet_samples"] = [
                t for t in sheet if "catwoman" in t.lower() or "absolute cat" in t.lower()
            ][:10]

            # URL query / hash
            from urllib.parse import parse_qs, urlparse

            parsed = urlparse(page.url)
            report["url_path"] = parsed.path
            report["url_query_params"] = parse_qs(parsed.query)
            report["url_fragment"] = parsed.fragment

            # Search params on any get_comics seen in page scripts (best-effort from block)
            report["june_10_2026_confirmed"] = {
                "url_contains_2026_06_10": "/2026/06/10" in (page.url or ""),
                "block_data_date": (block_attrs or {}).get("data-date") if block_attrs else None,
                "expected_iso": "2026-06-10",
            }

            out_path = (
                ROOT.parent.parent
                / "data/locg_browser_capture/2026-06-10/live_page_state_report.json"
            )
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(json.dumps(report, indent=2, ensure_ascii=False))
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
