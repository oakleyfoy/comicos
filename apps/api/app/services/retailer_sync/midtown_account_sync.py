from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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


class MidtownNeedsAttentionError(RuntimeError):
    """Raised when Midtown requires manual intervention or rejects login."""


@dataclass(slots=True)
class MidtownSyncResult:
    account: RetailerAccount
    run: RetailerSyncRun
    orders: list[MidtownOrderDetail]


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


def _first_visible(page, selectors: list[str]):
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() > 0:
            return locator.first
    return None


def _midtown_login(page, *, username: str, password: str) -> None:
    page.goto("https://www.midtowncomics.com/login", wait_until="domcontentloaded")
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
    lower_url = (page.url or "").lower()
    page_text = page.content().lower()
    if "captcha" in page_text or "cloudflare" in page_text:
        raise MidtownNeedsAttentionError("Midtown presented a CAPTCHA or security challenge.")
    if "/login" in lower_url and ("invalid" in page_text or "sign in" in page_text):
        raise MidtownNeedsAttentionError(
            "Midtown login failed. Verify the saved username and password."
        )


def _load_recent_order_details(page, *, limit_orders: int) -> list[MidtownOrderDetail]:
    page.goto("https://www.midtowncomics.com/account/orders", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
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
) -> list[RetailerOrderSnapshot]:
    if test_only:
        run.orders_seen = len(orders)
        run.items_seen = sum(len(order.items) for order in orders)
        run.summary_json = {
            "orders_seen": run.orders_seen,
            "items_seen": run.items_seen,
            "mode": "test",
        }
        session.add(run)
        session.flush()
        return []
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
    enrich_drafts_from_retailer_orders(session, account=account, order_snapshots=snapshots)
    run.orders_seen = summary.orders_seen
    run.orders_imported = summary.orders_imported
    run.items_seen = summary.items_seen
    run.items_imported = summary.items_imported
    run.items_updated = summary.items_updated
    session.add(run)
    session.flush()
    return snapshots


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
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 1100},
            )
            page = context.new_page()
            try:
                _midtown_login(page, username=account.username, password=password)
                orders = _load_recent_order_details(page, limit_orders=limit)
            except PlaywrightTimeoutError as exc:
                raise MidtownNeedsAttentionError(
                    "Midtown sync timed out while loading account pages."
                ) from exc
            finally:
                context.close()
                browser.close()

        _persist_success(
            session,
            account=account,
            run=run,
            orders=orders,
            test_only=test_only,
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
        return MidtownSyncResult(account=account, run=run, orders=orders)
    except (MidtownNeedsAttentionError, RetailerCredentialError) as exc:
        run.status = "needs_attention"
        run.finished_at = utc_now()
        run.error_message = _sanitize_error(str(exc), username=account.username)
        run.errors_count = 1
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
