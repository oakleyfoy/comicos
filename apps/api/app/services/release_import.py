from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.schemas.release_intelligence import (
    ReleaseImportFeedRequest,
    ReleaseImportResult,
    ReleaseIssueImport,
    ReleaseIssueRead,
    ReleaseKeySignalRead,
    ReleaseSeriesImport,
    ReleaseSeriesRead,
    ReleaseVariantImport,
    ReleaseVariantRead,
)
from app.services.lunar_issue_resolution import (
    _apply_issue_import,
    maybe_promote_canonical_uuid,
    resolve_canonical_issue_for_import,
)


def import_series(session: Session, *, owner_user_id: int, payload: ReleaseSeriesImport) -> tuple[ReleaseSeries, bool]:
    row = session.exec(
        select(ReleaseSeries)
        .where(ReleaseSeries.owner_user_id == owner_user_id)
        .where(ReleaseSeries.publisher == payload.publisher)
        .where(ReleaseSeries.series_name == payload.series_name)
        .where(ReleaseSeries.series_type == payload.series_type)
    ).first()
    if row is not None:
        return row, False
    row = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher=payload.publisher,
        series_name=payload.series_name,
        series_type=payload.series_type,
        status=payload.status,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, True


def import_issues(
    session: Session,
    *,
    owner_user_id: int,
    series_id: int,
    payloads: list[ReleaseIssueImport],
) -> tuple[list[ReleaseIssue], int, int]:
    created = 0
    matched = 0
    rows: list[ReleaseIssue] = []
    for payload in payloads:
        existing, matched_by_key = resolve_canonical_issue_for_import(
            session,
            owner_user_id=owner_user_id,
            series_id=series_id,
            payload=payload,
        )
        if existing is not None:
            maybe_promote_canonical_uuid(
                session,
                owner_user_id=owner_user_id,
                row=existing,
                payload=payload,
            )
            _apply_issue_import(existing, payload)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            matched += 1
            rows.append(existing)
            continue

        row = ReleaseIssue(
            owner_user_id=owner_user_id,
            release_uuid=payload.release_uuid,
            series_id=series_id,
            issue_number=payload.issue_number,
            title=payload.title,
            foc_date=payload.foc_date,
            release_date=payload.release_date,
            cover_price=payload.cover_price,
            release_status=payload.release_status,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        created += 1
        rows.append(row)
    return rows, created, matched


def import_variants(
    session: Session,
    *,
    issue_id: int,
    payloads: list[ReleaseVariantImport],
    owner_user_id: int | None = None,
) -> tuple[list[ReleaseVariant], int, int]:
    created = 0
    matched = 0
    rows: list[ReleaseVariant] = []
    for payload in payloads:
        row = None
        if payload.variant_uuid:
            row = session.exec(
                select(ReleaseVariant)
                .where(ReleaseVariant.issue_id == issue_id)
                .where(ReleaseVariant.variant_uuid == payload.variant_uuid)
            ).first()
        if row is None and payload.variant_uuid and owner_user_id is not None:
            row = session.exec(
                select(ReleaseVariant)
                .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
                .where(ReleaseIssue.owner_user_id == owner_user_id)
                .where(ReleaseVariant.variant_uuid == payload.variant_uuid)
            ).first()
            if row is not None and int(row.issue_id) != issue_id:
                row.issue_id = issue_id
        if row is None:
            row = session.exec(
                select(ReleaseVariant)
                .where(ReleaseVariant.issue_id == issue_id)
                .where(ReleaseVariant.variant_name == payload.variant_name)
                .where(ReleaseVariant.variant_type == payload.variant_type)
            ).first()
        if row is None:
            row = ReleaseVariant(
                issue_id=issue_id,
                variant_uuid=payload.variant_uuid or "",
                variant_name=payload.variant_name,
                ratio_value=payload.ratio_value,
                ratio_type=payload.ratio_type,
                is_incentive_variant=payload.is_incentive_variant,
                variant_type=payload.variant_type,
                cover_artist=payload.cover_artist,
                source_item_code=payload.source_item_code,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            created += 1
        else:
            row.ratio_value = payload.ratio_value
            row.ratio_type = payload.ratio_type
            row.is_incentive_variant = payload.is_incentive_variant
            row.cover_artist = payload.cover_artist
            row.source_item_code = payload.source_item_code or row.source_item_code
            if payload.variant_uuid and not row.variant_uuid:
                row.variant_uuid = payload.variant_uuid
            session.add(row)
            session.commit()
            session.refresh(row)
            matched += 1
        rows.append(row)
    return rows, created, matched


def import_release_feed(
    session: Session,
    *,
    owner_user_id: int,
    payload: ReleaseImportFeedRequest,
) -> ReleaseImportResult:
    series_created = 0
    series_matched = 0
    issues_created = 0
    issues_matched = 0
    variants_created = 0
    variants_matched = 0
    for series_payload in payload.series:
        series, created = import_series(session, owner_user_id=owner_user_id, payload=series_payload)
        if created:
            series_created += 1
        else:
            series_matched += 1
        issues, issue_created, issue_matched = import_issues(
            session,
            owner_user_id=owner_user_id,
            series_id=int(series.id or 0),
            payloads=series_payload.issues,
        )
        issues_created += issue_created
        issues_matched += issue_matched
        for issue, issue_payload in zip(issues, series_payload.issues, strict=True):
            _, variant_created, variant_matched = import_variants(
                session,
                issue_id=int(issue.id or 0),
                payloads=issue_payload.variants,
                owner_user_id=owner_user_id,
            )
            variants_created += variant_created
            variants_matched += variant_matched
    return ReleaseImportResult(
        series_created=series_created,
        issues_created=issues_created,
        variants_created=variants_created,
        series_matched=series_matched,
        issues_matched=issues_matched,
        variants_matched=variants_matched,
    )


def list_series_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ReleaseSeries)
        .where(ReleaseSeries.owner_user_id == owner_user_id)
        .order_by(ReleaseSeries.publisher.asc(), ReleaseSeries.series_name.asc(), ReleaseSeries.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [ReleaseSeriesRead.model_validate(row) for row in page], len(rows)


def list_issues_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseIssue.release_date.asc(), ReleaseIssue.foc_date.asc(), ReleaseIssue.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [ReleaseIssueRead.model_validate(row) for row in page], len(rows)


def list_variants_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    issue_ids = [int(x) for x in session.exec(select(ReleaseIssue.id).where(ReleaseIssue.owner_user_id == owner_user_id)).all() if x]
    if not issue_ids:
        return [], 0
    rows = session.exec(
        select(ReleaseVariant)
        .where(ReleaseVariant.issue_id.in_(issue_ids))
        .order_by(ReleaseVariant.created_at.desc(), ReleaseVariant.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [ReleaseVariantRead.model_validate(row) for row in page], len(rows)


def list_signals_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
    signal_type: str | None = None,
):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    query = select(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)
    if signal_type is not None:
        query = query.where(ReleaseKeySignal.signal_type == signal_type)
    rows = session.exec(query.order_by(ReleaseKeySignal.created_at.desc(), ReleaseKeySignal.id.desc())).all()
    page = rows[offset : offset + limit]
    return [ReleaseKeySignalRead.model_validate(row) for row in page], len(rows)
