"""Resolve stored cover images for import draft items."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models.asset_ledger import CoverImage, CoverImageDerivative
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch, ExternalCatalogVariant
from app.services.cover_images import cover_derivative_fetch_path, cover_fetch_path
from app.services.import_catalog_resolution_service import (
    ImportCatalogResolutionResult,
    _issue_number_key,
    _parse_release_date_from_item,
    normalize_import_title,
    resolve_import_catalog_match,
)
from app.services.import_cover_verification import (
    build_cover_item_updates,
    cover_fields_from_item_snapshot,
    item_cover_user_locked,
)
from app.services.retailer_lookup import enrich_item_with_midtown_lookup
from app.services.import_locg_hydrate_service import ImportLocgHydrateResult
from app.services.import_cover_display import cover_display_fields_from_urls


LOGGER = logging.getLogger(__name__)


@dataclass
class ImportCoverResolutionResultPayload:
    cover_image_url: str | None
    cover_thumbnail_url: str | None
    cover_image_source: str | None
    cover_image_source_id: int | None
    has_cover_image: bool
    cover_resolution_debug: dict[str, Any] | None = None
    cover_source: str | None = None
    cover_confidence: float | None = None
    variant_confidence: float | None = None
    cover_source_url: str | None = None
    cover_source_sku: str | None = None
    cover_verified_at: datetime | None = None
    cover_verified_by: str | None = None


def _with_cover_debug(
    payload: ImportCoverResolutionResultPayload,
    outcome: str,
    **extra: Any,
) -> ImportCoverResolutionResultPayload:
    debug: dict[str, Any] = {"outcome": outcome}
    for key, value in extra.items():
        if value is not None:
            debug[key] = value
    return replace(payload, cover_resolution_debug=debug)


def _variant_letter_matched_for_cover(
    session: Session,
    item: dict[str, Any],
    cover: ImportCoverResolutionResultPayload,
) -> bool | None:
    if cover.cover_image_source != "external_catalog_variant" or cover.cover_image_source_id is None:
        return None
    row = session.get(ExternalCatalogVariant, cover.cover_image_source_id)
    if row is None:
        return None
    item_letter = _item_cover_letter(item)
    if item_letter is None:
        return None
    return _variant_cover_letter(row) == item_letter


def _finalize_cover_payload(
    session: Session | None,
    item: dict[str, Any],
    payload: ImportCoverResolutionResultPayload,
    *,
    external_issue_id: int | None = None,
    variant_letter_matched: bool | None = None,
    used_issue_fallback: bool = False,
    retailer_cover: bool = False,
) -> ImportCoverResolutionResultPayload:
    if variant_letter_matched is None and session is not None and payload.has_cover_image:
        variant_letter_matched = _variant_letter_matched_for_cover(session, item, payload)
    if payload.cover_image_source == "external_catalog_issue":
        used_issue_fallback = True
    merged = build_cover_item_updates(
        {
            "cover_image_url": payload.cover_image_url,
            "cover_thumbnail_url": payload.cover_thumbnail_url,
            "cover_image_source": payload.cover_image_source,
            "cover_image_source_id": payload.cover_image_source_id,
            "has_cover_image": payload.has_cover_image,
            "cover_resolution_debug": payload.cover_resolution_debug,
        },
        session=session,
        external_issue_id=external_issue_id,
        item=item,
        variant_letter_matched=variant_letter_matched,
        used_issue_fallback=used_issue_fallback,
        retailer_cover=retailer_cover,
    )
    return replace(
        payload,
        cover_source=merged.get("cover_source") or payload.cover_source,
        cover_confidence=merged.get("cover_confidence"),
        variant_confidence=merged.get("variant_confidence"),
        cover_source_url=merged.get("cover_source_url"),
        cover_source_sku=merged.get("cover_source_sku"),
        cover_verified_at=merged.get("cover_verified_at"),
        cover_verified_by=merged.get("cover_verified_by"),
    )


def _resolve_retailer_cover(item: dict[str, Any]) -> ImportCoverResolutionResultPayload | None:
    url = (item.get("retailer_cover_url") or "").strip()
    if not url:
        return None
    source = "midtown_product" if (item.get("retailer_lookup_status") == "matched" or item.get("retailer_product_url")) else "retailer_cover"
    return ImportCoverResolutionResultPayload(
        cover_image_url=url,
        cover_thumbnail_url=url,
        cover_image_source=source,
        cover_image_source_id=None,
        has_cover_image=True,
        cover_source="RETAILER",
    )


def _locked_cover_payload(item: dict[str, Any]) -> ImportCoverResolutionResultPayload:
    snap = cover_fields_from_item_snapshot(item)
    return ImportCoverResolutionResultPayload(
        cover_image_url=snap.get("cover_image_url"),
        cover_thumbnail_url=snap.get("cover_thumbnail_url"),
        cover_image_source=snap.get("cover_image_source"),
        cover_image_source_id=snap.get("cover_image_source_id"),
        has_cover_image=bool(snap.get("has_cover_image")),
        cover_resolution_debug=snap.get("cover_resolution_debug"),
        cover_source=snap.get("cover_source"),
        cover_confidence=snap.get("cover_confidence"),
        variant_confidence=snap.get("variant_confidence"),
        cover_source_url=snap.get("cover_source_url"),
        cover_source_sku=snap.get("cover_source_sku"),
        cover_verified_at=snap.get("cover_verified_at"),
        cover_verified_by=snap.get("cover_verified_by"),
    )


def _locg_hydrate_debug_fields(result: ImportLocgHydrateResult) -> dict[str, Any]:
    return {
        "locg_hydrate_attempted": result.attempted,
        "locg_hydrated": result.hydrated,
        "locg_hydrate_external_issue_id": result.external_issue_id,
        "locg_hydrate_no_match_reason": result.no_match_reason,
        "locg_hydrate_error": result.error,
        "locg_hydrate_cached": result.cached,
    }


def _external_catalog_cover_miss_reason(
    session: Session,
    *,
    external_issue_id: int,
    item: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    all_variants = session.exec(
        select(ExternalCatalogVariant).where(
            ExternalCatalogVariant.external_issue_id == external_issue_id
        )
    ).all()
    with_images = [variant for variant in all_variants if variant.image_url]
    item_letter = _item_cover_letter(item)
    detail: dict[str, Any] = {
        "external_issue_id": external_issue_id,
        "variant_row_count": len(all_variants),
        "variant_rows_with_image_url": len(with_images),
        "requested_cover_letter": item_letter,
    }
    if with_images:
        best_variant = _pick_best_catalog_variant(item, with_images)
        if best_variant is None:
            if item_letter is not None:
                return "variant_letter_not_matched", detail
            return "no_matching_variant_row", detail
        return "unexpected_miss", detail

    issue = session.get(ExternalCatalogIssue, external_issue_id)
    if issue is None:
        return "external_issue_row_missing", detail

    has_issue_image = bool(
        issue.high_resolution_image_url or issue.cover_image_url or issue.thumbnail_url
    )
    detail["issue_has_image_urls"] = has_issue_image
    if not has_issue_image:
        if all_variants:
            return "catalog_variants_and_issue_missing_image_urls", detail
        return "catalog_issue_missing_image_urls", detail

    cover_name = (item.get("cover_name") or "").strip()
    if cover_name and all_variants:
        variant_letters = [_variant_cover_letter(variant) for variant in all_variants]
        if any(letter for letter in variant_letters if letter):
            return "variant_named_no_letter_match_no_issue_fallback", detail

    return "catalog_issue_image_unavailable", detail


_COVER_LETTER_PATTERN = re.compile(
    r"\bcover\s+([a-z]{1,2}|[0-9]{1,2})(?:\s|$|[^a-z])",
    re.IGNORECASE,
)
_LOCG_SHORT_COVER_LABEL = re.compile(r"^(?:cover\s*)?([a-z0-9]{1,2})$", re.IGNORECASE)


def _cover_letter_key(value: str | None) -> str | None:
    if not value:
        return None
    match = _COVER_LETTER_PATTERN.search(value)
    if not match:
        return None
    return match.group(1).lower()


def _variant_cover_letter(variant: ExternalCatalogVariant) -> str | None:
    for part in (variant.cover_label, variant.variant_name):
        letter = _cover_letter_key(part)
        if letter:
            return letter
    label = (variant.cover_label or "").strip()
    if label:
        short = _LOCG_SHORT_COVER_LABEL.match(label)
        if short:
            return short.group(1).lower()
    combined = " ".join(filter(None, [variant.cover_label, variant.variant_name]))
    return _cover_letter_key(combined)


def _item_cover_letter(item: dict[str, Any]) -> str | None:
    for field in ("cover_name", "canonical_variant_text", "raw_variant_text", "variant_type"):
        letter = _cover_letter_key(item.get(field) if isinstance(item.get(field), str) else None)
        if letter:
            return letter
    return None


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


def _text_tokens(value: str | None) -> set[str]:
    normalized = normalize_import_title(value)
    if not normalized:
        return set()
    return set(normalized.split())


def _variant_match_score(item: dict[str, Any], variant: ExternalCatalogVariant) -> int:
    score = 0
    item_letter = _item_cover_letter(item)
    variant_letter = _variant_cover_letter(variant)
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
    item_letter = _item_cover_letter(item)
    if item_letter:
        letter_variants = [variant for variant in variants if _variant_cover_letter(variant) == item_letter]
        if not letter_variants:
            return None
        variants = letter_variants
    scored = [(variant, _variant_match_score(item, variant)) for variant in variants]
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
        if (item.get("cover_name") or "").strip() or _item_cover_letter(item):
            item_letter = _item_cover_letter(item)
            if item_letter is not None:
                variant_letters = [_variant_cover_letter(variant) for variant in variants]
                if any(letter == item_letter for letter in variant_letters if letter):
                    return None
                if any(letter for letter in variant_letters if letter):
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


def _cover_payload_from_stored_image(
    session: Session,
    cover: CoverImage,
) -> ImportCoverResolutionResultPayload | None:
    if cover.id is None:
        return None
    derivatives = session.exec(
        select(CoverImageDerivative).where(CoverImageDerivative.cover_image_id == cover.id)
    ).all()
    thumb = next(
        (
            cover_derivative_fetch_path(cover.id, row.derivative_type)
            for row in derivatives
            if row.derivative_type == "thumb"
        ),
        None,
    )
    medium = next(
        (
            cover_derivative_fetch_path(cover.id, row.derivative_type)
            for row in derivatives
            if row.derivative_type == "medium"
        ),
        None,
    )
    return ImportCoverResolutionResultPayload(
        cover_image_url=medium or cover_fetch_path(cover.id),
        cover_thumbnail_url=thumb or medium or cover_fetch_path(cover.id),
        cover_image_source="draft_cover_image",
        cover_image_source_id=cover.id,
        has_cover_image=True,
    )


def _resolve_line_upload_cover(
    session: Session,
    item: dict[str, Any],
) -> ImportCoverResolutionResultPayload | None:
    raw_id = item.get("import_line_cover_image_id")
    if raw_id is None:
        return None
    try:
        cover_id = int(raw_id)
    except (TypeError, ValueError):
        return None
    cover = session.get(CoverImage, cover_id)
    if cover is None:
        return None
    if cover.processing_status == "failed":
        return None
    return _cover_payload_from_stored_image(session, cover)


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
    if cover is None:
        return None
    return _cover_payload_from_stored_image(session, cover)


def _attempt_locg_hydrate_for_cover_images(
    session: Session,
    item: dict[str, Any],
) -> ImportLocgHydrateResult:
    """Fetch LOCG detail when the mirror row exists but has no usable cover art yet."""
    from app.services.import_locg_hydrate_service import (
        hydrate_import_item_from_locg_calendar,
        import_locg_hydrate_enabled,
    )

    if not import_locg_hydrate_enabled():
        return ImportLocgHydrateResult(attempted=False, no_match_reason="hydrate_disabled")

    title = item.get("title") or item.get("canonical_title")
    issue_number = item.get("issue_number") or item.get("canonical_issue_number")
    if not normalize_import_title(title) or not issue_number:
        return ImportLocgHydrateResult(attempted=False, no_match_reason="missing_title_or_issue")

    try:
        return hydrate_import_item_from_locg_calendar(
            session,
            title=str(title),
            issue_number=str(issue_number),
            parsed_release_date=_parse_release_date_from_item(item),
        )
    except Exception:
        LOGGER.warning(
            "import_cover_locg_hydrate_failed title=%r issue=%r",
            title,
            issue_number,
            exc_info=True,
        )
        return ImportLocgHydrateResult(attempted=True, hydrated=False, error="hydrate_exception")


def _external_variant_debug_fields(
    session: Session,
    item: dict[str, Any],
    cover: ImportCoverResolutionResultPayload,
) -> dict[str, Any]:
    if cover.cover_image_source != "external_catalog_variant" or cover.cover_image_source_id is None:
        return {}
    row = session.get(ExternalCatalogVariant, cover.cover_image_source_id)
    if row is None:
        return {}
    return {
        "requested_cover_letter": _item_cover_letter(item),
        "matched_variant_id": row.id,
        "matched_variant_cover_label": row.cover_label,
        "matched_variant_letter": _variant_cover_letter(row),
        "matched_variant_artist": row.artist,
    }


def _emit_cover(
    session: Session | None,
    item: dict[str, Any],
    payload: ImportCoverResolutionResultPayload,
    outcome: str,
    *,
    external_issue_id: int | None = None,
    retailer_cover: bool = False,
    **debug: Any,
) -> ImportCoverResolutionResultPayload:
    decorated = _with_cover_debug(payload, outcome, **debug)
    return _finalize_cover_payload(
        session,
        item,
        decorated,
        external_issue_id=external_issue_id,
        retailer_cover=retailer_cover,
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
    last_hydrate: ImportLocgHydrateResult | None = None
    last_miss_reason: str | None = None
    last_miss_detail: dict[str, Any] | None = None
    resolved_external_issue_id: int | None = None

    if item_cover_user_locked(item):
        return _locked_cover_payload(item)

    if session is not None:
        line_upload_cover = _resolve_line_upload_cover(session, item)
        if line_upload_cover is not None:
            return _emit_cover(session, item, line_upload_cover, "line_upload")

        retailer_cover = _resolve_retailer_cover(item)
        if retailer_cover is not None:
            return _emit_cover(
                session,
                item,
                retailer_cover,
                "retailer_cover",
                retailer_cover=True,
            )

        external_issue_id = _resolve_external_issue_id(
            session,
            owner_user_id=owner_user_id,
            item=item,
            catalog_resolution=catalog_resolution,
        )
        resolved_external_issue_id = external_issue_id
        if external_issue_id is not None:
            external_cover = _resolve_external_catalog_cover(
                session,
                external_issue_id=external_issue_id,
                item=item,
            )
            if external_cover is not None:
                return _emit_cover(
                    session,
                    item,
                    external_cover,
                    external_cover.cover_image_source or "external_catalog",
                    external_issue_id=external_issue_id,
                    **_external_variant_debug_fields(session, item, external_cover),
                )
            last_miss_reason, last_miss_detail = _external_catalog_cover_miss_reason(
                session,
                external_issue_id=external_issue_id,
                item=item,
            )
            last_hydrate = _attempt_locg_hydrate_for_cover_images(session, item)
            refreshed_issue_id = _resolve_external_issue_id(
                session,
                owner_user_id=owner_user_id,
                item=item,
                catalog_resolution=None,
            )
            resolved_external_issue_id = refreshed_issue_id or resolved_external_issue_id
            if refreshed_issue_id is not None:
                external_cover = _resolve_external_catalog_cover(
                    session,
                    external_issue_id=refreshed_issue_id,
                    item=item,
                )
                if external_cover is not None:
                    return _emit_cover(
                        session,
                        item,
                        external_cover,
                        external_cover.cover_image_source or "external_catalog",
                        external_issue_id=refreshed_issue_id,
                        cover_miss_reason_before_hydrate=last_miss_reason,
                        **_locg_hydrate_debug_fields(last_hydrate),
                        **_external_variant_debug_fields(session, item, external_cover),
                    )
                last_miss_reason, last_miss_detail = _external_catalog_cover_miss_reason(
                    session,
                    external_issue_id=refreshed_issue_id,
                    item=item,
                )
        elif owner_user_id is not None:
            last_hydrate = _attempt_locg_hydrate_for_cover_images(session, item)
            external_issue_id = _resolve_external_issue_id(
                session,
                owner_user_id=owner_user_id,
                item=item,
                catalog_resolution=None,
            )
            resolved_external_issue_id = external_issue_id
            if external_issue_id is not None:
                external_cover = _resolve_external_catalog_cover(
                    session,
                    external_issue_id=external_issue_id,
                    item=item,
                )
                if external_cover is not None:
                    hydrate_fields = (
                        _locg_hydrate_debug_fields(last_hydrate) if last_hydrate else {}
                    )
                    return _emit_cover(
                        session,
                        item,
                        external_cover,
                        external_cover.cover_image_source or "external_catalog",
                        external_issue_id=external_issue_id,
                        **hydrate_fields,
                        **_external_variant_debug_fields(session, item, external_cover),
                    )
                last_miss_reason, last_miss_detail = _external_catalog_cover_miss_reason(
                    session,
                    external_issue_id=external_issue_id,
                    item=item,
                )
            elif last_hydrate is not None:
                last_miss_reason = last_hydrate.no_match_reason or "locg_hydrate_no_issue"
        else:
            last_miss_reason = "no_owner_user_for_catalog_or_hydrate"

        draft_cover = (
            _resolve_draft_cover(session, draft_import_id=draft_import_id)
            if allow_draft_cover_fallback
            else None
        )
        if draft_cover is not None:
            extra: dict[str, Any] = {}
            if last_hydrate is not None:
                extra.update(_locg_hydrate_debug_fields(last_hydrate))
            if last_miss_reason:
                extra["cover_miss_reason_before_draft"] = last_miss_reason
            return _emit_cover(session, item, draft_cover, "draft_cover_image", **extra)

    empty = ImportCoverResolutionResultPayload(
        cover_image_url=None,
        cover_thumbnail_url=None,
        cover_image_source=None,
        cover_image_source_id=None,
        has_cover_image=False,
    )
    reason = last_miss_reason
    if reason is None:
        if session is None:
            reason = "no_database_session"
        elif resolved_external_issue_id is None:
            reason = "no_external_issue_id"
        else:
            reason = "no_cover_source"
    debug_extra: dict[str, Any] = {
        "reason": reason,
        "external_issue_id": resolved_external_issue_id,
        "allow_draft_cover_fallback": allow_draft_cover_fallback,
    }
    if last_miss_detail:
        debug_extra["catalog_cover_detail"] = last_miss_detail
    if last_hydrate is not None:
        debug_extra.update(_locg_hydrate_debug_fields(last_hydrate))
    return _emit_cover(session, item, empty, "none", **debug_extra)


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
    retailer_hint = f"{parsed.retailer or ''}".casefold()
    should_try_midtown_lookup = "midtown" in retailer_hint or any(
        "midtowncomics.com" in f"{getattr(item, 'retailer_product_url', '') or ''}".casefold()
        for item in parsed.items
    )
    for item in parsed.items:
        item_dict = item.model_dump(mode="json")
        if should_try_midtown_lookup and parsed.retailer:
            item_dict["retailer"] = parsed.retailer
        has_exact_retailer_item_cover = bool(item.retailer_cover_url and (item.retailer_item_id or item.retailer_order_number))
        lookup_updates = (
            {}
            if not should_try_midtown_lookup or has_exact_retailer_item_cover
            else enrich_item_with_midtown_lookup(item_dict, limit=10)
        )
        item = item.model_copy(update=lookup_updates) if lookup_updates else item
        item_dict = item.model_dump(mode="json")
        cover = resolve_import_cover(
            session,
            item_dict,
            owner_user_id=owner_user_id,
            draft_import_id=draft_import_id,
            allow_draft_cover_fallback=allow_draft_cover,
        )
        display_fields = cover_display_fields_from_urls(
            cover_image_url=cover.cover_image_url or item.retailer_cover_url,
            cover_thumbnail_url=cover.cover_thumbnail_url or item.retailer_cover_url,
            retailer_cover_url=item.retailer_cover_url,
        )
        enriched_items.append(
            item.model_copy(
                update={
                    "cover_image_url": display_fields["cover_image_url"],
                    "cover_thumbnail_url": display_fields["cover_thumbnail_url"],
                    "cover_url": display_fields["cover_url"],
                    "cover_image_source": cover.cover_image_source
                    or ("midtown_product" if (item.retailer_cover_url or item.retailer_lookup_status == "matched") else None),
                    "cover_image_source_id": cover.cover_image_source_id,
                    "has_cover_image": display_fields["has_cover_image"] or cover.has_cover_image,
                    "cover_resolution_debug": cover.cover_resolution_debug,
                    "cover_source": cover.cover_source
                    or ("RETAILER" if (item.retailer_cover_url or item.retailer_lookup_status == "matched") else None),
                    "cover_confidence": cover.cover_confidence,
                    "variant_confidence": cover.variant_confidence,
                    "cover_source_url": cover.cover_source_url,
                    "cover_source_sku": cover.cover_source_sku,
                    "cover_verified_by": cover.cover_verified_by,
                    "cover_verified_at": cover.cover_verified_at,
                }
            )
        )

    return parsed.model_copy(update={"items": enriched_items})
