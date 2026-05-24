from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models import MetadataAlias
from app.schemas.metadata_aliases import (
    MetadataAliasCreate,
    MetadataAliasRead,
    MetadataAliasType,
    MetadataAliasUpdate,
)
from app.services.metadata_audits import record_metadata_audit

STATIC_PUBLISHER_ALIAS_MAP = {
    "dc": "DC",
    "dc comics": "DC",
    "marvel": "Marvel",
    "marvel comics": "Marvel",
    "image": "Image",
    "image comics": "Image",
    "idw": "IDW",
    "idw publishing": "IDW",
    "mad cave": "Mad Cave",
    "mad cave studios": "Mad Cave",
}

DEFAULT_METADATA_ALIAS_TYPE: MetadataAliasType = "publisher"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_spaces(value: str) -> str:
    return " ".join(value.split()).strip()


def normalize_alias_lookup_key(value: str | None) -> str:
    if value is None:
        return ""
    return _normalize_spaces(value).lower()


def serialize_metadata_alias(alias: MetadataAlias) -> MetadataAliasRead:
    if alias.id is None:
        raise HTTPException(status_code=500, detail="Metadata alias is missing an identifier")
    return MetadataAliasRead(
        id=alias.id,
        alias_value=alias.alias_value,
        canonical_value=alias.canonical_value,
        alias_type=alias.alias_type,  # type: ignore[arg-type]
        source=alias.source,
        is_active=alias.is_active,
        created_at=alias.created_at,
        updated_at=alias.updated_at,
    )


def get_active_db_alias_value(
    session: Session,
    *,
    alias_type: MetadataAliasType,
    alias_value: str,
) -> str | None:
    lookup_key = normalize_alias_lookup_key(alias_value)
    if not lookup_key:
        return None

    alias = session.exec(
        select(MetadataAlias)
        .where(
            MetadataAlias.alias_type == alias_type,
            MetadataAlias.is_active.is_(True),
            func.lower(MetadataAlias.alias_value) == lookup_key,
        )
        .order_by(MetadataAlias.updated_at.desc(), MetadataAlias.id.desc())
    ).first()
    if alias is None:
        return None
    return alias.canonical_value


def list_metadata_aliases(
    session: Session,
    *,
    alias_type: MetadataAliasType | None = None,
    is_active: bool | None = None,
) -> list[MetadataAliasRead]:
    stmt = select(MetadataAlias)
    if alias_type is not None:
        stmt = stmt.where(MetadataAlias.alias_type == alias_type)
    if is_active is not None:
        stmt = stmt.where(MetadataAlias.is_active.is_(is_active))
    aliases = session.exec(
        stmt.order_by(
            MetadataAlias.is_active.desc(),
            MetadataAlias.alias_type.asc(),
            MetadataAlias.alias_value.asc(),
        )
    ).all()
    return [serialize_metadata_alias(alias) for alias in aliases if alias.id is not None]


def _get_alias_or_404(
    session: Session,
    *,
    alias_id: int,
) -> MetadataAlias:
    alias = session.exec(select(MetadataAlias).where(MetadataAlias.id == alias_id)).first()
    if alias is None:
        raise HTTPException(status_code=404, detail="Metadata alias not found")
    return alias


def _ensure_alias_value_available(
    session: Session,
    *,
    alias_type: MetadataAliasType,
    alias_value: str,
    exclude_alias_id: int | None = None,
) -> None:
    lookup_key = normalize_alias_lookup_key(alias_value)
    existing = session.exec(
        select(MetadataAlias).where(
            MetadataAlias.alias_type == alias_type,
            func.lower(MetadataAlias.alias_value) == lookup_key,
        )
    ).all()
    for alias in existing:
        if exclude_alias_id is not None and alias.id == exclude_alias_id:
            continue
        raise HTTPException(status_code=400, detail="Metadata alias already exists")


def create_metadata_alias(
    session: Session,
    *,
    payload: MetadataAliasCreate,
    actor_user_id: int | None = None,
) -> MetadataAliasRead:
    _ensure_alias_value_available(
        session,
        alias_type=payload.alias_type,
        alias_value=payload.alias_value,
    )
    timestamp = utc_now()
    alias = MetadataAlias(
        alias_value=_normalize_spaces(payload.alias_value),
        canonical_value=_normalize_spaces(payload.canonical_value),
        alias_type=payload.alias_type,
        source="manual",
        is_active=True,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(alias)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="metadata_alias",
        entity_id=alias.id,
        action="alias_created",
        after_snapshot=alias,
        reason="Manual metadata alias created.",
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(alias)
    return serialize_metadata_alias(alias)


def update_metadata_alias(
    session: Session,
    *,
    alias_id: int,
    payload: MetadataAliasUpdate,
    actor_user_id: int | None = None,
) -> MetadataAliasRead:
    alias = _get_alias_or_404(session, alias_id=alias_id)
    before_snapshot = alias.model_dump()

    if payload.alias_value is not None:
        _ensure_alias_value_available(
            session,
            alias_type=alias.alias_type,  # type: ignore[arg-type]
            alias_value=payload.alias_value,
            exclude_alias_id=alias.id,
        )
        alias.alias_value = _normalize_spaces(payload.alias_value)
    if payload.canonical_value is not None:
        alias.canonical_value = _normalize_spaces(payload.canonical_value)
    if payload.is_active is not None:
        alias.is_active = payload.is_active

    alias.updated_at = utc_now()
    session.add(alias)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="metadata_alias",
        entity_id=alias.id,
        action="alias_updated",
        before_snapshot=before_snapshot,
        after_snapshot=alias,
        reason="Metadata alias updated.",
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(alias)
    return serialize_metadata_alias(alias)


def deactivate_metadata_alias(
    session: Session,
    *,
    alias_id: int,
    actor_user_id: int | None = None,
) -> MetadataAliasRead:
    alias = _get_alias_or_404(session, alias_id=alias_id)
    before_snapshot = alias.model_dump()
    alias.is_active = False
    alias.updated_at = utc_now()
    session.add(alias)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="metadata_alias",
        entity_id=alias.id,
        action="alias_deactivated",
        before_snapshot=before_snapshot,
        after_snapshot=alias,
        reason="Metadata alias deactivated.",
        actor_user_id=actor_user_id,
    )
    session.commit()
    session.refresh(alias)
    return serialize_metadata_alias(alias)
