from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any
import secrets

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import RetailerAccount, RetailerOrderSnapshot, RetailerSyncRun
from app.services.retailer_credentials import (
    RetailerCredentialError,
    decrypt_retailer_password,
    mask_retailer_username,
)
from app.services.retailer_sync.midtown_parser import (
    MidtownOrderDetail,
    MidtownOrderNumberError,
    parse_midtown_order_detail,
    parse_midtown_order_history,
)
from app.services.retailer_sync.retailer_import_enrichment import enrich_drafts_from_retailer_orders
from app.services.retailer_sync.retailer_order_persistence import upsert_retailer_order_snapshots


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


SESSION_STATE_ROOT = Path(__file__).resolve().parents[5] / "data" / "retailer_sessions"
CHALLENGE_RETRY_DELAY_SECONDS = 15 * 60
LOCAL_SYNC_TOKEN_TTL_MINUTES = 15
MIDTOWN_LOGIN_URL = "https://www.midtowncomics.com/login"
MIDTOWN_ORDERS_URL = "https://www.midtowncomics.com/account-settings"


class MidtownNeedsAttentionError(RuntimeError):
    """Raised when Midtown requires manual intervention or rejects login."""


class MidtownSecurityChallengeError(MidtownNeedsAttentionError):
    """Raised when Midtown presents a CAPTCHA / security challenge.

    Subclass of :class:`MidtownNeedsAttentionError` so existing handlers keep
    treating it as an attention-required state, while newer call sites can
    distinguish a genuine security challenge from a rejected login.
    """


class MidtownLoginRejectedError(MidtownNeedsAttentionError):
    """Raised when Midtown rejects the submitted credentials.

    Subclass of :class:`MidtownNeedsAttentionError` so legacy ``except`` blocks
    still catch it, but the orders/session flows can surface a precise
    "check your username/password" message instead of a security prompt.
    """


class MidtownAuthenticationRequiredError(RuntimeError):
    """Raised when a saved Midtown session is no longer authenticated."""


@dataclass(slots=True)
class MidtownSyncResult:
    account: RetailerAccount
    run: RetailerSyncRun
    orders: list[MidtownOrderDetail]
    touched_import_ids: list[int] = field(default_factory=list)


@dataclass(slots=True)
class MidtownLocalSyncStart:
    account: RetailerAccount
    run: RetailerSyncRun
    helper_token: str
    helper_token_expires_at: datetime
    capture_url: str


@dataclass(slots=True)
class MidtownLocalSyncCapture:
    detail_url: str
    html: str
    retailer_order_number: str | None = None
    fallback_order_number: str | None = None
    capture_diagnostics: dict | None = None


def _sanitize_error(message: str, *, username: str) -> str:
    cleaned = (message or "").strip() or "Unknown Midtown sync failure."
    if username:
        cleaned = cleaned.replace(username, mask_retailer_username(username))
    return cleaned[:1000]


def _create_sync_run(session: Session, *, account: RetailerAccount) -> RetailerSyncRun:
    run = RetailerSyncRun(
        owner_user_id=account.owner_user_id,
        retailer_account_id=account.id,
        retailer=account.retailer,
        status="running",
        started_at=utc_now(),
        summary_json={},
    )
    session.add(run)
    session.flush()
    return run


def _helper_token_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _session_state_path(account_id: int) -> Path:
    return SESSION_STATE_ROOT / f"midtown-account-{account_id}.json"


def _challenge_summary(message: str) -> dict:
    retry_allowed_at = utc_now().timestamp() + CHALLENGE_RETRY_DELAY_SECONDS
    return {
        "error_code": "captcha_or_security",
        "challenge_detected": True,
        "action_required": "Wait before retrying and avoid repeated sync attempts.",
        "suggested_next_step": (
            "Midtown blocked the automated login with a CAPTCHA or security challenge. "
            "Wait for the cooldown, then retry. If a prior Midtown session is cached, "
            "future syncs may reuse it without logging in again."
        ),
        "retry_after_seconds": CHALLENGE_RETRY_DELAY_SECONDS,
        "retry_allowed_at": datetime.fromtimestamp(
            retry_allowed_at, tz=timezone.utc
        ).isoformat(),
        "user_message": message,
    }


def _error_summary(*, error_code: str, message: str) -> dict:
    return {
        "error_code": error_code,
        "user_message": message,
    }


def _success_summary(
    *,
    orders_seen: int,
    orders_imported: int,
    items_seen: int,
    items_imported: int,
    items_updated: int,
    touched_import_ids: list[int],
    capture_quality_report: list[dict],
    parser_quality_report: list[dict],
    sync_path: str,
) -> dict:
    return {
        "sync_path": sync_path,
        "orders_seen": orders_seen,
        "orders_imported": orders_imported,
        "items_seen": items_seen,
        "items_imported": items_imported,
        "items_updated": items_updated,
        "touched_import_ids": touched_import_ids,
        "capture_quality_report": capture_quality_report,
        "parser_quality_report": parser_quality_report,
    }


def _local_sync_start_summary(
    *,
    helper_token: str,
    helper_token_expires_at: datetime,
    limit_orders: int,
) -> dict:
    return {
        "mode": "browser_assisted_pending",
        "sync_path": "browser_assisted",
        "capture_url": MIDTOWN_ORDERS_URL,
        "limit_orders": limit_orders,
        "helper_token_hash": _helper_token_hash(helper_token),
        "helper_token_expires_at": helper_token_expires_at.isoformat(),
        "action_required": (
            "Open Midtown in your browser, finish any login or verification, "
            "then click the Comicos Midtown capture button on the Midtown order detail page."
        ),
        "suggested_next_step": (
            "Open the Midtown order detail page for the order you want imported before using the capture button. "
            "The capture button will capture that single order detail page from your current browser session."
        ),
    }


def _browser_capture_failure_summary(message: str) -> dict:
    return {
        "error_code": "browser_capture_failed",
        "user_message": message,
        "action_required": "Start browser sync again from Connected Retailers.",
        "suggested_next_step": (
            "Open Midtown in your browser, wait until the order detail page is visible, "
            "then click the Comicos Midtown capture button again."
        ),
    }


def _first_visible(page, selectors: list[str]):
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            return locator.first
    return None


# Cloudflare / CAPTCHA interstitial markers. These intentionally target the
# *rendered* challenge page (title + visible body text + visible challenge
# widgets) rather than raw HTML, because Midtown is fronted by Cloudflare and
# every normal page embeds the words "cloudflare"/"captcha" in script/CDN URLs.
_MIDTOWN_CHALLENGE_TITLE_MARKERS = (
    "just a moment",
    "attention required",
    "access denied",
    "verify you are human",
)
_MIDTOWN_CHALLENGE_TEXT_MARKERS = (
    "checking your browser before accessing",
    "please stand by, while we are checking your browser",
    "verify you are human",
    "verifying you are human",
    "complete the security check",
    "needs to review the security of your connection",
    "enable javascript and cookies to continue",
)
_MIDTOWN_CHALLENGE_SELECTORS = (
    "#challenge-form",
    "#challenge-running",
    "#cf-challenge-running",
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[title*='Cloudflare security challenge']",
    "iframe[title*='recaptcha challenge']",
)


def _midtown_page_title(page) -> str:
    try:
        return page.title() or ""
    except Exception:
        return ""


def _midtown_visible_text(page, *, limit: int | None = None) -> str:
    text: object = ""
    try:
        text = page.inner_text("body")
    except Exception:
        try:
            text = page.evaluate("() => (document.body ? document.body.innerText : '')")
        except Exception:
            text = ""
    if not isinstance(text, str):
        text = ""
    return text[:limit] if limit else text


def _locator_is_visible(page, selector: str) -> bool:
    try:
        locator = page.locator(selector)
        if locator.count() <= 0:
            return False
        try:
            return bool(locator.first.is_visible())
        except Exception:
            # If we cannot evaluate visibility, fall back to existence.
            return True
    except Exception:
        return False


def _detect_midtown_challenge(page) -> tuple[bool, str | None]:
    """Detect a real Cloudflare/CAPTCHA interstitial (not incidental references)."""
    title = _midtown_page_title(page).lower()
    for marker in _MIDTOWN_CHALLENGE_TITLE_MARKERS:
        if marker in title:
            return True, f"title:{marker}"
    visible_text = _midtown_visible_text(page).lower()
    for marker in _MIDTOWN_CHALLENGE_TEXT_MARKERS:
        if marker in visible_text:
            return True, f"visible_text:{marker}"
    for selector in _MIDTOWN_CHALLENGE_SELECTORS:
        if _locator_is_visible(page, selector):
            return True, f"visible_selector:{selector}"
    return False, None


def _has_midtown_challenge(page) -> bool:
    detected, _ = _detect_midtown_challenge(page)
    return detected


def _detect_midtown_login(page) -> tuple[bool, str | None]:
    """Detect an actual login page/form (a *visible* password field or login URL)."""
    lower_url = (getattr(page, "url", "") or "").lower()
    if "/login" in lower_url or "/sign-in" in lower_url or "/signin" in lower_url:
        return True, f"url:{lower_url}"
    if _locator_is_visible(page, "input[type='password']"):
        return True, "visible_password_input"
    return False, None


def _requires_midtown_login(page) -> bool:
    detected, _ = _detect_midtown_login(page)
    return detected


def _save_session_state(context, *, account_id: int) -> None:
    SESSION_STATE_ROOT.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(_session_state_path(account_id)))


def _best_effort_wait_for_load(page, *, timeout_ms: int = 15000) -> None:
    try:
        page.wait_for_load_state("load", timeout=timeout_ms)
    except Exception:
        return


# Visible login-button candidates, ordered so the explicit "Log In" CTA wins
# over a bare form submit. We click the visible button rather than submitting
# the form / pressing Enter, which some bot-protected forms ignore.
_MIDTOWN_LOGIN_BUTTON_SELECTORS = (
    "button:has-text('Log In')",
    "button:has-text('Login')",
    "button:has-text('Sign In')",
    "button:has-text('Sign in')",
    "input[type='submit']",
    "button[type='submit']",
    "a:has-text('Log In')",
    "a:has-text('Login')",
)

# Selectors that commonly carry a visible login error / banner.
_MIDTOWN_LOGIN_ERROR_SELECTORS = (
    "[role='alert']",
    ".alert",
    ".alert-danger",
    ".error",
    ".form-error",
    ".help-block",
    ".message--error",
    ".validation-summary-errors",
    ".notification",
    "[class*='error']",
    "[class*='Error']",
)


def _find_visible_login_button(page):
    """Return ``(locator, selector)`` for the first *visible* login button."""
    for selector in _MIDTOWN_LOGIN_BUTTON_SELECTORS:
        try:
            locator = page.locator(selector)
            count = locator.count()
        except Exception:
            continue
        for idx in range(min(count, 5)):
            try:
                node = locator.nth(idx)
                if node.is_visible():
                    return node, selector
            except Exception:
                continue
    return None, None


def _midtown_visible_error_text(page, *, limit: int = 300) -> str:
    """Best-effort read of any visible login error/banner text."""
    for selector in _MIDTOWN_LOGIN_ERROR_SELECTORS:
        try:
            locator = page.locator(selector)
            count = locator.count()
        except Exception:
            continue
        for idx in range(min(count, 5)):
            try:
                node = locator.nth(idx)
                if node.is_visible():
                    text = (node.inner_text() or "").strip()
                    if text:
                        return text[:limit]
            except Exception:
                continue
    return ""


def _collect_login_diagnostics(page, *, stage: str, submit_strategy: str | None = None) -> dict[str, Any]:
    """Capture non-secret, post-submit page state for diagnostics/logging."""
    return {
        "stage": stage,
        "submit_strategy": submit_strategy,
        "post_submit_url": getattr(page, "url", None),
        "post_submit_title": _midtown_page_title(page),
        "login_form_visible": _locator_is_visible(page, "input[type='password']"),
        "error_text": _midtown_visible_error_text(page),
        "visible_text_excerpt": _midtown_visible_text(page, limit=300),
    }


def _login_rejected(message: str, diagnostics: dict[str, Any]) -> MidtownLoginRejectedError:
    exc = MidtownLoginRejectedError(message)
    exc.diagnostics = diagnostics  # type: ignore[attr-defined]
    return exc


def _login_challenge(message: str, diagnostics: dict[str, Any]) -> MidtownSecurityChallengeError:
    exc = MidtownSecurityChallengeError(message)
    exc.diagnostics = diagnostics  # type: ignore[attr-defined]
    return exc


def _midtown_login(page, *, username: str, password: str) -> dict[str, Any]:
    """Submit the Midtown login form using stored credentials.

    Login is performed by explicitly filling the email + password fields and
    then clicking the *visible* login button (not a form submit / Enter), which
    some bot-protected forms ignore.

    Returns a diagnostics dict on success (no secrets). Raises
    :class:`MidtownSecurityChallengeError` when a CAPTCHA/security challenge
    blocks the login, and :class:`MidtownLoginRejectedError` when the
    credentials are rejected or the login form cannot be driven. Both
    exceptions carry a ``.diagnostics`` dict describing the post-submit state.
    """
    page.goto(MIDTOWN_LOGIN_URL, wait_until="domcontentloaded")
    _best_effort_wait_for_load(page)
    username_input = _first_visible(
        page,
        [
            "input[type='email']",
            "input[name='email']",
            "input[name='username']",
            "input[id*='email']",
        ],
    )
    password_input = _first_visible(
        page,
        [
            "input[type='password']",
            "input[name='password']",
            "input[id*='password']",
        ],
    )
    if username_input is None or password_input is None:
        raise _login_rejected(
            "Midtown login form could not be located. Try the live browser fallback.",
            _collect_login_diagnostics(page, stage="form_not_found"),
        )

    # 1) fill email, 2) fill password
    username_input.fill(username)
    password_input.fill(password)

    # 3) click the visible LOGIN button (not form submit / Enter)
    submit, submit_strategy = _find_visible_login_button(page)
    if submit is None:
        raise _login_rejected(
            "Midtown login button could not be located. Try the live browser fallback.",
            _collect_login_diagnostics(page, stage="login_button_not_found"),
        )
    submit.click()
    _best_effort_wait_for_load(page)
    # Give the page time to navigate / render any error banner before judging.
    try:
        page.wait_for_timeout(1500)
    except Exception:  # noqa: BLE001 - timing helper only
        pass

    diagnostics = _collect_login_diagnostics(page, stage="post_submit", submit_strategy=submit_strategy)

    # A challenge taking over after submit is a security state, not a rejection.
    if _has_midtown_challenge(page):
        raise _login_challenge(
            "Midtown presented a CAPTCHA or security challenge.", diagnostics
        )

    # If the login form is still present (URL still on /login or a password
    # field is still visible), the credentials were rejected.
    if _requires_midtown_login(page):
        raise _login_rejected(
            "Midtown rejected the sign-in. Check the saved username and password.",
            diagnostics,
        )

    return {
        "post_login_url": getattr(page, "url", None),
        "post_login_title": _midtown_page_title(page),
        **diagnostics,
    }


def _load_recent_order_details(
    page, *, limit_orders: int, allow_login_redirect: bool = False
) -> list[MidtownOrderDetail]:
    page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
    _best_effort_wait_for_load(page)
    if _has_midtown_challenge(page):
        raise MidtownNeedsAttentionError("Midtown presented a CAPTCHA or security challenge.")
    if _requires_midtown_login(page):
        if allow_login_redirect:
            raise MidtownAuthenticationRequiredError("Midtown session requires login.")
        raise MidtownNeedsAttentionError("Midtown account login is still required.")
    history_html = page.content()
    history = parse_midtown_order_history(history_html)[:limit_orders]
    if not history:
        raise MidtownNeedsAttentionError("No Midtown orders were visible after login.")
    details: list[MidtownOrderDetail] = []
    for entry in history:
        if not entry.detail_url:
            continue
        page.goto(entry.detail_url, wait_until="domcontentloaded")
        _best_effort_wait_for_load(page)
        if _has_midtown_challenge(page):
            raise MidtownNeedsAttentionError("Midtown presented a CAPTCHA or security challenge.")
        details.append(
            _parse_midtown_detail_or_raise(
                page.content(),
                fallback_order_number=entry.retailer_order_number,
                detail_url=entry.detail_url,
            )
        )
    return details


def _parse_midtown_detail_or_raise(
    html_text: str,
    *,
    fallback_order_number: str | None = None,
    detail_url: str | None = None,
) -> MidtownOrderDetail:
    try:
        return parse_midtown_order_detail(
            html_text,
            fallback_order_number=fallback_order_number,
            detail_url=detail_url,
        )
    except MidtownOrderNumberError as exc:
        raise MidtownNeedsAttentionError(str(exc)) from exc


def _build_parser_quality_report(order: MidtownOrderDetail) -> dict:
    order_fields = {
        "retailer_order_number": order.retailer_order_number,
        "order_date": order.order_date,
        "order_status": order.order_status,
        "order_total": order.order_total,
        "detail_url": order.detail_url,
    }
    order_fields_extracted = [name for name, value in order_fields.items() if value not in (None, "", [])]
    order_fields_missing = [name for name, value in order_fields.items() if value in (None, "", [])]
    item_fields_extracted = 0
    item_fields_total = 0
    item_fields_missing: set[str] = set()
    for item in order.items:
        diagnostics = item.parse_diagnostics or {}
        item_fields_extracted += int(diagnostics.get("fields_extracted_count") or 0)
        item_fields_total += int(diagnostics.get("fields_total") or 0)
        item_fields_missing.update(str(field) for field in diagnostics.get("fields_missing") or [])
    return {
        "retailer_order_number": order.retailer_order_number,
        "order_fields_extracted_count": len(order_fields_extracted),
        "order_fields_total": len(order_fields),
        "order_fields_missing": order_fields_missing,
        "item_blocks_found": int((order.parse_diagnostics or {}).get("item_blocks_found") or 0),
        "items_parsed": int((order.parse_diagnostics or {}).get("items_parsed") or 0),
        "items_skipped": int((order.parse_diagnostics or {}).get("items_skipped") or 0),
        "skipped_reasons": dict((order.parse_diagnostics or {}).get("skipped_reasons") or {}),
        "item_fields_extracted_count": item_fields_extracted,
        "item_fields_total": item_fields_total,
        "item_fields_missing": sorted(item_fields_missing),
    }


def _build_capture_quality_report(
    capture: MidtownLocalSyncCapture | None,
    order: MidtownOrderDetail,
) -> dict:
    diagnostics = dict(capture.capture_diagnostics or {}) if capture is not None else {}
    return {
        "retailer_order_number": order.retailer_order_number,
        "detail_url": order.detail_url or (capture.detail_url if capture is not None else None),
        "current_url": diagnostics.get("current_url"),
        "ready_state": diagnostics.get("ready_state"),
        "items_detected_client_side": int(diagnostics.get("items_detected_client_side") or 0),
        "html_length": int(diagnostics.get("html_length") or 0),
        "text_length": int(diagnostics.get("text_length") or 0),
        "body_inner_html_length": int(diagnostics.get("body_inner_html_length") or 0),
        "body_inner_text_length": int(diagnostics.get("body_inner_text_length") or 0),
        "image_count": int(diagnostics.get("image_count") or 0),
        "product_link_count": int(diagnostics.get("product_link_count") or 0),
        "visible_order_item_block_count": int(diagnostics.get("visible_order_item_block_count") or 0),
        "each_match_count": int(diagnostics.get("each_match_count") or 0),
        "qty_match_count": int(diagnostics.get("qty_match_count") or 0),
        "status_match_count": int(diagnostics.get("status_match_count") or 0),
        "scroll_height": int(diagnostics.get("scroll_height") or 0),
        "scroll_position": int(diagnostics.get("scroll_position") or 0),
        "parser_item_blocks_found": int((order.parse_diagnostics or {}).get("item_blocks_found") or 0),
        "parser_items_parsed": int((order.parse_diagnostics or {}).get("items_parsed") or 0),
        "parser_items_skipped": int((order.parse_diagnostics or {}).get("items_skipped") or 0),
    }


def _persist_success(
    session: Session,
    *,
    account: RetailerAccount,
    run: RetailerSyncRun,
    orders: list[MidtownOrderDetail],
    captures: list[MidtownLocalSyncCapture] | None,
    test_only: bool,
    sync_path: str,
) -> tuple[list[RetailerOrderSnapshot], list[int]]:
    parser_quality_report = [_build_parser_quality_report(order) for order in orders]
    capture_lookup_by_url = {
        capture.detail_url: capture
        for capture in (captures or [])
        if capture.detail_url and capture.html
    }
    capture_lookup_by_order_number = {
        capture.retailer_order_number: capture
        for capture in (captures or [])
        if capture.retailer_order_number and capture.html
    }
    capture_lookup_by_fallback_order_number = {
        capture.fallback_order_number: capture
        for capture in (captures or [])
        if capture.fallback_order_number and capture.html
    }
    capture_quality_report = []
    for order in orders:
        capture = capture_lookup_by_url.get(order.detail_url or "")
        if capture is None:
            capture = capture_lookup_by_order_number.get(order.retailer_order_number)
        if capture is None:
            capture = capture_lookup_by_fallback_order_number.get(order.retailer_order_number)
        capture_quality_report.append(_build_capture_quality_report(capture, order))
    if test_only:
        run.orders_seen = len(orders)
        run.items_seen = sum(len(order.items) for order in orders)
        run.summary_json = {
            "orders_seen": run.orders_seen,
            "items_seen": run.items_seen,
            "mode": "test",
            "sync_path": sync_path,
            "capture_quality_report": capture_quality_report,
            "parser_quality_report": parser_quality_report,
        }
        session.add(run)
        session.flush()
        return [], []
    summary = upsert_retailer_order_snapshots(session, account=account, sync_run=run, orders=orders)
    order_numbers = [order.retailer_order_number for order in orders]
    snapshots = session.exec(
        select(RetailerOrderSnapshot)
        .where(
            RetailerOrderSnapshot.retailer_account_id == account.id,
            RetailerOrderSnapshot.retailer_order_number.in_(order_numbers),
        )
        .order_by(RetailerOrderSnapshot.order_date.desc(), RetailerOrderSnapshot.id.desc())
    ).all()
    touched_import_ids = enrich_drafts_from_retailer_orders(
        session, account=account, order_snapshots=snapshots
    )
    run.orders_seen = summary.orders_seen
    run.orders_imported = summary.orders_imported
    run.items_seen = summary.items_seen
    run.items_imported = summary.items_imported
    run.items_updated = summary.items_updated
    run.summary_json = _success_summary(
        orders_seen=run.orders_seen,
        orders_imported=run.orders_imported,
        items_seen=run.items_seen,
        items_imported=run.items_imported,
        items_updated=run.items_updated,
        touched_import_ids=touched_import_ids,
        capture_quality_report=capture_quality_report,
        parser_quality_report=parser_quality_report,
        sync_path=sync_path,
    )
    session.add(run)
    session.flush()
    return snapshots, touched_import_ids


def _parse_local_sync_expiration(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _get_local_sync_context(
    run: RetailerSyncRun, *, helper_token: str
) -> tuple[dict, datetime]:
    summary = dict(run.summary_json or {})
    token_hash = str(summary.get("helper_token_hash") or "").strip()
    expires_at = _parse_local_sync_expiration(str(summary.get("helper_token_expires_at") or "").strip())
    if not token_hash or expires_at is None:
        raise MidtownNeedsAttentionError("Midtown browser sync is missing helper metadata. Start it again.")
    if _helper_token_hash(helper_token) != token_hash:
        raise MidtownNeedsAttentionError("Midtown browser sync token was invalid. Start it again.")
    if expires_at <= utc_now():
        raise MidtownNeedsAttentionError("Midtown browser sync expired. Start it again from Connected Retailers.")
    return summary, expires_at


def start_midtown_browser_sync(
    session: Session,
    *,
    account: RetailerAccount,
    limit_orders: int,
) -> MidtownLocalSyncStart:
    if account.id is None:
        raise RuntimeError("Retailer account must be saved before syncing.")
    helper_token = secrets.token_urlsafe(24)
    helper_token_expires_at = utc_now() + timedelta(minutes=LOCAL_SYNC_TOKEN_TTL_MINUTES)
    run = _create_sync_run(session, account=account)
    run.status = "awaiting_browser"
    run.summary_json = _local_sync_start_summary(
        helper_token=helper_token,
        helper_token_expires_at=helper_token_expires_at,
        limit_orders=limit_orders,
    )
    account.status = "awaiting_browser"
    account.last_error = None
    account.updated_at = utc_now()
    session.add(account)
    session.add(run)
    session.commit()
    session.refresh(account)
    session.refresh(run)
    return MidtownLocalSyncStart(
        account=account,
        run=run,
        helper_token=helper_token,
        helper_token_expires_at=helper_token_expires_at,
        capture_url=MIDTOWN_ORDERS_URL,
    )


def complete_midtown_browser_sync(
    session: Session,
    *,
    account: RetailerAccount,
    sync_run_id: int,
    helper_token: str,
    history_html: str,
    detail_pages: list[MidtownLocalSyncCapture],
) -> MidtownSyncResult:
    if account.id is None:
        raise RuntimeError("Retailer account must be saved before syncing.")
    run = session.get(RetailerSyncRun, sync_run_id)
    if run is None or run.retailer_account_id != account.id:
        raise MidtownNeedsAttentionError("Midtown browser sync run was not found. Start it again.")
    try:
        summary, _ = _get_local_sync_context(run, helper_token=helper_token)
        limit_orders = int(summary.get("limit_orders") or 25)
        run.status = "capturing"
        session.add(run)
        session.flush()
        history = parse_midtown_order_history(history_html)[:limit_orders] if history_html else []
        detail_by_url = {
            page.detail_url: page
            for page in detail_pages
            if page.detail_url and page.html
        }
        detail_by_order_number_exact = {
            page.retailer_order_number: page
            for page in detail_pages
            if page.retailer_order_number and page.html
        }
        detail_by_order_number = {
            page.fallback_order_number: page
            for page in detail_pages
            if page.fallback_order_number and page.html
        }
        orders: list[MidtownOrderDetail] = []
        for entry in history:
            detail_capture = detail_by_url.get(entry.detail_url or "")
            if detail_capture is None:
                detail_capture = detail_by_order_number_exact.get(entry.retailer_order_number)
            if detail_capture is None:
                detail_capture = detail_by_order_number.get(entry.retailer_order_number)
            if detail_capture is None:
                continue
            orders.append(
                _parse_midtown_detail_or_raise(
                    detail_capture.html,
                    fallback_order_number=entry.retailer_order_number,
                    detail_url=detail_capture.detail_url or entry.detail_url,
                )
            )
        if not orders and detail_pages:
            for detail_capture in detail_pages:
                if not detail_capture.html:
                    continue
                fallback_order_number = (
                    detail_capture.retailer_order_number
                    or detail_capture.fallback_order_number
                    or None
                )
                orders.append(
                    _parse_midtown_detail_or_raise(
                        detail_capture.html,
                        fallback_order_number=fallback_order_number,
                        detail_url=detail_capture.detail_url or None,
                    )
                )
        if not orders:
            raise MidtownNeedsAttentionError(
                "Midtown browser sync captured the Midtown page but no order details were uploaded."
            )
        try:
            _, touched_import_ids = _persist_success(
                session,
                account=account,
                run=run,
                orders=orders,
                captures=detail_pages,
                test_only=False,
                sync_path="browser_assisted",
            )
        except MidtownOrderNumberError as exc:
            raise MidtownNeedsAttentionError(str(exc)) from exc
        run.status = "succeeded"
        run.finished_at = utc_now()
        account.status = "connected"
        account.last_sync_at = run.finished_at
        account.last_success_at = run.finished_at
        account.last_error = None
        account.updated_at = utc_now()
        session.add(account)
        session.add(run)
        session.commit()
        session.refresh(account)
        session.refresh(run)
        return MidtownSyncResult(
            account=account,
            run=run,
            orders=orders,
            touched_import_ids=touched_import_ids,
        )
    except MidtownNeedsAttentionError as exc:
        session.rollback()
        run.status = "needs_attention"
        run.finished_at = utc_now()
        run.error_message = _sanitize_error(str(exc), username=account.username)
        run.errors_count = 1
        run.summary_json = _browser_capture_failure_summary(run.error_message)
        account.status = "needs_attention"
        account.last_sync_at = run.finished_at
        account.last_error = run.error_message
        account.updated_at = utc_now()
        session.add(account)
        session.add(run)
        session.commit()
        session.refresh(account)
        session.refresh(run)
        return MidtownSyncResult(account=account, run=run, orders=[])
    except Exception as exc:
        session.rollback()
        run.status = "failed"
        run.finished_at = utc_now()
        run.error_message = _sanitize_error(str(exc), username=account.username)
        run.errors_count = 1
        run.summary_json = _error_summary(error_code="browser_sync_failed", message=run.error_message)
        account.status = "error"
        account.last_sync_at = run.finished_at
        account.last_error = run.error_message
        account.updated_at = utc_now()
        session.add(account)
        session.add(run)
        session.commit()
        session.refresh(account)
        session.refresh(run)
        return MidtownSyncResult(account=account, run=run, orders=[])


def sync_midtown_account(
    session: Session,
    *,
    account: RetailerAccount,
    limit_orders: int | None = None,
    test_only: bool = False,
) -> MidtownSyncResult:
    settings = get_settings()
    if not settings.midtown_sync_enabled:
        raise RuntimeError("MIDTOWN_SYNC_ENABLED is disabled.")
    if account.id is None:
        raise RuntimeError("Retailer account must be saved before syncing.")
    run = _create_sync_run(session, account=account)
    password = decrypt_retailer_password(account.encrypted_password)
    limit = limit_orders or settings.retailer_sync_default_limit_orders
    try:
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "playwright is required for Midtown sync; "
                "install it and run `playwright install chromium`."
            ) from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context_kwargs = {
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                "viewport": {"width": 1440, "height": 1100},
                "locale": "en-US",
                "timezone_id": "America/Chicago",
            }
            state_path = _session_state_path(int(account.id))
            if state_path.exists():
                context_kwargs["storage_state"] = str(state_path)
            context = browser.new_context(**context_kwargs)
            page = context.new_page()
            try:
                try:
                    orders = _load_recent_order_details(
                        page,
                        limit_orders=limit,
                        allow_login_redirect=True,
                    )
                except MidtownAuthenticationRequiredError:
                    page.wait_for_timeout(900)
                    _midtown_login(page, username=account.username, password=password)
                    _save_session_state(context, account_id=int(account.id))
                    page.wait_for_timeout(1200)
                    orders = _load_recent_order_details(page, limit_orders=limit)
                else:
                    _save_session_state(context, account_id=int(account.id))
            except PlaywrightTimeoutError as exc:
                raise MidtownNeedsAttentionError(
                    "Midtown sync timed out while loading account pages."
                ) from exc
            finally:
                context.close()
                browser.close()

        try:
            _, touched_import_ids = _persist_success(
                session,
                account=account,
                run=run,
                orders=orders,
                captures=None,
                test_only=test_only,
                sync_path="server_playwright",
            )
        except MidtownOrderNumberError as exc:
            raise MidtownNeedsAttentionError(str(exc)) from exc
        run.status = "succeeded"
        run.finished_at = utc_now()
        account.status = "connected"
        account.last_sync_at = run.finished_at
        account.last_success_at = run.finished_at
        account.last_error = None
        account.updated_at = utc_now()
        session.add(account)
        session.add(run)
        session.commit()
        session.refresh(account)
        session.refresh(run)
        return MidtownSyncResult(
            account=account,
            run=run,
            orders=orders,
            touched_import_ids=touched_import_ids,
        )
    except (MidtownNeedsAttentionError, RetailerCredentialError) as exc:
        run.status = "needs_attention"
        run.finished_at = utc_now()
        run.error_message = _sanitize_error(str(exc), username=account.username)
        run.errors_count = 1
        run.summary_json = (
            _challenge_summary(run.error_message)
            if "captcha" in str(exc).lower() or "challenge" in str(exc).lower()
            else _error_summary(error_code="needs_attention", message=run.error_message)
        )
        account.status = "needs_attention"
        account.last_sync_at = run.finished_at
        account.last_error = run.error_message
        account.updated_at = utc_now()
        session.add(account)
        session.add(run)
        session.commit()
        session.refresh(account)
        session.refresh(run)
        return MidtownSyncResult(account=account, run=run, orders=[])
    except Exception as exc:
        run.status = "failed"
        run.finished_at = utc_now()
        run.error_message = _sanitize_error(str(exc), username=account.username)
        run.errors_count = 1
        run.summary_json = _error_summary(error_code="sync_failed", message=run.error_message)
        account.status = "error"
        account.last_sync_at = run.finished_at
        account.last_error = run.error_message
        account.updated_at = utc_now()
        session.add(account)
        session.add(run)
        session.commit()
        session.refresh(account)
        session.refresh(run)
        return MidtownSyncResult(account=account, run=run, orders=[])
