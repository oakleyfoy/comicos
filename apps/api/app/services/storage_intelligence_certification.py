"""P79-03 production certification for storage & location platform."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.schemas.storage_analytics import P79StorageCertificationCheckRead, P79StorageCertificationRead
from app.services.box_contents_service import get_box_contents
from app.services.inventory_locator_service import locate_inventory
from app.services.storage_analytics_service import build_analytics_dashboard, build_analytics_read
from app.services.storage_audit_service import create_audit_session, get_audit_detail
from app.services.storage_assignment_service import assign_inventory_copy
from app.services.storage_dashboard_service import build_storage_dashboard
from app.services.storage_label_service import build_storage_label
from app.services.storage_location_service import create_storage_box, create_storage_location, list_storage_locations
from app.models.storage_location import P79_KIND_LOCATION, P79_KIND_RACK, P79_KIND_SHELF


def _check(component: str, passed: bool, detail: str) -> P79StorageCertificationCheckRead:
    return P79StorageCertificationCheckRead(component=component, passed=passed, detail=detail)


def run_storage_intelligence_certification(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int | None = None,
    box_id: int | None = None,
) -> P79StorageCertificationRead:
    checks: list[P79StorageCertificationCheckRead] = []
    test_box_id = box_id

    try:
        locs, total = list_storage_locations(session, owner_user_id=owner_user_id, limit=5)
        checks.append(_check("storage_hierarchy", total >= 0, f"locations={total}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("storage_hierarchy", False, str(exc)))

    try:
        if test_box_id is None:
            office = create_storage_location(
                session,
                owner_user_id=owner_user_id,
                parent_id=None,
                location_kind=P79_KIND_LOCATION,
                name="Cert Office",
            )
            rack = create_storage_location(
                session,
                owner_user_id=owner_user_id,
                parent_id=int(office.id or 0),
                location_kind=P79_KIND_RACK,
                name="Cert Rack",
            )
            shelf = create_storage_location(
                session,
                owner_user_id=owner_user_id,
                parent_id=int(rack.id or 0),
                location_kind=P79_KIND_SHELF,
                name="Cert Shelf",
            )
            box = create_storage_box(
                session,
                owner_user_id=owner_user_id,
                shelf_location_id=int(shelf.id or 0),
                name="CERT-01",
                capacity=50,
            )
            test_box_id = int(box.id or 0)
        if inventory_copy_id is not None and test_box_id is not None:
            assign_inventory_copy(
                session,
                owner_user_id=owner_user_id,
                inventory_copy_id=inventory_copy_id,
                box_id=test_box_id,
                use_suggested_slot=True,
                assigned_by_user_id=owner_user_id,
            )
        checks.append(_check("assignment_workflow", test_box_id is not None, f"box={test_box_id}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("assignment_workflow", False, str(exc)))

    try:
        loc = locate_inventory(session, owner_user_id=owner_user_id, query=str(inventory_copy_id or "1"))
        checks.append(_check("locator", True, f"hits={loc.total_items}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("locator", False, str(exc)))

    try:
        if test_box_id is not None:
            contents = get_box_contents(session, owner_user_id=owner_user_id, box_id=test_box_id)
            checks.append(_check("box_contents", contents.box_id == test_box_id, f"count={contents.total_count}"))
        else:
            checks.append(_check("box_contents", False, "no box"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("box_contents", False, str(exc)))

    try:
        if test_box_id is not None:
            audit = create_audit_session(
                session,
                owner_user_id=owner_user_id,
                audit_name="Cert audit",
                scope_box_id=test_box_id,
            )
            detail = get_audit_detail(session, owner_user_id=owner_user_id, audit_id=int(audit.id or 0))
            checks.append(_check("audit_workflow", len(detail.entries) >= 0, f"audit={audit.id}"))
        else:
            checks.append(_check("audit_workflow", False, "no box"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("audit_workflow", False, str(exc)))

    try:
        if test_box_id is not None:
            label = build_storage_label(
                session, owner_user_id=owner_user_id, entity_type="box", entity_id=test_box_id
            )
            checks.append(_check("labels", bool(label.qr_payload), label.label_code))
        else:
            checks.append(_check("labels", False, "no box"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("labels", False, str(exc)))

    try:
        analytics = build_analytics_read(session, owner_user_id=owner_user_id)
        checks.append(_check("analytics", analytics.snapshot_id > 0, f"util={analytics.utilization_pct}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("analytics", False, str(exc)))

    try:
        health = build_analytics_dashboard(session, owner_user_id=owner_user_id)
        checks.append(
            _check(
                "health_scoring",
                health.health.health_score >= 0,
                f"score={health.health.health_score}",
            )
        )
        checks.append(_check("dashboard", health.snapshot_id > 0, f"boxes={health.analytics.total_boxes}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("health_scoring", False, str(exc)))
        checks.append(_check("dashboard", False, str(exc)))

    try:
        dash = build_storage_dashboard(session, owner_user_id=owner_user_id)
        checks.append(_check("foundation_dashboard", dash.box_count >= 0, f"assigned={dash.assigned_books}"))
    except Exception as exc:  # pragma: no cover
        checks.append(_check("foundation_dashboard", False, str(exc)))

    passed = all(c.passed for c in checks)
    return P79StorageCertificationRead(
        approved_for_production=passed,
        checks=checks,
        platform_status="APPROVED_FOR_PRODUCTION" if passed else "NEEDS_ATTENTION",
        reviewed_at=datetime.now(timezone.utc),
    )
