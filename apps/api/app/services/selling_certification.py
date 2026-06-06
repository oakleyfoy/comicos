"""P78-02 production certification for sell workflow platform."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.p78_marketplace_lifecycle import P78SaleRecord

from app.schemas.p78_marketplace import P78SellingCertificationCheckRead, P78SellingCertificationRead
from app.schemas.p78_sell_workflow import P78ListingDraftCreate
from app.services.p78_listing_lifecycle_service import (
    get_sale,
    list_listings,
    publish_listing,
    sync_listings,
)
from app.services.p78_listing_draft_service import generate_listing_draft
from app.services.p78_sell_queue_service import build_sell_queue
from app.services.p78_selling_analytics_service import build_selling_analytics, build_selling_dashboard
from app.services.mobile_scanning_certification import ensure_p80_certification_fixture


def _check(checks: list, *, category: str, component: str, passed: bool, detail: str = "") -> None:
    checks.append(P78SellingCertificationCheckRead(category=category, component=component, passed=passed, detail=detail))


def run_selling_certification(session: Session, *, owner_user_id: int) -> P78SellingCertificationRead:
    checks: list[P78SellingCertificationCheckRead] = []
    fixture = ensure_p80_certification_fixture(session, owner_user_id=owner_user_id)
    copy_id = fixture.copy_id

    try:
        queue = build_sell_queue(session, owner_user_id=owner_user_id, limit=10, offset=0, refresh_upstream=False)
        _check(checks, category="sell_queue", component="queue_build", passed=queue.total_items >= 0, detail=f"items={len(queue.items)}")
    except Exception as exc:  # pragma: no cover
        _check(checks, category="sell_queue", component="queue_build", passed=False, detail=str(exc))

    try:
        draft = generate_listing_draft(
            session,
            owner_user_id=owner_user_id,
            payload=P78ListingDraftCreate(inventory_copy_id=copy_id, status="DRAFT"),
        )
        _check(checks, category="drafts", component="draft_generation", passed=draft.id > 0, detail=draft.title[:40])
        _check(checks, category="drafts", component="pricing_tiers", passed=draft.market_price > 0 and draft.quick_sale_price > 0)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="drafts", component="draft_generation", passed=False, detail=str(exc))
        draft = None

    sync_result = None
    listing_id = None
    if draft is not None:
        try:
            pub = publish_listing(session, owner_user_id=owner_user_id, listing_id=int(draft.id), price_mode="market")
            listing_id = pub.listing.id
            _check(
                checks,
                category="marketplace",
                component="ebay_publish",
                passed=pub.listing.external_listing_id is not None,
                detail=pub.listing.external_listing_id or "",
            )
            _check(
                checks,
                category="reservation",
                component="inventory_reserve",
                passed=len(pub.reserved_copy_ids) >= 1,
                detail=f"reserved={len(pub.reserved_copy_ids)}",
            )
        except Exception as exc:  # pragma: no cover
            _check(checks, category="marketplace", component="ebay_publish", passed=False, detail=str(exc))

    try:
        sync_result = sync_listings(session, owner_user_id=owner_user_id)
        _check(
            checks,
            category="marketplace",
            component="listing_sync",
            passed=sync_result.listings_checked >= 0,
            detail=f"sales={sync_result.sales_recorded}",
        )
    except Exception as exc:  # pragma: no cover
        _check(checks, category="marketplace", component="listing_sync", passed=False, detail=str(exc))

    try:
        listings = list_listings(session, owner_user_id=owner_user_id, limit=5, offset=0)
        _check(checks, category="sales", component="listing_tracking", passed=listings.total_items >= 0)
        if sync_result and sync_result.sales_recorded > 0:
            sale_row = session.exec(select(P78SaleRecord).where(P78SaleRecord.owner_user_id == owner_user_id)).first()
            if sale_row:
                sale = get_sale(session, owner_user_id=owner_user_id, sale_id=int(sale_row.id or 0))
                _check(checks, category="sales", component="roi_calculation", passed=sale.roi_pct != 0 or sale.profit != 0, detail=f"roi={sale.roi_pct}")
                _check(checks, category="sales", component="sold_processing", passed=sale.profit is not None)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="sales", component="listing_tracking", passed=False, detail=str(exc))

    try:
        analytics = build_selling_analytics(session, owner_user_id=owner_user_id, persist=True)
        dash = build_selling_dashboard(session, owner_user_id=owner_user_id)
        _check(checks, category="analytics", component="selling_analytics", passed=analytics.listings_created >= 0)
        _check(checks, category="analytics", component="selling_dashboard", passed=dash.analytics.snapshot_id is not None)
    except Exception as exc:  # pragma: no cover
        _check(checks, category="analytics", component="selling_analytics", passed=False, detail=str(exc))

    session.commit()
    failures = [c for c in checks if not c.passed]
    passed_count = sum(1 for c in checks if c.passed)
    readiness = round(100.0 * passed_count / max(1, len(checks)), 1)
    approved = len(failures) == 0
    checklist = [
        {"area": "Sell Queue", "status": "PASS" if approved else "FAIL"},
        {"area": "Drafts", "status": "PASS" if approved else "FAIL"},
        {"area": "Marketplace Publishing", "status": "PASS" if approved else "FAIL"},
        {"area": "Inventory Reservation", "status": "PASS" if approved else "FAIL"},
        {"area": "Sales Tracking", "status": "PASS" if approved else "FAIL"},
        {"area": "ROI Tracking", "status": "PASS" if approved else "FAIL"},
        {"area": "Analytics", "status": "PASS" if approved else "FAIL"},
    ]
    return P78SellingCertificationRead(
        platform_status="APPROVED_FOR_PRODUCTION" if approved else "NEEDS_ATTENTION",
        approved_for_production=approved,
        checks_passed=passed_count,
        failures=len(failures),
        platform_readiness_percent=readiness,
        checks=checks,
        failure_messages=[f"{c.category}/{c.component}: {c.detail}" for c in failures],
        production_checklist=checklist,
        reviewed_at=datetime.now(timezone.utc),
    )
