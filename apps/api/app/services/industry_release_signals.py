from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import utc_now
from app.models.industry_release_scan import IndustryReleaseCandidate
from app.models.industry_release_signal import IndustryReleaseSignal
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.schemas.industry_release_signal import IndustryReleaseSignalLatestRead, IndustryReleaseSignalRead
from app.services.industry_release_scans import latest_scan_run_id
from app.services.industry_release_signal_classifier import classify_industry_release_candidate


def _signal_to_read(
    row: IndustryReleaseSignal,
    *,
    candidate: IndustryReleaseCandidate,
) -> IndustryReleaseSignalRead:
    return IndustryReleaseSignalRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        candidate_id=int(row.candidate_id),
        scan_run_id=int(row.scan_run_id),
        release_id=int(row.release_id),
        publisher_code=candidate.publisher_code,
        publisher_name=candidate.publisher_name,
        series_name=candidate.series_name,
        issue_number=candidate.issue_number,
        signal_type=row.signal_type,
        confidence_score=float(row.confidence_score),
        rationale=row.rationale,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _upsert_signal(
    session: Session,
    *,
    owner_user_id: int,
    candidate: IndustryReleaseCandidate,
    signal_type: str,
    confidence_score: float,
    rationale: str,
) -> tuple[IndustryReleaseSignal, bool]:
    row = session.exec(
        select(IndustryReleaseSignal)
        .where(IndustryReleaseSignal.candidate_id == int(candidate.id or 0))
        .where(IndustryReleaseSignal.signal_type == signal_type)
    ).first()
    if row is None:
        row = IndustryReleaseSignal(
            owner_user_id=owner_user_id,
            candidate_id=int(candidate.id or 0),
            scan_run_id=int(candidate.scan_run_id),
            release_id=int(candidate.release_id),
            signal_type=signal_type,
            confidence_score=confidence_score,
            rationale=rationale,
        )
        session.add(row)
        return row, True
    unchanged = (
        float(row.confidence_score) >= float(confidence_score)
        and row.rationale == rationale
        and int(row.scan_run_id) == int(candidate.scan_run_id)
    )
    if unchanged:
        return row, False
    row.confidence_score = max(float(row.confidence_score), float(confidence_score))
    row.rationale = rationale
    row.scan_run_id = int(candidate.scan_run_id)
    row.updated_at = utc_now()
    session.add(row)
    return row, True


def synchronize_industry_release_signals(session: Session, *, owner_user_id: int, scan_run_id: int) -> int:
    candidates = session.exec(
        select(IndustryReleaseCandidate)
        .where(IndustryReleaseCandidate.owner_user_id == owner_user_id)
        .where(IndustryReleaseCandidate.scan_run_id == scan_run_id)
    ).all()
    if not candidates:
        return 0

    release_ids = [int(c.release_id) for c in candidates]
    issues = {
        int(row.id or 0): row
        for row in session.exec(select(ReleaseIssue).where(ReleaseIssue.id.in_(release_ids))).all()
    }
    series_ids = {int(issues[rid].series_id) for rid in release_ids if rid in issues}
    series_map = {
        int(row.id or 0): row
        for row in session.exec(select(ReleaseSeries).where(ReleaseSeries.id.in_(series_ids))).all()
    }
    variant_rows = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id.in_(release_ids))).all()
    variants_by_issue: dict[int, list[ReleaseVariant]] = {}
    for variant in variant_rows:
        variants_by_issue.setdefault(int(variant.issue_id), []).append(variant)

    changed = 0
    for candidate in candidates:
        issue = issues.get(int(candidate.release_id))
        if issue is None:
            continue
        series = series_map.get(int(issue.series_id))
        if series is None:
            continue
        detections = classify_industry_release_candidate(
            session,
            candidate=candidate,
            issue=issue,
            series=series,
            variants=variants_by_issue.get(int(candidate.release_id), []),
        )
        for detection in detections:
            _, did_change = _upsert_signal(
                session,
                owner_user_id=owner_user_id,
                candidate=candidate,
                signal_type=detection.signal_type,
                confidence_score=detection.confidence_score,
                rationale=detection.rationale,
            )
            if did_change:
                changed += 1
    session.commit()
    return changed


def classify_latest_industry_release_signals(session: Session, *, owner_user_id: int) -> IndustryReleaseSignalLatestRead:
    run_id = latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return IndustryReleaseSignalLatestRead(scan_run_id=None, signals_classified=0, items=[])

    classified = synchronize_industry_release_signals(session, owner_user_id=owner_user_id, scan_run_id=run_id)
    items, _ = list_industry_release_signals(
        session,
        owner_user_id=owner_user_id,
        scan_run_id=run_id,
        limit=200,
        offset=0,
    )
    return IndustryReleaseSignalLatestRead(
        scan_run_id=run_id,
        signals_classified=classified,
        items=items,
    )


def list_industry_release_signals(
    session: Session,
    *,
    owner_user_id: int,
    scan_run_id: int | None = None,
    signal_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IndustryReleaseSignalRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    run_id = scan_run_id or latest_scan_run_id(session, owner_user_id=owner_user_id)
    if run_id is None:
        return [], 0

    statement = (
        select(IndustryReleaseSignal, IndustryReleaseCandidate)
        .join(IndustryReleaseCandidate, IndustryReleaseCandidate.id == IndustryReleaseSignal.candidate_id)
        .where(IndustryReleaseSignal.owner_user_id == owner_user_id)
        .where(IndustryReleaseSignal.scan_run_id == run_id)
    )
    if signal_type:
        statement = statement.where(IndustryReleaseSignal.signal_type == signal_type.strip().upper())

    rows = session.exec(
        statement.order_by(
            IndustryReleaseSignal.confidence_score.desc(),
            IndustryReleaseCandidate.series_name.asc(),
            IndustryReleaseCandidate.issue_number.asc(),
            IndustryReleaseSignal.signal_type.asc(),
        )
    ).all()
    items = [_signal_to_read(signal, candidate=candidate) for signal, candidate in rows]
    total = len(items)
    return items[offset : offset + limit], total
