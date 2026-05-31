from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.exit_candidate import ExitCandidate
from app.schemas.exit_candidate import ExitCandidateRead, ExitCandidateSummaryRead
from app.services.exit_candidate_engine import generate_exit_candidates
from app.services.sell_candidate_engine import _split_identity_key


def _latest_exit_candidate_rows(session: Session, *, owner_user_id: int) -> dict[int, ExitCandidate]:
    rows = session.exec(
        select(ExitCandidate)
        .where(ExitCandidate.owner_user_id == owner_user_id)
        .order_by(ExitCandidate.created_at.desc(), ExitCandidate.id.desc())
    ).all()
    latest: dict[int, ExitCandidate] = {}
    for row in rows:
        if row.inventory_item_id not in latest:
            latest[row.inventory_item_id] = row
    return latest


def _to_read(session: Session, *, row: ExitCandidate) -> ExitCandidateRead:
    copy = session.get(InventoryCopy, row.inventory_item_id)
    publisher, series, issue_number, _variant = _split_identity_key(copy.metadata_identity_key if copy else None)
    title = series or (copy.metadata_identity_key if copy else "")
    return ExitCandidateRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        inventory_item_id=int(row.inventory_item_id),
        candidate_score=float(row.candidate_score),
        confidence_score=float(row.confidence_score),
        estimated_fmv=float(row.estimated_fmv),
        acquisition_cost=float(row.acquisition_cost),
        unrealized_gain=float(row.unrealized_gain),
        candidate_reason=row.candidate_reason,  # type: ignore[arg-type]
        created_at=row.created_at.isoformat(),
        title=title,
        issue_number=issue_number,
        publisher=publisher,
    )


def persist_exit_candidates(session: Session, *, owner_user_id: int) -> int:
    computed = generate_exit_candidates(session, owner_user_id=owner_user_id)
    latest = _latest_exit_candidate_rows(session, owner_user_id=owner_user_id)
    created = 0
    for result in computed:
        prior = latest.get(result.inventory_item_id)
        if prior is not None:
            if (
                abs(float(prior.candidate_score) - float(result.candidate_score)) < 1e-9
                and abs(float(prior.confidence_score) - float(result.confidence_score)) < 1e-9
                and prior.candidate_reason == result.candidate_reason
                and abs(float(prior.unrealized_gain) - float(result.unrealized_gain)) < 1e-9
            ):
                continue
        session.add(
            ExitCandidate(
                owner_user_id=owner_user_id,
                inventory_item_id=result.inventory_item_id,
                candidate_score=result.candidate_score,
                confidence_score=result.confidence_score,
                estimated_fmv=result.estimated_fmv,
                acquisition_cost=result.acquisition_cost,
                unrealized_gain=result.unrealized_gain,
                candidate_reason=result.candidate_reason,
            )
        )
        created += 1
    session.commit()
    return created


def list_exit_candidates(
    session: Session,
    *,
    owner_user_id: int,
    candidate_reason: str | None = None,
    score_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ExitCandidateRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    latest = _latest_exit_candidate_rows(session, owner_user_id=owner_user_id)
    items: list[ExitCandidateRead] = []
    for inv_id in sorted(latest.keys()):
        row = latest[inv_id]
        if candidate_reason and row.candidate_reason != candidate_reason.strip().upper():
            continue
        if score_min is not None and float(row.candidate_score) < float(score_min):
            continue
        read = _to_read(session, row=row)
        if publisher and publisher.strip().lower() not in read.publisher.lower():
            continue
        items.append(read)
    items.sort(key=lambda r: (-r.candidate_score, -r.confidence_score, r.inventory_item_id))
    total = len(items)
    return items[offset : offset + limit], total


def refresh_and_list_latest_exit_candidates(
    session: Session,
    *,
    owner_user_id: int,
    candidate_reason: str | None = None,
    score_min: float | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ExitCandidateRead], int]:
    persist_exit_candidates(session, owner_user_id=owner_user_id)
    return list_exit_candidates(
        session,
        owner_user_id=owner_user_id,
        candidate_reason=candidate_reason,
        score_min=score_min,
        publisher=publisher,
        limit=limit,
        offset=offset,
    )


def build_exit_candidate_summary(session: Session, *, owner_user_id: int) -> ExitCandidateSummaryRead:
    latest = _latest_exit_candidate_rows(session, owner_user_id=owner_user_id)
    counts = {
        "DUPLICATE": 0,
        "PROFITABLE": 0,
        "GRADED": 0,
        "OVEREXPOSED": 0,
        "CAPITAL_RECOVERY": 0,
        "MULTIPLE_SIGNALS": 0,
    }
    total_gain = 0.0
    score_sum = 0.0
    for row in latest.values():
        counts[row.candidate_reason] = counts.get(row.candidate_reason, 0) + 1
        total_gain += float(row.unrealized_gain)
        score_sum += float(row.candidate_score)
    total = len(latest)
    avg = round(score_sum / total, 1) if total else 0.0
    return ExitCandidateSummaryRead(
        total_candidates=total,
        duplicate_count=int(counts.get("DUPLICATE", 0)),
        profitable_count=int(counts.get("PROFITABLE", 0)),
        graded_count=int(counts.get("GRADED", 0)),
        overexposed_count=int(counts.get("OVEREXPOSED", 0)),
        capital_recovery_count=int(counts.get("CAPITAL_RECOVERY", 0)),
        multiple_signals_count=int(counts.get("MULTIPLE_SIGNALS", 0)),
        total_unrealized_gain=round(total_gain, 2),
        average_candidate_score=avg,
    )
