from __future__ import annotations

from decimal import Decimal

from sqlalchemy import and_, func, or_
from sqlmodel import Session, select

from app.models import InventoryCopy, MarketForecast, Order, ScanImage
from app.models.data_integrity import DataIntegrityCheck, DataIntegrityIssue
from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingMapping
from app.schemas.data_integrity import (
    DataIntegrityCheckDetail,
    DataIntegrityCheckListResponse,
    DataIntegrityCheckRead,
    DataIntegrityIssueListResponse,
    DataIntegrityIssueRead,
)


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _issue(
    *,
    issue_type: str,
    severity: str,
    entity_type: str,
    entity_id: int | None,
    issue_message: str,
    issue_payload_json: dict,
) -> dict:
    return {
        "issue_type": issue_type,
        "severity": severity,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "issue_message": issue_message,
        "issue_payload_json": issue_payload_json,
    }


def check_inventory_integrity(session: Session, *, owner_user_id: int) -> list[dict]:
    rows = session.exec(
        select(InventoryCopy).where(
            InventoryCopy.user_id == owner_user_id,
            or_(
                InventoryCopy.acquisition_cost < Decimal("0"),
                InventoryCopy.current_fmv < Decimal("0"),
            ),
        )
    ).all()
    issues: list[dict] = []
    for row in rows:
        issues.append(
            _issue(
                issue_type="negative_inventory_value",
                severity="HIGH",
                entity_type="inventory_copy",
                entity_id=row.id,
                issue_message="Inventory copy contains a negative monetary value.",
                issue_payload_json={
                    "acquisition_cost": str(row.acquisition_cost),
                    "current_fmv": str(row.current_fmv) if row.current_fmv is not None else None,
                },
            )
        )
    return issues


def check_order_integrity(session: Session, *, owner_user_id: int) -> list[dict]:
    rows = session.exec(
        select(Order).where(
            Order.user_id == owner_user_id,
            or_(
                Order.total_amount < Decimal("0"),
                Order.shipping_amount < Decimal("0"),
                Order.tax_amount < Decimal("0"),
                Order.total_amount < (Order.shipping_amount + Order.tax_amount),
            ),
        )
    ).all()
    return [
        _issue(
            issue_type="invalid_order_total",
            severity="HIGH",
            entity_type="order",
            entity_id=row.id,
            issue_message="Order totals are internally inconsistent.",
            issue_payload_json={
                "shipping_amount": str(row.shipping_amount),
                "tax_amount": str(row.tax_amount),
                "total_amount": str(row.total_amount),
            },
        )
        for row in rows
    ]


def check_listing_integrity(session: Session, *, owner_user_id: int) -> list[dict]:
    listings = session.exec(
        select(MarketplaceListing).where(
            MarketplaceListing.owner_id == owner_user_id,
            or_(MarketplaceListing.asking_price < Decimal("0"), MarketplaceListing.quantity < 0),
        )
    ).all()
    issues = [
        _issue(
            issue_type="invalid_listing_value",
            severity="HIGH",
            entity_type="marketplace_listing",
            entity_id=row.id,
            issue_message="Marketplace listing contains an invalid price or quantity.",
            issue_payload_json={"asking_price": str(row.asking_price), "quantity": row.quantity, "status": row.status},
        )
        for row in listings
    ]

    mappings = session.exec(
        select(MarketplaceListingMapping)
        .join(MarketplaceListing, MarketplaceListing.id == MarketplaceListingMapping.listing_id)
        .where(
            MarketplaceListing.owner_id == owner_user_id,
            MarketplaceListingMapping.sync_status == "synced",
            MarketplaceListingMapping.external_listing_id.is_(None),  # type: ignore[union-attr]
        )
    ).all()
    for row in mappings:
        issues.append(
            _issue(
                issue_type="missing_external_listing_id",
                severity="MEDIUM",
                entity_type="marketplace_listing_mapping",
                entity_id=row.id,
                issue_message="Synced marketplace listing mapping is missing an external listing id.",
                issue_payload_json={"listing_id": row.listing_id, "sync_status": row.sync_status},
            )
        )
    return issues


def check_scan_integrity(session: Session, *, owner_user_id: int) -> list[dict]:
    rows = session.exec(
        select(ScanImage).where(
            ScanImage.owner_user_id == owner_user_id,
            or_(
                ScanImage.file_size_bytes <= 0,
                and_(ScanImage.is_duplicate.is_(True), ScanImage.duplicate_of_scan_image_id.is_(None)),  # type: ignore[union-attr]
            ),
        )
    ).all()
    issues: list[dict] = []
    for row in rows:
        issue_type = "duplicate_reference_missing" if row.is_duplicate and row.duplicate_of_scan_image_id is None else "invalid_scan_file_size"
        issues.append(
            _issue(
                issue_type=issue_type,
                severity="MEDIUM",
                entity_type="scan_image",
                entity_id=row.id,
                issue_message="Scan image metadata is inconsistent.",
                issue_payload_json={
                    "file_size_bytes": row.file_size_bytes,
                    "is_duplicate": row.is_duplicate,
                    "duplicate_of_scan_image_id": row.duplicate_of_scan_image_id,
                },
            )
        )
    return issues


def check_forecast_integrity(session: Session, *, owner_user_id: int) -> list[dict]:
    rows = session.exec(
        select(MarketForecast).where(
            MarketForecast.owner_user_id == owner_user_id,
            or_(
                MarketForecast.forecast_horizon_days <= 0,
                MarketForecast.confidence_score < 0,
                MarketForecast.confidence_score > 1,
            ),
        )
    ).all()
    return [
        _issue(
            issue_type="invalid_forecast_range",
            severity="MEDIUM",
            entity_type="market_forecast",
            entity_id=row.id,
            issue_message="Forecast contains an invalid horizon or confidence score.",
            issue_payload_json={
                "forecast_horizon_days": row.forecast_horizon_days,
                "confidence_score": row.confidence_score,
            },
        )
        for row in rows
    ]


def check_marketplace_integrity(session: Session, *, owner_user_id: int) -> list[dict]:
    duplicate_external_ids = session.exec(
        select(
            MarketplaceListingMapping.external_listing_id,
            func.count(MarketplaceListingMapping.id),
        )
        .join(MarketplaceListing, MarketplaceListing.id == MarketplaceListingMapping.listing_id)
        .where(
            MarketplaceListing.owner_id == owner_user_id,
            MarketplaceListingMapping.external_listing_id.is_not(None),
        )
        .group_by(MarketplaceListingMapping.external_listing_id)
        .having(func.count(MarketplaceListingMapping.id) > 1)
    ).all()
    return [
        _issue(
            issue_type="duplicate_external_listing_id",
            severity="HIGH",
            entity_type="marketplace_listing_mapping",
            entity_id=None,
            issue_message="Multiple marketplace mappings share the same external listing id.",
            issue_payload_json={"external_listing_id": external_listing_id, "mapping_count": int(mapping_count or 0)},
        )
        for external_listing_id, mapping_count in duplicate_external_ids
    ]


def run_integrity_check(
    session: Session,
    *,
    owner_user_id: int,
    check_type: str = "full",
) -> DataIntegrityCheckDetail:
    checks = {
        "inventory": check_inventory_integrity(session, owner_user_id=owner_user_id),
        "orders": check_order_integrity(session, owner_user_id=owner_user_id),
        "listings": check_listing_integrity(session, owner_user_id=owner_user_id),
        "scans": check_scan_integrity(session, owner_user_id=owner_user_id),
        "forecasts": check_forecast_integrity(session, owner_user_id=owner_user_id),
        "marketplace": check_marketplace_integrity(session, owner_user_id=owner_user_id),
    }
    issues = [issue for group in checks.values() for issue in group]
    status = "PASS" if not issues else "WARNING"

    check_row = DataIntegrityCheck(
        owner_user_id=owner_user_id,
        check_type=check_type,
        check_status=status,
        summary_json={
            "issue_count": len(issues),
            "issues_by_category": {key: len(value) for key, value in checks.items()},
        },
    )
    session.add(check_row)
    session.commit()
    session.refresh(check_row)

    issue_rows: list[DataIntegrityIssue] = []
    for issue in issues:
        row = DataIntegrityIssue(check_id=check_row.id, **issue)
        session.add(row)
        issue_rows.append(row)
    session.commit()
    for row in issue_rows:
        session.refresh(row)

    return DataIntegrityCheckDetail(
        check=DataIntegrityCheckRead.model_validate(check_row),
        issues=[DataIntegrityIssueRead.model_validate(row) for row in issue_rows],
    )


def list_integrity_checks(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> DataIntegrityCheckListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(DataIntegrityCheck)
        .where(DataIntegrityCheck.owner_user_id == owner_user_id)
        .order_by(DataIntegrityCheck.created_at.desc(), DataIntegrityCheck.id.desc())
    ).all()
    items = [DataIntegrityCheckRead.model_validate(row) for row in rows[offset : offset + limit]]
    return DataIntegrityCheckListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)


def get_integrity_check(session: Session, *, owner_user_id: int, check_id: int) -> DataIntegrityCheckDetail | None:
    row = session.get(DataIntegrityCheck, check_id)
    if row is None or row.owner_user_id != owner_user_id:
        return None
    issues = session.exec(
        select(DataIntegrityIssue)
        .where(DataIntegrityIssue.check_id == check_id)
        .order_by(DataIntegrityIssue.created_at.asc(), DataIntegrityIssue.id.asc())
    ).all()
    return DataIntegrityCheckDetail(
        check=DataIntegrityCheckRead.model_validate(row),
        issues=[DataIntegrityIssueRead.model_validate(issue) for issue in issues],
    )


def list_integrity_issues(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> DataIntegrityIssueListResponse:
    limit, offset = _paginate(limit, offset)
    check_ids = session.exec(select(DataIntegrityCheck.id).where(DataIntegrityCheck.owner_user_id == owner_user_id)).all()
    if not check_ids:
        return DataIntegrityIssueListResponse(items=[], total_items=0, limit=limit, offset=offset)

    rows = session.exec(
        select(DataIntegrityIssue)
        .where(DataIntegrityIssue.check_id.in_(check_ids))
        .order_by(DataIntegrityIssue.created_at.desc(), DataIntegrityIssue.id.desc())
    ).all()
    items = [DataIntegrityIssueRead.model_validate(row) for row in rows[offset : offset + limit]]
    return DataIntegrityIssueListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)
