from __future__ import annotations

from sqlmodel import Session, select

from app.models.data_integrity import DataIntegrityCheck, MigrationSafetyCheck
from app.models.production_readiness import ReadinessChecklistItem
from app.schemas.production_readiness import ReadinessChecklistItemRead
from sqlalchemy import text

from app.services.production_readiness import CHECK_STATUS_FAIL, CHECK_STATUS_PASS, CHECK_STATUS_WARNING
from app.services.production_readiness_notes import encode_scoped_notes, notes_owner_user_id, notes_summary
from app.services.recovery_recommendations import build_operations_summary
from app.services.agent_platform_validation import validate_platform as validate_agent_platform_core
from app.services.forecast_platform_validation import validate_forecast_platform
from app.services.marketplace_validation import validate_marketplace_platform

ITEM_COMPLETE = "COMPLETE"
ITEM_INCOMPLETE = "INCOMPLETE"
ITEM_NOT_RUN = "NOT_RUN"


def _persist_item(
    session: Session,
    *,
    owner_user_id: int,
    checklist_category: str,
    item_name: str,
    item_status: str,
    summary: str,
) -> ReadinessChecklistItemRead:
    row = ReadinessChecklistItem(
        checklist_category=checklist_category,
        item_name=item_name,
        item_status=item_status,
        validation_notes=encode_scoped_notes(owner_user_id=owner_user_id, summary=summary),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(row)


def _to_read(row: ReadinessChecklistItem) -> ReadinessChecklistItemRead:
    data = row.model_dump()
    data["validation_notes"] = notes_summary(row.validation_notes)
    return ReadinessChecklistItemRead.model_validate(data)


def _validation_item_status(overall: str) -> str:
    if overall == CHECK_STATUS_PASS:
        return ITEM_COMPLETE
    if overall == CHECK_STATUS_FAIL:
        return ITEM_INCOMPLETE
    return ITEM_NOT_RUN if overall == CHECK_STATUS_WARNING else ITEM_INCOMPLETE


def generate_readiness_checklist(session: Session, *, owner_user_id: int) -> list[ReadinessChecklistItemRead]:
    items: list[ReadinessChecklistItemRead] = []

    marketplace = validate_marketplace_platform(session, owner_id=owner_user_id)
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Marketplace Platform",
            item_name="Marketplace closeout validation",
            item_status=_validation_item_status(marketplace.overall_status),
            summary=f"Overall marketplace status {marketplace.overall_status}.",
        )
    )

    forecast = validate_forecast_platform(session, owner_user_id=owner_user_id)
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Forecast Platform",
            item_name="Forecast platform closeout validation",
            item_status=_validation_item_status(forecast.overall_status),
            summary=f"Overall forecast status {forecast.overall_status}.",
        )
    )

    integrity = session.exec(
        select(DataIntegrityCheck)
        .where(DataIntegrityCheck.owner_user_id == owner_user_id)
        .order_by(DataIntegrityCheck.created_at.desc(), DataIntegrityCheck.id.desc())
    ).first()
    data_status = ITEM_NOT_RUN if integrity is None else _validation_item_status(integrity.check_status)
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Data Protection",
            item_name="Latest integrity check reviewed",
            item_status=data_status,
            summary="No integrity check on record." if integrity is None else f"Integrity check {integrity.check_status}.",
        )
    )

    ops = build_operations_summary(session, owner_user_id=owner_user_id)
    ops_status = ITEM_COMPLETE if ops.platform_health_status == "HEALTHY" else ITEM_NOT_RUN
    if ops.platform_health_status == "FAILED":
        ops_status = ITEM_INCOMPLETE
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Operations Reliability",
            item_name="Operations command center reviewed",
            item_status=ops_status,
            summary=f"Platform health {ops.platform_health_status}; readiness {ops.readiness_score}.",
        )
    )

    agents = validate_agent_platform_core(session, owner_user_id=owner_user_id)
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Agent Platform",
            item_name="Agent platform validation",
            item_status=_validation_item_status(agents.overall_status),
            summary=f"Agent platform status {agents.overall_status}.",
        )
    )

    db_status = CHECK_STATUS_PASS
    db_summary = "Database connectivity verified."
    try:
        session.exec(text("SELECT 1")).one()
    except Exception as exc:  # noqa: BLE001
        db_status = CHECK_STATUS_FAIL
        db_summary = f"Database connectivity check failed: {exc.__class__.__name__}."
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Database Health",
            item_name="Database connectivity validation",
            item_status=_validation_item_status(db_status),
            summary=db_summary,
        )
    )

    migration = session.exec(
        select(MigrationSafetyCheck)
        .where(MigrationSafetyCheck.owner_user_id == owner_user_id)
        .order_by(MigrationSafetyCheck.created_at.desc(), MigrationSafetyCheck.id.desc())
    ).first()
    backup_status = ITEM_NOT_RUN if migration is None else _validation_item_status(migration.check_status)
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Backup Validation",
            item_name="Migration safety snapshot reviewed",
            item_status=backup_status,
            summary="No migration safety record." if migration is None else f"Migration safety {migration.check_status}.",
        )
    )

    restore_status = ITEM_COMPLETE if migration is not None and migration.check_status == CHECK_STATUS_PASS else ITEM_NOT_RUN
    if migration is not None and migration.check_status == CHECK_STATUS_FAIL:
        restore_status = ITEM_INCOMPLETE
    items.append(
        _persist_item(
            session,
            owner_user_id=owner_user_id,
            checklist_category="Restore Validation",
            item_name="Restore procedure readiness (advisory)",
            item_status=restore_status,
            summary=(
                "Restore validation is advisory: confirm backup integrity and rehearse restore outside production."
                if migration is None
                else f"Migration count parity {migration.check_status}; manual restore rehearsal still required."
            ),
        )
    )

    return items


def list_checklist_items_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ReadinessChecklistItemRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ReadinessChecklistItem).order_by(
            ReadinessChecklistItem.validated_at.desc(),
            ReadinessChecklistItem.id.desc(),
        )
    ).all()
    filtered = [row for row in rows if notes_owner_user_id(row.validation_notes) == owner_user_id]
    page = filtered[offset : offset + limit]
    return [_to_read(row) for row in page], len(filtered)


def latest_checklist_summary_for_owner(session: Session, *, owner_user_id: int) -> tuple[int, int]:
    items, _ = list_checklist_items_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    if not items:
        return 0, 0
    latest_at = items[0].validated_at
    batch = [item for item in items if item.validated_at == latest_at]
    if not batch:
        batch = items[:8]
    pass_count = sum(1 for item in batch if item.item_status == ITEM_COMPLETE)
    return pass_count, len(batch)
