from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin

from app.services.external_catalog.league_of_comic_geeks import LOCG_BASE_URL, _abs_url

EXPECTED_MINIMUM_ISSUE_COUNT = 230
EXPECTED_APPROXIMATE_ISSUE_COUNT = 234
PROOF_RUN_TYPICAL_WEEK_LI_ROWS = 400
LOCG_CAPTURE_LIST_VIEW = "text"
SCROLL_WAIT_MS = 1500
# Consecutive scrolls with zero new li.issue rows before stopping.
SCROLL_STABLE_ROUNDS_REQUIRED = 1
SCROLL_MAX_ATTEMPTS = 25


@dataclass
class ListDiscoveryAudit:
    page_title: str = ""
    page_url: str = ""
    discovery_timestamp: str = ""
    total_li_issue_rows: int = 0
    total_cards_found_on_page: int = 0
    total_issue_links_found: int = 0
    unique_issue_urls: int = 0
    unique_raw_hrefs: int = 0
    unique_parent_issue_urls: int = 0
    unique_variant_urls: int = 0
    filtered_out_urls: int = 0
    duplicate_urls_removed: int = 0
    final_parent_issue_queue_count: int = 0
    final_variant_queue_count: int = 0
    final_issue_queue_count: int = 0
    duplicate_parent_li_rows: int = 0
    duplicate_variant_li_rows: int = 0
    parent_issue_rows: int = 0
    variant_rows: int = 0
    variant_child_rows: int = 0
    other_release_rows: int = 0
    total_release_rows_reconciled: int = 0
    release_type_counts: dict[str, int] = field(default_factory=dict)
    pagination_mechanism: str = ""
    pagination_extend_calls: int = 0
    pagination_final_offset: str | None = None
    pagination_extend_now: str | None = None
    cloudflare_wait_count: int = 0
    cloudflare_total_wait_seconds: float = 0.0
    all_issue_urls: list[str] = field(default_factory=list)
    filtered_out_samples: list[str] = field(default_factory=list)
    duplicate_samples: list[str] = field(default_factory=list)
    root_cause_hints: list[str] = field(default_factory=list)
    discovery_row_count_log: list[dict[str, Any]] = field(default_factory=list)
    scroll_attempts: int = 0
    scroll_row_count_stabilized: bool = False
    scroll_final_li_issue_rows: int = 0

    def to_report_dict(self) -> dict[str, Any]:
        urls = self.all_issue_urls
        return {
            "page_title": self.page_title,
            "page_url": self.page_url,
            "discovery_timestamp": self.discovery_timestamp,
            "expected_approximate_issue_count": EXPECTED_APPROXIMATE_ISSUE_COUNT,
            "expected_minimum_issue_count": EXPECTED_MINIMUM_ISSUE_COUNT,
            "total_li_issue_rows": self.total_li_issue_rows,
            "total_cards_found_on_page": self.total_cards_found_on_page,
            "parent_issue_rows": self.parent_issue_rows,
            "variant_rows": self.variant_rows,
            "other_release_rows": self.other_release_rows,
            "total_release_rows_reconciled": self.total_release_rows_reconciled,
            "unique_parent_issue_urls": self.unique_parent_issue_urls,
            "unique_variant_urls": self.unique_variant_urls,
            "final_parent_issue_queue_count": self.final_parent_issue_queue_count,
            "final_variant_queue_count": self.final_variant_queue_count,
            "duplicate_parent_li_rows": self.duplicate_parent_li_rows,
            "duplicate_variant_li_rows": self.duplicate_variant_li_rows,
            "total_issue_links_found": self.total_issue_links_found,
            "unique_issue_urls": self.unique_issue_urls,
            "unique_raw_hrefs": self.unique_raw_hrefs,
            "filtered_out_urls": self.filtered_out_urls,
            "duplicate_urls_removed": self.duplicate_urls_removed,
            "final_issue_queue_count": self.final_issue_queue_count,
            "variant_child_rows": self.variant_child_rows,
            "release_type_counts": self.release_type_counts,
            "pagination": {
                "mechanism": self.pagination_mechanism,
                "extend_calls": self.pagination_extend_calls,
                "final_offset": self.pagination_final_offset,
                "extend_now": self.pagination_extend_now,
            },
            "cloudflare_wait_count": self.cloudflare_wait_count,
            "cloudflare_total_wait_seconds": self.cloudflare_total_wait_seconds,
            "first_20_urls": urls[:20],
            "last_20_urls": urls[-20:] if urls else [],
            "root_cause_hints": self.root_cause_hints,
            "filtered_out_samples": self.filtered_out_samples[:20],
            "duplicate_samples": self.duplicate_samples[:20],
            "discovery_row_count_log": self.discovery_row_count_log,
            "scroll_discovery": {
                "attempts": self.scroll_attempts,
                "row_count_stabilized": self.scroll_row_count_stabilized,
                "final_li_issue_rows": self.scroll_final_li_issue_rows,
            },
        }


def _abs_comic_href(href: str) -> str | None:
    cleaned = (href or "").strip()
    if not cleaned.startswith("/comic/"):
        return None
    return _abs_url(cleaned)


def audit_list_html(html: str, *, page_url: str, page_title: str = "") -> ListDiscoveryAudit:
    from app.services.external_catalog.locg_browser import parse_list_page_html
    from app.services.external_catalog.locg_live_html import parse_release_date_variant_rows

    audit = ListDiscoveryAudit(
        page_url=page_url,
        page_title=page_title or _extract_title(html),
        discovery_timestamp=datetime.now(timezone.utc).isoformat(),
    )
    audit.total_li_issue_rows = len(re.findall(r"<li[^>]*\bissue\b", html, re.IGNORECASE))
    audit.total_cards_found_on_page = audit.total_li_issue_rows

    raw_hrefs = re.findall(r'href="(/comic/[^"]+)"', html, re.IGNORECASE)
    audit.total_issue_links_found = len(raw_hrefs)

    seen_exact_href: set[str] = set()
    seen_parent_base: set[str] = set()
    seen_variant_full: set[str] = set()
    duplicates: list[str] = []
    filtered: list[str] = []
    card_primary_urls: list[str] = []

    for block in re.finditer(r"<li[^>]*\bissue\b[^>]*>.*?</li>", html, re.IGNORECASE | re.DOTALL):
        match = re.search(r'href="(/comic/\d+/[^"]+)"', block.group(0), re.IGNORECASE)
        if match:
            card_primary_urls.append(_abs_url(match.group(1)))

    for href in raw_hrefs:
        if href in seen_exact_href:
            audit.duplicate_urls_removed += 1
            if len(duplicates) < 20:
                duplicates.append(href)
            continue
        seen_exact_href.add(href)
        abs_url = _abs_comic_href(href)
        if not abs_url:
            audit.filtered_out_urls += 1
            if len(filtered) < 20:
                filtered.append(href)
            continue
        if "?variant=" in href.lower():
            seen_variant_full.add(abs_url)
        else:
            base = abs_url.split("?", 1)[0]
            seen_parent_base.add(base)

    audit.all_issue_urls = card_primary_urls
    audit.unique_parent_issue_urls = len(seen_parent_base)
    audit.unique_variant_urls = len(seen_variant_full)
    audit.unique_issue_urls = len(seen_parent_base | seen_variant_full)
    audit.unique_raw_hrefs = len(seen_exact_href)
    audit.duplicate_samples = duplicates
    audit.filtered_out_samples = filtered

    parent_rows = 0
    variant_rows = 0
    other_rows = 0
    for match in re.finditer(
        r'<li[^>]*\bissue\b[^>]*data-parent="(\d+)"',
        html,
        re.IGNORECASE,
    ):
        parent_id = match.group(1)
        block_start = match.start()
        block_snip = html[block_start : block_start + 400]
        classes_m = re.search(r'class="([^"]*)"', block_snip, re.IGNORECASE)
        classes = classes_m.group(1) if classes_m else ""
        if parent_id == "0":
            parent_rows += 1
        else:
            variant_rows += 1
        if "variant-collapsed" in classes or "variant" in classes:
            audit.release_type_counts["variant_row"] = audit.release_type_counts.get("variant_row", 0) + 1
        elif parent_id == "0":
            audit.release_type_counts["parent_issue_row"] = (
                audit.release_type_counts.get("parent_issue_row", 0) + 1
            )
        else:
            audit.release_type_counts["variant_child_row"] = (
                audit.release_type_counts.get("variant_child_row", 0) + 1
            )

    audit.parent_issue_rows = parent_rows
    audit.variant_rows = variant_rows
    audit.variant_child_rows = variant_rows
    audit.other_release_rows = max(0, audit.total_li_issue_rows - parent_rows - variant_rows)
    audit.total_release_rows_reconciled = parent_rows + variant_rows + audit.other_release_rows

    audit.final_parent_issue_queue_count = len(parse_list_page_html(html, page_date=None))
    audit.final_variant_queue_count = len(parse_release_date_variant_rows(html, page_date=None))
    audit.final_issue_queue_count = audit.final_parent_issue_queue_count
    audit.duplicate_parent_li_rows = max(0, audit.parent_issue_rows - audit.final_parent_issue_queue_count)
    audit.duplicate_variant_li_rows = max(0, audit.variant_rows - audit.final_variant_queue_count)

    _classify_release_types_from_titles(html, audit)
    return audit


def _extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _classify_release_types_from_titles(html: str, audit: ListDiscoveryAudit) -> None:
    title_blocks = re.findall(
        r'<div class="title[^"]*"[^>]*>\s*<a href="[^"]+">([^<]+)</a>',
        html,
        re.IGNORECASE,
    )
    for title in title_blocks:
        lower = title.lower()
        if "variant" in lower or "cover " in lower:
            audit.release_type_counts["title_variant"] = audit.release_type_counts.get("title_variant", 0) + 1
        elif "facsimile" in lower:
            audit.release_type_counts["title_facsimile"] = audit.release_type_counts.get("title_facsimile", 0) + 1
        elif "magazine" in lower:
            audit.release_type_counts["title_magazine"] = audit.release_type_counts.get("title_magazine", 0) + 1
        elif "omnibus" in lower or "tp" in lower or "trade" in lower or "hc" in lower:
            audit.release_type_counts["title_collected_edition"] = (
                audit.release_type_counts.get("title_collected_edition", 0) + 1
            )
        elif "reprint" in lower:
            audit.release_type_counts["title_reprint"] = audit.release_type_counts.get("title_reprint", 0) + 1
        else:
            audit.release_type_counts["title_standard_issue"] = (
                audit.release_type_counts.get("title_standard_issue", 0) + 1
            )


def _block_params(page) -> dict[str, str]:
    block = page.locator("#comic-list-block")
    attrs = [
        "data-list",
        "data-list-option",
        "data-date-type",
        "data-date",
        "data-date-end",
        "data-series-id",
        "data-character",
        "data-user",
        "data-search",
        "data-view",
        "data-list-offset",
    ]
    params: dict[str, str] = {}
    for attr in attrs:
        key = attr.replace("data-", "").replace("-", "_")
        value = block.get_attribute(attr)
        if value is not None:
            params[key] = value
    if "date_type" not in params:
        params["date_type"] = "week"
    params["view"] = LOCG_CAPTURE_LIST_VIEW
    return params


def _list_block_attrs(page) -> dict[str, str | None]:
    block = page.locator("#comic-list-block")
    if block.count() == 0:
        return {}
    return {
        "data_list_offset": block.get_attribute("data-list-offset", timeout=5_000),
        "data_extend_now": block.get_attribute("data-extend-now", timeout=5_000),
    }


def snapshot_list_row_counts(page, *, phase: str) -> dict[str, Any]:
    """Row count + list block attrs for discovery diagnostics."""
    li_count = page.locator("#comic-list-issues li.issue").count()
    attrs = _list_block_attrs(page)
    entry = {
        "phase": phase,
        "li_issue_rows": li_count,
        "data_list_offset": attrs.get("data_list_offset"),
        "data_extend_now": attrs.get("data_extend_now"),
    }
    print(
        f"[discovery] {phase}: li.issue={li_count} "
        f"data-list-offset={attrs.get('data_list_offset')!r} "
        f"data-extend-now={attrs.get('data_extend_now')!r}",
        flush=True,
    )
    return entry


def _scroll_stable_rounds_needed(
    counts: list[int],
    *,
    stable_rounds_required: int = SCROLL_STABLE_ROUNDS_REQUIRED,
) -> int | None:
    """Return 1-based scroll attempt index once row count is unchanged N times in a row."""
    if len(counts) < stable_rounds_required + 1:
        return None
    unchanged_streak = 0
    prev: int | None = None
    for i, count in enumerate(counts):
        if prev is not None and count == prev:
            unchanged_streak += 1
            if unchanged_streak >= stable_rounds_required:
                return i + 1
        else:
            unchanged_streak = 0
        prev = count
    return None


def scroll_list_to_bottom_until_stable(
    page,
    discovery_log: list[dict[str, Any]],
    *,
    max_attempts: int = SCROLL_MAX_ATTEMPTS,
    stable_rounds_required: int = SCROLL_STABLE_ROUNDS_REQUIRED,
    scroll_wait_ms: int = SCROLL_WAIT_MS,
) -> tuple[int, bool, int]:
    """
    Scroll release list until li.issue count stops growing (permanent capture path).
    Returns (final_row_count, stabilized, scroll_attempts).
    """
    counts: list[int] = []
    for i in range(1, max_attempts + 1):
        page.evaluate(
            """() => {
                const ul = document.querySelector('#comic-list-issues');
                if (ul) ul.scrollTop = ul.scrollHeight;
                window.scrollTo(0, document.body.scrollHeight);
            }"""
        )
        page.wait_for_timeout(scroll_wait_ms)
        entry = snapshot_list_row_counts(page, phase=f"after_scroll_to_bottom_{i}")
        discovery_log.append(entry)
        counts.append(int(entry["li_issue_rows"]))
        stable_at = _scroll_stable_rounds_needed(
            counts, stable_rounds_required=stable_rounds_required
        )
        if stable_at is not None:
            final = counts[-1]
            print(
                f"[discovery] scroll stabilized after {stable_at} attempt(s) "
                f"at {final} li.issue rows",
                flush=True,
            )
            return final, True, stable_at
    final = counts[-1] if counts else 0
    print(
        f"[discovery] scroll stopped at max attempts ({max_attempts}); "
        f"final li.issue rows={final} (not stabilized)",
        flush=True,
    )
    return final, False, len(counts)


def print_discovery_row_count_log(discovery_log: list[dict[str, Any]]) -> None:
    if not discovery_log:
        return
    print("\n--- Discovery row count timeline ---", flush=True)
    for entry in discovery_log:
        print(
            f"  {entry.get('phase')}: rows={entry.get('li_issue_rows')} "
            f"offset={entry.get('data_list_offset')!r} extend_now={entry.get('data_extend_now')!r}",
            flush=True,
        )


def apply_text_list_view(page) -> None:
    """Default capture view: Text List (flat release list)."""
    page.evaluate(
        """() => {
            const block = document.querySelector('#comic-list-block');
            if (block) block.setAttribute('data-view', 'text');
            document.querySelectorAll('#options-issues .comic-toolbar-views').forEach((el) => {
                el.classList.toggle('active', el.getAttribute('data-view') === 'text');
            });
            if (typeof ComicList !== 'undefined' && ComicList.loadList) {
                ComicList.loadList();
            }
        }"""
    )
    page.wait_for_timeout(2500)


def extend_release_list_pagination(
    page,
    context,
    *,
    max_extend_calls: int = 40,
    security_stats: Any | None = None,
    discovery_log: list[dict[str, Any]] | None = None,
) -> tuple[int, str]:
    """
    Paginate via GET /comic/get_comics until data-extend-now is 0 or two consecutive
    extend cycles add zero rows.
    """
    block = page.locator("#comic-list-block")
    if block.count() == 0:
        return 0, "list_block_not_found"

    extend_calls = 0
    mechanism = "initial_dom_only"
    prev_li = page.locator("#comic-list-issues li.issue").count()
    attr_offset_raw = block.get_attribute("data-list-offset", timeout=5_000) or "0"
    try:
        attr_offset = int(attr_offset_raw)
    except ValueError:
        attr_offset = prev_li
    # LoCG can leave data-list-offset ahead of rendered <li> rows; API slice must start at DOM count.
    offset = prev_li
    if attr_offset > prev_li + 2:
        page.evaluate(
            """(n) => {
                const b = document.querySelector('#comic-list-block');
                if (b) b.setAttribute('data-list-offset', String(n));
            }""",
            prev_li,
        )
    zero_growth_streak = 0
    force_pagination = prev_li < EXPECTED_MINIMUM_ISSUE_COUNT
    log = discovery_log if discovery_log is not None else []

    from app.services.external_catalog.locg_browser_security import (
        wait_for_security_verification_clear,
    )

    log.append(
        snapshot_list_row_counts(
            page,
            phase="get_comics_loop_start",
        )
    )

    while extend_calls < max_extend_calls:
        if security_stats is not None:
            if not wait_for_security_verification_clear(
                page, for_list_page=True, accumulator=security_stats
            ):
                break
        extend_now = block.get_attribute("data-extend-now", timeout=5_000) or "0"
        if extend_now != "1" and zero_growth_streak >= 1 and not force_pagination:
            break

        params = _block_params(page)
        params["list_offset"] = str(offset)
        api_url = urljoin(LOCG_BASE_URL, "/comic/get_comics")
        rows_before = page.locator("#comic-list-issues li.issue").count()
        response = context.request.get(api_url, params=params, timeout=60_000)
        attempt_entry: dict[str, Any] = {
            "phase": f"get_comics_attempt_{extend_calls + 1}",
            "list_offset": offset,
            "http_status": response.status,
            "li_issue_rows_before": rows_before,
        }
        if response.status != 200:
            attempt_entry["result"] = "http_error"
            log.append(attempt_entry)
            print(
                f"[discovery] get_comics attempt {extend_calls + 1}: status={response.status} "
                f"offset={offset} rows_before={rows_before}",
                flush=True,
            )
            break
        try:
            payload = response.json()
        except Exception as exc:
            attempt_entry["result"] = "json_error"
            attempt_entry["error"] = str(exc)
            log.append(attempt_entry)
            break
        chunk_html = payload.get("list") if isinstance(payload, dict) else None
        chunk_len = len(chunk_html) if isinstance(chunk_html, str) else 0
        attempt_entry["chunk_html_chars"] = chunk_len
        if not isinstance(chunk_html, str) or not chunk_html.strip():
            attempt_entry["result"] = "empty_chunk"
            attempt_entry.update(_list_block_attrs(page))
            log.append(attempt_entry)
            print(
                f"[discovery] get_comics attempt {extend_calls + 1}: empty chunk "
                f"offset={offset} rows_before={rows_before}",
                flush=True,
            )
            zero_growth_streak += 1
            if zero_growth_streak >= 2:
                break
            continue

        page.evaluate(
            """(html) => {
                const ul = document.querySelector('#comic-list-issues');
                if (ul) ul.insertAdjacentHTML('beforeend', html);
            }""",
            chunk_html,
        )
        extend_calls += 1
        mechanism = f"hidden_api_get_comics_pagination_view_{LOCG_CAPTURE_LIST_VIEW}"
        new_li = page.locator("#comic-list-issues li.issue").count()
        attempt_entry["li_issue_rows_after"] = new_li
        attempt_entry["result"] = "appended" if new_li > prev_li else "no_row_growth"
        attempt_entry.update(_list_block_attrs(page))
        log.append(attempt_entry)
        print(
            f"[discovery] get_comics attempt {extend_calls}: rows {rows_before} -> {new_li} "
            f"chunk_chars={chunk_len} offset={offset} "
            f"extend_now={attempt_entry.get('data_extend_now')!r}",
            flush=True,
        )
        if new_li <= prev_li:
            zero_growth_streak += 1
            if zero_growth_streak >= 2:
                break
        else:
            zero_growth_streak = 0
            prev_li = new_li
            offset = new_li
            force_pagination = prev_li < EXPECTED_MINIMUM_ISSUE_COUNT
            page.evaluate(
                """(n) => {
                    const b = document.querySelector('#comic-list-block');
                    if (b) b.setAttribute('data-list-offset', String(n));
                }""",
                new_li,
            )

        extend_now = block.get_attribute("data-extend-now", timeout=5_000) or "0"
        if extend_now == "0" and zero_growth_streak >= 1 and not force_pagination:
            break

    return extend_calls, mechanism


def discover_release_list_in_browser(
    page,
    context,
    *,
    page_date: date,
    list_url: str,
    max_extend_calls: int = 40,
    security_stats: Any | None = None,
) -> tuple[str, ListDiscoveryAudit]:
    """
    Standard release-list discovery for every capture week (not date-specific).

    Flow:
      1. Load release page
      2. Switch to text view
      3. Scroll-to-bottom until row count stabilizes (logged each scroll)
      4. Run /comic/get_comics pagination extension
      5. Final HTML audit → discovery_report.json (via save_discovery_report)
    """
    get_comics_hits: list[dict[str, Any]] = []

    def on_response(response) -> None:
        if "/comic/get_comics" in response.url:
            try:
                get_comics_hits.append(
                    {
                        "url": response.url,
                        "status": response.status,
                    }
                )
            except Exception:
                pass

    page.on("response", on_response)
    page.goto(list_url, wait_until="domcontentloaded", timeout=60_000)

    from app.services.external_catalog.locg_browser_readiness import wait_for_list_readiness
    from app.services.external_catalog.locg_browser_security import (
        wait_for_security_verification_clear,
    )

    from app.services.external_catalog.locg_browser_security import LocgSecurityVerificationTimeout

    if not wait_for_security_verification_clear(
        page, for_list_page=True, accumulator=security_stats
    ):
        raise LocgSecurityVerificationTimeout(
            "security verification did not clear within 60s (list page)"
        )

    wait_for_list_readiness(page)

    discovery_log: list[dict[str, Any]] = []
    discovery_log.append(snapshot_list_row_counts(page, phase="before_text_view"))

    block = page.locator("#comic-list-block")
    if block.count() == 0:
        html = page.content()
        audit = audit_list_html(html, page_url=list_url, page_title=page.title())
        audit.pagination_mechanism = "list_block_not_found"
        audit.root_cause_hints.append(
            "selector_mismatch: #comic-list-block missing (login, bot wall, or wrong page)"
        )
        audit.discovery_row_count_log = discovery_log
        return html, audit

    apply_text_list_view(page)
    discovery_log.append(snapshot_list_row_counts(page, phase="after_text_view"))
    if not wait_for_security_verification_clear(
        page, for_list_page=True, accumulator=security_stats
    ):
        raise LocgSecurityVerificationTimeout(
            "security verification did not clear within 60s (after text view)"
        )
    scroll_final, scroll_stable, scroll_attempts = scroll_list_to_bottom_until_stable(
        page, discovery_log
    )
    extend_calls, mechanism = extend_release_list_pagination(
        page,
        context,
        max_extend_calls=max_extend_calls,
        security_stats=security_stats,
        discovery_log=discovery_log,
    )
    if get_comics_hits and extend_calls == 0:
        mechanism = "hidden_api_get_comics_detected_no_extend"

    html = page.content()
    audit = audit_list_html(
        html,
        page_url=list_url,
        page_title=page.title(),
    )
    audit.pagination_mechanism = mechanism
    audit.pagination_extend_calls = extend_calls
    audit.release_type_counts["capture_list_view"] = 1
    audit.release_type_counts["capture_view_mode"] = LOCG_CAPTURE_LIST_VIEW
    list_block = page.locator("#comic-list-block")
    if list_block.count():
        audit.pagination_final_offset = list_block.get_attribute("data-list-offset", timeout=5_000)
        audit.pagination_extend_now = list_block.get_attribute("data-extend-now", timeout=5_000)
    discovery_log.append(snapshot_list_row_counts(page, phase="final_after_pagination"))
    audit.discovery_row_count_log = discovery_log
    audit.scroll_attempts = scroll_attempts
    audit.scroll_row_count_stabilized = scroll_stable
    audit.scroll_final_li_issue_rows = scroll_final
    print_discovery_row_count_log(discovery_log)
    audit.root_cause_hints.extend(_build_root_cause_hints(audit))
    if security_stats is not None:
        audit.cloudflare_wait_count = security_stats.cloudflare_wait_count
        audit.cloudflare_total_wait_seconds = security_stats.cloudflare_total_wait_seconds
    return html, audit


def _build_root_cause_hints(audit: ListDiscoveryAudit) -> list[str]:
    hints: list[str] = []
    if audit.total_li_issue_rows < EXPECTED_MINIMUM_ISSUE_COUNT:
        if audit.pagination_extend_calls == 0:
            hints.append("pagination: no /comic/get_comics extend calls detected; only initial DOM captured")
        if audit.pagination_extend_now == "1":
            hints.append("pagination: data-extend-now still 1 after extend loop; list may be incomplete")
    if audit.total_release_rows_reconciled != audit.total_li_issue_rows:
        hints.append(
            f"reconciliation: parent+variant+other ({audit.total_release_rows_reconciled}) "
            f"!= total_li_issue_rows ({audit.total_li_issue_rows})"
        )
    return hints


def save_discovery_report(audit: ListDiscoveryAudit, report_path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(audit.to_report_dict(), indent=2), encoding="utf-8")


def print_verification_summary(audit: ListDiscoveryAudit) -> None:
    expected = EXPECTED_APPROXIMATE_ISSUE_COUNT
    actual = audit.total_li_issue_rows
    diff = expected - actual
    missing_pct = round(100.0 * diff / expected, 1) if expected else 0.0
    print(f"Expected count: ~{expected}")
    print(f"Actual count discovered (li.issue rows): {actual}")
    print(f"Parent issue rows (data-parent=0): {audit.parent_issue_rows}")
    print(f"Variant rows (data-parent!=0): {audit.variant_rows}")
    print(f"Other release rows: {audit.other_release_rows}")
    print(f"Total reconciled: {audit.total_release_rows_reconciled}")
    print(f"Parent queue count: {audit.final_parent_issue_queue_count}")
    print(f"Variant queue count: {audit.final_variant_queue_count}")
    print(f"Unique parent URLs (base): {audit.unique_parent_issue_urls}")
    print(f"Unique variant URLs (?variant=): {audit.unique_variant_urls}")
    print(f"Capture list view: {LOCG_CAPTURE_LIST_VIEW}")
    print(f"Difference vs spreadsheet ~{expected}: {diff}")
    print(f"Missing percentage: {missing_pct}%")
    print(f"Pagination mechanism: {audit.pagination_mechanism}")
    print(f"Extend API calls: {audit.pagination_extend_calls}")
    if audit.root_cause_hints:
        print("Root-cause hints:")
        for hint in audit.root_cause_hints:
            print(f"  - {hint}")


def validate_discovery_reconciliation(audit: ListDiscoveryAudit) -> None:
    if audit.total_release_rows_reconciled != audit.total_li_issue_rows:
        raise RuntimeError(
            "Release row reconciliation failed: "
            f"parent({audit.parent_issue_rows}) + variant({audit.variant_rows}) + "
            f"other({audit.other_release_rows}) != total_li_issue_rows({audit.total_li_issue_rows})"
        )


def validate_discovery_threshold(audit: ListDiscoveryAudit) -> None:
    validate_discovery_reconciliation(audit)
    if audit.total_li_issue_rows < EXPECTED_MINIMUM_ISSUE_COUNT:
        raise RuntimeError("Issue discovery count below expected threshold.")
