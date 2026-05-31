from __future__ import annotations

from sqlmodel import Session, select

from app.models.marketplace_acquisition import (
    DEFAULT_CANDIDATE_STATUS,
    DEFAULT_RECOMMENDATION,
    MarketplaceAcquisitionCandidate,
    MarketplaceSource,
    utc_now,
)
from app.schemas.marketplace_acquisition import (
    MarketplaceAcquisitionCandidateCreate,
    MarketplaceAcquisitionCandidateRead,
    MarketplaceAcquisitionCandidateUpdate,
    MarketplaceAcquisitionSummaryRead,
    MarketplaceSourceRead,
)
from app.services.marketplace_acquisition_matcher import match_candidate_to_opportunities
from app.services.marketplace_acquisition_scoring import score_marketplace_candidate

DEFAULT_SOURCES: tuple[tuple[str, str, str | None], ...] = (
    ("eBay", "EBAY", "https://www.ebay.com"),
    ("Whatnot", "WHATNOT", "https://www.whatnot.com"),
    ("MyComicShop", "MYCOMICSHOP", "https://www.mycomicshop.com"),
    ("ComicLink", "COMICLINK", "https://www.comiclink.com"),
    ("ComicConnect", "COMICCONNECT", "https://www.comicconnect.com"),
    ("Manual", "MANUAL", None),
)


class MarketplaceCandidateNotFoundError(LookupError):
    pass


def ensure_marketplace_acquisition_sources(session: Session) -> list[MarketplaceSource]:
    created: list[MarketplaceSource] = []
    for name, source_type, base_url in DEFAULT_SOURCES:
        existing = session.exec(
            select(MarketplaceSource).where(MarketplaceSource.source_type == source_type)
        ).first()
        if existing is not None:
            continue
        row = MarketplaceSource(name=name, source_type=source_type, base_url=base_url, is_active=True)
        session.add(row)
        created.append(row)
    if created:
        session.commit()
        for row in created:
            session.refresh(row)
    return list(session.exec(select(MarketplaceSource).order_by(MarketplaceSource.id)).all())


def list_marketplace_sources(session: Session) -> list[MarketplaceSourceRead]:
    ensure_marketplace_acquisition_sources(session)
    rows = session.exec(select(MarketplaceSource).where(MarketplaceSource.is_active == True).order_by(MarketplaceSource.id)).all()  # noqa: E712
    return [
        MarketplaceSourceRead(
            id=int(row.id or 0),
            name=row.name,
            source_type=row.source_type,  # type: ignore[arg-type]
            base_url=row.base_url,
            is_active=bool(row.is_active),
        )
        for row in rows
    ]


def _resolve_total_price(
    *,
    asking_price: float | None,
    shipping_price: float | None,
    total_price: float | None,
) -> float | None:
    if total_price is not None:
        return round(float(total_price), 2)
    if asking_price is None:
        return None
    ship = float(shipping_price or 0)
    return round(float(asking_price) + ship, 2)


def _get_candidate_row(session: Session, *, owner_user_id: int, candidate_id: int) -> MarketplaceAcquisitionCandidate:
    row = session.get(MarketplaceAcquisitionCandidate, candidate_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise MarketplaceCandidateNotFoundError(f"Candidate {candidate_id} not found.")
    return row


def _source_map(session: Session) -> dict[int, MarketplaceSource]:
    ensure_marketplace_acquisition_sources(session)
    rows = session.exec(select(MarketplaceSource)).all()
    return {int(r.id or 0): r for r in rows}


def _to_read(session: Session, *, row: MarketplaceAcquisitionCandidate) -> MarketplaceAcquisitionCandidateRead:
    sources = _source_map(session)
    src = sources.get(int(row.marketplace_source_id or 0))
    return MarketplaceAcquisitionCandidateRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        marketplace_source_id=row.marketplace_source_id,
        source_name=src.name if src else None,
        source_type=src.source_type if src else None,  # type: ignore[arg-type]
        acquisition_opportunity_id=row.acquisition_opportunity_id,
        title=row.title,
        publisher=row.publisher,
        series_name=row.series_name,
        issue_number=row.issue_number,
        variant_description=row.variant_description,
        listing_url=row.listing_url,
        asking_price=row.asking_price,
        shipping_price=row.shipping_price,
        total_price=row.total_price,
        condition_description=row.condition_description,
        grade_label=row.grade_label,
        seller_name=row.seller_name,
        match_confidence=float(row.match_confidence),
        value_score=float(row.value_score),
        recommendation=row.recommendation,  # type: ignore[arg-type]
        rationale=row.rationale,
        status=row.status,  # type: ignore[arg-type]
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def create_marketplace_candidate(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketplaceAcquisitionCandidateCreate,
) -> MarketplaceAcquisitionCandidateRead:
    ensure_marketplace_acquisition_sources(session)
    source_id = payload.marketplace_source_id
    if source_id is None:
        manual = session.exec(select(MarketplaceSource).where(MarketplaceSource.source_type == "MANUAL")).first()
        source_id = int(manual.id or 0) if manual else None
    total = _resolve_total_price(
        asking_price=payload.asking_price,
        shipping_price=payload.shipping_price,
        total_price=payload.total_price,
    )
    row = MarketplaceAcquisitionCandidate(
        owner_user_id=owner_user_id,
        marketplace_source_id=source_id,
        title=payload.title.strip(),
        publisher=(payload.publisher or "").strip() or None,
        series_name=(payload.series_name or "").strip() or None,
        issue_number=(payload.issue_number or "").strip() or None,
        variant_description=(payload.variant_description or "").strip() or None,
        listing_url=(payload.listing_url or "").strip() or None,
        asking_price=payload.asking_price,
        shipping_price=payload.shipping_price,
        total_price=total,
        condition_description=(payload.condition_description or "").strip() or None,
        grade_label=(payload.grade_label or "").strip() or None,
        seller_name=(payload.seller_name or "").strip() or None,
        recommendation=DEFAULT_RECOMMENDATION,
        status=DEFAULT_CANDIDATE_STATUS,
        rationale="Manual marketplace candidate captured; run evaluate for match and value guidance.",
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(session, row=row)


def update_marketplace_candidate(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
    payload: MarketplaceAcquisitionCandidateUpdate,
) -> MarketplaceAcquisitionCandidateRead:
    row = _get_candidate_row(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    if payload.marketplace_source_id is not None:
        row.marketplace_source_id = payload.marketplace_source_id
    if payload.title is not None:
        row.title = payload.title.strip()
    if payload.publisher is not None:
        row.publisher = payload.publisher.strip() or None
    if payload.series_name is not None:
        row.series_name = payload.series_name.strip() or None
    if payload.issue_number is not None:
        row.issue_number = payload.issue_number.strip() or None
    if payload.variant_description is not None:
        row.variant_description = payload.variant_description.strip() or None
    if payload.listing_url is not None:
        row.listing_url = payload.listing_url.strip() or None
    if payload.asking_price is not None:
        row.asking_price = payload.asking_price
    if payload.shipping_price is not None:
        row.shipping_price = payload.shipping_price
    if payload.total_price is not None:
        row.total_price = payload.total_price
    if payload.condition_description is not None:
        row.condition_description = payload.condition_description.strip() or None
    if payload.grade_label is not None:
        row.grade_label = payload.grade_label.strip() or None
    if payload.seller_name is not None:
        row.seller_name = payload.seller_name.strip() or None
    if payload.status is not None:
        row.status = payload.status
    row.total_price = _resolve_total_price(
        asking_price=row.asking_price,
        shipping_price=row.shipping_price,
        total_price=row.total_price,
    )
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(session, row=row)


def list_marketplace_candidates(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    publisher: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MarketplaceAcquisitionCandidateRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    sources = _source_map(session)
    source_ids: set[int] | None = None
    if source_type:
        st = source_type.strip().upper()
        source_ids = {sid for sid, src in sources.items() if src.source_type == st}

    stmt = select(MarketplaceAcquisitionCandidate).where(MarketplaceAcquisitionCandidate.owner_user_id == owner_user_id)
    if recommendation:
        stmt = stmt.where(MarketplaceAcquisitionCandidate.recommendation == recommendation.strip().upper())
    if status:
        stmt = stmt.where(MarketplaceAcquisitionCandidate.status == status.strip().upper())
    if source_ids is not None:
        if not source_ids:
            return [], 0
        stmt = stmt.where(MarketplaceAcquisitionCandidate.marketplace_source_id.in_(list(source_ids)))  # type: ignore[attr-defined]

    rows = list(session.exec(stmt.order_by(MarketplaceAcquisitionCandidate.updated_at.desc(), MarketplaceAcquisitionCandidate.id.desc())).all())
    if publisher:
        pub = publisher.strip().lower()
        rows = [r for r in rows if pub in (r.publisher or "").lower() or pub in r.title.lower()]
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(session, row=r) for r in page], total


def get_marketplace_candidate(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
) -> MarketplaceAcquisitionCandidateRead:
    row = _get_candidate_row(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    return _to_read(session, row=row)


def evaluate_marketplace_candidate(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
) -> MarketplaceAcquisitionCandidateRead:
    row = _get_candidate_row(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    match = match_candidate_to_opportunities(session, owner_user_id=owner_user_id, candidate_id=candidate_id)
    row.acquisition_opportunity_id = match.acquisition_opportunity_id
    row.match_confidence = match.match_confidence
    session.add(row)
    session.flush()
    score = score_marketplace_candidate(session, candidate_id=candidate_id)
    row.value_score = score.value_score
    row.recommendation = score.recommendation
    parts = [match.rationale, score.rationale]
    row.rationale = " ".join(p for p in parts if p).strip()
    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_read(session, row=row)


def build_marketplace_acquisition_summary(session: Session, *, owner_user_id: int) -> MarketplaceAcquisitionSummaryRead:
    rows = list(
        session.exec(select(MarketplaceAcquisitionCandidate).where(MarketplaceAcquisitionCandidate.owner_user_id == owner_user_id)).all()
    )
    by_rec: dict[str, int] = {}
    by_status: dict[str, int] = {}
    match_sum = 0.0
    value_sum = 0.0
    for row in rows:
        by_rec[row.recommendation] = by_rec.get(row.recommendation, 0) + 1
        by_status[row.status] = by_status.get(row.status, 0) + 1
        match_sum += float(row.match_confidence)
        value_sum += float(row.value_score)
    count = len(rows)
    return MarketplaceAcquisitionSummaryRead(
        total_candidates=count,
        by_recommendation=by_rec,
        by_status=by_status,
        average_match_confidence=round(match_sum / count, 2) if count else 0.0,
        average_value_score=round(value_sum / count, 1) if count else 0.0,
        sources=list_marketplace_sources(session),
    )
