"""Measure LoCG release list counts per view mode and variant display setting."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LIST_URL = "https://leagueofcomicgeeks.com/comics/new-comics/2026/06/10"
OUT_DIR = Path(ROOT).parent.parent / "data" / "locg_browser_capture" / "2026-06-10" / "view_mode_investigation"
SPREADSHEET_TARGET = 234


def _count_rows(html: str) -> dict[str, int]:
    total = len(re.findall(r'<li class="issue', html, re.IGNORECASE))
    parent = len(re.findall(r'data-parent="0"', html))
    variant = 0
    for m in re.finditer(
        r'<li class="issue[^"]*"[^>]*data-parent="(\d+)"',
        html,
        re.IGNORECASE,
    ):
        if m.group(1) != "0":
            variant += 1
    if variant == 0 and total > parent:
        variant = total - parent
    visible = len(
        re.findall(
            r'<li class="issue(?![^"]*hidden)[^"]*"[^>]*>',
            html,
            re.IGNORECASE,
        )
    )
    hidden_variant = len(
        re.findall(r'<li class="issue[^"]*variant-collapsed hidden', html, re.IGNORECASE)
    )
    return {
        "total_li_issue_rows": total,
        "parent_issue_rows": parent,
        "variant_rows": variant,
        "visible_issue_rows": visible,
        "hidden_variant_collapsed_rows": hidden_variant,
    }


def _extend_list(page, context, max_calls: int = 40) -> int:
    block = page.locator("#comic-list-block")
    if block.count() == 0:
        return 0
    calls = 0
    prev = page.locator("#comic-list-issues li.issue").count()
    offset = int(block.get_attribute("data-list-offset", timeout=5_000) or str(prev))
    from urllib.parse import urljoin

    from app.services.external_catalog.league_of_comic_geeks import LOCG_BASE_URL
    from app.services.external_catalog.locg_list_discovery import (
        LOCG_CAPTURE_LIST_VIEW,
        _block_params,
        apply_text_list_view,
        extend_release_list_pagination,
    )

    while calls < max_calls:
        extend_now = block.get_attribute("data-extend-now", timeout=5_000) or "0"
        if calls > 0 and extend_now != "1" and prev >= 200:
            break
        params = _block_params(page)
        params["list_offset"] = str(offset)
        api_url = urljoin(LOCG_BASE_URL, "/comic/get_comics")
        response = context.request.get(api_url, params=params, timeout=60_000)
        if response.status != 200:
            break
        try:
            payload = response.json()
        except Exception:
            break
        chunk = payload.get("list") if isinstance(payload, dict) else None
        if not isinstance(chunk, str) or not chunk.strip():
            break
        page.evaluate(
            """(html) => {
                const ul = document.querySelector('#comic-list-issues');
                if (ul) ul.insertAdjacentHTML('beforeend', html);
            }""",
            chunk,
        )
        calls += 1
        new_count = page.locator("#comic-list-issues li.issue").count()
        if new_count <= prev:
            break
        prev = new_count
        offset = new_count
        page.evaluate(
            """(n) => {
                const b = document.querySelector('#comic-list-block');
                if (b) b.setAttribute('data-list-offset', String(n));
            }""",
            new_count,
        )
        if prev >= 230:
            break
    return calls


def _switch_view(page, view: str) -> None:
    page.evaluate(
        """(view) => {
            const block = document.querySelector('#comic-list-block');
            if (block) block.setAttribute('data-view', view);
            const opts = document.querySelectorAll('#options-issues .comic-toolbar-views');
            opts.forEach((el) => {
                el.classList.toggle('active', el.getAttribute('data-view') === view);
            });
            if (typeof ComicList !== 'undefined' && ComicList.loadList) {
                ComicList.loadList();
            }
        }""",
        view,
    )
    page.wait_for_timeout(2500)


def _find_separate_variants_controls(page) -> list[dict[str, str]]:
    return page.evaluate(
        """() => {
            const hits = [];
            document.querySelectorAll('li, label, span, a, button').forEach((el) => {
                const t = (el.textContent || '').trim();
                if (/separate\\s+variant/i.test(t) && t.length < 80) {
                    hits.push({
                        tag: el.tagName,
                        text: t,
                        classes: el.className || '',
                        preferenceId: el.getAttribute('data-preference-id') || '',
                        dataId: el.getAttribute('data-id') || '',
                    });
                }
            });
            return hits.slice(0, 20);
        }"""
    )


def _toggle_separate_variants(page, enable: bool) -> bool:
    """Best-effort: click Separate Variants preference if present."""
    return page.evaluate(
        """(enable) => {
            const candidates = Array.from(document.querySelectorAll('.filter-options-preference, li.option'));
            for (const el of candidates) {
                const t = (el.textContent || '').trim();
                if (!/separate\\s+variant/i.test(t)) continue;
                const selected = el.classList.contains('selected');
                const wantOn = enable;
                if (wantOn !== selected) {
                    el.click();
                    return true;
                }
                return true;
            }
            return false;
        }""",
        enable,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--headful", action="store_true")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright required", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    api_log: list[dict] = []

    def on_response(response) -> None:
        if "/comic/get_comics" not in response.url:
            return
        try:
            qs = parse_qs(urlparse(response.url).query)
            api_log.append(
                {
                    "url": response.url,
                    "status": response.status,
                    "view": (qs.get("view") or [""])[0],
                    "list_offset": (qs.get("list_offset") or [""])[0],
                    "list": (qs.get("list") or [""])[0],
                }
            )
        except Exception:
            pass

    report: dict = {
        "list_url": LIST_URL,
        "spreadsheet_target": SPREADSHEET_TARGET,
        "views": {},
        "separate_variants": {},
        "separate_variants_controls_found": [],
        "api_calls_sample": [],
        "notes": [],
    }

    views = [
        ("thumbs", "Thumbnail View"),
        ("list", "Detailed View"),
        ("text", "Text List View"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headful)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.on("response", on_response)
        try:
            page.goto(LIST_URL, wait_until="domcontentloaded", timeout=60_000)
            page.wait_for_timeout(3000)
            if page.locator("#comic-list-block").count() == 0:
                report["notes"].append("list_block_not_found: login or bot wall")
                OUT_DIR.joinpath("report.json").write_text(
                    json.dumps(report, indent=2), encoding="utf-8"
                )
                print(json.dumps(report, indent=2))
                return 2

            report["separate_variants_controls_found"] = _find_separate_variants_controls(page)
            apply_text_list_view(page)
            extend_calls, _ = extend_release_list_pagination(page, context)
            report["pagination_extend_calls_baseline"] = extend_calls
            report["default_capture_view"] = LOCG_CAPTURE_LIST_VIEW

            for view_key, label in views:
                api_log.clear()
                _switch_view(page, view_key)
                extend_release_list_pagination(page, context)
                html = page.content()
                counts = _count_rows(html)
                block = page.locator("#comic-list-block")
                counts["data_view_attr"] = block.get_attribute("data-view") or ""
                counts["extend_now"] = block.get_attribute("data-extend-now") or ""
                counts["list_offset"] = block.get_attribute("data-list-offset") or ""
                counts["label"] = label
                counts["extend_calls_this_view"] = len(api_log)
                report["views"][view_key] = counts
                (OUT_DIR / f"list_{view_key}.html").write_text(html, encoding="utf-8")

            # Separate Variants ON/OFF (if control exists)
            for flag, key in ((False, "off"), (True, "on")):
                api_log.clear()
                toggled = _toggle_separate_variants(page, flag)
                if toggled:
                    page.wait_for_timeout(2500)
                    _extend_list(page, context)
                html = page.content()
                counts = _count_rows(html)
                counts["toggle_found"] = toggled
                report["separate_variants"][key] = counts
                (OUT_DIR / f"list_variants_{key}.html").write_text(html, encoding="utf-8")

            if not report["separate_variants_controls_found"]:
                report["notes"].append(
                    "Separate Variants control not found in DOM (may require logged-in Pro UI)."
                )

            report["api_calls_sample"] = api_log[-30:]
        finally:
            context.close()
            browser.close()

    # Covers only is locked in snapshot; note it
    report["covers_only_view"] = {
        "status": "locked_pro_feature_in_dom",
        "count": None,
    }

    best_key = None
    best_diff = 10_000
    for view_key, data in report["views"].items():
        total = int(data.get("total_li_issue_rows") or 0)
        diff = abs(SPREADSHEET_TARGET - total)
        if diff < best_diff:
            best_diff = diff
            best_key = view_key
    report["closest_to_spreadsheet_234"] = {
        "view": best_key,
        "total_li_issue_rows": (report["views"].get(best_key or "") or {}).get(
            "total_li_issue_rows"
        ),
        "delta": best_diff,
    }

    out_path = OUT_DIR / "report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
