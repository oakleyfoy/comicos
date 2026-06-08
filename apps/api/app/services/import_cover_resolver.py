"""Resolve stored cover images for import draft items."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.models.asset_ledger import CoverImage, CoverImageDerivative
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch, ExternalCatalogVariant
from app.services.cover_images import cover_derivative_fetch_path, cover_fetch_path
from app.services.import_catalog_resolution_service import (
    ImportCatalogResolutionResult,
    normalize_import_title,
)


@dataclass
class ImportCoverResolutionResultPayload:
    cover_image_url: str | None
    cover_thumbnail_url: str | None
    cover_image_source: str | None
    cover_image_source_id: int | None
    has_cover_image: bool


def _text_tokens(value: str | None) -> set[str]:
    normalized = normalize_import_title(value)
    if not normalized:
        return set()
    return set(normalized.split())


def _variant_match_score(item: dict[str, Any], variant: ExternalCatalogVariant) -> int:
    score = 0
    cover_tokens = _text_tokens(item.get("cover_name"))
    variant_tokens = _text_tokens(" ".join(filter(None, [variant.cover_label, variant.variant_name])))
    if cover_tokens and variant_tokens:
        overlap = len(cover_tokens & variant_tokens)
        if overlap:
            score += overlap * 5
    artist_tokens = _text_tokens(item.get("cover_artist"))
    variant_artist_tokens = _text_tokens(variant.artist)
    if artist_tokens and variant_artist_tokens and artist_tokens & variant_artist_tokens:
        score += 10
    return score


def _resolve_external_issue_id(
    session: Session | None,
    *,
    owner_user_id: int | None,
    item: dict[str, Any],
    catalog_resolution: ImportCatalogResolutionResult | None,
) -> int | None:
    if session is None:
        return None
    if catalog_resolution and catalog_resolution.matched:
        if catalog_resolution.source == "ExternalCatalogIssue":
            return catalog_resolution.source_id
        if (
            catalog_resolution.source == "ReleaseIssue"
            and catalog_resolution.source_id is not None
            and owner_user_id is not None
        ):
            match = session.exec(
                select(ExternalCatalogMatch)
                .where(ExternalCatalogMatch.owner_user_id == owner_user_id)
                .where(ExternalCatalogMatch.release_issue_id == catalog_resolution.source_id)
                .order_by(
                    ExternalCatalogMatch.match_confidence.desc(),
                    ExternalCatalogMatch.updated_at.desc(),
                    ExternalCatalogMatch.id.desc(),
                )
            ).first()
            return match.external_issue_id if match is not None else None
    source = item.get("catalog_match_source")
    source_id = item.get("catalog_match_source_id")
    if source == "ExternalCatalogIssue" and source_id is not None:
        return int(source_id)
    if source == "ReleaseIssue" and source_id is not None and owner_user_id is not None:
        match = session.exec(
            select(ExternalCatalogMatch)
            .where(ExternalCatalogMatch.owner_user_id == owner_user_id)
            .where(ExternalCatalogMatch.release_issue_id == int(source_id))
            .order_by(
                ExternalCatalogMatch.match_confidence.desc(),
                ExternalCatalogMatch.updated_at.desc(),
                ExternalCatalogMatch.id.desc(),
            )
        ).first()
        return match.external_issue_id if match is not None else None
    return None


def _resolve_external_catalog_cover(
    session: Session,
    *,
    external_issue_id: int,
    item: dict[str, Any],
) -> ImportCoverResolutionResultPayload | None:
    variants = session.exec(
        select(ExternalCatalogVariant)
        .where(ExternalCatalogVariant.external_issue_id == external_issue_id)
        .where(ExternalCatalogVariant.image_url.is_not(None))  # type: ignore[attr-defined]
    ).all()
    if variants:
        best_variant = max(variants, key=lambda row: (_variant_match_score(item, row), -(row.id or 0)))
        if best_variant.image_url and best_variant.id is not None:
            return ImportCoverResolutionResultPayload(
                cover_image_url=best_variant.image_url,
                cover_thumbnail_url=best_variant.image_url,
                cover_image_source="external_catalog_variant",
                cover_image_source_id=best_variant.id,
                has_cover_image=True,
            )

    issue = session.get(ExternalCatalogIssue, external_issue_id)
    if issue is None:
        return None

    image_url = issue.high_resolution_image_url or issue.cover_image_url or issue.thumbnail_url
    thumb_url = issue.thumbnail_url or issue.cover_image_url or issue.high_resolution_image_url
    if image_url or thumb_url:
        return ImportCoverResolutionResultPayload(
            cover_image_url=image_url or thumb_url,
            cover_thumbnail_url=thumb_url or image_url,
            cover_image_source="external_catalog_issue",
            cover_image_source_id=external_issue_id,
            has_cover_image=True,
        )
    return None


def _resolve_draft_cover(
    session: Session,
    *,
    draft_import_id: int | None,
) -> ImportCoverResolutionResultPayload | None:
    if draft_import_id is None:
        return None
    cover = session.exec(
        select(CoverImage)
        .where(CoverImage.draft_import_id == draft_import_id)
        .order_by(CoverImage.created_at.asc(), CoverImage.id.asc())
    ).first()
    if cover is None or cover.id is None:
        return None

    derivatives = session.exec(
        select(CoverImageDerivative)
        .where(CoverImageDerivative.cover_image_id == cover.id)
    ).all()
    thumb = next(
        (cover_derivative_fetch_path(cover.id, row.derivative_type) for row in derivatives if row.derivative_type == "thumb"),
        None,
    )
    medium = next(
        (cover_derivative_fetch_path(cover.id, row.derivative_type) for row in derivatives if row.derivative_type == "medium"),
        None,
    )
    return ImportCoverResolutionResultPayload(
        cover_image_url=medium or cover_fetch_path(cover.id),
        cover_thumbnail_url=thumb or medium or cover_fetch_path(cover.id),
        cover_image_source="draft_cover_image",
        cover_image_source_id=cover.id,
        has_cover_image=True,
    )


def resolve_import_cover(
    session: Session | None,
    item: dict[str, Any],
    *,
    owner_user_id: int | None = None,
    draft_import_id: int | None = None,
    catalog_resolution: ImportCatalogResolutionResult | None = None,
) -> ImportCoverResolutionResultPayload:
    if session is not None:
        external_issue_id = _resolve_external_issue_id(
            session,
            owner_user_id=owner_user_id,
            item=item,
            catalog_resolution=catalog_resolution,
        )
        if external_issue_id is not None:
            external_cover = _resolve_external_catalog_cover(
                session,
                external_issue_id=external_issue_id,
                item=item,
            )
            if external_cover is not None:
                return external_cover

        draft_cover = _resolve_draft_cover(session, draft_import_id=draft_import_id)
        if draft_cover is not None:
            return draft_cover

    return ImportCoverResolutionResultPayload(
        cover_image_url=None,
        cover_thumbnail_url=None,
        cover_image_source=None,
        cover_image_source_id=None,
        has_cover_image=False,
    )


def apply_import_cover_to_parse_order(
    parsed: Any,
    *,
    session: Session | None,
    owner_user_id: int | None,
    draft_import_id: int | None,
) -> Any:
    from app.schemas.ai import ParseOrderResponse

    if not isinstance(parsed, ParseOrderResponse):
        parsed = ParseOrderResponse.model_validate(parsed)

    enriched_items = []
    for item in parsed.items:
        item_dict = item.model_dump(mode="json")
        cover = resolve_import_cover(
            session,
            item_dict,
            owner_user_id=owner_user_id,
            draft_import_id=draft_import_id,
        )
        enriched_items.append(
            item.model_copy(
                update={
                    "cover_image_url": cover.cover_image_url,
                    "cover_thumbnail_url": cover.cover_thumbnail_url,
                    "cover_image_source": cover.cover_image_source,
                    "cover_image_source_id": cover.cover_image_source_id,
                    "has_cover_image": cover.has_cover_image,
                }
            )
        )

    return parsed.model_copy(update={"items": enriched_items})
