from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from importlib.metadata import PackageNotFoundError, version as package_version
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
    MidtownNeedsAttentionError,
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

LOGGER = logging.getLogger(__name__)


class RetailerBrowserConfigurationError(RuntimeError):
    pass


class RetailerBrowserEnvironmentError(RuntimeError):
    pass


class RetailerBrowserStateError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    LOGGER.info("midtown_browser_session %s", json.dumps(payload, default=str, sort_keys=True))


def _playwright_version() -> str | None:
    try:
        return package_version("playwright")
    except PackageNotFoundError:
        return None


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
        raise RetailerBrowserConfigurationError("Retailer browser session is not configured.")
    return account


def _ensure_session_state_root() -> None:
    try:
        SESSION_STATE_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _log_event("session_state_root_create_failed", root=str(SESSION_STATE_ROOT), error=str(exc))
        raise RetailerBrowserStateError("Could not create retailer session directory.") from exc


def _read_browser_state(account_id: int) -> dict[str, Any]:
    state_path = _browser_state_path(account_id)
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except OSError as exc:
        _log_event("browser_state_load_failed", account_id=account_id, path=str(state_path), error=str(exc))
        raise RetailerBrowserStateError("Failed loading saved browser state.") from exc
    except json.JSONDecodeError as exc:
        _log_event("browser_state_decode_failed", account_id=account_id, path=str(state_path), error=str(exc))
        raise RetailerBrowserStateError("Failed loading saved browser state.") from exc


def _write_browser_state(account_id: int, payload: dict[str, Any]) -> None:
    state_path = _browser_state_path(account_id)
    _ensure_session_state_root()
    try:
        state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    except OSError as exc:
        _log_event("browser_state_write_failed", account_id=account_id, path=str(state_path), error=str(exc))
        raise RetailerBrowserStateError("Could not create retailer session directory.") from exc


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


def _security_verification_status(
    *,
    account: RetailerAccount,
    current_url: str | None,
    orders_url: str = MIDTOWN_ORDERS_URL,
    order_count: int = 0,
) -> MidtownBrowserStatus:
    return MidtownBrowserStatus(
        retailer="midtown",
        account_id=int(account.id or 0),
        status="security_verification_required",
        message="Midtown requires security verification.",
        current_url=current_url or MIDTOWN_LOGIN_URL,
        orders_url=orders_url,
        authenticated=False,
        order_count=order_count,
        last_updated_at=utc_now(),
    )


def _session_context_kwargs(account_id: int) -> dict[str, Any]:
    _ensure_session_state_root()
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
        _log_event("storage_state_load_attempt", account_id=account_id, path=str(state_path))
        try:
            json.loads(state_path.read_text(encoding="utf-8"))
        except OSError as exc:
            _log_event("storage_state_load_failed", account_id=account_id, path=str(state_path), error=str(exc))
            raise RetailerBrowserStateError("Failed loading saved browser state.") from exc
        except json.JSONDecodeError as exc:
            _log_event("storage_state_load_failed", account_id=account_id, path=str(state_path), error=str(exc))
            raise RetailerBrowserStateError("Failed loading saved browser state.") from exc
        context_kwargs["storage_state"] = str(state_path)
        _log_event("storage_state_load_success", account_id=account_id, path=str(state_path))
    return context_kwargs


def _launch_midtown_browser(*, playwright, account_id: int, launch_args: dict[str, Any] | None = None):
    browser_type = playwright.chromium
    executable_path = getattr(browser_type, "executable_path", None)
    _log_event(
        "playwright_launch_attempt",
        account_id=account_id,
        headless=True,
        playwright_version=_playwright_version(),
        browser_type=getattr(browser_type, "name", "chromium"),
        browser_executable_path=str(executable_path) if executable_path else None,
        launch_args=launch_args or {"headless": True},
    )
    try:
        browser = browser_type.launch(headless=True, **(launch_args or {}))
    except Exception as exc:
        LOGGER.exception(
            "midtown_browser_session playwright_launch_failed account_id=%s executable_path=%s launch_args=%s",
            account_id,
            executable_path,
            launch_args or {"headless": True},
        )
        raise RetailerBrowserEnvironmentError("Playwright Chromium failed to launch.") from exc
    _log_event("playwright_launch_success", account_id=account_id)
    return browser


def _ensure_midtown_session(account: RetailerAccount) -> tuple[str, list[MidtownOrderHistoryEntry]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RetailerBrowserEnvironmentError(
            "playwright is required for Midtown browser sessions; install it and run `playwright install chromium`."
        ) from exc

    if account.id is None:
        raise RetailerBrowserConfigurationError("Retailer browser session is not configured.")

    _ensure_session_state_root()
    _log_event(
        "midtown_browser_init_start",
        account_id=int(account.id),
        owner_user_id=int(account.owner_user_id or 0),
        session_directory=str(SESSION_STATE_ROOT),
        storage_state_path=str(Path(SESSION_STATE_ROOT) / f"midtown-account-{int(account.id)}.json"),
        playwright_version=_playwright_version(),
    )
    password = decrypt_retailer_password(account.encrypted_password)
    state_path = Path(SESSION_STATE_ROOT) / f"midtown-account-{int(account.id)}.json"
    status = "ready"
    orders: list[MidtownOrderHistoryEntry] = []

    with sync_playwright() as playwright:
        browser = _launch_midtown_browser(
            playwright=playwright,
            account_id=int(account.id),
            launch_args={"headless": True},
        )
        context = browser.new_context(**_session_context_kwargs(int(account.id)))
        page = context.new_page()
        try:
            _log_event(
                "midtown_browser_init_ready",
                account_id=int(account.id),
                current_url=MIDTOWN_ORDERS_URL,
                storage_state_path=str(state_path),
            )
            page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            if _requires_midtown_login(page):
                _log_event("midtown_browser_login_required", account_id=int(account.id), current_url=page.url)
                try:
                    _midtown_login(page, username=account.username, password=password)
                    _log_event("midtown_browser_storage_state_save_start", account_id=int(account.id), path=str(state_path))
                    _save_session_state(context, account_id=int(account.id))
                    _log_event("midtown_browser_storage_state_save_success", account_id=int(account.id), path=str(state_path))
                    page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
                    page.wait_for_load_state("networkidle")
                except MidtownNeedsAttentionError as exc:
                    _log_event(
                        "midtown_browser_security_verification_required",
                        account_id=int(account.id),
                        current_url=page.url,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                    status = "security_verification_required"
                    _write_browser_state(
                        int(account.id),
                        {
                            "status": status,
                            "current_url": page.url or MIDTOWN_LOGIN_URL,
                            "orders_url": MIDTOWN_ORDERS_URL,
                            "order_count": 0,
                            "authenticated": False,
                            "message": str(exc),
                            "last_updated_at": utc_now().isoformat(),
                        },
                    )
                    return status, orders
            if _has_midtown_challenge(page):
                _log_event("midtown_browser_security_challenge_detected", account_id=int(account.id), current_url=page.url)
                status = "security_verification_required"
                _write_browser_state(
                    int(account.id),
                    {
                        "status": status,
                        "current_url": page.url or MIDTOWN_LOGIN_URL,
                        "orders_url": MIDTOWN_ORDERS_URL,
                        "order_count": len(orders),
                        "authenticated": False,
                        "message": "Midtown requires security verification.",
                        "last_updated_at": utc_now().isoformat(),
                    },
                )
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
    _log_event("midtown_browser_session_start_request", owner_user_id=owner_user_id)
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    try:
        status, orders = _ensure_midtown_session(account)
        state = _read_browser_state(int(account.id or 0))
        if status in {"needs_attention", "security_verification_required"}:
            current_url = state.get("current_url") or MIDTOWN_LOGIN_URL
            return _security_verification_status(
                account=account,
                current_url=current_url,
                orders_url=str(state.get("orders_url") or MIDTOWN_ORDERS_URL),
                order_count=int(state.get("order_count") or 0),
            )
        result = MidtownBrowserStatus(
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
        _log_event(
            "midtown_browser_session_start_success",
            account_id=result.account_id,
            status=result.status,
            current_url=result.current_url,
            order_count=result.order_count,
        )
        return result
    except (RetailerBrowserConfigurationError, RetailerBrowserStateError, RetailerBrowserEnvironmentError):
        raise
    except Exception as exc:
        LOGGER.exception(
            "midtown_browser_session_start_failed owner_user_id=%s account_id=%s error_type=%s error_message=%s",
            owner_user_id,
            getattr(account, "id", None),
            type(exc).__name__,
            str(exc),
        )
        raise RetailerBrowserEnvironmentError("Midtown browser initialization failed.") from exc


def get_midtown_browser_session_status(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    try:
        state = _read_browser_state(int(account.id or 0))
    except RetailerBrowserStateError:
        raise
    last_updated_at = None
    if state.get("last_updated_at"):
        try:
            last_updated_at = datetime.fromisoformat(str(state["last_updated_at"]))
        except ValueError:
            last_updated_at = None
    status = str(state.get("status") or "idle")
    if status in {"needs_attention", "security_verification_required"}:
        return MidtownBrowserStatus(
            retailer="midtown",
            account_id=int(account.id or 0),
            status="security_verification_required",
            message="Midtown requires security verification.",
            current_url=state.get("current_url") or MIDTOWN_LOGIN_URL,
            orders_url=str(state.get("orders_url") or MIDTOWN_ORDERS_URL),
            authenticated=False,
            order_count=int(state.get("order_count") or 0),
            last_updated_at=last_updated_at,
        )
    return MidtownBrowserStatus(
        retailer="midtown",
        account_id=int(account.id or 0),
        status=status,
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
    state = _read_browser_state(int(account.id or 0))
    if status in {"needs_attention", "security_verification_required"}:
        return MidtownBrowserOrders(
            status=_security_verification_status(
                account=account,
                current_url=state.get("current_url") or MIDTOWN_LOGIN_URL,
                orders_url=str(state.get("orders_url") or MIDTOWN_ORDERS_URL),
                order_count=int(state.get("order_count") or 0),
            ),
            orders=[],
        )
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
        raise RetailerBrowserEnvironmentError(
            "playwright is required for Midtown browser sessions; install it and run `playwright install chromium`."
        ) from exc

    _log_event(
        "midtown_browser_detail_capture_start",
        account_id=int(account.id or 0),
        retailer_order_number=retailer_order_number,
        detail_url=history_entry.detail_url,
    )

    with sync_playwright() as playwright:
        browser = _launch_midtown_browser(playwright=playwright, account_id=int(account.id or 0))
        context = browser.new_context(**_session_context_kwargs(int(account.id or 0)))
        page = context.new_page()
        try:
            page.goto(history_entry.detail_url or MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            if _requires_midtown_login(page):
                _log_event(
                    "midtown_browser_detail_login_required",
                    account_id=int(account.id or 0),
                    current_url=page.url,
                )
                _midtown_login(page, username=account.username, password=decrypt_retailer_password(account.encrypted_password))
                _log_event(
                    "midtown_browser_storage_state_save_start",
                    account_id=int(account.id or 0),
                    path=str(Path(SESSION_STATE_ROOT) / f"midtown-account-{int(account.id)}.json"),
                )
                _save_session_state(context, account_id=int(account.id or 0))
                _log_event(
                    "midtown_browser_storage_state_save_success",
                    account_id=int(account.id or 0),
                    path=str(Path(SESSION_STATE_ROOT) / f"midtown-account-{int(account.id)}.json"),
                )
                page.goto(history_entry.detail_url or MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle")
            if _has_midtown_challenge(page):
                _log_event(
                    "midtown_browser_detail_security_challenge_detected",
                    account_id=int(account.id or 0),
                    current_url=page.url,
                )
                raise MidtownNeedsAttentionError("Midtown presented a CAPTCHA or security challenge.")
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
        raise RetailerBrowserStateError("Retailer order snapshot was not created.")
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
