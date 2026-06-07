"""P88-04 marketplace adapter diagnostics (read-only)."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, func, select

from app.models.p88_marketplace_listing import MarketplaceSearchRun, P88MarketplaceListing
from app.schemas.p88_marketplace_comparison import MarketplaceDiagnosticsRead, MarketplaceDiagnosticsRow
from app.services.marketplace.marketplace_registry import list_supported_marketplace_codes, marketplace_definition


def _adapter_status(code: str) -> str:
    definition = marketplace_definition(code)
    if definition.supports_search:
        return "READY"
    return "NOT_SUPPORTED"


def build_marketplace_diagnostics(session: Session) -> MarketplaceDiagnosticsRead:
    rows: list[MarketplaceDiagnosticsRow] = []
    recent_errors: list[str] = []
    runs = session.exec(select(MarketplaceSearchRun).order_by(MarketplaceSearchRun.id.desc()).limit(20)).all()
    for run in runs:
        for err in run.errors_json or []:
            if isinstance(err, str):
                recent_errors.append(err)
        if len(recent_errors) >= 10:
            break

    for code in list_supported_marketplace_codes():
        definition = marketplace_definition(code)
        last_verified = session.exec(
            select(func.max(P88MarketplaceListing.last_verified_at)).where(P88MarketplaceListing.marketplace == code)
        ).one()
        listing_count = session.exec(
            select(func.count())
            .select_from(P88MarketplaceListing)
            .where(P88MarketplaceListing.marketplace == code)
        ).one()
        if isinstance(listing_count, tuple):
            listing_count = listing_count[0]
        adapter_status = _adapter_status(code)
        rows.append(
            MarketplaceDiagnosticsRow(
                marketplace=code,
                marketplace_name=definition.display_name,
                adapter_status=adapter_status,
                marketplace_support_status="SUPPORTED" if definition.supports_search else "SHELL",
                supports_search=definition.supports_search,
                supports_listing_lookup=definition.supports_listing_lookup,
                supports_price_tracking=definition.supports_price_tracking,
                supports_refresh=definition.supports_refresh,
                listing_count=int(listing_count or 0),
                last_successful_refresh=last_verified if isinstance(last_verified, datetime) else None,
                last_successful_search=last_verified if isinstance(last_verified, datetime) else None,
            )
        )

    last_run = runs[0] if runs else None
    return MarketplaceDiagnosticsRead(
        adapters=rows,
        recent_errors=recent_errors[:10],
        last_search_run_at=last_run.created_at if last_run else None,
    )
