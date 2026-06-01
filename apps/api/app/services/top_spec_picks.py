from __future__ import annotations

from sqlmodel import Session, select

from app.models.top_spec_pick import TopSpecPick
from app.schemas.top_spec_pick import TopSpecPickLatestRead, TopSpecPickRead, TopSpecPickSummaryRead
from app.services.top_spec_pick_engine import generate_top_spec_picks


def _to_read(row: TopSpecPick) -> TopSpecPickRead:
    return TopSpecPickRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        rank=int(row.rank),
        release_id=int(row.release_id) if row.release_id is not None else None,
        spec_input_id=int(row.spec_input_id),
        title=row.title,
        publisher=row.publisher,
        issue_number=row.issue_number,
        final_score=float(row.final_score),
        confidence_score=float(row.confidence_score),
        risk_level=row.risk_level,
        suggested_quantity=int(row.suggested_quantity) if row.suggested_quantity is not None else None,
        foc_date=row.foc_date.isoformat() if row.foc_date else None,
        release_date=row.release_date.isoformat() if row.release_date else None,
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
    )


def list_top_spec_picks(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[TopSpecPickRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(TopSpecPick)
        .where(TopSpecPick.owner_user_id == owner_user_id)
        .order_by(TopSpecPick.rank.asc(), TopSpecPick.id.asc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(row) for row in page], total


def get_latest_top_spec_picks_read(session: Session, *, owner_user_id: int, limit: int = 20) -> TopSpecPickLatestRead:
    items, _ = list_top_spec_picks(session, owner_user_id=owner_user_id, limit=limit, offset=0)
    return TopSpecPickLatestRead(picks_computed=0, picks_skipped=True, items=items)


def refresh_latest_top_spec_picks(session: Session, *, owner_user_id: int, limit: int = 20) -> TopSpecPickLatestRead:
    result = generate_top_spec_picks(session, owner_user_id=owner_user_id, limit=limit)
    items, _ = list_top_spec_picks(session, owner_user_id=owner_user_id, limit=limit, offset=0)
    return TopSpecPickLatestRead(
        picks_computed=result.computed,
        picks_skipped=result.skipped,
        items=items,
    )


def build_top_spec_pick_summary(session: Session, *, owner_user_id: int) -> TopSpecPickSummaryRead:
    rows = session.exec(
        select(TopSpecPick)
        .where(TopSpecPick.owner_user_id == owner_user_id)
        .order_by(TopSpecPick.rank.asc(), TopSpecPick.id.asc())
    ).all()
    if not rows:
        return TopSpecPickSummaryRead()
    finals = [float(row.final_score) for row in rows]
    confidences = [float(row.confidence_score) for row in rows]
    return TopSpecPickSummaryRead(
        total_picks=len(rows),
        average_final_score=round(sum(finals) / len(finals), 2),
        average_confidence_score=round(sum(confidences) / len(confidences), 3),
        low_risk_count=sum(1 for row in rows if row.risk_level == "LOW"),
        medium_risk_count=sum(1 for row in rows if row.risk_level == "MEDIUM"),
        high_risk_count=sum(1 for row in rows if row.risk_level == "HIGH"),
        with_suggested_quantity=sum(1 for row in rows if row.suggested_quantity is not None),
    )
