from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import InventoryCopy, MarketForecast, Order, ScanImage
from app.models.data_integrity import MigrationSafetyCheck
from app.models.marketplace_listing import MarketplaceListing
from app.schemas.data_integrity import MigrationSafetyCheckListResponse, MigrationSafetyCheckRead


def _paginate(limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _count_for_owner(session: Session, model: type, owner_user_id: int) -> int:
    owner_field = getattr(model, "owner_user_id", None)
    if owner_field is not None:
        count = session.exec(select(func.count()).select_from(model).where(owner_field == owner_user_id)).one()
        return int(count or 0)

    user_field = getattr(model, "user_id", None)
    if user_field is not None:
        count = session.exec(select(func.count()).select_from(model).where(user_field == owner_user_id)).one()
        return int(count or 0)

    return 0


def capture_pre_migration_counts(session: Session, *, owner_user_id: int) -> dict[str, int]:
    return {
        "inventory_copies": _count_for_owner(session, InventoryCopy, owner_user_id),
        "orders": _count_for_owner(session, Order, owner_user_id),
        "marketplace_listings": _count_for_owner(session, MarketplaceListing, owner_user_id),
        "scan_images": _count_for_owner(session, ScanImage, owner_user_id),
        "market_forecasts": _count_for_owner(session, MarketForecast, owner_user_id),
    }


def capture_post_migration_counts(session: Session, *, owner_user_id: int) -> dict[str, int]:
    return capture_pre_migration_counts(session, owner_user_id=owner_user_id)


def compare_migration_counts(pre_count_json: dict[str, int], post_count_json: dict[str, int]) -> dict[str, dict[str, int]]:
    entity_names = sorted(set(pre_count_json) | set(post_count_json))
    return {
        entity_name: {
            "pre": int(pre_count_json.get(entity_name, 0)),
            "post": int(post_count_json.get(entity_name, 0)),
            "delta": int(post_count_json.get(entity_name, 0)) - int(pre_count_json.get(entity_name, 0)),
        }
        for entity_name in entity_names
    }


def validate_migration_result(
    session: Session,
    *,
    owner_user_id: int,
    migration_revision: str,
    pre_count_json: dict[str, int] | None = None,
    post_count_json: dict[str, int] | None = None,
) -> MigrationSafetyCheckRead:
    pre_counts = pre_count_json or capture_pre_migration_counts(session, owner_user_id=owner_user_id)
    post_counts = post_count_json or capture_post_migration_counts(session, owner_user_id=owner_user_id)
    comparison = compare_migration_counts(pre_counts, post_counts)
    negative_deltas = [name for name, values in comparison.items() if values["delta"] < 0]
    check_status = "PASS" if not negative_deltas else "WARNING"

    row = MigrationSafetyCheck(
        owner_user_id=owner_user_id,
        migration_revision=migration_revision.strip(),
        check_status=check_status,
        pre_count_json=pre_counts,
        post_count_json=post_counts,
        validation_payload_json={
            "comparison": comparison,
            "negative_delta_entities": negative_deltas,
        },
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return MigrationSafetyCheckRead.model_validate(row)


def list_migration_safety_checks(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> MigrationSafetyCheckListResponse:
    limit, offset = _paginate(limit, offset)
    rows = session.exec(
        select(MigrationSafetyCheck)
        .where(MigrationSafetyCheck.owner_user_id == owner_user_id)
        .order_by(MigrationSafetyCheck.created_at.desc(), MigrationSafetyCheck.id.desc())
    ).all()
    items = [MigrationSafetyCheckRead.model_validate(row) for row in rows[offset : offset + limit]]
    return MigrationSafetyCheckListResponse(items=items, total_items=len(rows), limit=limit, offset=offset)
