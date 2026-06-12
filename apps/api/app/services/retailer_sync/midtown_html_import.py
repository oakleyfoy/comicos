from __future__ import annotations

from datetime import datetime, timezone

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


class MidtownHtmlImportError(RuntimeError):
    """Raised when a saved Midtown order HTML file cannot be imported."""


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


def parse_saved_midtown_order_html(html_text: str):
    """Extract order header, line items, cover URLs, and totals from saved HTML."""
    normalized = _normalize_saved_midtown_html(html_text)
    return parse_midtown_order_detail(normalized)


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

    try:
        detail = parse_saved_midtown_order_html(html_text)
    except MidtownOrderNumberError as exc:
        raise MidtownHtmlImportError(
            "Could not find a Midtown order number in this file. Make sure you saved the "
            "order detail page (the page that shows Order #...), not the order list."
        ) from exc

    if not detail.items:
        raise MidtownHtmlImportError(
            "No order items were found in this file. On the Midtown order page press "
            "Ctrl+S and save as \"Webpage, HTML Only\", then upload that .html file."
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
