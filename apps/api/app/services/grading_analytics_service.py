"""P67-04 Grading analytics — consumes P66 variant decisions + inventory FMV."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session, select

from app.models.portfolio_analytics_platform import P67GradingOpportunityItem, P67GradingOpportunitySnapshot, utc_now
from app.services.p67_inventory_bridge import enrich_row_value, fmv_lookup_by_title, load_p67_inventory_context
from app.services.variant_decision_engine import get_latest_variant_decision_snapshot, list_variant_decision_items


def get_latest_grading_opportunity_snapshot(session: Session, *, owner_user_id: int) -> P67GradingOpportunitySnapshot | None:
    return session.exec(
        select(P67GradingOpportunitySnapshot)
        .where(P67GradingOpportunitySnapshot.owner_user_id == owner_user_id)
        .order_by(P67GradingOpportunitySnapshot.generated_at.desc(), P67GradingOpportunitySnapshot.id.desc())
    ).first()


def list_grading_opportunity_items(session: Session, *, snapshot_id: int, limit: int = 50) -> list[P67GradingOpportunityItem]:
    return list(
        session.exec(
            select(P67GradingOpportunityItem)
            .where(P67GradingOpportunityItem.snapshot_id == snapshot_id)
            .order_by(P67GradingOpportunityItem.submission_priority.asc(), P67GradingOpportunityItem.id.asc())
            .limit(min(max(limit, 1), 200))
        ).all()
    )


def build_grading_opportunity_snapshot(session: Session, *, owner_user_id: int) -> P67GradingOpportunitySnapshot:
    today = date.today()
    snap = P67GradingOpportunitySnapshot(
        owner_user_id=owner_user_id,
        snapshot_date=today,
        generated_at=utc_now(),
    )
    session.add(snap)
    session.flush()

    inv = load_p67_inventory_context(session, owner_user_id=owner_user_id)
    fmv_map = fmv_lookup_by_title(session, owner_user_id=owner_user_id)
    raw_by_title = {r.title.strip().lower(): r for r in inv if (r.grade_status or "raw") == "raw"}

    candidates: list[P67GradingOpportunityItem] = []
    v_snap = get_latest_variant_decision_snapshot(session, owner_user_id=owner_user_id)
    if v_snap:
        for row in list_variant_decision_items(session, snapshot_id=int(v_snap.id or 0), limit=80):
            title_key = (row.title or "").strip().lower()
            inv_row = raw_by_title.get(title_key)
            raw_val = enrich_row_value(inv_row, fmv_map) if inv_row else 0.0
            if raw_val <= 0:
                raw_val = 25.0
            graded_val = round(raw_val * 1.35, 2)
            roi = ((graded_val - raw_val - 30.0) / max(raw_val, 1.0)) * 100.0
            score = 50.0
            plan = row.quantity_plan_json or {}
            if plan.get("grade_first"):
                score += 15.0
            candidates.append(
                P67GradingOpportunityItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    inventory_copy_id=inv_row.copy_id if inv_row else None,
                    title=row.title or "Unknown",
                    estimated_grade="9.4",
                    submission_candidate_score=round(score, 2),
                    estimated_roi_pct=round(roi, 2),
                    raw_value=raw_val,
                    graded_value=graded_val,
                    submission_priority=0,
                    notes_json={"source": "p66_variant_decision", "summary": row.recommendation_summary},
                )
            )

    if not candidates:
        for row in inv[:20]:
            if (row.grade_status or "raw") != "raw":
                continue
            raw_val = enrich_row_value(row, fmv_map) or row.cost_basis
            graded_val = round(raw_val * 1.25, 2)
            roi = ((graded_val - raw_val - 25.0) / max(raw_val, 1.0)) * 100.0
            candidates.append(
                P67GradingOpportunityItem(
                    snapshot_id=int(snap.id or 0),
                    owner_user_id=owner_user_id,
                    inventory_copy_id=row.copy_id,
                    title=f"{row.title} #{row.issue_number}",
                    estimated_grade="9.2",
                    submission_candidate_score=45.0,
                    estimated_roi_pct=round(roi, 2),
                    raw_value=raw_val,
                    graded_value=graded_val,
                    submission_priority=0,
                    notes_json={"source": "inventory_fmv"},
                )
            )

    candidates.sort(key=lambda c: c.estimated_roi_pct, reverse=True)
    for idx, c in enumerate(candidates[:40]):
        c.submission_priority = idx + 1
        session.add(c)

    snap.total_candidates = len(candidates[:40])
    snap.metadata_json = {"top_queue": [c.title for c in candidates[:10]]}
    session.add(snap)
    session.flush()
    return snap
