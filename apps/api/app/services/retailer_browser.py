from __future__ import annotations

import base64
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
from contextlib import contextmanager
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
    _detect_midtown_challenge,
    _detect_midtown_login,
    _has_midtown_challenge,
    _load_recent_order_details,
    _midtown_login,
    _midtown_page_title,
    _midtown_visible_text,
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


class MidtownBrowserBusyError(RuntimeError):
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


def _screenshot_cache_path(account_id: int) -> Path:
    return SESSION_STATE_ROOT / f"midtown-account-{account_id}.frame.json"


def _write_last_screenshot(account_id: int, image_data_url: str, width: int, height: int) -> None:
    """Best-effort persistence of the most recent successful screenshot. Never raises."""
    if not image_data_url:
        return
    path = _screenshot_cache_path(account_id)
    try:
        _ensure_session_state_root()
        path.write_text(
            json.dumps(
                {
                    "image_data_url": image_data_url,
                    "image_width": int(width),
                    "image_height": int(height),
                    "captured_at": utc_now().isoformat(),
                }
            ),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - caching must never break the request
        _log_event("midtown_screenshot_cache_write_failed", account_id=account_id, error=str(exc))


def _read_last_screenshot(account_id: int) -> dict[str, Any] | None:
    """Best-effort read of the last successful screenshot. Never raises."""
    path = _screenshot_cache_path(account_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - missing/corrupt cache is non-fatal
        _log_event("midtown_screenshot_cache_read_failed", account_id=account_id, error=str(exc))
        return None
    if not isinstance(data, dict) or not data.get("image_data_url"):
        return None
    return data


def _capture_or_cached_frame(account_id: int, page) -> tuple[str, int, int, str]:
    """Capture a live screenshot, falling back to the last cached one.

    Returns ``(image_data_url, width, height, source)`` where ``source`` is one of
    ``"live"``, ``"cache"``, or ``"none"``. Never raises.
    """
    if page is not None:
        try:
            image_data_url, width, height = _live_session_frame_data_url(page)
            _write_last_screenshot(account_id, image_data_url, width, height)
            return image_data_url, width, height, "live"
        except Exception as exc:  # noqa: BLE001 - screenshot failure must never crash the endpoint
            LOGGER.exception(
                "midtown_live_session_frame_capture_failed account_id=%s error_type=%s error_message=%s",
                account_id,
                type(exc).__name__,
                exc,
            )
    cached = _read_last_screenshot(account_id)
    if cached:
        return (
            str(cached.get("image_data_url") or ""),
            int(cached.get("image_width") or 1440),
            int(cached.get("image_height") or 1100),
            "cache",
        )
    return "", 1440, 1100, "none"


def _assemble_frame_payload(
    account_id: int,
    status: "MidtownBrowserStatus",
    *,
    image_data_url: str,
    image_width: int,
    image_height: int,
    frame_available: bool,
    page=None,
) -> dict[str, Any]:
    page_title: str | None = None
    page_url: str | None = status.current_url
    if page is not None:
        try:
            page_title = page.title() if hasattr(page, "title") else None
        except Exception:  # noqa: BLE001 - diagnostics only
            page_title = None
        page_url = getattr(page, "url", None) or status.current_url
    image_bytes_size = len(image_data_url.split(",", 1)[1]) if "," in image_data_url else 0
    return {
        "session": status,
        "image_data_url": image_data_url,
        "image_width": int(image_width or status.viewport_width or 1440),
        "image_height": int(image_height or status.viewport_height or 1100),
        "viewport_width": status.viewport_width,
        "viewport_height": status.viewport_height,
        "live_session_active": True,
        "captured_at": utc_now().isoformat(),
        "endpoint_status": 200,
        "image_bytes_size": image_bytes_size,
        "frame_available": frame_available,
        "page_title": page_title,
        "page_url": page_url,
        "browser_exists": page is not None,
        "context_exists": page is not None,
        "page_exists": page is not None,
        "process_id": os.getpid(),
        "registry_contains_account": _midtown_live_metadata_contains(account_id),
        "registry_session_count": len(_MIDTOWN_LIVE_SESSION_METADATA),
        "active_element_tag": status.active_element_tag,
        "active_element_name": status.active_element_name,
        "active_element_type": status.active_element_type,
        "active_element_placeholder": status.active_element_placeholder,
    }


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
    active_element_tag: str | None = None
    active_element_name: str | None = None
    active_element_type: str | None = None
    active_element_placeholder: str | None = None


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
_MIDTOWN_LIVE_SESSION_METADATA: dict[int, MidtownBrowserStatus] = {}
_MIDTOWN_LIVE_SESSION_METADATA_LOCK = threading.RLock()
_MIDTOWN_OPERATION_LOCKS: dict[int, threading.Lock] = {}
_MIDTOWN_OPERATION_LOCKS_LOCK = threading.RLock()
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
        "active_element_tag": status.active_element_tag,
        "active_element_name": status.active_element_name,
        "active_element_type": status.active_element_type,
        "active_element_placeholder": status.active_element_placeholder,
    }


def _record_midtown_live_metadata(status: MidtownBrowserStatus) -> None:
    if status.account_id is None:
        return
    with _MIDTOWN_LIVE_SESSION_METADATA_LOCK:
        _MIDTOWN_LIVE_SESSION_METADATA[int(status.account_id)] = status


def _midtown_live_metadata_contains(account_id: int) -> bool:
    with _MIDTOWN_LIVE_SESSION_METADATA_LOCK:
        return account_id in _MIDTOWN_LIVE_SESSION_METADATA


def _midtown_account_operation_lock(account_id: int) -> threading.Lock:
    with _MIDTOWN_OPERATION_LOCKS_LOCK:
        lock = _MIDTOWN_OPERATION_LOCKS.get(account_id)
        if lock is None:
            lock = threading.Lock()
            _MIDTOWN_OPERATION_LOCKS[account_id] = lock
        return lock


@contextmanager
def _midtown_single_operation(account_id: int):
    lock = _midtown_account_operation_lock(account_id)
    if not lock.acquire(blocking=False):
        raise MidtownBrowserBusyError("Midtown browser is busy. Try again shortly.")
    try:
        yield
    finally:
        lock.release()


def _build_midtown_status_from_page(
    account: RetailerAccount,
    page,
    *,
    default_status: str | None = None,
    message: str | None = None,
) -> MidtownBrowserStatus:
    status = _classify_midtown_live_page(account, page)
    if default_status is not None and status.status not in {"security_verification_required", "login_required", "failed"}:
        status.status = default_status
        status.message = message or status.message
    _apply_midtown_viewport_metadata(status, page)
    status.live_session_active = True
    status.process_id = os.getpid()
    status.registry_contains_account = True
    status.registry_session_count = len(_MIDTOWN_LIVE_SESSION_METADATA)
    active = _capture_midtown_active_element(page)
    status.active_element_tag = active.get("tag")
    status.active_element_name = active.get("name")
    status.active_element_type = active.get("type")
    status.active_element_placeholder = active.get("placeholder")
    _record_midtown_live_metadata(status)
    _write_browser_state(int(account.id or 0), _browser_state_payload(status))
    return status


@contextmanager
def _midtown_request_browser(account: RetailerAccount, *, target_url: str | None = None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RetailerBrowserEnvironmentError(
            "playwright is required for Midtown browser sessions; install it and run `playwright install chromium`."
        ) from exc

    if account.id is None:
        raise RetailerBrowserConfigurationError("Retailer browser session is not configured.")

    account_id = int(account.id)
    _ensure_session_state_root()
    _log_event(
        "midtown_request_browser_open",
        account_id=account_id,
        target_url=target_url,
        process_id=os.getpid(),
    )
    with sync_playwright() as playwright:
        browser = _launch_midtown_browser(playwright=playwright, account_id=account_id, launch_args={"headless": True})
        context = browser.new_context(**_session_context_kwargs(account_id))
        page = context.new_page()
        if target_url:
            page.goto(target_url, wait_until="domcontentloaded")
            _best_effort_wait_for_load(page)
        try:
            yield browser, context, page
        finally:
            try:
                context.close()
            finally:
                browser.close()


def _capture_midtown_active_element(page) -> dict[str, str | None]:
    try:
        return page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el) {
                  return { tag: null, name: null, type: null, placeholder: null };
                }
                const tag = el.tagName ? el.tagName.toLowerCase() : null;
                return {
                  tag,
                  name: typeof el.getAttribute === 'function' ? (el.getAttribute('name') || null) : null,
                  type: typeof el.getAttribute === 'function' ? (el.getAttribute('type') || null) : null,
                  placeholder: typeof el.getAttribute === 'function' ? (el.getAttribute('placeholder') || null) : null,
                };
            }"""
        )
    except Exception:
        return {"tag": None, "name": None, "type": None, "placeholder": None}


def _apply_midtown_viewport_metadata(status: MidtownBrowserStatus, page) -> None:
    viewport_size = getattr(page, "viewport_size", None) or {}
    status.viewport_width = int(viewport_size["width"]) if viewport_size.get("width") else 1440
    status.viewport_height = int(viewport_size["height"]) if viewport_size.get("height") else 1100


def _log_midtown_interaction(
    *,
    event: str,
    account_id: int,
    page,
    status: MidtownBrowserStatus,
    displayed_image_width: int | None = None,
    displayed_image_height: int | None = None,
    received_x: float | None = None,
    received_y: float | None = None,
    playwright_x: float | None = None,
    playwright_y: float | None = None,
) -> None:
    active = _capture_midtown_active_element(page)
    _log_event(
        event,
        account_id=account_id,
        process_id=os.getpid(),
        current_url=getattr(page, "url", None),
        page_title=(page.title() if hasattr(page, "title") else None),
        viewport_width=status.viewport_width,
        viewport_height=status.viewport_height,
        displayed_image_width=displayed_image_width,
        displayed_image_height=displayed_image_height,
        received_x=received_x,
        received_y=received_y,
        playwright_x=playwright_x,
        playwright_y=playwright_y,
        active_element_tag=active.get("tag"),
        active_element_name=active.get("name"),
        active_element_type=active.get("type"),
        active_element_placeholder=active.get("placeholder"),
    )


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
    account_id = int(account.id or 0)
    current_url = getattr(page, "url", None)
    page_title = _midtown_page_title(page)
    text_excerpt = _midtown_visible_text(page, limit=500)

    # Decisions go through the monkeypatchable bool wrappers; the detect variants
    # provide the human-readable rule that fired, for diagnostics.
    challenge = _has_midtown_challenge(page)
    login = _requires_midtown_login(page)
    try:
        _, challenge_reason = _detect_midtown_challenge(page)
    except Exception:  # noqa: BLE001 - diagnostics only
        challenge_reason = None
    try:
        _, login_reason = _detect_midtown_login(page)
    except Exception:  # noqa: BLE001 - diagnostics only
        login_reason = None

    def _emit(detected_status: str, detection_rule: str | None, *, authenticated: bool, order_count: int) -> None:
        _log_event(
            "midtown_page_classification",
            account_id=account_id,
            current_url=current_url,
            page_title=page_title,
            detected_status=detected_status,
            detection_rule=detection_rule,
            challenge_detected=challenge,
            login_detected=login,
            authenticated=authenticated,
            order_count=order_count,
            page_text_excerpt=text_excerpt,
        )

    if challenge:
        _emit("security_verification_required", challenge_reason or "challenge", authenticated=False, order_count=0)
        return _security_verification_status(
            account=account,
            current_url=current_url or MIDTOWN_LOGIN_URL,
            order_count=0,
        )
    if login:
        _emit("login_required", login_reason or "login", authenticated=False, order_count=0)
        return _login_required_status(
            account=account,
            current_url=current_url or MIDTOWN_LOGIN_URL,
            order_count=0,
        )
    try:
        orders = parse_midtown_order_history(page.content())
    except Exception as exc:
        _emit("failed", f"parse_error:{type(exc).__name__}", authenticated=False, order_count=0)
        _log_event(
            "midtown_live_page_parse_failed",
            account_id=account_id,
            current_url=current_url,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        return MidtownBrowserStatus(
            retailer="midtown",
            account_id=account_id,
            status="failed",
            message="Midtown page could not be read.",
            current_url=current_url,
            orders_url=MIDTOWN_ORDERS_URL,
            authenticated=False,
            order_count=0,
            last_updated_at=utc_now(),
        )

    # No challenge and no login form: this is an authenticated / normal Midtown
    # page. We do NOT treat it as a security challenge.
    if orders:
        _emit("ready", "order_history_parsed", authenticated=True, order_count=len(orders))
        message = "Midtown orders are ready."
    else:
        _emit("authenticated", "no_challenge_no_login", authenticated=True, order_count=0)
        message = "Signed in to Midtown."
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
    screenshot = page.screenshot(type="jpeg", quality=55)
    width = int(page.viewport_size["width"]) if page.viewport_size and page.viewport_size.get("width") else 1440
    height = int(page.viewport_size["height"]) if page.viewport_size and page.viewport_size.get("height") else 1100
    encoded = base64.b64encode(screenshot).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}", width, height


def _scale_midtown_coordinate(
    value: float,
    *,
    displayed_size: int | None,
    viewport_size: int | None,
) -> float:
    if displayed_size and viewport_size and displayed_size > 0 and viewport_size > 0:
        return max(0.0, min(float(viewport_size), (value / float(displayed_size)) * float(viewport_size)))
    return float(value)


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
                try:
                    _midtown_attempt_assisted_login(
                        account,
                        context=context,
                        page=page,
                        post_login_url=MIDTOWN_ORDERS_URL,
                        save_session_state=True,
                    )
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


def _midtown_attempt_assisted_login(
    account: RetailerAccount,
    *,
    context,
    page,
    post_login_url: str | None = None,
    save_session_state: bool = False,
) -> bool:
    if not _requires_midtown_login(page):
        return False
    account_id = int(account.id or 0)
    _log_event("midtown_browser_login_required", account_id=account_id, current_url=page.url)
    password = decrypt_retailer_password(account.encrypted_password)
    _midtown_login(page, username=account.username, password=password)
    if save_session_state:
        _log_event(
            "midtown_browser_storage_state_save_start",
            account_id=account_id,
            path=str(Path(SESSION_STATE_ROOT) / f"midtown-account-{account_id}.json"),
        )
        _save_session_state(context, account_id=account_id)
        _log_event(
            "midtown_browser_storage_state_save_success",
            account_id=account_id,
            path=str(Path(SESSION_STATE_ROOT) / f"midtown-account-{account_id}.json"),
        )
    if post_login_url:
        page.goto(post_login_url, wait_until="domcontentloaded")
        _best_effort_wait_for_load(page)
    return True


def start_midtown_browser_session(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserStatus:
    _log_event("midtown_browser_session_start_request", owner_user_id=owner_user_id)
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    account_id = int(account.id or 0)
    try:
        with _midtown_single_operation(account_id):
            state = _read_browser_state(account_id)
            target_url = str(
                state.get("current_url")
                or state.get("orders_url")
                or state.get("last_known_url")
                or MIDTOWN_ORDERS_URL
            )
            post_login_url = str(state.get("orders_url") or MIDTOWN_ORDERS_URL)
            with _midtown_request_browser(account, target_url=target_url) as (_browser, context, page):
                try:
                    _midtown_attempt_assisted_login(
                        account,
                        context=context,
                        page=page,
                        post_login_url=post_login_url,
                        save_session_state=True,
                    )
                except MidtownNeedsAttentionError as exc:
                    # CAPTCHA / security challenge is a valid application state, not a failure.
                    LOGGER.warning(
                        "midtown_browser_session_start_security_verification account_id=%s error_type=%s error_message=%s",
                        account_id,
                        type(exc).__name__,
                        exc,
                        exc_info=True,
                    )
                    _log_event(
                        "midtown_browser_security_verification_required",
                        account_id=account_id,
                        current_url=getattr(page, "url", None),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                    result = _security_verification_status(
                        account=account,
                        current_url=getattr(page, "url", None) or MIDTOWN_LOGIN_URL,
                        order_count=0,
                    )
                    _apply_midtown_viewport_metadata(result, page)
                    _write_browser_state(account_id, _browser_state_payload(result))
                    return result
                result = _build_midtown_status_from_page(account, page)
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
    except MidtownBrowserBusyError:
        raise
    except MidtownNeedsAttentionError as exc:
        # Defensive: a security challenge must NEVER be reported as an environment failure.
        LOGGER.warning(
            "midtown_browser_session_start_security_verification_late account_id=%s error_type=%s error_message=%s",
            account_id,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        result = _security_verification_status(
            account=account,
            current_url=MIDTOWN_LOGIN_URL,
            order_count=0,
        )
        try:
            _write_browser_state(account_id, _browser_state_payload(result))
        except Exception:  # noqa: BLE001 - persistence is best-effort here
            pass
        return result
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
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        state = _read_browser_state(account_id)
        target_url = str(
            state.get("current_url")
            or state.get("orders_url")
            or state.get("last_known_url")
            or MIDTOWN_ORDERS_URL
        )
        post_login_url = str(state.get("orders_url") or MIDTOWN_ORDERS_URL)
        with _midtown_request_browser(account, target_url=target_url) as (_browser, context, page):
            try:
                _midtown_attempt_assisted_login(
                    account,
                    context=context,
                    page=page,
                    post_login_url=post_login_url,
                    save_session_state=True,
                )
            except MidtownNeedsAttentionError as exc:
                _log_event(
                    "midtown_browser_security_verification_required",
                    account_id=account_id,
                    current_url=page.url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                return _security_verification_status(
                    account=account,
                    current_url=page.url or MIDTOWN_LOGIN_URL,
                    order_count=0,
                )
            status = _build_midtown_status_from_page(account, page)
            _log_event(
                "midtown_browser_status_request",
                account_id=int(account.id or 0),
                current_url=getattr(page, "url", None),
                page_title=(page.title() if hasattr(page, "title") else None),
                live_session_active=status.live_session_active,
                process_id=status.process_id,
                registry_contains_account=status.registry_contains_account,
                registry_session_count=status.registry_session_count,
            )
            return status


_MIDTOWN_ACCOUNT_PROBE_URLS = (
    "https://www.midtowncomics.com/account-settings",
    "https://www.midtowncomics.com/track_my_order",
    "https://www.midtowncomics.com/browsing-history",
)


def _probe_midtown_authentication(page, *, account_id: int) -> tuple[str, list[dict[str, Any]]]:
    """Navigate known Midtown account pages to authoritatively classify auth state.

    Returns ``(status, results)`` where status is one of ``"authenticated"``,
    ``"login_required"``, or ``"security_verification_required"``. Each result row
    records whether the account page was directly accessible.
    """
    results: list[dict[str, Any]] = []
    final_status = "login_required"
    for url in _MIDTOWN_ACCOUNT_PROBE_URLS:
        entry: dict[str, Any] = {"requested_url": url}
        try:
            page.goto(url, wait_until="domcontentloaded")
            _best_effort_wait_for_load(page)
        except Exception as exc:  # noqa: BLE001 - probe must never raise
            entry.update({"error_type": type(exc).__name__, "error_message": str(exc), "accessible": False})
            results.append(entry)
            continue
        challenge, challenge_reason = _detect_midtown_challenge(page)
        login, login_reason = _detect_midtown_login(page)
        accessible = not challenge and not login
        entry.update(
            {
                "landed_url": getattr(page, "url", None),
                "page_title": _midtown_page_title(page),
                "challenge_detected": challenge,
                "challenge_reason": challenge_reason,
                "login_detected": login,
                "login_reason": login_reason,
                "accessible": accessible,
            }
        )
        results.append(entry)
        if challenge:
            final_status = "security_verification_required"
            break
        if accessible:
            final_status = "authenticated"
            break
        final_status = "login_required"
        break
    _log_event("midtown_auth_probe", account_id=account_id, final_status=final_status, results=results)
    return final_status, results


def list_midtown_browser_orders(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserOrders:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        # Order history lives on the Midtown account page, so always load that page
        # rather than a stale last-known URL (e.g. a search-results page).
        target_url = MIDTOWN_ORDERS_URL
        post_login_url = MIDTOWN_ORDERS_URL
        with _midtown_request_browser(account, target_url=target_url) as (_browser, context, page):
            try:
                _midtown_attempt_assisted_login(
                    account,
                    context=context,
                    page=page,
                    post_login_url=post_login_url,
                    save_session_state=True,
                )
            except MidtownNeedsAttentionError as exc:
                _log_event(
                    "midtown_browser_security_verification_required",
                    account_id=account_id,
                    current_url=page.url,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                )
                return MidtownBrowserOrders(
                    status=_security_verification_status(
                        account=account,
                        current_url=page.url or MIDTOWN_LOGIN_URL,
                        order_count=0,
                    ),
                    orders=[],
                )
            status = _build_midtown_status_from_page(account, page)
            if status.status in {"needs_attention", "security_verification_required", "login_required", "failed"}:
                return MidtownBrowserOrders(status=status, orders=[])
            orders = parse_midtown_order_history(page.content())
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
            if not normalized_orders:
                # No order rows parsed. Confirm whether we are actually signed in by
                # probing known account pages, so we don't report a logged-out user
                # as an empty (authenticated) account.
                probe_status, _ = _probe_midtown_authentication(page, account_id=account_id)
                if probe_status == "security_verification_required":
                    security = _security_verification_status(
                        account=account,
                        current_url=getattr(page, "url", None) or MIDTOWN_LOGIN_URL,
                        order_count=0,
                    )
                    _write_browser_state(account_id, _browser_state_payload(security))
                    return MidtownBrowserOrders(status=security, orders=[])
                if probe_status == "login_required":
                    login_status = _login_required_status(
                        account=account,
                        current_url=getattr(page, "url", None) or MIDTOWN_LOGIN_URL,
                        order_count=0,
                    )
                    _write_browser_state(account_id, _browser_state_payload(login_status))
                    return MidtownBrowserOrders(status=login_status, orders=[])

            status.status = "ready" if normalized_orders else "empty"
            status.message = "Midtown orders are ready." if normalized_orders else "No Midtown orders found for this account."
            status.order_count = len(normalized_orders)
            status.authenticated = True
            _record_midtown_live_metadata(status)
            _write_browser_state(int(account.id or 0), _browser_state_payload(status))
            return MidtownBrowserOrders(status=status, orders=normalized_orders)


def capture_midtown_browser_order(
    session: Session,
    *,
    owner_user_id: int,
    retailer_order_number: str,
) -> tuple[MidtownBrowserStatus, MidtownOrderDetail, int]:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        status, orders = _ensure_midtown_session(account)
        order_map = {order.retailer_order_number: order for order in orders}
        history_entry = order_map.get(retailer_order_number)
        if history_entry is None:
            raise ValueError(f"Midtown order {retailer_order_number} was not found.")

        _log_event(
            "midtown_browser_detail_capture_start",
            account_id=int(account.id or 0),
            retailer_order_number=retailer_order_number,
            detail_url=history_entry.detail_url,
        )

        with _midtown_request_browser(account, target_url=history_entry.detail_url or MIDTOWN_ORDERS_URL) as (
            _browser,
            context,
            page,
        ):
            if _requires_midtown_login(page):
                _midtown_attempt_assisted_login(
                    account,
                    context=context,
                    page=page,
                    post_login_url=history_entry.detail_url or MIDTOWN_ORDERS_URL,
                    save_session_state=True,
                )
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
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        try:
            state = _read_browser_state(account_id)
            target_url = str(
                state.get("current_url")
                or state.get("orders_url")
                or state.get("last_known_url")
                or MIDTOWN_ORDERS_URL
            )
            post_login_url = str(state.get("orders_url") or MIDTOWN_ORDERS_URL)
            with _midtown_request_browser(account, target_url=target_url) as (_browser, context, page):
                security_required = False
                try:
                    _midtown_attempt_assisted_login(
                        account,
                        context=context,
                        page=page,
                        post_login_url=post_login_url,
                        save_session_state=True,
                    )
                except MidtownNeedsAttentionError as exc:
                    # CAPTCHA / security challenge is a normal workflow state. Keep serving
                    # the live screenshot so the user can complete verification in-panel.
                    LOGGER.warning(
                        "midtown_live_session_frame_security_verification account_id=%s error_type=%s error_message=%s",
                        account_id,
                        type(exc).__name__,
                        exc,
                        exc_info=True,
                    )
                    _log_event(
                        "midtown_browser_security_verification_required",
                        account_id=account_id,
                        current_url=getattr(page, "url", None),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                    status = _security_verification_status(
                        account=account,
                        current_url=getattr(page, "url", None) or MIDTOWN_LOGIN_URL,
                        order_count=0,
                    )
                    _apply_midtown_viewport_metadata(status, page)
                    security_required = True

                if not security_required:
                    status = _build_midtown_status_from_page(account, page)

                image_data_url, width, height, source = _capture_or_cached_frame(account_id, page)

                if not security_required:
                    if source == "none":
                        status.status = "no_frame_available"
                        status.message = "Midtown browser screenshot is temporarily unavailable."
                    elif source == "cache":
                        status.status = "frame_capture_failed"
                        status.message = "Showing the last Midtown screenshot while the live view recovers."

                payload = _assemble_frame_payload(
                    account_id,
                    status,
                    image_data_url=image_data_url,
                    image_width=width,
                    image_height=height,
                    frame_available=source != "none",
                    page=page,
                )
                _log_event(
                    "midtown_live_session_frame",
                    account_id=account_id,
                    endpoint_status=200,
                    image_bytes_size=payload["image_bytes_size"],
                    captured_at=payload["captured_at"],
                    page_url=payload["page_url"],
                    page_title=payload["page_title"],
                    status=status.status,
                    frame_source=source,
                    registry_contains_account=_midtown_live_metadata_contains(account_id),
                )
                return payload
        except (RetailerBrowserConfigurationError, MidtownBrowserBusyError):
            raise
        except Exception as exc:  # noqa: BLE001 - the frame endpoint must never crash
            LOGGER.exception(
                "midtown_live_session_frame_unhandled account_id=%s error_type=%s error_message=%s",
                account_id,
                type(exc).__name__,
                exc,
            )
            return _offline_frame_payload(account, account_id)


def _offline_frame_payload(account: RetailerAccount, account_id: int) -> dict[str, Any]:
    """Build a controlled frame payload when the live browser cannot be reached.

    Serves the last successful screenshot when available; otherwise returns a
    ``no_frame_available`` payload so the endpoint stays at HTTP 200.
    """
    try:
        state = _read_browser_state(account_id)
    except Exception:  # noqa: BLE001 - corrupt state must not block a controlled response
        state = {}
    if state:
        status = _status_from_browser_state(account, state)
    else:
        status = _login_required_status(account=account, current_url=MIDTOWN_LOGIN_URL)
    status.live_session_active = True
    status.process_id = os.getpid()

    cached = _read_last_screenshot(account_id)
    if cached and cached.get("image_data_url"):
        status.status = "frame_capture_failed"
        status.message = "Showing the last Midtown screenshot while the live view recovers."
        image_data_url = str(cached.get("image_data_url") or "")
        width = int(cached.get("image_width") or 1440)
        height = int(cached.get("image_height") or 1100)
        frame_available = True
    else:
        status.status = "no_frame_available"
        status.message = "Midtown browser is temporarily unavailable. Retry shortly."
        image_data_url, width, height, frame_available = "", 1440, 1100, False

    return _assemble_frame_payload(
        account_id,
        status,
        image_data_url=image_data_url,
        image_width=width,
        image_height=height,
        frame_available=frame_available,
        page=None,
    )


def click_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
    x: float,
    y: float,
    button: str = "left",
    click_count: int = 1,
    displayed_image_width: int | None = None,
    displayed_image_height: int | None = None,
    viewport_width: int | None = None,
    viewport_height: int | None = None,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        state = _read_browser_state(account_id)
        target_url = str(
            state.get("current_url")
            or state.get("orders_url")
            or state.get("last_known_url")
            or MIDTOWN_ORDERS_URL
        )
        with _midtown_request_browser(account, target_url=target_url) as (_, context, page):
            viewport = getattr(page, "viewport_size", None) or {}
            effective_viewport_width = viewport_width or viewport.get("width")
            effective_viewport_height = viewport_height or viewport.get("height")
            scaled_x = _scale_midtown_coordinate(x, displayed_size=displayed_image_width, viewport_size=effective_viewport_width)
            scaled_y = _scale_midtown_coordinate(y, displayed_size=displayed_image_height, viewport_size=effective_viewport_height)
            page.mouse.click(scaled_x, scaled_y, button=button, click_count=click_count)
            _best_effort_wait_for_load(page)
            status = _build_midtown_status_from_page(account, page)
            active = _capture_midtown_active_element(page)
            status.active_element_tag = active.get("tag")
            status.active_element_name = active.get("name")
            status.active_element_type = active.get("type")
            status.active_element_placeholder = active.get("placeholder")
            last_click = {
                "x": x,
                "y": y,
                "button": button,
                "click_count": click_count,
                "displayed_image_width": displayed_image_width,
                "displayed_image_height": displayed_image_height,
                "viewport_width": effective_viewport_width,
                "viewport_height": effective_viewport_height,
                "scaled_x": scaled_x,
                "scaled_y": scaled_y,
                "page_url": getattr(page, "url", None),
                "page_title": page.title() if hasattr(page, "title") else None,
                "captured_at": utc_now().isoformat(),
            }
            state.update(
                {
                    "status": status.status,
                    "current_url": getattr(page, "url", None),
                    "orders_url": status.orders_url,
                    "order_count": status.order_count,
                    "authenticated": status.authenticated,
                    "message": status.message,
                    "last_updated_at": utc_now().isoformat(),
                    "last_click": last_click,
                    "last_interaction_type": "click",
                    "last_click_active_element": active,
                }
            )
            _write_browser_state(account_id, state)
            _log_midtown_interaction(
                event="midtown_browser_click_forwarded",
                account_id=account_id,
                page=page,
                status=status,
                displayed_image_width=displayed_image_width,
                displayed_image_height=displayed_image_height,
                received_x=x,
                received_y=y,
                playwright_x=scaled_x,
                playwright_y=scaled_y,
            )
            return status


def type_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
    text: str,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        state = _read_browser_state(account_id)
        target_url = str(
            state.get("current_url")
            or state.get("orders_url")
            or state.get("last_known_url")
            or MIDTOWN_ORDERS_URL
        )
        with _midtown_request_browser(account, target_url=target_url) as (_, context, page):
            last_click = state.get("last_click") or {}
            replay_x = last_click.get("scaled_x", last_click.get("x"))
            replay_y = last_click.get("scaled_y", last_click.get("y"))
            if replay_x is not None and replay_y is not None:
                page.mouse.click(float(replay_x), float(replay_y))
                _best_effort_wait_for_load(page)
            if text:
                try:
                    page.keyboard.type(text)
                except Exception:
                    page.keyboard.insert_text(text)
            status = _build_midtown_status_from_page(account, page)
            active = _capture_midtown_active_element(page)
            status.active_element_tag = active.get("tag")
            status.active_element_name = active.get("name")
            status.active_element_type = active.get("type")
            status.active_element_placeholder = active.get("placeholder")
            state.update(
                {
                    "status": status.status,
                    "current_url": getattr(page, "url", None),
                    "orders_url": status.orders_url,
                    "order_count": status.order_count,
                    "authenticated": status.authenticated,
                    "message": status.message,
                    "last_updated_at": utc_now().isoformat(),
                    "last_interaction_type": "type",
                    "last_typed_text_length": len(text),
                }
            )
            _write_browser_state(account_id, state)
            _log_midtown_interaction(
                event="midtown_browser_type_forwarded",
                account_id=account_id,
                page=page,
                status=status,
                received_x=float(last_click.get("x")) if last_click.get("x") is not None else None,
                received_y=float(last_click.get("y")) if last_click.get("y") is not None else None,
                playwright_x=float(replay_x) if replay_x is not None else None,
                playwright_y=float(replay_y) if replay_y is not None else None,
            )
            return status


def key_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
    key: str,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        state = _read_browser_state(account_id)
        target_url = str(
            state.get("current_url")
            or state.get("orders_url")
            or state.get("last_known_url")
            or MIDTOWN_ORDERS_URL
        )
        with _midtown_request_browser(account, target_url=target_url) as (_, context, page):
            page.keyboard.press(key)
            _best_effort_wait_for_load(page)
            status = _build_midtown_status_from_page(account, page)
            state.update(
                {
                    "status": status.status,
                    "current_url": getattr(page, "url", None),
                    "orders_url": status.orders_url,
                    "order_count": status.order_count,
                    "authenticated": status.authenticated,
                    "message": status.message,
                    "last_updated_at": utc_now().isoformat(),
                    "last_interaction_type": "key",
                    "last_key": key,
                }
            )
            _write_browser_state(account_id, state)
            return status


def retry_midtown_browser_live_session(
    session: Session,
    *,
    owner_user_id: int,
) -> MidtownBrowserStatus:
    account = _midtown_account_for_user_or_404(session, owner_user_id=owner_user_id)
    account_id = int(account.id or 0)
    with _midtown_single_operation(account_id):
        state = _read_browser_state(account_id)
        target_url = str(
            state.get("current_url")
            or state.get("orders_url")
            or state.get("last_known_url")
            or MIDTOWN_ORDERS_URL
        )
        with _midtown_request_browser(account, target_url=target_url) as (_, context, page):
            page.goto(MIDTOWN_ORDERS_URL, wait_until="domcontentloaded")
            _best_effort_wait_for_load(page)
            status = _build_midtown_status_from_page(account, page)
            state.update(
                {
                    "status": status.status,
                    "current_url": getattr(page, "url", None),
                    "orders_url": status.orders_url,
                    "order_count": status.order_count,
                    "authenticated": status.authenticated,
                    "message": status.message,
                    "last_updated_at": utc_now().isoformat(),
                    "last_interaction_type": "retry",
                }
            )
            _write_browser_state(account_id, state)
            if status.status == "ready":
                _save_session_state(context, account_id=account_id)
            return status
