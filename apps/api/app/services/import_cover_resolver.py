"""Resolve stored cover images for import draft items."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlmodel import Session, select

from app.models.asset_ledger import CoverImage, CoverImageDerivative
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch, ExternalCatalogVariant
from app.services.cover_images import cover_derivative_fetch_path, cover_fetch_path
from app.services.import_catalog_resolution_service import (
    ImportCatalogResolutionResult,
    _issue_number_key,
    normalize_import_title,
    resolve_import_catalog_match,
)


@dataclass
class ImportCoverResolutionResultPayload:
    cover_image_url: str | None
    cover_thumbnail_url: str | None
    cover_image_source: str | None
    cover_image_source_id: int | None
    has_cover_image: bool


_COVER_LETTER_PATTERN = re.compile(
    r"\bcover\s+([a-z]{1,2}|[0-9]{1,2})(?:\s|$|[^a-z])",
    re.IGNORECASE,
)


def _issue_numbers_compatible(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return True
    return _issue_number_key(left) == _issue_number_key(right)


def _external_issue_matches_item(issue: ExternalCatalogIssue | None, item: dict[str, Any]) -> bool:
    if issue is None:
        return False
    line_issue = item.get("issue_number") or item.get("canonical_issue_number")
    if not line_issue:
        return True
    return _issue_numbers_compatible(issue.issue_number, str(line_issue))


def _cover_letter_key(value: str | None) -> str | None:
    if not value:
        return None
    match = _COVER_LETTER_PATTERN.search(value)
    if not match:
        return None
    return match.group(1).lower()


def _text_tokens(value: str | None) -> set[str]:
    normalized = normalize_import_title(value)
    if not normalized:
        return set()
    return set(normalized.split())


def _variant_match_score(item: dict[str, Any], variant: ExternalCatalogVariant) -> int:
    score = 0
    item_letter = _cover_letter_key(item.get("cover_name"))
    variant_letter = _cover_letter_key(
        " ".join(filter(None, [variant.cover_label, variant.variant_name]))
    )
    if item_letter and variant_letter:
        if item_letter == variant_letter:
            score += 120
        else:
            return -1000

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


def _pick_best_catalog_variant(
    item: dict[str, Any],
    variants: list[ExternalCatalogVariant],
) -> ExternalCatalogVariant | None:
    if not variants:
        return None
    item_letter = _cover_letter_key(item.get("cover_name"))
    scored = [(variant, _variant_match_score(item, variant)) for variant in variants]
    if item_letter:
        letter_matches = [row for row in scored if row[1] >= 0]
        if letter_matches:
            scored = letter_matches
    best_variant, best_score = max(scored, key=lambda row: (row[1], -(row[0].id or 0)))
    if best_score < 0:
        return None
    return best_variant


def _external_issue_id_from_catalog_resolution(
    session: Session,
    *,
    owner_user_id: int,
    item: dict[str, Any],
    catalog_resolution: ImportCatalogResolutionResult,
) -> int | None:
    if not catalog_resolution.matched:
        return None
    if catalog_resolution.source == "ExternalCatalogIssue" and catalog_resolution.source_id is not None:
        row = session.get(ExternalCatalogIssue, catalog_resolution.source_id)
        if _external_issue_matches_item(row, item):
            return catalog_resolution.source_id
        return None
    if catalog_resolution.source == "ReleaseIssue" and catalog_resolution.source_id is not None:
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
        if match is None:
            return None
        row = session.get(ExternalCatalogIssue, match.external_issue_id)
        if _external_issue_matches_item(row, item):
            return match.external_issue_id
    return None


def _resolve_external_issue_id(
    session: Session | None,
    *,
    owner_user_id: int | None,
    item: dict[str, Any],
    catalog_resolution: ImportCatalogResolutionResult | None,
) -> int | None:
    if session is None:
        return None

    source = item.get("catalog_match_source")
    source_id = item.get("catalog_match_source_id")
    if source == "ExternalCatalogIssue" and source_id is not None:
        row = session.get(ExternalCatalogIssue, int(source_id))
        if _external_issue_matches_item(row, item):
            return int(source_id)

    if owner_user_id is None:
        return None

    if catalog_resolution and catalog_resolution.matched:
        ext_id = _external_issue_id_from_catalog_resolution(
            session,
            owner_user_id=owner_user_id,
            item=item,
            catalog_resolution=catalog_resolution,
        )
        if ext_id is not None:
            return ext_id

    if source == "ReleaseIssue" and source_id is not None:
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
        if match is not None:
            row = session.get(ExternalCatalogIssue, match.external_issue_id)
            if _external_issue_matches_item(row, item):
                return match.external_issue_id

    fresh = resolve_import_catalog_match(session, owner_user_id=owner_user_id, item=item)
    return _external_issue_id_from_catalog_resolution(
        session,
        owner_user_id=owner_user_id,
        item=item,
        catalog_resolution=fresh,
    )


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
        best_variant = _pick_best_catalog_variant(item, variants)
        if best_variant is not None and best_variant.image_url and best_variant.id is not None:
            return ImportCoverResolutionResultPayload(
                cover_image_url=best_variant.image_url,
                cover_thumbnail_url=best_variant.image_url,
                cover_image_source="external_catalog_variant",
                cover_image_source_id=best_variant.id,
                has_cover_image=True,
            )
        if (item.get("cover_name") or "").strip():
            return None

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
    allow_draft_cover_fallback: bool = True,
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

        draft_cover = (
            _resolve_draft_cover(session, draft_import_id=draft_import_id)
            if allow_draft_cover_fallback
            else None
        )
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
    allow_draft_cover = len(parsed.items) <= 1
    for item in parsed.items:
        item_dict = item.model_dump(mode="json")
        cover = resolve_import_cover(
            session,
            item_dict,
            owner_user_id=owner_user_id,
            draft_import_id=draft_import_id,
            allow_draft_cover_fallback=allow_draft_cover,
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
