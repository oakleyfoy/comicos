"""Shared upload/parse/persist pipeline for saved retailer order HTML.

This is the retailer-agnostic counterpart to ``midtown_html_import``. It selects
a parser from :mod:`retailer_html_parsers`, normalizes the order, and persists it
through the shared snapshot persistence layer. Confirm/materialization happens
later via the existing common ``confirm_retailer_order`` path, so it is identical
for every retailer.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlmodel import Session, select

from app.models import RetailerAccount, RetailerOrderSnapshot, RetailerSyncRun
from app.services.retailer_sync.midtown_html_import import (
    MAX_HTML_BYTES,
    import_midtown_order_from_html,
)
from app.services.retailer_sync.retailer_html_common import RetailerHtmlImportError
from app.services.retailer_sync.retailer_html_parsers import (
    MidtownOrderNumberError,
    get_retailer_html_parser,
)
from app.services.retailer_sync.retailer_order_persistence import (
    upsert_retailer_order_snapshots,
)

logger = logging.getLogger(__name__)

_HTML_FAILURE_ROOT = Path(__file__).resolve().parents[5] / "data" / "retailer_html_upload_failures"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class RetailerHtmlImportResult:
    order_id: int
    retailer: str
    retailer_order_number: str
    item_count: int
    parser_status: str
    warnings: tuple[str, ...] = ()


def _save_failed_upload(
    html_text: str,
    *,
    retailer: str,
    owner_user_id: int,
    source_filename: str | None,
    retailer_order_number: str | None,
) -> Path:
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    order_part = retailer_order_number or "unknown-order"
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", (source_filename or "upload.html").strip())[:120]
    target_dir = _HTML_FAILURE_ROOT / retailer / str(owner_user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{stamp}_{order_part}_{safe_name}"
    path.write_text(html_text, encoding="utf-8")
    return path


_RETAILER_DISPLAY_NAMES = {
    "midtown": "Midtown Comics",
    "dcbs": "DCBS / Discount Comic Book Service",
    "third_eye": "Third Eye Comics",
    "mycomicshop": "MyComicShop",
    "unknown": "Saved Order Upload",
}


def _get_or_create_retailer_account(
    session: Session, *, owner_user_id: int, retailer: str
) -> RetailerAccount:
    """Reuse the user's retailer account, or create a credential-less upload one."""
    account = session.exec(
        select(RetailerAccount).where(
            RetailerAccount.owner_user_id == owner_user_id,
            RetailerAccount.retailer == retailer,
        )
    ).first()
    if account is not None:
        return account
    account = RetailerAccount(
        owner_user_id=owner_user_id,
        retailer=retailer,
        display_name=_RETAILER_DISPLAY_NAMES.get(retailer, retailer.title()),
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


def _synthesize_order_number(source_filename: str | None) -> str:
    stamp = utc_now().strftime("%Y%m%d%H%M%S")
    base = re.sub(r"[^A-Za-z0-9]+", "", (source_filename or "upload").split(".")[0])[:20] or "upload"
    return f"UP-{base}-{stamp}"


def debug_retailer_order_html(retailer: str, html_text: str) -> dict:
    parser = get_retailer_html_parser(retailer)
    return parser.analyze(html_text).debug_response()


def import_retailer_order_from_html(
    session: Session,
    *,
    owner_user_id: int,
    retailer: str,
    html_text: str,
    source_filename: str | None = None,
) -> RetailerHtmlImportResult:
    """Parse a saved retailer order HTML page and persist it as a snapshot.

    Raises :class:`RetailerHtmlImportError` with a user-facing message and
    structured diagnostics on failure. Midtown delegates to its proven parser
    so existing behavior is preserved exactly.
    """
    parser = get_retailer_html_parser(retailer)
    retailer_key = parser.retailer_key

    if not html_text or not html_text.strip():
        raise RetailerHtmlImportError("The uploaded file was empty.")

    if retailer_key == "midtown":
        # Preserve the battle-tested Midtown flow (messages, diagnostics, failures).
        order_id, order_number, stats = import_midtown_order_from_html(
            session,
            owner_user_id=owner_user_id,
            html_text=html_text,
            source_filename=source_filename,
        )
        return RetailerHtmlImportResult(
            order_id=order_id,
            retailer="midtown",
            retailer_order_number=order_number,
            item_count=int(stats.get("items_imported", 0)),
            parser_status=parser.status,
        )

    diagnostics = parser.analyze(html_text)
    warnings: list[str] = []

    try:
        detail = parser.parse(html_text)
    except (RetailerHtmlImportError, MidtownOrderNumberError) as exc:
        saved_path = _save_failed_upload(
            html_text,
            retailer=retailer_key,
            owner_user_id=owner_user_id,
            source_filename=source_filename,
            retailer_order_number=None,
        )
        diagnostics.saved_html_path = str(saved_path)
        diagnostics.parsed = {"error": "parse_failed", "items_parsed": 0}
        raise RetailerHtmlImportError(str(exc), diagnostics=diagnostics) from exc

    if not detail.items:
        saved_path = _save_failed_upload(
            html_text,
            retailer=retailer_key,
            owner_user_id=owner_user_id,
            source_filename=source_filename,
            retailer_order_number=detail.retailer_order_number or None,
        )
        diagnostics.saved_html_path = str(saved_path)
        diagnostics.parsed = {
            "retailer_order_number": detail.retailer_order_number or None,
            "items_parsed": 0,
            "parse_diagnostics": detail.parse_diagnostics,
        }
        raise RetailerHtmlImportError(
            "No order items were found in this file. Open the retailer's order detail page, "
            "save it as \"Webpage, HTML Only\", and upload that .html file.",
            diagnostics=diagnostics,
        )

    if not (detail.retailer_order_number or "").strip():
        detail.retailer_order_number = _synthesize_order_number(source_filename)
        warnings.append(
            "No order number was detected, so a temporary one was generated. "
            "You can still review and confirm this order."
        )

    account = _get_or_create_retailer_account(
        session, owner_user_id=owner_user_id, retailer=retailer_key
    )
    run = RetailerSyncRun(
        owner_user_id=owner_user_id,
        retailer_account_id=int(account.id or 0),
        retailer=retailer_key,
        status="html_upload",
        started_at=utc_now(),
        summary_json={
            "sync_path": "html_upload",
            "mode": "manual_html",
            "source_filename": source_filename,
            "retailer_order_number": detail.retailer_order_number,
            "parser_status": parser.status,
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
            RetailerOrderSnapshot.retailer == retailer_key,
            RetailerOrderSnapshot.retailer_order_number == detail.retailer_order_number,
        )
    ).first()
    if snapshot is None or snapshot.id is None:
        raise RetailerHtmlImportError("The order snapshot could not be created.")

    if parser.status == "beta":
        warnings.append(
            f"{parser.display_name} support is in beta. Please review the detected books carefully "
            "before confirming."
        )

    return RetailerHtmlImportResult(
        order_id=int(snapshot.id),
        retailer=retailer_key,
        retailer_order_number=detail.retailer_order_number,
        item_count=int(summary.items_imported),
        parser_status=parser.status,
        warnings=tuple(warnings),
    )
