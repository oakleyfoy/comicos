"""P62 Phase 1 — V3 preview certification."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, func, select

from app.models.demand_intelligence import DemandVelocitySnapshot, IssueDemandSnapshot, SpecOpportunitySnapshot
from app.services.p62_feature_flags import p62_v3_persist_enabled, p62_v3_preview_enabled
from app.services.recommendation_v3_preview_service import build_recommendation_v3_preview


def certify_recommendation_v3_preview(session: Session, *, owner_user_id: int) -> dict:
    notes: list[str] = []
    demand_count = int(session.exec(select(func.count()).select_from(IssueDemandSnapshot)).one() or 0)
    velocity_count = int(session.exec(select(func.count()).select_from(DemandVelocitySnapshot)).one() or 0)
    spec_count = int(session.exec(select(func.count()).select_from(SpecOpportunitySnapshot)).one() or 0)

    ok_demand = demand_count > 0
    ok_velocity = velocity_count > 0
    if not ok_demand:
        notes.append("No issue_demand_snapshot rows.")
    else:
        notes.append(f"{demand_count} issue demand snapshots.")
    if not ok_velocity:
        notes.append("No demand_velocity_snapshot rows.")
    else:
        notes.append(f"{velocity_count} velocity snapshots.")

    if spec_count == 0:
        notes.append("No spec_opportunity_snapshot (NOT_READY for spec; preview may still run).")
    else:
        notes.append(f"{spec_count} spec opportunity snapshot(s).")

    preview = build_recommendation_v3_preview(session, owner_user_id=owner_user_id, limit=10)
    ok_preview = preview.get("enabled") and preview.get("preview_count", 0) > 0
    if preview.get("enabled") and not ok_preview:
        notes.append("V3 preview returned zero scored candidates.")
    elif ok_preview:
        notes.append(f"V3 preview scored {preview.get('preview_count')} candidates.")

    ok_no_v2_mutation = not preview.get("v2_mutated", True)
    if not ok_no_v2_mutation:
        notes.append("V2 persisted cross_system rows changed during preview (forbidden).")

    ok_persist_flag = not p62_v3_persist_enabled()
    if not ok_persist_flag:
        notes.append("P62_V3_PERSIST_ENABLED is true (Phase 1 expects false).")

    certified = (
        p62_v3_preview_enabled()
        and ok_demand
        and ok_velocity
        and ok_preview
        and ok_no_v2_mutation
        and ok_persist_flag
    )
    status = "PASS" if certified else "NOT_READY" if not ok_demand else "WARNING"

    return {
        "component": "P62-01_V3_PREVIEW",
        "certified": certified,
        "status": status,
        "summary": "V3 preview certified" if certified else "V3 preview not certified",
        "notes": notes,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "flags": {
            "P62_V3_PREVIEW_ENABLED": p62_v3_preview_enabled(),
            "P62_V3_PERSIST_ENABLED": p62_v3_persist_enabled(),
        },
        "preview": {
            "not_ready": preview.get("not_ready"),
            "reason_codes": preview.get("reason_codes"),
            "v2_mutated": preview.get("v2_mutated"),
        },
    }
