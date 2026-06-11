from __future__ import annotations

import base64
import os
import threading
from dataclasses import dataclass, field
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
    viewport_width: int | None = None
    viewport_height: int | None = None
    live_session_active: bool = False
    process_id: int | None = None
    registry_contains_account: bool | None = None
    registry_session_count: int | None = None


@dataclass(slots=True)
class MidtownBrowserOrders:
    status: MidtownBrowserStatus
    orders: list[dict[str, Any]]


@dataclass(slots=True)
class MidtownLiveBrowserSession:
    account_id: int
    owner_user_id: int
    browser: Any
    context: Any
    page: Any
    status: str
    message: str | None
    current_url: str | None
    orders_url: str
    authenticated: bool
    order_count: int
    last_updated_at: datetime | None
    viewport_width: int = 1440
    viewport_height: int = 1100
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


_MIDTOWN_LIVE_SESSIONS: dict[int, MidtownLiveBrowserSession] = {}
_MIDTOWN_LIVE_SESSIONS_LOCK = threading.RLock()
_MIDTOWN_PLAYWRIGHT = None
_MIDTOWN_PLAYWRIGHT_LOCK = threading.RLock()


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
        live_session_active=True,
        process_id=os.getpid(),
        registry_contains_account=int(account.id or 0) in _MIDTOWN_LIVE_SESSIONS,
        registry_session_count=len(_MIDTOWN_LIVE_SESSIONS),
    )


def _login_required_status(
    *,
    account: RetailerAccount,
    current_url: str | None,
    orders_url: str = MIDTOWN_ORDERS_URL,
    order_count: int = 0,
) -> MidtownBrowserStatus:
    return MidtownBrowserStatus(
        retailer="midtown",
        account_id=int(account.id or 0),
        status="login_required",
        message="Midtown login is required.",
        current_url=current_url or MIDTOWN_LOGIN_URL,
        orders_url=orders_url,
        authenticated=False,
        order_count=order_count,
        last_updated_at=utc_now(),
        live_session_active=True,
        process_id=os.getpid(),
        registry_contains_account=int(account.id or 0) in _MIDTOWN_LIVE_SESSIONS,
        registry_session_count=len(_MIDTOWN_LIVE_SESSIONS),
    )


def _ready_status(
    *,
    account: RetailerAccount,
    current_url: str | None,
    orders_url: str = MIDTOWN_ORDERS_URL,
    order_count: int = 0,
    message: str | None = None,
) -> MidtownBrowserStatus:
    return MidtownBrowserStatus(
        retailer="midtown",
        account_id=int(account.id or 0),
        status="ready",
        message=message or "Midtown orders are ready.",
        current_url=current_url or orders_url,
        orders_url=orders_url,
        authenticated=True,
        order_count=order_count,
        last_updated_at=utc_now(),
        live_session_active=True,
        process_id=os.getpid(),
        registry_contains_account=int(account.id or 0) in _MIDTOWN_LIVE_SESSIONS,
        registry_session_count=len(_MIDTOWN_LIVE_SESSIONS),
    )


def _browser_state_payload(status: MidtownBrowserStatus) -> dict[str, Any]:
    return {
        "status": status.status,
        "current_url": status.current_url,
        "orders_url": status.orders_url,
        "order_count": status.order_count,
        "authenticated": status.authenticated,
        "message": status.message,
        "last_updated_at": status.last_updated_at.isoformat() if status.last_updated_at else None,
        "viewport_width": status.viewport_width,
        "viewport_height": status.viewport_height,
        "live_session_active": status.live_session_active,
        "process_id": status.process_id,
        "registry_contains_account": status.registry_contains_account,
        "registry_session_count": status.registry_session_count,
    }


def _midtown_playwright():
    global _MIDTOWN_PLAYWRIGHT
    with _MIDTOWN_PLAYWRIGHT_LOCK:
        if _MIDTOWN_PLAYWRIGHT is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as exc:  # pragma: no cover - environment guard
                raise RetailerBrowserEnvironmentError(
                    "playwright is required for Midtown browser sessions; install it and run `playwright install chromium`."
                ) from exc
            playwright_handle = sync_playwright()
            if hasattr(playwright_handle, "start"):
                _MIDTOWN_PLAYWRIGHT = playwright_handle.start()
            elif hasattr(playwright_handle, "__enter__"):
                _MIDTOWN_PLAYWRIGHT = playwright_handle.__enter__()
            else:
                _MIDTOWN_PLAYWRIGHT = playwright_handle
        return _MIDTOWN_PLAYWRIGHT


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
    args = dict(launch_args or {})
    args.setdefault("headless", True)
    _log_event(
        "playwright_launch_attempt",
        account_id=account_id,
        headless=bool(args.get("headless", True)),
        playwright_version=_playwright_version(),
        browser_type=getattr(browser_type, "name", "chromium"),
        browser_executable_path=str(executable_path) if executable_path else None,
        launch_args=args,
    )
    try:
        browser = browser_type.launch(**args)
    except Exception as exc:
        LOGGER.exception(
            "midtown_browser_session playwright_launch_failed account_id=%s executable_path=%s launch_args=%s",
            account_id,
            executable_path,
            args,
        )
        raise RetailerBrowserEnvironmentError("Playwright Chromium failed to launch.") from exc
    _log_event("playwright_launch_success", account_id=account_id)
    return browser


def _best_effort_wait_for_load(page, *, timeout_ms: int = 15000) -> None:
    try:
        page.wait_for_load_state("load", timeout=timeout_ms)
    except Exception:
        return


def _parse_last_updated_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _midtown_live_session_is_closed(session: MidtownLiveBrowserSession) -> bool:
    try:
        if hasattr(session.page, "is_closed") and session.page.is_closed():
            return True
    except Exception:
        return True
    try:
        if hasattr(session.browser, "is_connected") and not session.browser.is_connected():
            return True
    except Exception:
        return True
    return False


def _classify_midtown_live_page(account: RetailerAccount, page) -> MidtownBrowserStatus:
    current_url = getattr(page, "url", None)
    if _has_midtown_challenge(page):
        return _security_verification_status(
            account=account,
            current_url=current_url or MIDTOWN_LOGIN_URL,
            order_count=0,
        )
    if _requires_midtown_login(page):
        return _login_required_status(
            account=account,
            current_url=current_url or MIDTOWN_LOGIN_URL,
            order_count=0,
        )
    try:
        orders = parse_midtown_order_history(page.content())
    except Exception as exc:
        _log_event(
            "midtown_live_page_parse_failed",
            account_id=int(account.id or 0),
            current_url=current_url,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return MidtownBrowserStatus(
            retailer="midtown",
            account_id=int(account.id or 0),
            status="failed",
            message="Midtown page could not be read.",
            current_url=current_url,
            orders_url=MIDTOWN_ORDERS_URL,
            authenticated=False,
            order_count=0,
            last_updated_at=utc_now(),
        )

    message = "Midtown orders are ready." if orders else "Midtown browser is open."
    return _ready_status(
        account=account,
        current_url=current_url,
        order_count=len(orders),
        message=message,
    )


def _refresh_midtown_live_session_state(session: MidtownLiveBrowserSession, account: RetailerAccount) -> MidtownBrowserStatus:
    with session.lock:
        if _midtown_live_session_is_closed(session):
            raise RetailerBrowserEnvironmentError("Midtown browser session is no longer available.")
        status = _classify_midtown_live_page(account, session.page)
        status.viewport_width = session.viewport_width
        status.viewport_height = session.viewport_height
        status.live_session_active = True
        status.process_id = os.getpid()
        status.registry_contains_account = int(account.id or 0) in _MIDTOWN_LIVE_SESSIONS
        status.registry_session_count = len(_MIDTOWN_LIVE_SESSIONS)
        _log_event(
            "midtown_live_session_refresh",
            account_id=int(account.id or 0),
            process_id=os.getpid(),
            browser_exists=session.browser is not None,
            context_exists=session.context is not None,
            page_exists=session.page is not None,
            page_url=getattr(session.page, "url", None),
            page_title=(session.page.title() if hasattr(session.page, "title") else None),
            viewport_width=session.viewport_width,
            viewport_height=session.viewport_height,
            live_session_active=status.live_session_active,
            status=status.status,
            registry_contains_account=status.registry_contains_account,
            registry_session_count=status.registry_session_count,
        )
        session.status = status.status
        session.message = status.message
        session.current_url = status.current_url
        session.orders_url = status.orders_url
        session.authenticated = status.authenticated
        session.order_count = status.order_count
        session.last_updated_at = status.last_updated_at
        _write_browser_state(int(account.id or 0), _browser_state_payload(status))
        return status


def _create_midtown_live_session(account: RetailerAccount) -> MidtownLiveBrowserSession:
    if account.id is None:
        raise RetailerBrowserConfigurationError("Retailer browser session is not configured.")

    _ensure_session_state_root()
    account_id = int(account.id)
    state_path = Path(SESSION_STATE_ROOT) / f"midtown-account-{account_id}.json"
    _log_event(
        "midtown_live_session_create_start",
        account_id=account_id,
        owner_user_id=int(account.owner_user_id or 0),
        session_directory=str(SESSION_STATE_ROOT),
        storage_state_path=str(state_path),
        playwright_version=_playwright_version(),
    )
    playwright = _midtown_playwright()
    browser = _launch_midtown_browser(playwright=playwright, account_id=account_id, launch_args={"headless": True})
    context = browser.new_context(**_session_context_kwargs(account_id))
    page = context.new_page()
    page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
    _best_effort_wait_for_load(page)
    session = MidtownLiveBrowserSession(
        account_id=account_id,
        owner_user_id=int(account.owner_user_id or 0),
        browser=browser,
        context=context,
        page=page,
        status="initializing",
        message=None,
        current_url=getattr(page, "url", None),
        orders_url=MIDTOWN_ORDERS_URL,
        authenticated=False,
        order_count=0,
        last_updated_at=utc_now(),
    )
    status = _refresh_midtown_live_session_state(session, account)
    if status.status == "ready" and hasattr(context, "storage_state"):
        _log_event(
            "midtown_live_session_storage_state_save_start",
            account_id=account_id,
            path=str(state_path),
        )
        try:
            _save_session_state(context, account_id=account_id)
        except Exception as exc:
            _log_event(
                "midtown_live_session_storage_state_save_failed",
                account_id=account_id,
                path=str(state_path),
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        else:
            _log_event(
                "midtown_live_session_storage_state_save_success",
                account_id=account_id,
                path=str(state_path),
            )
    _log_event(
        "midtown_live_session_create_success",
        account_id=account_id,
        status=status.status,
        current_url=status.current_url,
        order_count=status.order_count,
    )
    return session


def _rehydrate_midtown_live_session(account: RetailerAccount, state: dict[str, Any]) -> MidtownLiveBrowserSession:
    if account.id is None:
        raise RetailerBrowserConfigurationError("Retailer browser session is not configured.")

    account_id = int(account.id)
    target_url = str(
        state.get("current_url")
        or state.get("orders_url")
        or state.get("last_known_url")
        or MIDTOWN_ORDERS_URL
    )
    _log_event(
        "midtown_live_session_rehydrate_start",
        account_id=account_id,
        target_url=target_url,
        state_status=state.get("status"),
        state_live_session_active=state.get("live_session_active"),
        registry_session_count=len(_MIDTOWN_LIVE_SESSIONS),
    )
    playwright = _midtown_playwright()
    browser = _launch_midtown_browser(playwright=playwright, account_id=account_id, launch_args={"headless": True})
    context = browser.new_context(**_session_context_kwargs(account_id))
    page = context.new_page()
    page.goto(target_url, wait_until="domcontentloaded")
    _best_effort_wait_for_load(page)
    session = MidtownLiveBrowserSession(
        account_id=account_id,
        owner_user_id=int(account.owner_user_id or 0),
        browser=browser,
        context=context,
        page=page,
        status=str(state.get("status") or "rehydrated"),
        message=state.get("message"),
        current_url=getattr(page, "url", target_url),
        orders_url=str(state.get("orders_url") or MIDTOWN_ORDERS_URL),
        authenticated=bool(state.get("authenticated", False)),
        order_count=int(state.get("order_count") or 0),
        last_updated_at=utc_now(),
        viewport_width=int(state.get("viewport_width") or 1440),
        viewport_height=int(state.get("viewport_height") or 1100),
    )
    status = _refresh_midtown_live_session_state(session, account)
    _log_event(
        "midtown_live_session_rehydrate_success",
        account_id=account_id,
        process_id=os.getpid(),
        current_url=status.current_url,
        page_title=(page.title() if hasattr(page, "title") else None),
        live_session_active=status.live_session_active,
        registry_contains_account=status.registry_contains_account,
        registry_session_count=status.registry_session_count,
    )
    return session


def _get_midtown_live_session(account_id: int) -> MidtownLiveBrowserSession | None:
    with _MIDTOWN_LIVE_SESSIONS_LOCK:
        session = _MIDTOWN_LIVE_SESSIONS.get(account_id)
        if session is None:
            return None
        if _midtown_live_session_is_closed(session):
            _MIDTOWN_LIVE_SESSIONS.pop(account_id, None)
            return None
        return session


def _set_midtown_live_session(account_id: int, session: MidtownLiveBrowserSession) -> MidtownLiveBrowserSession:
    with _MIDTOWN_LIVE_SESSIONS_LOCK:
        _MIDTOWN_LIVE_SESSIONS[account_id] = session
    return session


def _ensure_midtown_live_session(account: RetailerAccount) -> MidtownLiveBrowserSession:
    if account.id is None:
        raise RetailerBrowserConfigurationError("Retailer browser session is not configured.")
    account_id = int(account.id)
    session = _get_midtown_live_session(account_id)
    if session is not None:
        return session
    state = _read_browser_state(account_id)
    if state:
        try:
            return _set_midtown_live_session(account_id, _rehydrate_midtown_live_session(account, state))
        except Exception as exc:
            _log_event(
                "midtown_live_session_rehydrate_failed",
                account_id=account_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
    return _set_midtown_live_session(account_id, _create_midtown_live_session(account))


def _rebuild_midtown_live_session(account: RetailerAccount) -> MidtownLiveBrowserSession:
    if account.id is None:
        raise RetailerBrowserConfigurationError("Retailer browser session is not configured.")
    account_id = int(account.id)
    with _MIDTOWN_LIVE_SESSIONS_LOCK:
        old_session = _MIDTOWN_LIVE_SESSIONS.pop(account_id, None)
    if old_session is not None:
        with old_session.lock:
            try:
                old_session.context.close()
            except Exception:
                pass
            try:
                old_session.browser.close()
            except Exception:
                pass
    return _set_midtown_live_session(account_id, _create_midtown_live_session(account))


def _browser_state_from_live_session(status: MidtownBrowserStatus, *, live_session: MidtownLiveBrowserSession) -> dict[str, Any]:
    payload = _browser_state_payload(status)
    payload.update(
        {
            "viewport_width": live_session.viewport_width,
            "viewport_height": live_session.viewport_height,
        }
    )
    return payload


def _live_session_frame_data_url(page) -> tuple[str, int, int]:
    screenshot = page.screenshot(type="jpeg", quality=75)
    width = int(page.viewport_size["width"]) if page.viewport_size and page.viewport_size.get("width") else 1440
    height = int(page.viewport_size["height"]) if page.viewport_size and page.viewport_size.get("height") else 1100
    encoded = base64.b64encode(screenshot).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}", width, height


def _status_from_browser_state(account: RetailerAccount, state: dict[str, Any]) -> MidtownBrowserStatus:
    last_updated_at = _parse_last_updated_at(state.get("last_updated_at"))
    status = str(state.get("status") or "idle")
    current_url = state.get("current_url")
    orders_url = str(state.get("orders_url") or MIDTOWN_ORDERS_URL)
    order_count = int(state.get("order_count") or 0)
    authenticated = bool(state.get("authenticated", False))
    message = state.get("message")
    if status in {"needs_attention", "security_verification_required"}:
        return _security_verification_status(
            account=account,
            current_url=current_url or MIDTOWN_LOGIN_URL,
            orders_url=orders_url,
            order_count=order_count,
        )
    if status == "login_required":
        return _login_required_status(
            account=account,
            current_url=current_url or MIDTOWN_LOGIN_URL,
            orders_url=orders_url,
            order_count=order_count,
        )
    if status == "ready":
        return MidtownBrowserStatus(
            retailer="midtown",
            account_id=int(account.id or 0),
            status="ready",
            message=message or "Midtown orders are ready.",
            current_url=current_url or orders_url,
            orders_url=orders_url,
            authenticated=True,
            order_count=order_count,
            last_updated_at=last_updated_at or utc_now(),
        )
    return MidtownBrowserStatus(
        retailer="midtown",
        account_id=int(account.id or 0),
        status=status,
        message=message,
        current_url=current_url,
        orders_url=orders_url,
        authenticated=authenticated,
        order_count=order_count,
        last_updated_at=last_updated_at,
        process_id=os.getpid(),
        registry_contains_account=False,
        registry_session_count=len(_MIDTOWN_LIVE_SESSIONS),
    )


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
            _best_effort_wait_for_load(page)
            if _requires_midtown_login(page):
                _log_event("midtown_browser_login_required", account_id=int(account.id), current_url=page.url)
                try:
                    _midtown_login(page, username=account.username, password=password)
                    _log_event("midtown_browser_storage_state_save_start", account_id=int(account.id), path=str(state_path))
                    _save_session_state(context, account_id=int(account.id))
                    _log_event("midtown_browser_storage_state_save_success", account_id=int(account.id), path=str(state_path))
                    page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
                    _best_effort_wait_for_load(page)
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
        live_session = _ensure_midtown_live_session(account)
        result = _refresh_midtown_live_session_state(live_session, account)
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
        live_session = _ensure_midtown_live_session(account)
        return _refresh_midtown_live_session_state(live_session, account)
    except RetailerBrowserStateError:
        raise


def list_midtown_browser_orders(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserOrders:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    live_session = _get_midtown_live_session(int(account.id or 0))
    if live_session is not None:
        status = _refresh_midtown_live_session_state(live_session, account)
        if status.status in {"needs_attention", "security_verification_required", "login_required"}:
            return MidtownBrowserOrders(status=status, orders=[])
        if status.status == "failed":
            return MidtownBrowserOrders(status=status, orders=[])
        with live_session.lock:
            orders = parse_midtown_order_history(live_session.page.content())
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
        session_status = _ready_status(
            account=account,
            current_url=live_session.current_url or MIDTOWN_ORDERS_URL,
            order_count=len(normalized_orders),
            message=status.message or "Midtown orders are ready.",
        )
        _write_browser_state(int(account.id or 0), _browser_state_payload(session_status))
        return MidtownBrowserOrders(
            status=session_status,
            orders=normalized_orders,
        )
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
            _best_effort_wait_for_load(page)
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


def get_midtown_browser_live_frame(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[str, Any]:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    live_session = _ensure_midtown_live_session(account)
    with live_session.lock:
        if _midtown_live_session_is_closed(live_session):
            raise RetailerBrowserEnvironmentError("Midtown browser session is no longer available.")
        status = _refresh_midtown_live_session_state(live_session, account)
        image_data_url, width, height = _live_session_frame_data_url(live_session.page)
        image_bytes_size = len(image_data_url.split(",", 1)[1]) if "," in image_data_url else 0
        page_title = live_session.page.title() if hasattr(live_session.page, "title") else None
        page_url = getattr(live_session.page, "url", None)
        payload = {
            "session": status,
            "image_data_url": image_data_url,
            "image_width": width,
            "image_height": height,
            "viewport_width": live_session.viewport_width,
            "viewport_height": live_session.viewport_height,
            "live_session_active": True,
            "captured_at": utc_now().isoformat(),
            "endpoint_status": 200,
            "image_bytes_size": image_bytes_size,
            "page_title": page_title,
            "page_url": page_url,
            "registry_contains_account": int(account.id or 0) in _MIDTOWN_LIVE_SESSIONS,
            "registry_session_count": len(_MIDTOWN_LIVE_SESSIONS),
        }
        _log_event(
            "midtown_live_session_frame",
            account_id=int(account.id or 0),
            endpoint_status=200,
            image_bytes_size=image_bytes_size,
            captured_at=payload["captured_at"],
            page_url=page_url,
            page_title=page_title,
            viewport_width=live_session.viewport_width,
            viewport_height=live_session.viewport_height,
            browser_exists=live_session.browser is not None,
            context_exists=live_session.context is not None,
            page_exists=live_session.page is not None,
            registry_contains_account=int(account.id or 0) in _MIDTOWN_LIVE_SESSIONS,
        )
        return payload


def click_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
    x: float,
    y: float,
    button: str = "left",
    click_count: int = 1,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    live_session = _ensure_midtown_live_session(account)
    with live_session.lock:
        if _midtown_live_session_is_closed(live_session):
            raise RetailerBrowserEnvironmentError("Midtown browser session is no longer available.")
        live_session.page.mouse.click(x, y, button=button, click_count=click_count)
        _best_effort_wait_for_load(live_session.page)
        return _refresh_midtown_live_session_state(live_session, account)


def type_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
    text: str,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    live_session = _ensure_midtown_live_session(account)
    with live_session.lock:
        if _midtown_live_session_is_closed(live_session):
            raise RetailerBrowserEnvironmentError("Midtown browser session is no longer available.")
        live_session.page.keyboard.insert_text(text)
        return _refresh_midtown_live_session_state(live_session, account)


def key_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
    key: str,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    live_session = _ensure_midtown_live_session(account)
    with live_session.lock:
        if _midtown_live_session_is_closed(live_session):
            raise RetailerBrowserEnvironmentError("Midtown browser session is no longer available.")
        live_session.page.keyboard.press(key)
        _best_effort_wait_for_load(live_session.page)
        return _refresh_midtown_live_session_state(live_session, account)


def retry_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    live_session = _ensure_midtown_live_session(account)
    with live_session.lock:
        if _midtown_live_session_is_closed(live_session):
            raise RetailerBrowserEnvironmentError("Midtown browser session is no longer available.")
        live_session.page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
        _best_effort_wait_for_load(live_session.page)
        status = _refresh_midtown_live_session_state(live_session, account)
        if status.status == "ready":
            _save_session_state(live_session.context, account_id=int(account.id or 0))
        return status
