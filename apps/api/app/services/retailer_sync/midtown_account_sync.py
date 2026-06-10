from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
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


def _has_midtown_challenge(page) -> bool:
    page_text = page.content().lower()
    return "captcha" in page_text or "cloudflare" in page_text or "security challenge" in page_text


def _requires_midtown_login(page) -> bool:
    lower_url = (page.url or "").lower()
    if "/login" in lower_url:
        return True
    return _first_visible(
        page,
        [
            "input[type='email']",
            "input[name='email']",
            "input[name='username']",
            "input[type='password']",
        ],
    ) is not None


def _save_session_state(context, *, account_id: int) -> None:
    SESSION_STATE_ROOT.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(_session_state_path(account_id)))


def _midtown_login(page, *, username: str, password: str) -> None:
    page.goto(MIDTOWN_LOGIN_URL, wait_until="domcontentloaded")
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
        raise MidtownNeedsAttentionError("Midtown login form could not be located.")
    username_input.fill(username)
    password_input.fill(password)
    submit = _first_visible(
        page,
        [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Sign In')",
            "button:has-text('Login')",
        ],
    )
    if submit is None:
        raise MidtownNeedsAttentionError("Midtown login submit action could not be located.")
    submit.click()
    page.wait_for_load_state("networkidle")
    if _has_midtown_challenge(page):
        raise MidtownNeedsAttentionError("Midtown presented a CAPTCHA or security challenge.")
    lower_url = (page.url or "").lower()
    page_text = page.content().lower()
    page.wait_for_timeout(1200)
    if "/login" in lower_url and ("invalid" in page_text or "sign in" in page_text):
        raise MidtownNeedsAttentionError(
            "Midtown login failed. Verify the saved username and password."
        )


def _load_recent_order_details(
    page, *, limit_orders: int, allow_login_redirect: bool = False
) -> list[MidtownOrderDetail]:
    page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
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
        page.wait_for_load_state("networkidle")
        if _has_midtown_challenge(page):
            raise MidtownNeedsAttentionError("Midtown presented a CAPTCHA or security challenge.")
        details.append(
            parse_midtown_order_detail(
                page.content(),
                fallback_order_number=entry.retailer_order_number,
                detail_url=entry.detail_url,
            )
        )
    return details


def _persist_success(
    session: Session,
    *,
    account: RetailerAccount,
    run: RetailerSyncRun,
    orders: list[MidtownOrderDetail],
    test_only: bool,
    sync_path: str,
) -> tuple[list[RetailerOrderSnapshot], list[int]]:
    if test_only:
        run.orders_seen = len(orders)
        run.items_seen = sum(len(order.items) for order in orders)
        run.summary_json = {
            "orders_seen": run.orders_seen,
            "items_seen": run.items_seen,
            "mode": "test",
            "sync_path": sync_path,
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
                parse_midtown_order_detail(
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
                    parse_midtown_order_detail(
                        detail_capture.html,
                        fallback_order_number=fallback_order_number,
                        detail_url=detail_capture.detail_url or None,
                    )
                )
        if not orders:
            raise MidtownNeedsAttentionError(
                "Midtown browser sync captured the Midtown page but no order details were uploaded."
            )
        _, touched_import_ids = _persist_success(
            session,
            account=account,
            run=run,
            orders=orders,
            test_only=False,
            sync_path="browser_assisted",
        )
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

        _, touched_import_ids = _persist_success(
            session,
            account=account,
            run=run,
            orders=orders,
            test_only=test_only,
            sync_path="server_playwright",
        )
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
