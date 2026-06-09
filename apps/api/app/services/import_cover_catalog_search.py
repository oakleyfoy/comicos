"""Catalog cover candidates for import line review."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import User
from app.models.external_catalog import ExternalCatalogVariant
from app.schemas.ai import ParseOrderResponse
from app.services.import_cover_resolver import (
    _resolve_external_issue_id,
    _variant_cover_letter,
)
from app.services.imports import get_import_for_user_or_404, normalize_parsed_order_response


@dataclass(frozen=True)
class ImportLineCoverCandidate:
    external_variant_id: int
    cover_label: str | None
    variant_name: str | None
    artist: str | None
    image_url: str | None
    cover_letter: str | None


def list_import_line_cover_candidates(
    session: Session,
    *,
    owner_user_id: int,
    draft_import_id: int,
    line_index: int,
) -> list[ImportLineCoverCandidate]:
    from app.models import DraftImport

    draft = session.get(DraftImport, draft_import_id)
    if draft is None or draft.user_id != owner_user_id:
        return []

    parsed = ParseOrderResponse.model_validate(draft.parsed_payload_json)
    if line_index < 0 or line_index >= len(parsed.items):
        return []

    item = parsed.items[line_index].model_dump(mode="json")
    external_issue_id = _resolve_external_issue_id(
        session,
        owner_user_id=owner_user_id,
        item=item,
        catalog_resolution=None,
    )
    if external_issue_id is None:
        return []

    variants = session.exec(
        select(ExternalCatalogVariant)
        .where(ExternalCatalogVariant.external_issue_id == external_issue_id)
        .order_by(ExternalCatalogVariant.id.asc())
    ).all()

    return [
        ImportLineCoverCandidate(
            external_variant_id=int(variant.id or 0),
            cover_label=variant.cover_label,
            variant_name=variant.variant_name,
            artist=variant.artist,
            image_url=variant.image_url,
            cover_letter=_variant_cover_letter(variant),
        )
        for variant in variants
        if variant.id is not None
    ]


def apply_import_line_cover_candidate(
    session: Session,
    *,
    current_user: User,
    draft_import_id: int,
    line_index: int,
    external_variant_id: int,
) -> None:
    from datetime import datetime, timezone

    from app.services.import_cover_resolver import apply_import_cover_to_parse_order
    from app.services.import_line_cover_resolution_service import persist_parse_order_line_cover_resolutions

    draft_import = get_import_for_user_or_404(session, current_user, draft_import_id)
    if draft_import.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft imports can be edited.")

    variant = session.get(ExternalCatalogVariant, external_variant_id)
    if variant is None or not variant.image_url:
        raise HTTPException(status_code=404, detail="Cover variant not found.")

    parsed = ParseOrderResponse.model_validate(draft_import.parsed_payload_json)
    if line_index < 0 or line_index >= len(parsed.items):
        raise HTTPException(status_code=422, detail="Invalid import line index.")

    items = list(parsed.items)
    now = datetime.now(timezone.utc)
    items[line_index] = items[line_index].model_copy(
        update={
            "cover_image_url": variant.image_url,
            "cover_thumbnail_url": variant.image_url,
            "cover_image_source": "external_catalog_variant",
            "cover_image_source_id": variant.id,
            "has_cover_image": True,
            "cover_source": "LOCG",
            "cover_confidence": 1.0,
            "variant_confidence": 1.0,
            "cover_verified_by": "USER",
            "cover_verified_at": now,
        }
    )
    parsed = parsed.model_copy(update={"items": items})
    normalized_payload = normalize_parsed_order_response(
        parsed,
        session=session,
        owner_user_id=current_user.id,
        raw_text=draft_import.raw_text,
    )
    normalized_payload = apply_import_cover_to_parse_order(
        normalized_payload,
        session=session,
        owner_user_id=current_user.id,
        draft_import_id=draft_import_id,
    )
    persist_parse_order_line_cover_resolutions(
        session,
        owner_user_id=int(current_user.id),
        draft_import_id=draft_import_id,
        items=normalized_payload.items,
    )
    draft_import.parsed_payload_json = normalized_payload.model_dump(mode="json")
    draft_import.updated_at = now
    session.add(draft_import)
    session.commit()
