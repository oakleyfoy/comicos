from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from app.services.external_catalog.locg_capture_timing import CaptureTimingAudit, IssueCaptureTiming
from urllib.parse import urljoin

from app.services.external_catalog.character_extract import expand_characters_from_raw
from app.services.external_catalog.league_of_comic_geeks import (
    LOCG_BASE_URL,
    LocgListIssueStub,
    LocgListVariantRowStub,
    merge_detail_into_seed,
    parse_issue_detail_page,
    parse_release_date_page,
    stub_to_detail_seed,
)

from app.services.external_catalog.locg_browser_readiness import (
    NAVIGATION_TIMEOUT_MS,
    wait_for_detail_readiness,
)


class LocgBrowserBlockedError(Exception):
    pass


def calendar_url_slash_format(page_date: date) -> str:
    return urljoin(
        LOCG_BASE_URL,
        f"/comics/new-comics/{page_date.year}/{page_date.month:02d}/{page_date.day:02d}",
    )


def detect_access_blocked(*, html: str, final_url: str, status_code: int | None) -> str | None:
    if status_code in {401, 403, 429}:
        return f"HTTP {status_code}"
    lower = (html or "").lower()
    url_lower = (final_url or "").lower()
    if "cf-browser-verification" in lower or "just a moment" in lower and "cloudflare" in lower:
        return "cloudflare_challenge"
    if "access denied" in lower or "forbidden" in lower[:2000]:
        return "access_denied"
    if "/login" in url_lower and "sign in" in lower:
        return "login_redirect"
    return None


def enrich_detail_payload(detail: dict[str, Any]) -> dict[str, Any]:
    merged = dict(detail)
    merged["characters"] = expand_characters_from_raw(merged)
    return merged


def parse_list_page_html(html: str, *, page_date: date) -> list[LocgListIssueStub]:
    from app.services.external_catalog.locg_live_html import parse_release_date_live_page

    if "comic-list-issues" in html or 'data-list="releases"' in html:
        live = parse_release_date_live_page(html, page_date=page_date)
        if live:
            return live
    stubs = parse_release_date_page(html, page_date=page_date)
    if stubs:
        return stubs
    return parse_release_date_live_page(html, page_date=page_date)


def parse_list_variant_rows(html: str, *, page_date: date) -> list[LocgListVariantRowStub]:
    from app.services.external_catalog.locg_live_html import parse_release_date_variant_rows

    return parse_release_date_variant_rows(html, page_date=page_date)


def parse_detail_page_html(html: str) -> dict[str, Any]:
    from app.services.external_catalog.locg_live_html import enrich_issue_detail_from_live_html

    base = parse_issue_detail_page(html)
    enriched = enrich_issue_detail_from_live_html(html, base)
    return enrich_detail_payload(enriched)


@dataclass
class BrowserCaptureCounters:
    list_page_loaded: bool = False
    list_issues_found: int = 0
    list_variants_found: int = 0
    list_variants_persisted: int = 0
    variant_skipped_reason_counts: dict[str, int] = field(default_factory=dict)
    detail_pages_attempted: int = 0
    detail_pages_succeeded: int = 0
    intentional_parent_skips: int = 0
    resume_parent_skips: int = 0
    skipped_blocked_details: list[dict[str, str]] = field(default_factory=list)
    issues_created: int = 0
    issues_updated: int = 0
    variants_created: int = 0
    creators_created: int = 0
    characters_created: int = 0
    errors_count: int = 0
    error_sample: list[str] = field(default_factory=list)
    post_capture_warnings: list[str] = field(default_factory=list)


def run_playwright_capture(
    *,
    page_date: date,
    headless: bool,
    delay_seconds: float,
    max_issues: int | None,
    dry_run: bool,
    save_raw_dir: Path | None,
    process_issue: Callable[[LocgListIssueStub, str, IssueCaptureTiming], None],
    should_skip_url: Callable[[str], bool] | None = None,
    user_skip_matcher: Callable[[str, str], bool] | None = None,
    persist_list_variants: Callable[..., Any] | None = None,
    timing_audit: CaptureTimingAudit | None = None,
    adaptive_delay: Any | None = None,
) -> tuple[BrowserCaptureCounters, CaptureTimingAudit]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "playwright is required for browser capture; pip install playwright && playwright install chromium"
        ) from exc

    counters = BrowserCaptureCounters()
    audit = timing_audit if timing_audit is not None else CaptureTimingAudit()
    run_started = time.perf_counter()
    list_url = calendar_url_slash_format(page_date)
    first_issue = True

    with sync_playwright() as playwright:
        launch_started = time.perf_counter()
        browser = playwright.chromium.launch(headless=headless)
        audit.browser_launch_seconds = round(time.perf_counter() - launch_started, 3)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 900},
        )
        page = context.new_page()
        discovery_report_dir = save_raw_dir
        if discovery_report_dir is None:
            discovery_report_dir = (
                Path(__file__).resolve().parents[5]
                / "data"
                / "locg_browser_capture"
                / page_date.isoformat()
            )
        try:
            from app.services.external_catalog.locg_list_discovery import (
                discover_release_list_in_browser,
                print_verification_summary,
                save_discovery_report,
                validate_discovery_reconciliation,
            )

            from app.services.external_catalog.locg_browser_security import (
                LocgSecurityVerificationTimeout,
                SecurityWaitAccumulator,
                wait_for_security_verification_clear,
            )

            security_stats = SecurityWaitAccumulator()
            t0 = time.perf_counter()
            try:
                list_html, discovery_audit = discover_release_list_in_browser(
                    page,
                    context,
                    page_date=page_date,
                    list_url=list_url,
                    security_stats=security_stats,
                )
            except LocgSecurityVerificationTimeout as exc:
                raise LocgBrowserBlockedError(str(exc)) from exc
            audit.cloudflare_wait_count = security_stats.cloudflare_wait_count
            audit.cloudflare_total_wait_seconds = security_stats.cloudflare_total_wait_seconds
            audit.list_page_goto_seconds = round(time.perf_counter() - t0, 3)
            report_path = discovery_report_dir / "discovery_report.json"
            try:
                save_discovery_report(discovery_audit, report_path)
            except OSError as exc:
                counters.post_capture_warnings.append(f"discovery_report.json: {exc}")
            print("\n--- List discovery verification ---", flush=True)
            print_verification_summary(discovery_audit)
            print(f"Discovery report: {report_path}", flush=True)
            validate_discovery_reconciliation(discovery_audit)

            if delay_seconds > 0:
                t_wait = time.perf_counter()
                page.wait_for_timeout(int(delay_seconds * 1000))
                audit.list_page_wait_seconds = round(time.perf_counter() - t_wait, 3)
            audit.list_selector_wait_seconds = 0.0
            audit.list_html_extraction_seconds = 0.0
            status = None
            blocked = detect_access_blocked(
                html=list_html, final_url=page.url or list_url, status_code=status
            )
            if blocked:
                raise LocgBrowserBlockedError(f"list page blocked: {blocked} ({list_url})")

            if save_raw_dir is not None:
                from app.services.external_catalog.locg_capture_io import safe_write_text

                t_raw = time.perf_counter()
                safe_write_text(
                    save_raw_dir / "list_page.html",
                    list_html,
                    warnings=counters.post_capture_warnings,
                    label="list_page.html",
                )
                audit.list_raw_save_seconds = round(time.perf_counter() - t_raw, 3)

            counters.list_page_loaded = True
            t_parse = time.perf_counter()
            stubs = parse_list_page_html(list_html, page_date=page_date)
            audit.list_parser_seconds = round(time.perf_counter() - t_parse, 3)
            counters.list_issues_found = len(stubs)

            budget = max_issues if max_issues is not None else len(stubs)
            if adaptive_delay is not None:
                adaptive_delay.log_status(
                    cloudflare_wait_count=security_stats.cloudflare_wait_count,
                    force=True,
                )
            for stub in stubs[:budget]:
                detail_url = stub.source_url
                if not detail_url:
                    continue
                issue_timing = IssueCaptureTiming(
                    issue_title=stub.title,
                    issue_url=detail_url,
                )
                if first_issue:
                    issue_timing.browser_launch_seconds = audit.browser_launch_seconds
                    first_issue = False
                if should_skip_url and should_skip_url(detail_url):
                    issue_timing.skipped = True
                    counters.resume_parent_skips += 1
                    audit.issue_timings.append(issue_timing)
                    continue
                if user_skip_matcher and user_skip_matcher(detail_url, stub.title):
                    from app.services.external_catalog.locg_browser_user_skip import (
                        record_skipped_blocked_detail,
                    )

                    issue_timing.skipped = True
                    record_skipped_blocked_detail(
                        counters, url=detail_url, title=stub.title
                    )
                    print(
                        f"skipped_blocked_detail: {detail_url} ({stub.title})",
                        flush=True,
                    )
                    audit.issue_timings.append(issue_timing)
                    continue
                counters.detail_pages_attempted += 1
                issue_started = time.perf_counter()
                cf_at_issue_start = security_stats.cloudflare_wait_count
                issue_had_429 = False
                issue_had_cloudflare = False
                try:
                    if not wait_for_security_verification_clear(
                        page,
                        for_list_page=False,
                        accumulator=security_stats,
                    ):
                        raise LocgBrowserBlockedError(
                            "security verification did not clear within 60s (before detail)"
                        )
                    if security_stats.cloudflare_wait_count > cf_at_issue_start:
                        issue_had_cloudflare = True
                    audit.cloudflare_wait_count = security_stats.cloudflare_wait_count
                    audit.cloudflare_total_wait_seconds = (
                        security_stats.cloudflare_total_wait_seconds
                    )
                    pre_sleep = 0.0
                    if adaptive_delay is not None:
                        pre_sleep = adaptive_delay.sample_pre_goto_delay()
                    elif delay_seconds > 0:
                        pre_sleep = delay_seconds
                    if pre_sleep > 0:
                        t_pre = time.perf_counter()
                        time.sleep(pre_sleep)
                        issue_timing.pre_goto_sleep_seconds = round(time.perf_counter() - t_pre, 3)
                    detail_response = None
                    detail_html = ""
                    detail_status: int | None = None
                    last_goto_error: Exception | None = None
                    for attempt in range(6):
                        t_goto = time.perf_counter()
                        try:
                            detail_response = page.goto(
                                detail_url,
                                wait_until="domcontentloaded",
                                timeout=NAVIGATION_TIMEOUT_MS,
                            )
                            last_goto_error = None
                        except Exception as goto_exc:  # noqa: BLE001
                            last_goto_error = goto_exc
                            detail_response = None
                            detail_status = None
                            issue_timing.page_goto_seconds = round(
                                time.perf_counter() - t_goto, 3
                            )
                            backoff = min(120.0, 5.0 * (2**attempt))
                            print(
                                f"detail goto failed ({detail_url}); "
                                f"attempt {attempt + 1}/6; sleeping {backoff:.0f}s: {goto_exc}",
                                flush=True,
                            )
                            time.sleep(backoff)
                            continue
                        issue_timing.page_goto_seconds = round(time.perf_counter() - t_goto, 3)
                        detail_status = detail_response.status if detail_response else None
                        if detail_status != 429:
                            break
                        issue_had_429 = True
                        backoff = min(120.0, 15.0 * (2**attempt))
                        print(
                            f"rate limited (429) on {detail_url}; sleeping {backoff:.0f}s before retry",
                            flush=True,
                        )
                        time.sleep(backoff)
                    if last_goto_error is not None:
                        raise last_goto_error
                    if detail_status == 429:
                        raise LocgBrowserBlockedError(
                            f"detail page blocked: HTTP 429 ({detail_url})"
                        )
                    if not wait_for_security_verification_clear(
                        page,
                        for_list_page=False,
                        accumulator=security_stats,
                    ):
                        raise LocgBrowserBlockedError(
                            "security verification did not clear within 60s (after detail goto)"
                        )
                    if security_stats.cloudflare_wait_count > cf_at_issue_start:
                        issue_had_cloudflare = True
                    audit.cloudflare_wait_count = security_stats.cloudflare_wait_count
                    audit.cloudflare_total_wait_seconds = (
                        security_stats.cloudflare_total_wait_seconds
                    )
                    issue_timing.dom_content_loaded_seconds = issue_timing.page_goto_seconds
                    if adaptive_delay is None and delay_seconds > 0:
                        t_post = time.perf_counter()
                        page.wait_for_timeout(int(delay_seconds * 1000))
                        issue_timing.post_load_wait_timeout_seconds = round(
                            time.perf_counter() - t_post, 3
                        )
                    ready, method, ready_seconds = wait_for_detail_readiness(page)
                    issue_timing.ready_detected = ready
                    issue_timing.readiness_method = method
                    issue_timing.selector_wait_seconds = ready_seconds
                    if not ready:
                        issue_timing.readiness_warning = (
                            f"detail readiness not detected for {detail_url}; parsing HTML anyway"
                        )
                        print(f"warning: {issue_timing.readiness_warning}", flush=True)
                    issue_timing.additional_wait_seconds = round(
                        issue_timing.pre_goto_sleep_seconds
                        + issue_timing.post_load_wait_timeout_seconds
                        + issue_timing.selector_wait_seconds,
                        3,
                    )
                    t_html_d = time.perf_counter()
                    detail_html = page.content()
                    issue_timing.html_extraction_seconds = round(time.perf_counter() - t_html_d, 3)
                    detail_blocked = detect_access_blocked(
                        html=detail_html,
                        final_url=page.url,
                        status_code=detail_status,
                    )
                    if detail_blocked:
                        raise LocgBrowserBlockedError(
                            f"detail page blocked: {detail_blocked} ({detail_url})"
                        )
                    issue_id = re.search(r"/comic/(\d+)", detail_url)
                    if save_raw_dir is not None and issue_id:
                        from app.services.external_catalog.locg_capture_io import (
                            safe_write_text,
                            sanitize_path_segment,
                        )

                        t_raw_d = time.perf_counter()
                        fname = f"{sanitize_path_segment(issue_id.group(1))}_detail.html"
                        safe_write_text(
                            save_raw_dir / fname,
                            detail_html,
                            warnings=counters.post_capture_warnings,
                            label=fname,
                        )
                        issue_timing.raw_save_seconds = round(time.perf_counter() - t_raw_d, 3)
                    process_issue(stub, detail_html, issue_timing)
                    issue_timing.finalize()
                    wall = time.perf_counter() - issue_started
                    if issue_timing.total_issue_seconds < wall:
                        issue_timing.total_issue_seconds = round(wall, 3)
                    audit.issue_timings.append(issue_timing)
                    counters.detail_pages_succeeded += 1
                    if adaptive_delay is not None:
                        adaptive_delay.record_issue_outcome(
                            had_429=issue_had_429,
                            had_cloudflare=issue_had_cloudflare,
                            succeeded=True,
                        )
                        adaptive_delay.log_status(
                            cloudflare_wait_count=security_stats.cloudflare_wait_count,
                            force=True,
                        )
                except LocgBrowserBlockedError as blocked_exc:
                    if user_skip_matcher and user_skip_matcher(detail_url, stub.title):
                        from app.services.external_catalog.locg_browser_user_skip import (
                            record_skipped_blocked_detail,
                        )

                        issue_timing.skipped = True
                        record_skipped_blocked_detail(
                            counters,
                            url=detail_url,
                            title=stub.title,
                            reason=f"skipped_blocked_detail: {blocked_exc}",
                        )
                        print(
                            f"skipped_blocked_detail: {detail_url} ({stub.title})",
                            flush=True,
                        )
                        audit.issue_timings.append(issue_timing)
                        continue
                    raise
                except LocgSecurityVerificationTimeout as exc:
                    raise LocgBrowserBlockedError(str(exc)) from exc
                except Exception as exc:  # noqa: BLE001
                    counters.errors_count += 1
                    if len(counters.error_sample) < 20:
                        counters.error_sample.append(f"{detail_url}: {exc}")
                    issue_timing.finalize()
                    audit.issue_timings.append(issue_timing)

            variant_rows = parse_list_variant_rows(list_html, page_date=page_date)
            counters.list_variants_found = len(variant_rows)
            if persist_list_variants is not None and variant_rows:
                persist_result = persist_list_variants(
                    variant_rows,
                    list_html=list_html,
                    page_date=page_date,
                )
                from app.services.external_catalog.sync_service import LocgVariantPersistStats

                if isinstance(persist_result, LocgVariantPersistStats):
                    counters.list_variants_persisted = persist_result.persisted
                    counters.variant_skipped_reason_counts = persist_result.to_dict()
                else:
                    counters.list_variants_persisted = int(persist_result or 0)
            print(
                f"List variant rows: found={counters.list_variants_found} "
                f"persisted={counters.list_variants_persisted}",
                flush=True,
            )

            from app.services.external_catalog.locg_capture_certification import (
                build_live_page_state,
                build_source_universe_report,
                certify_locg_capture,
                print_capture_certification_summary,
                save_capture_certification_artifacts,
            )

            parent_detail_seconds = [
                t.total_issue_seconds
                for t in audit.issue_timings
                if not t.skipped and t.total_issue_seconds > 0
            ]
            cert = certify_locg_capture(
                page_date=page_date,
                final_url=list_url,
                page_title=page.title(),
                html=list_html,
                discovery_audit=discovery_audit,
                list_variants_found=counters.list_variants_found,
                list_variants_persisted=counters.list_variants_persisted,
                detail_pages_succeeded=counters.detail_pages_succeeded,
                detail_pages_attempted=counters.detail_pages_attempted,
                dry_run=dry_run,
                variant_persist_skipped_reason=(
                    "dry_run" if dry_run else None
                ),
                parent_detail_seconds=parent_detail_seconds,
                cloudflare_wait_count=audit.cloudflare_wait_count,
                cloudflare_total_wait_seconds=audit.cloudflare_total_wait_seconds,
                variant_skipped_reason_counts=counters.variant_skipped_reason_counts,
                intentional_parent_skips=counters.intentional_parent_skips,
                resume_parent_skips=counters.resume_parent_skips,
                skipped_blocked_details=counters.skipped_blocked_details,
            )
            live_state = build_live_page_state(
                page_date=page_date,
                final_url=list_url,
                page_title=page.title(),
                html=list_html,
                discovery_audit=discovery_audit,
            )
            universe = build_source_universe_report(list_html)
            save_capture_certification_artifacts(
                report_dir=discovery_report_dir,
                cert=cert,
                live_page_state=live_state,
                source_universe=universe,
                warnings=counters.post_capture_warnings,
            )
            try:
                print_capture_certification_summary(cert)
            except OSError as exc:
                counters.post_capture_warnings.append(f"certification_summary_print: {exc}")
            audit.total_runtime_seconds = round(time.perf_counter() - run_started, 3)
            cert.runtime["total_runtime_seconds"] = audit.total_runtime_seconds
            save_capture_certification_artifacts(
                report_dir=discovery_report_dir,
                cert=cert,
                live_page_state=live_state,
                source_universe=universe,
                warnings=counters.post_capture_warnings,
            )
            parent_loop_complete = (
                counters.list_issues_found > 0
                and counters.detail_pages_succeeded
                + counters.intentional_parent_skips
                + counters.resume_parent_skips
                >= counters.list_issues_found
            )
            if not dry_run and not cert.passed:
                reason = "LoCG capture certification failed: " + "; ".join(cert.failure_reasons)
                if parent_loop_complete:
                    counters.post_capture_warnings.append(reason)
                else:
                    raise RuntimeError(reason)
            if adaptive_delay is not None:
                audit.adaptive_throttle = adaptive_delay.to_dict()
                audit.adaptive_throttle["cloudflare_wait_count"] = (
                    security_stats.cloudflare_wait_count
                )
                adaptive_delay.log_status(
                    cloudflare_wait_count=security_stats.cloudflare_wait_count,
                    force=True,
                )
        finally:
            from app.services.external_catalog.locg_capture_io import safe_browser_teardown

            t_down = time.perf_counter()
            safe_browser_teardown(
                close_fn=context.close,
                warnings=counters.post_capture_warnings,
                label="browser context close",
            )
            safe_browser_teardown(
                close_fn=browser.close,
                warnings=counters.post_capture_warnings,
                label="browser close",
            )
            audit.browser_teardown_seconds = round(time.perf_counter() - t_down, 3)

    audit.total_runtime_seconds = round(time.perf_counter() - run_started, 3)
    return counters, audit


def build_merged_issue_dict(
    stub: LocgListIssueStub,
    detail_html: str,
) -> dict[str, Any]:
    seed = stub_to_detail_seed(stub)
    detail = parse_detail_page_html(detail_html)
    detail["source_url"] = stub.source_url
    return merge_detail_into_seed(seed, detail)
