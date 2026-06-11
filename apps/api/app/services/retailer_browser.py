from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models import RetailerAccount, RetailerOrderSnapshot, RetailerSyncRun
from app.services.retailer_credentials import decrypt_retailer_password
from app.services.retailer_sync.midtown_account_sync import (
    MIDTOWN_LOGIN_URL,
    MIDTOWN_ORDERS_URL,
    SESSION_STATE_ROOT,
    _has_midtown_challenge,
    _load_recent_order_details,
    _midtown_login,
    _parse_midtown_detail_or_raise,
    _requires_midtown_login,
    _save_session_state,
)
from app.services.retailer_sync.midtown_parser import (
    MidtownOrderDetail,
    MidtownOrderHistoryEntry,
    parse_midtown_order_history,
)
from app.services.retailer_sync.retailer_order_persistence import upsert_retailer_order_snapshots


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _browser_state_path(account_id: int) -> Path:
    return SESSION_STATE_ROOT / f"midtown-account-{account_id}.browser.json"


def _midtown_account_for_user_or_404(session: Session, *, owner_user_id: int) -> RetailerAccount:
    account = session.exec(
        select(RetailerAccount).where(
            RetailerAccount.owner_user_id == owner_user_id,
            RetailerAccount.retailer == "midtown",
        )
    ).first()
    if account is None:
        raise ValueError("Midtown retailer account not found.")
    return account


def _read_browser_state(account_id: int) -> dict[str, Any]:
    state_path = _browser_state_path(account_id)
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_browser_state(account_id: int, payload: dict[str, Any]) -> None:
    state_path = _browser_state_path(account_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _history_item_count(fragment: str) -> int | None:
    import re

    match = re.search(r"\b(\d+)\s+items?\b", fragment, flags=re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))


@dataclass(slots=True)
class MidtownBrowserStatus:
    retailer: str
    account_id: int
    status: str
    message: str | None
    current_url: str | None
    orders_url: str
    authenticated: bool
    order_count: int
    last_updated_at: datetime | None


@dataclass(slots=True)
class MidtownBrowserOrders:
    status: MidtownBrowserStatus
    orders: list[dict[str, Any]]


def _session_context_kwargs(account_id: int) -> dict[str, Any]:
    context_kwargs = {
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1440, "height": 1100},
        "locale": "en-US",
        "timezone_id": "America/Chicago",
    }
    state_path = Path(SESSION_STATE_ROOT) / f"midtown-account-{account_id}.json"
    if state_path.exists():
        context_kwargs["storage_state"] = str(state_path)
    return context_kwargs


def _ensure_midtown_session(account: RetailerAccount) -> tuple[str, list[MidtownOrderHistoryEntry]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "playwright is required for Midtown browser sessions; install it and run `playwright install chromium`."
        ) from exc

    if account.id is None:
        raise RuntimeError("Retailer account must be saved before starting a Midtown session.")

    password = decrypt_retailer_password(account.encrypted_password)
    state_path = Path(SESSION_STATE_ROOT) / f"midtown-account-{int(account.id)}.json"
    status = "ready"
    orders: list[MidtownOrderHistoryEntry] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(**_session_context_kwargs(int(account.id)))
        page = context.new_page()
        try:
            page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            if _requires_midtown_login(page):
                _midtown_login(page, username=account.username, password=password)
                _save_session_state(context, account_id=int(account.id))
                page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle")
            if _has_midtown_challenge(page):
                status = "needs_attention"
            else:
                orders = parse_midtown_order_history(page.content())
                status = "ready" if orders else "empty"
                _write_browser_state(
                    int(account.id),
                    {
                        "status": status,
                        "current_url": page.url,
                        "orders_url": MIDTOWN_ORDERS_URL,
                        "order_count": len(orders),
                        "authenticated": True,
                        "last_updated_at": utc_now().isoformat(),
                    },
                )
        finally:
            context.close()
            browser.close()

    if not state_path.exists():
        _write_browser_state(
            int(account.id),
            {
                "status": status,
                "current_url": MIDTOWN_LOGIN_URL,
                "orders_url": MIDTOWN_ORDERS_URL,
                "order_count": len(orders),
                "authenticated": False,
                "last_updated_at": utc_now().isoformat(),
            },
        )
    return status, orders


def start_midtown_browser_session(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    status, orders = _ensure_midtown_session(account)
    state = _read_browser_state(int(account.id or 0))
    return MidtownBrowserStatus(
        retailer="midtown",
        account_id=int(account.id or 0),
        status=status,
        message=state.get("message"),
        current_url=state.get("current_url") or MIDTOWN_ORDERS_URL,
        orders_url=state.get("orders_url") or MIDTOWN_ORDERS_URL,
        authenticated=bool(state.get("authenticated", True)),
        order_count=len(orders) if orders else int(state.get("order_count") or 0),
        last_updated_at=datetime.fromisoformat(state["last_updated_at"]) if state.get("last_updated_at") else None,
    )


def get_midtown_browser_session_status(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    state = _read_browser_state(int(account.id or 0))
    last_updated_at = None
    if state.get("last_updated_at"):
        try:
            last_updated_at = datetime.fromisoformat(str(state["last_updated_at"]))
        except ValueError:
            last_updated_at = None
    return MidtownBrowserStatus(
        retailer="midtown",
        account_id=int(account.id or 0),
        status=str(state.get("status") or "idle"),
        message=state.get("message"),
        current_url=state.get("current_url"),
        orders_url=str(state.get("orders_url") or MIDTOWN_ORDERS_URL),
        authenticated=bool(state.get("authenticated", False)),
        order_count=int(state.get("order_count") or 0),
        last_updated_at=last_updated_at,
    )


def list_midtown_browser_orders(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserOrders:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    status, orders = _ensure_midtown_session(account)
    normalized_orders = [
        {
            "retailer_order_number": order.retailer_order_number,
            "order_date": order.order_date,
            "order_status": order.order_status,
            "order_total": order.order_total,
            "item_count": _history_item_count(order.raw_fragment),
            "detail_url": order.detail_url,
        }
        for order in orders
    ]
    state = _read_browser_state(int(account.id or 0))
    state.update(
        {
            "status": status,
            "current_url": MIDTOWN_ORDERS_URL,
            "orders_url": MIDTOWN_ORDERS_URL,
            "order_count": len(normalized_orders),
            "authenticated": True,
            "last_updated_at": utc_now().isoformat(),
        }
    )
    _write_browser_state(int(account.id or 0), state)
    return MidtownBrowserOrders(
        status=MidtownBrowserStatus(
            retailer="midtown",
            account_id=int(account.id or 0),
            status=status,
            message=state.get("message"),
            current_url=MIDTOWN_ORDERS_URL,
            orders_url=MIDTOWN_ORDERS_URL,
            authenticated=True,
            order_count=len(normalized_orders),
            last_updated_at=utc_now(),
        ),
        orders=normalized_orders,
    )


def capture_midtown_browser_order(
    session: Session,
    *,
    owner_user_id: int,
    retailer_order_number: str,
) -> tuple[MidtownBrowserStatus, MidtownOrderDetail, int]:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    status, orders = _ensure_midtown_session(account)
    order_map = {order.retailer_order_number: order for order in orders}
    history_entry = order_map.get(retailer_order_number)
    if history_entry is None:
        raise ValueError(f"Midtown order {retailer_order_number} was not found.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            "playwright is required for Midtown browser sessions; install it and run `playwright install chromium`."
        ) from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(**_session_context_kwargs(int(account.id or 0)))
        page = context.new_page()
        try:
            page.goto(history_entry.detail_url or MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            if _requires_midtown_login(page):
                _midtown_login(page, username=account.username, password=decrypt_retailer_password(account.encrypted_password))
                _save_session_state(context, account_id=int(account.id or 0))
                page.goto(history_entry.detail_url or MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle")
            if _has_midtown_challenge(page):
                raise RuntimeError("Midtown presented a CAPTCHA or security challenge.")
            detail = _parse_midtown_detail_or_raise(
                page.content(),
                fallback_order_number=history_entry.retailer_order_number,
                detail_url=history_entry.detail_url,
            )
        finally:
            context.close()
            browser.close()

    run = RetailerSyncRun(
        owner_user_id=account.owner_user_id,
        retailer_account_id=int(account.id or 0),
        retailer="midtown",
        status="browser_capture",
        started_at=utc_now(),
        summary_json={
            "sync_path": "browser_session",
            "mode": "browser_capture",
            "retailer_order_number": retailer_order_number,
            "current_url": history_entry.detail_url,
        },
    )
    session.add(run)
    session.flush()
    _summary = upsert_retailer_order_snapshots(
        session,
        account=account,
        sync_run=run,
        orders=[detail],
    )
    session.commit()
    snapshot = session.exec(
        select(RetailerOrderSnapshot).where(
            RetailerOrderSnapshot.owner_user_id == account.owner_user_id,
            RetailerOrderSnapshot.retailer == "midtown",
            RetailerOrderSnapshot.retailer_order_number == detail.retailer_order_number,
        )
    ).first()
    if snapshot is None or snapshot.id is None:
        raise RuntimeError("Retailer order snapshot was not created.")
    state = _read_browser_state(int(account.id or 0))
    state.update(
        {
            "status": "captured",
            "current_url": history_entry.detail_url,
            "orders_url": MIDTOWN_ORDERS_URL,
            "order_count": len(orders),
            "authenticated": True,
            "last_updated_at": utc_now().isoformat(),
            "last_captured_order_number": detail.retailer_order_number,
        }
    )
    _write_browser_state(int(account.id or 0), state)
    return (
        MidtownBrowserStatus(
            retailer="midtown",
            account_id=int(account.id or 0),
            status="captured",
            message="Midtown order captured inside ComicOS.",
            current_url=history_entry.detail_url,
            orders_url=MIDTOWN_ORDERS_URL,
            authenticated=True,
            order_count=len(orders),
            last_updated_at=utc_now(),
        ),
        detail,
        int(snapshot.id),
    )
