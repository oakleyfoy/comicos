from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import CoverImage, CoverImageLinkDecision, CoverImageMatchCandidate, DraftImport, InventoryCopy, User
from app.schemas.cover_link_decisions import CoverImageLinkDecisionCreate, CoverImageLinkDecisionRead
from app.services.metadata_audits import record_metadata_audit


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def cover_link_pair_key(source_cover_image_id: int, candidate_cover_image_id: int) -> str:
    left, right = sorted((int(source_cover_image_id), int(candidate_cover_image_id)))
    return f"{left}:{right}"


def _reviewer_email_map(session: Session, reviewer_ids: set[int]) -> dict[int, str]:
    if not reviewer_ids:
        return {}
    rows = session.exec(select(User).where(User.id.in_(sorted(reviewer_ids)))).all()
    return {row.id: row.email for row in rows if row.id is not None}


def _normalize_reason(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _decision_snapshot(row: CoverImageLinkDecision) -> dict[str, object]:
    return {
        "id": row.id,
        "source_cover_image_id": row.source_cover_image_id,
        "candidate_cover_image_id": row.candidate_cover_image_id,
        "pair_key": row.pair_key,
        "source_match_candidate_id": row.source_match_candidate_id,
        "decision_type": row.decision_type,
        "relationship_type": row.relationship_type,
        "decision_state": row.decision_state,
        "reviewer_user_id": row.reviewer_user_id,
        "decision_reason": row.decision_reason,
        "decision_source": row.decision_source,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "reverted_at": row.reverted_at,
        "superseded_by_decision_id": row.superseded_by_decision_id,
    }


def cover_link_decision_entity_to_read(
    session: Session,
    row: CoverImageLinkDecision,
    *,
    reviewer_emails: dict[int, str] | None = None,
) -> CoverImageLinkDecisionRead:
    if row.id is None:
        raise ValueError("cover link decision must be flushed before serialization")
    emails = reviewer_emails or _reviewer_email_map(
        session, {row.reviewer_user_id} if row.reviewer_user_id is not None else set()
    )
    return CoverImageLinkDecisionRead(
        id=row.id,
        source_cover_image_id=row.source_cover_image_id,
        candidate_cover_image_id=row.candidate_cover_image_id,
        pair_key=row.pair_key,
        source_match_candidate_id=row.source_match_candidate_id,
        decision_type=row.decision_type,  # type: ignore[arg-type]
        relationship_type=row.relationship_type,  # type: ignore[arg-type]
        decision_state=row.decision_state,  # type: ignore[arg-type]
        reviewer_user_id=row.reviewer_user_id,
        reviewer_user_email=emails.get(row.reviewer_user_id) if row.reviewer_user_id is not None else None,
        decision_reason=row.decision_reason,
        decision_source=row.decision_source,  # type: ignore[arg-type]
        created_at=row.created_at,
        updated_at=row.updated_at,
        reverted_at=row.reverted_at,
        superseded_by_decision_id=row.superseded_by_decision_id,
    )


def active_cover_link_decisions_for_pairs(
    session: Session,
    *,
    pairs: list[tuple[int, int]],
) -> dict[str, CoverImageLinkDecision]:
    pair_keys = sorted({cover_link_pair_key(left, right) for left, right in pairs})
    if not pair_keys:
        return {}
    rows = session.exec(
        select(CoverImageLinkDecision)
        .where(
            CoverImageLinkDecision.pair_key.in_(pair_keys),
            CoverImageLinkDecision.decision_state == "active",
        )
        .order_by(CoverImageLinkDecision.updated_at.desc(), CoverImageLinkDecision.id.desc())
    ).all()
    out: dict[str, CoverImageLinkDecision] = {}
    for row in rows:
        if row.pair_key not in out:
            out[row.pair_key] = row
    return out


def get_cover_link_decision_or_404(session: Session, decision_id: int) -> CoverImageLinkDecision:
    row = session.get(CoverImageLinkDecision, decision_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cover link decision not found")
    return row


def get_cover_match_candidate_or_404(session: Session, match_candidate_id: int) -> CoverImageMatchCandidate:
    row = session.get(CoverImageMatchCandidate, match_candidate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Cover image match candidate not found")
    return row


def get_cover_or_404(session: Session, cover_image_id: int) -> CoverImage:
    cover = session.get(CoverImage, cover_image_id)
    if cover is None:
        raise HTTPException(status_code=404, detail="Cover image not found")
    return cover


def owner_can_access_cover(session: Session, *, cover: CoverImage, current_user: User) -> bool:
    if current_user.id is None:
        return False
    if cover.inventory_copy_id is not None:
        owner_id = session.exec(
            select(InventoryCopy.user_id).where(InventoryCopy.id == cover.inventory_copy_id)
        ).first()
        return owner_id == current_user.id
    if cover.draft_import_id is not None:
        owner_id = session.exec(select(DraftImport.user_id).where(DraftImport.id == cover.draft_import_id)).first()
        return owner_id == current_user.id
    return False


def _require_owner_access_to_source_cover(
    session: Session,
    *,
    source_cover_image_id: int,
    current_user: User,
) -> CoverImage:
    cover = get_cover_or_404(session, source_cover_image_id)
    if not owner_can_access_cover(session, cover=cover, current_user=current_user):
        raise HTTPException(status_code=404, detail="Cover image not found")
    return cover


def _require_owner_access_to_decision(
    session: Session,
    *,
    decision: CoverImageLinkDecision,
    current_user: User,
) -> None:
    source_cover = get_cover_or_404(session, decision.source_cover_image_id)
    candidate_cover = get_cover_or_404(session, decision.candidate_cover_image_id)
    if owner_can_access_cover(session, cover=source_cover, current_user=current_user):
        return
    if owner_can_access_cover(session, cover=candidate_cover, current_user=current_user):
        return
    raise HTTPException(status_code=404, detail="Cover link decision not found")


def _validate_decision_payload(payload: CoverImageLinkDecisionCreate) -> None:
    if payload.source_cover_image_id == payload.candidate_cover_image_id:
        raise HTTPException(status_code=400, detail="Self-link decisions are not allowed")
    if payload.decision_type == "approved_link" and payload.relationship_type == "unrelated":
        raise HTTPException(status_code=400, detail="Approved links cannot use relationship_type unrelated")
    if payload.decision_type == "rejected_link" and payload.relationship_type != "unrelated":
        raise HTTPException(status_code=400, detail="Rejected links must use relationship_type unrelated")


def _resolve_payload_match_candidate(
    session: Session,
    *,
    payload: CoverImageLinkDecisionCreate,
) -> CoverImageMatchCandidate | None:
    if payload.source_match_candidate_id is None:
        return None
    candidate = get_cover_match_candidate_or_404(session, payload.source_match_candidate_id)
    if candidate.source_cover_image_id != payload.source_cover_image_id:
        raise HTTPException(status_code=400, detail="source_match_candidate_id does not match source_cover_image_id")
    if candidate.candidate_cover_image_id != payload.candidate_cover_image_id:
        raise HTTPException(status_code=400, detail="source_match_candidate_id does not match candidate_cover_image_id")
    return candidate


def _decision_action_for_type(decision_type: str) -> str | None:
    if decision_type == "approved_link":
        return "cover_link_decision_approved"
    if decision_type == "rejected_link":
        return "cover_link_decision_rejected"
    return None


def _finalize_decision_read(session: Session, row: CoverImageLinkDecision) -> CoverImageLinkDecisionRead:
    session.refresh(row)
    return cover_link_decision_entity_to_read(session, row)


def create_cover_link_decision(
    session: Session,
    *,
    payload: CoverImageLinkDecisionCreate,
    reviewer_user_id: int | None,
    decision_source: str = "human",
) -> CoverImageLinkDecision:
    _validate_decision_payload(payload)
    _resolve_payload_match_candidate(session, payload=payload)
    get_cover_or_404(session, payload.source_cover_image_id)
    get_cover_or_404(session, payload.candidate_cover_image_id)

    pair_key = cover_link_pair_key(payload.source_cover_image_id, payload.candidate_cover_image_id)
    now = utc_now()
    active_rows = session.exec(
        select(CoverImageLinkDecision)
        .where(
            CoverImageLinkDecision.pair_key == pair_key,
            CoverImageLinkDecision.decision_state == "active",
        )
        .order_by(CoverImageLinkDecision.updated_at.desc(), CoverImageLinkDecision.id.desc())
    ).all()

    normalized_reason = _normalize_reason(payload.decision_reason)
    for existing in active_rows:
        if (
            existing.source_cover_image_id == payload.source_cover_image_id
            and existing.candidate_cover_image_id == payload.candidate_cover_image_id
            and existing.source_match_candidate_id == payload.source_match_candidate_id
            and existing.decision_type == payload.decision_type
            and existing.relationship_type == payload.relationship_type
            and _normalize_reason(existing.decision_reason) == normalized_reason
            and existing.decision_source == decision_source
        ):
            return existing

    row = CoverImageLinkDecision(
        source_cover_image_id=payload.source_cover_image_id,
        candidate_cover_image_id=payload.candidate_cover_image_id,
        pair_key=pair_key,
        source_match_candidate_id=payload.source_match_candidate_id,
        decision_type=payload.decision_type,
        relationship_type=payload.relationship_type,
        decision_state="active",
        reviewer_user_id=reviewer_user_id,
        decision_reason=normalized_reason,
        decision_source=decision_source,
        created_at=now,
        updated_at=now,
        reverted_at=None,
        superseded_by_decision_id=None,
    )
    session.add(row)
    session.flush()

    for existing in active_rows:
        before = _decision_snapshot(existing)
        existing.decision_state = "superseded"
        existing.updated_at = now
        existing.superseded_by_decision_id = row.id
        session.add(existing)
        session.flush()
        record_metadata_audit(
            session,
            entity_type="cover_link_decision",
            entity_id=existing.id or -1,
            action="cover_link_decision_superseded",
            before_snapshot=before,
            after_snapshot=_decision_snapshot(existing),
            actor_user_id=reviewer_user_id,
        )

    record_metadata_audit(
        session,
        entity_type="cover_link_decision",
        entity_id=row.id or -1,
        action="cover_link_decision_created",
        before_snapshot=None,
        after_snapshot=_decision_snapshot(row),
        actor_user_id=reviewer_user_id,
    )
    action = _decision_action_for_type(row.decision_type)
    if action is not None:
        record_metadata_audit(
            session,
            entity_type="cover_link_decision",
            entity_id=row.id or -1,
            action=action,
            before_snapshot=None,
            after_snapshot=_decision_snapshot(row),
            actor_user_id=reviewer_user_id,
        )
    session.commit()
    return row


def create_cover_link_decision_for_owner(
    session: Session,
    *,
    payload: CoverImageLinkDecisionCreate,
    current_user: User,
) -> CoverImageLinkDecisionRead:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    _require_owner_access_to_source_cover(
        session,
        source_cover_image_id=payload.source_cover_image_id,
        current_user=current_user,
    )
    row = create_cover_link_decision(
        session,
        payload=payload,
        reviewer_user_id=current_user.id,
        decision_source="human",
    )
    return _finalize_decision_read(session, row)


def create_cover_link_decision_for_ops(
    session: Session,
    *,
    payload: CoverImageLinkDecisionCreate,
    actor_user_id: int,
) -> CoverImageLinkDecisionRead:
    row = create_cover_link_decision(
        session,
        payload=payload,
        reviewer_user_id=actor_user_id,
        decision_source="human",
    )
    return _finalize_decision_read(session, row)


def get_cover_link_decision_for_owner(
    session: Session,
    *,
    decision_id: int,
    current_user: User,
) -> CoverImageLinkDecisionRead:
    row = get_cover_link_decision_or_404(session, decision_id)
    _require_owner_access_to_decision(session, decision=row, current_user=current_user)
    return cover_link_decision_entity_to_read(session, row)


def get_cover_link_decision_for_ops(
    session: Session,
    *,
    decision_id: int,
) -> CoverImageLinkDecisionRead:
    row = get_cover_link_decision_or_404(session, decision_id)
    return cover_link_decision_entity_to_read(session, row)


def list_cover_link_decisions_for_owner(
    session: Session,
    *,
    current_user: User,
    cover_image_id: int | None = None,
    include_inactive: bool = False,
    limit: int = 50,
) -> list[CoverImageLinkDecisionRead]:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    stmt = select(CoverImageLinkDecision)
    if cover_image_id is not None:
        stmt = stmt.where(
            or_(
                CoverImageLinkDecision.source_cover_image_id == cover_image_id,
                CoverImageLinkDecision.candidate_cover_image_id == cover_image_id,
            )
        )
    if not include_inactive:
        stmt = stmt.where(CoverImageLinkDecision.decision_state == "active")
    rows = session.exec(
        stmt.order_by(CoverImageLinkDecision.created_at.desc(), CoverImageLinkDecision.id.desc()).limit(max(1, limit * 3))
    ).all()
    visible = []
    reviewer_ids: set[int] = set()
    for row in rows:
        source_cover = get_cover_or_404(session, row.source_cover_image_id)
        candidate_cover = get_cover_or_404(session, row.candidate_cover_image_id)
        if not (
            owner_can_access_cover(session, cover=source_cover, current_user=current_user)
            or owner_can_access_cover(session, cover=candidate_cover, current_user=current_user)
        ):
            continue
        visible.append(row)
        if row.reviewer_user_id is not None:
            reviewer_ids.add(row.reviewer_user_id)
        if len(visible) >= limit:
            break
    emails = _reviewer_email_map(session, reviewer_ids)
    return [cover_link_decision_entity_to_read(session, row, reviewer_emails=emails) for row in visible]


def list_cover_link_decisions_for_ops(
    session: Session,
    *,
    cover_image_id: int | None = None,
    include_inactive: bool = False,
    limit: int = 50,
) -> list[CoverImageLinkDecisionRead]:
    stmt = select(CoverImageLinkDecision)
    if cover_image_id is not None:
        stmt = stmt.where(
            or_(
                CoverImageLinkDecision.source_cover_image_id == cover_image_id,
                CoverImageLinkDecision.candidate_cover_image_id == cover_image_id,
            )
        )
    if not include_inactive:
        stmt = stmt.where(CoverImageLinkDecision.decision_state == "active")
    rows = session.exec(
        stmt.order_by(CoverImageLinkDecision.created_at.desc(), CoverImageLinkDecision.id.desc()).limit(max(1, limit))
    ).all()
    reviewer_ids = {row.reviewer_user_id for row in rows if row.reviewer_user_id is not None}
    emails = _reviewer_email_map(session, reviewer_ids)
    return [cover_link_decision_entity_to_read(session, row, reviewer_emails=emails) for row in rows]


def revert_cover_link_decision(
    session: Session,
    *,
    decision: CoverImageLinkDecision,
    actor_user_id: int | None,
) -> CoverImageLinkDecision:
    if decision.decision_state != "active":
        raise HTTPException(status_code=400, detail="Only active cover link decisions can be reverted")
    before = _decision_snapshot(decision)
    now = utc_now()
    decision.decision_state = "reverted"
    decision.reverted_at = now
    decision.updated_at = now
    session.add(decision)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="cover_link_decision",
        entity_id=decision.id or -1,
        action="cover_link_decision_reverted",
        before_snapshot=before,
        after_snapshot=_decision_snapshot(decision),
        actor_user_id=actor_user_id,
    )
    session.commit()
    return decision


def revert_cover_link_decision_for_owner(
    session: Session,
    *,
    decision_id: int,
    current_user: User,
) -> CoverImageLinkDecisionRead:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    row = get_cover_link_decision_or_404(session, decision_id)
    _require_owner_access_to_decision(session, decision=row, current_user=current_user)
    reverted = revert_cover_link_decision(session, decision=row, actor_user_id=current_user.id)
    return _finalize_decision_read(session, reverted)


def revert_cover_link_decision_for_ops(
    session: Session,
    *,
    decision_id: int,
    actor_user_id: int,
) -> CoverImageLinkDecisionRead:
    row = get_cover_link_decision_or_404(session, decision_id)
    reverted = revert_cover_link_decision(session, decision=row, actor_user_id=actor_user_id)
    return _finalize_decision_read(session, reverted)

