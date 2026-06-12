from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup
from sqlmodel import Session, select

from app.models import RetailerAccount, RetailerOrderSnapshot, RetailerSyncRun
from app.services.retailer_sync.midtown_parser import (
    MidtownOrderNumberError,
    parse_midtown_order_detail,
)
from app.services.retailer_sync.retailer_order_persistence import (
    upsert_retailer_order_snapshots,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Saved order pages are small; cap the upload to avoid pathological inputs.
MAX_HTML_BYTES = 8 * 1024 * 1024

MIDTOWN_HTML_FAILURE_ROOT = (
    Path(__file__).resolve().parents[5] / "data" / "midtown_html_upload_failures"
)

_VISIBLE_TEXT_EXCERPT_LIMIT = 5000
_ORDER_HASH_LINK_RE = re.compile(r"order\s*#", flags=re.IGNORECASE)


@dataclass
class MidtownHtmlPageDiagnostics:
    title: str | None
    page_length: int
    order_item_count: int
    order_number_link_count: int
    visible_text_excerpt: str
    has_right_contents: bool
    has_info_container: bool
    saved_html_path: str | None = None
    parsed: dict | None = field(default=None)

    def to_dict(self) -> dict:
        return asdict(self)

    def debug_response(self) -> dict:
        return {
            "title": self.title,
            "page_length": self.page_length,
            "order_item_count": self.order_item_count,
            "has_right_contents": self.has_right_contents,
            "has_info_container": self.has_info_container,
            "visible_text_excerpt": self.visible_text_excerpt,
        }


class MidtownHtmlImportError(RuntimeError):
    """Raised when a saved Midtown order HTML file cannot be imported."""

    def __init__(self, message: str, *, diagnostics: MidtownHtmlPageDiagnostics | dict | None = None):
        super().__init__(message)
        if isinstance(diagnostics, MidtownHtmlPageDiagnostics):
            self.diagnostics = diagnostics.to_dict()
        else:
            self.diagnostics = diagnostics


def _normalize_saved_midtown_html(html_text: str) -> str:
    """Parse browser-saved HTML with BeautifulSoup and return a normalized document.

    Saved pages may include broken tags or encoding quirks; normalizing through
    the parser keeps downstream extraction stable while preserving links, images,
    and table rows the Midtown order parser expects.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    if soup.body is not None:
        return str(soup)
    return str(soup)


def analyze_midtown_saved_html(html_text: str) -> MidtownHtmlPageDiagnostics:
    """Collect page structure diagnostics for saved Midtown order HTML uploads."""
    normalized = _normalize_saved_midtown_html(html_text)
    soup = BeautifulSoup(normalized, "html.parser")
    title_tag = soup.title.get_text(strip=True) if soup.title else None
    visible = soup.get_text("\n", strip=True)
    order_number_link_count = 0
    for anchor in soup.find_all("a"):
        link_text = anchor.get_text(" ", strip=True)
        href = anchor.get("href") or ""
        if _ORDER_HASH_LINK_RE.search(link_text) or _ORDER_HASH_LINK_RE.search(href):
            order_number_link_count += 1
    return MidtownHtmlPageDiagnostics(
        title=title_tag,
        page_length=len(html_text),
        order_item_count=len(soup.select(".order-item")),
        order_number_link_count=order_number_link_count,
        visible_text_excerpt=visible[:_VISIBLE_TEXT_EXCERPT_LIMIT],
        has_right_contents=soup.select_one("#right-contents") is not None,
        has_info_container=soup.select_one(".info-container") is not None,
    )


def save_failed_midtown_html_upload(
    html_text: str,
    *,
    owner_user_id: int,
    source_filename: str | None,
    retailer_order_number: str | None,
) -> Path:
    """Persist uploaded HTML when import fails so we can inspect it offline."""
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    order_part = retailer_order_number or "unknown-order"
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", (source_filename or "upload.html").strip())[:120]
    target_dir = MIDTOWN_HTML_FAILURE_ROOT / str(owner_user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{stamp}_{order_part}_{safe_name}"
    path.write_text(html_text, encoding="utf-8")
    return path


def _parsed_preview(detail) -> dict:
    return {
        "retailer_order_number": detail.retailer_order_number,
        "order_status": detail.order_status,
        "order_date": detail.order_date.isoformat() if detail.order_date else None,
        "order_total": str(detail.order_total) if detail.order_total is not None else None,
        "items_parsed": len(detail.items),
        "item_titles": [item.title for item in detail.items[:25]],
        "parse_diagnostics": detail.parse_diagnostics,
    }


def parse_saved_midtown_order_html(html_text: str):
    """Extract order header, line items, cover URLs, and totals from saved HTML."""
    normalized = _normalize_saved_midtown_html(html_text)
    return parse_midtown_order_detail(normalized)


def debug_midtown_saved_html(html_text: str) -> dict:
    """Return lightweight parser debug fields for a saved Midtown order upload."""
    return analyze_midtown_saved_html(html_text).debug_response()


def _get_or_create_midtown_account(
    session: Session, *, owner_user_id: int
) -> RetailerAccount:
    """Reuse the user's existing Midtown account, or create a manual-upload one.

    The HTML upload flow does not need live credentials, but persistence keys
    snapshots to a ``RetailerAccount``. We reuse a connected account when one
    exists, otherwise create a credential-less placeholder so manual uploads
    work even before the retailer is connected.
    """
    account = session.exec(
        select(RetailerAccount).where(
            RetailerAccount.owner_user_id == owner_user_id,
            RetailerAccount.retailer == "midtown",
        )
    ).first()
    if account is not None:
        return account
    account = RetailerAccount(
        owner_user_id=owner_user_id,
        retailer="midtown",
        display_name="Midtown Comics",
        username="manual-html-upload",
        encrypted_password="",
        credential_version=1,
        status="manual_upload",
        sync_enabled=False,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    session.add(account)
    session.flush()
    return account


def import_midtown_order_from_html(
    session: Session,
    *,
    owner_user_id: int,
    html_text: str,
    source_filename: str | None = None,
) -> tuple[int, str, dict]:
    """Parse a saved Midtown order HTML page and persist it as a snapshot.

    Returns ``(snapshot_id, retailer_order_number, stats)``. Raises
    :class:`MidtownHtmlImportError` with a user-facing message on any failure.
    """
    if not html_text or not html_text.strip():
        raise MidtownHtmlImportError("The uploaded file was empty.")

    page_diagnostics = analyze_midtown_saved_html(html_text)

    try:
        detail = parse_saved_midtown_order_html(html_text)
    except MidtownOrderNumberError as exc:
        saved_path = save_failed_midtown_html_upload(
            html_text,
            owner_user_id=owner_user_id,
            source_filename=source_filename,
            retailer_order_number=None,
        )
        page_diagnostics.saved_html_path = str(saved_path)
        page_diagnostics.parsed = {"error": "parser_no_order_number", "items_parsed": 0}
        raise MidtownHtmlImportError(
            "Could not find a Midtown order number in this file. Make sure you saved the "
            "order detail page (the page that shows Order #...), not the order list.",
            diagnostics=page_diagnostics,
        ) from exc

    page_diagnostics.parsed = _parsed_preview(detail)

    if not detail.items:
        saved_path = save_failed_midtown_html_upload(
            html_text,
            owner_user_id=owner_user_id,
            source_filename=source_filename,
            retailer_order_number=detail.retailer_order_number,
        )
        page_diagnostics.saved_html_path = str(saved_path)
        raise MidtownHtmlImportError(
            "No order items were found in this file. On the Midtown order page press "
            'Ctrl+S and save as "Webpage, HTML Only", then upload that .html file.',
            diagnostics=page_diagnostics,
        )

    account = _get_or_create_midtown_account(session, owner_user_id=owner_user_id)
    run = RetailerSyncRun(
        owner_user_id=owner_user_id,
        retailer_account_id=int(account.id or 0),
        retailer="midtown",
        status="html_upload",
        started_at=utc_now(),
        summary_json={
            "sync_path": "html_upload",
            "mode": "manual_html",
            "source_filename": source_filename,
            "retailer_order_number": detail.retailer_order_number,
        },
    )
    session.add(run)
    session.flush()

    summary = upsert_retailer_order_snapshots(
        session,
        account=account,
        sync_run=run,
        orders=[detail],
    )
    run.status = "completed"
    run.finished_at = utc_now()
    session.add(run)
    session.commit()

    snapshot = session.exec(
        select(RetailerOrderSnapshot).where(
            RetailerOrderSnapshot.owner_user_id == owner_user_id,
            RetailerOrderSnapshot.retailer == "midtown",
            RetailerOrderSnapshot.retailer_order_number == detail.retailer_order_number,
        )
    ).first()
    if snapshot is None or snapshot.id is None:
        raise MidtownHtmlImportError("The order snapshot could not be created.")

    stats = {
        "items_imported": summary.items_imported,
        "items_seen": summary.items_seen,
        "items_updated": summary.items_updated,
    }
    return int(snapshot.id), detail.retailer_order_number, stats
