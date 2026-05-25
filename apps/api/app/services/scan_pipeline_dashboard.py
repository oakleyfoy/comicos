"""Deterministic aggregates for bulk ingest scan pipeline dashboards (reads only)."""

from __future__ import annotations

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import (
    HighResReviewRequest,
    QueueRoutingRecommendation,
    ScanPipelineReplayRun,
    ScanQaResult,
    ScanSession,
    ScanSessionItem,
)
from app.schemas.scan_pipeline_dashboard import (
    ScanPipelineDashboardRead,
    ScanPipelineDashboardSummaryRead,
    ScannerProfileUsageRowRead,
)
from app.schemas.scan_sessions import ScanSessionSummaryRead
from app.services.physical_intake import build_physical_intake_summary


def _sess_owner_preds(owner_user_id: int | None) -> tuple:
    return (ScanSession.owner_user_id == owner_user_id,) if owner_user_id is not None else ()


def _apply_scan_session_owner(stmt, owner_user_id: int | None):
    if owner_user_id is None:
        return stmt
    return stmt.where(ScanSession.owner_user_id == owner_user_id)


def _count(session: Session, stmt) -> int:
    raw = session.exec(stmt).first()
    if raw is None:
        return 0
    if isinstance(raw, tuple | list):
        return int(raw[0] or 0)
    return int(raw)


def scan_pipeline_dashboard_summary(session: Session, *, owner_user_id: int | None) -> ScanPipelineDashboardSummaryRead:
    return _dashboard_summary(session, owner_user_id=owner_user_id)


def scan_pipeline_dashboard(session: Session, *, owner_user_id: int | None) -> ScanPipelineDashboardRead:
    summary = scan_pipeline_dashboard_summary(session, owner_user_id=owner_user_id)
    active_rows, recent_rows = _dashboard_session_lists(session, owner_user_id=owner_user_id)
    return ScanPipelineDashboardRead(
        summary=summary,
        active_sessions=active_rows,
        recent_sessions=recent_rows,
    )


def _dashboard_session_lists(
    session: Session,
    *,
    owner_user_id: int | None,
    active_limit: int = 15,
    recent_limit: int = 15,
) -> tuple[list[ScanSessionSummaryRead], list[ScanSessionSummaryRead]]:
    active_stmt = (
        select(ScanSession)
        .where(ScanSession.status.in_(("pending", "active", "paused")))
        .order_by(ScanSession.updated_at.desc(), ScanSession.id.desc())
        .limit(active_limit)
    )
    active_stmt = _apply_scan_session_owner(active_stmt, owner_user_id)
    active_reads = [
        ScanSessionSummaryRead.model_validate(r, from_attributes=True) for r in session.exec(active_stmt).all()
    ]

    recent_stmt = (
        select(ScanSession)
        .where(ScanSession.status.in_(("completed", "completed_with_errors", "cancelled")))
        .order_by(ScanSession.updated_at.desc(), ScanSession.id.desc())
        .limit(recent_limit)
    )
    recent_stmt = _apply_scan_session_owner(recent_stmt, owner_user_id)
    recent_reads = [
        ScanSessionSummaryRead.model_validate(r, from_attributes=True) for r in session.exec(recent_stmt).all()
    ]

    return active_reads, recent_reads


def _routing_open_counts(session: Session, *, owner_user_id: int | None) -> tuple[int, int]:
    def typed_count(recommendation_type: str) -> int:
        stmt = (
            select(func.count())
            .select_from(QueueRoutingRecommendation)
            .join(ScanSessionItem, QueueRoutingRecommendation.scan_session_item_id == ScanSessionItem.id)
            .join(ScanSession, ScanSessionItem.scan_session_id == ScanSession.id)
            .where(
                QueueRoutingRecommendation.routing_status == "open",
                QueueRoutingRecommendation.recommendation_type == recommendation_type,
                *_sess_owner_preds(owner_user_id),
            )
        )
        return _count(session, stmt)

    return typed_count("recommend_ocr"), typed_count("recommend_high_res_review")


def _dashboard_summary(session: Session, *, owner_user_id: int | None) -> ScanPipelineDashboardSummaryRead:
    active_sessions = _count(
        session,
        select(func.count()).select_from(ScanSession).where(
            ScanSession.status.in_(("pending", "active", "paused")),
            *_sess_owner_preds(owner_user_id),
        ),
    )
    sess_completed_errors = _count(
        session,
        select(func.count()).select_from(ScanSession).where(
            ScanSession.status == "completed_with_errors",
            *_sess_owner_preds(owner_user_id),
        ),
    )

    failed_sum_stmt = select(func.coalesce(func.sum(ScanSession.failed_items), 0)).where(
        *_sess_owner_preds(owner_user_id),
    )
    failed_items = int(_count(session, failed_sum_stmt))

    review_required_items = _count(
        session,
        select(func.count())
        .select_from(ScanSessionItem)
        .join(ScanSession, ScanSessionItem.scan_session_id == ScanSession.id)
        .where(
            ScanSessionItem.ingest_status == "review_required",
            *_sess_owner_preds(owner_user_id),
        ),
    )

    qa_needs_rescan = _count(
        session,
        select(func.count())
        .select_from(ScanQaResult)
        .join(ScanSession, ScanQaResult.scan_session_id == ScanSession.id)
        .where(
            ScanQaResult.qa_classification == "needs_rescan",
            *_sess_owner_preds(owner_user_id),
        ),
    )

    qa_corrupt_or_unreadable = _count(
        session,
        select(func.count())
        .select_from(ScanQaResult)
        .join(ScanSession, ScanQaResult.scan_session_id == ScanSession.id)
        .where(
            ScanQaResult.qa_classification == "corrupt_or_unreadable",
            *_sess_owner_preds(owner_user_id),
        ),
    )

    routing_recommend_ocr, routing_recommend_high_res_review = _routing_open_counts(session, owner_user_id=owner_user_id)

    high_res_pending = _count(
        session,
        select(func.count())
        .select_from(HighResReviewRequest)
        .where(
            HighResReviewRequest.status == "pending",
            *((HighResReviewRequest.owner_user_id == owner_user_id,) if owner_user_id is not None else ()),
        ),
    )

    physical_intake_counts = build_physical_intake_summary(session, owner_user_id=owner_user_id)

    replay_runs_with_changes = _count(
        session,
        select(func.count())
        .select_from(ScanPipelineReplayRun)
        .where(
            ScanPipelineReplayRun.changed_items > 0,
            *(
                (ScanPipelineReplayRun.owner_user_id == owner_user_id,)
                if owner_user_id is not None
                else ()
            ),
        ),
    )

    profiles_stmt = (
        select(
            ScanSession.scanner_profile_id,
            ScanSession.scanner_profile,
            func.count(ScanSession.id),
        )
        .where(
            ScanSession.session_type == "bulk_ingest",
            *_sess_owner_preds(owner_user_id),
            or_(
                ScanSession.scanner_profile_id.is_not(None),
                ScanSession.scanner_profile.is_not(None),
            ),
        )
        .group_by(ScanSession.scanner_profile_id, ScanSession.scanner_profile)
        .order_by(func.count(ScanSession.id).desc(), ScanSession.scanner_profile_id.asc())
        .limit(12)
    )
    profile_totals_raw = session.exec(profiles_stmt).all()

    most_used: list[ScannerProfileUsageRowRead] = []
    for pid, label, ct in profile_totals_raw:
        lbl = (label or "").strip() if label else ""
        if not lbl:
            lbl = "Unnamed preset" if pid is not None else "(no preset label)"
        most_used.append(
            ScannerProfileUsageRowRead(
                scanner_profile_id=int(pid) if pid is not None else None,
                profile_label=lbl[:200],
                scan_session_count=int(ct or 0),
            ),
        )

    return ScanPipelineDashboardSummaryRead(
        active_sessions=active_sessions,
        sessions_completed_with_errors=sess_completed_errors,
        failed_items=failed_items,
        review_required_items=review_required_items,
        qa_needs_rescan=qa_needs_rescan,
        qa_corrupt_or_unreadable=qa_corrupt_or_unreadable,
        routing_recommend_ocr=routing_recommend_ocr,
        routing_recommend_high_res_review=routing_recommend_high_res_review,
        high_res_pending=high_res_pending,
        physical_intake_received_pending_scan=physical_intake_counts.counts.received_pending_scan,
        replay_runs_with_changes=replay_runs_with_changes,
        most_used_scanner_profiles=most_used,
    )
