import re

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import CanonicalCreator
from app.models.asset_ledger import utc_now
from app.schemas.ops import OpsCanonicalCreatorRow
from app.services.metadata_audits import record_metadata_audit


def _normalize_creator_component(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def compute_creator_key(normalized_name: str) -> str:
    normalized = _normalize_creator_component(normalized_name).lower()
    return f"creator:{normalized}"


def get_or_create_canonical_creator(
    session: Session,
    *,
    canonical_name: str,
    normalized_name: str,
    actor_user_id: int | None = None,
    audit_reason: str | None = None,
) -> CanonicalCreator:
    normalized = _normalize_creator_component(normalized_name).lower()
    canonical = _normalize_creator_component(canonical_name)
    creator_key = compute_creator_key(normalized)
    existing = session.exec(
        select(CanonicalCreator).where(CanonicalCreator.creator_key == creator_key)
    ).first()
    now = utc_now()

    if existing is not None:
        existing.last_seen_at = now
        existing.updated_at = now
        if canonical and canonical != existing.canonical_name:
            existing.canonical_name = canonical
        if normalized and normalized != existing.normalized_name:
            existing.normalized_name = normalized
        session.add(existing)
        session.flush()
        return existing

    canonical_creator = CanonicalCreator(
        canonical_name=canonical,
        normalized_name=normalized,
        creator_key=creator_key,
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
        is_active=True,
    )
    session.add(canonical_creator)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="canonical_creator",
        entity_id=canonical_creator.id,
        action="enriched",
        after_snapshot=canonical_creator,
        reason=audit_reason,
        actor_user_id=actor_user_id,
    )
    return canonical_creator


def list_canonical_creators_registry(
    session: Session,
    *,
    name: str | None = None,
    canonical_name: str | None = None,
    normalized_name: str | None = None,
    creator_key: str | None = None,
) -> list[OpsCanonicalCreatorRow]:
    name_filter = name.strip() if name else ""
    canonical_name_filter = canonical_name.strip() if canonical_name else ""
    normalized_name_filter = normalized_name.strip() if normalized_name else ""
    creator_key_filter = creator_key.strip() if creator_key else ""
    stmt = select(CanonicalCreator).order_by(
        CanonicalCreator.canonical_name.asc(),
        CanonicalCreator.id.asc(),
    )
    if name_filter:
        search_term = f"%{name_filter}%"
        stmt = stmt.where(
            or_(
                CanonicalCreator.canonical_name.ilike(search_term),
                CanonicalCreator.normalized_name.ilike(search_term),
                CanonicalCreator.creator_key.ilike(search_term),
            )
        )

    if canonical_name_filter:
        stmt = stmt.where(
            CanonicalCreator.canonical_name.ilike(f"%{canonical_name_filter}%")
        )
    if normalized_name_filter:
        stmt = stmt.where(
            CanonicalCreator.normalized_name.ilike(f"%{normalized_name_filter}%")
        )
    if creator_key_filter:
        stmt = stmt.where(CanonicalCreator.creator_key.ilike(f"%{creator_key_filter}%"))

    rows = session.exec(stmt).all()
    return [OpsCanonicalCreatorRow.model_validate(row, from_attributes=True) for row in rows]
