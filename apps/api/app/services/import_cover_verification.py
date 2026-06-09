"""P92-07 cover provenance, confidence, and verification helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

CoverSourceKind = Literal["RETAILER", "LOCG", "EXTERNAL_CATALOG", "USER_UPLOAD"]
CoverVerifiedBy = Literal["SYSTEM", "USER"]

COVER_AUTO_VERIFY_COVER_CONFIDENCE = 0.85
COVER_AUTO_VERIFY_VARIANT_CONFIDENCE = 0.80

_LEGACY_SOURCE_TO_KIND: dict[str, CoverSourceKind] = {
    "draft_cover_image": "USER_UPLOAD",
    "line_upload": "USER_UPLOAD",
    "external_catalog_variant": "LOCG",
    "external_catalog_issue": "LOCG",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def locg_issue_source_name(session: Any, external_issue_id: int | None) -> str | None:
    if session is None or external_issue_id is None:
        return None
    from app.models.external_catalog import ExternalCatalogIssue

    row = session.get(ExternalCatalogIssue, external_issue_id)
    if row is None:
        return None
    return (row.source_name or "").strip().lower() or None


def cover_source_kind_for_legacy(
    legacy_source: str | None,
    *,
    session: Any = None,
    external_issue_id: int | None = None,
    retailer_cover: bool = False,
) -> CoverSourceKind | None:
    if retailer_cover:
        return "RETAILER"
    if not legacy_source:
        return None
    if legacy_source in {"draft_cover_image", "line_upload"}:
        return "USER_UPLOAD"
    if legacy_source.startswith("external_catalog"):
        provider = locg_issue_source_name(session, external_issue_id)
        if provider and provider != "locg":
            return "EXTERNAL_CATALOG"
        return "LOCG"
    return _LEGACY_SOURCE_TO_KIND.get(legacy_source, "EXTERNAL_CATALOG")


def confidence_for_resolution(
    *,
    legacy_source: str | None,
    item: dict[str, Any],
    variant_letter_matched: bool | None,
    used_issue_fallback: bool,
    user_upload: bool = False,
    retailer_cover: bool = False,
) -> tuple[float, float]:
    """Return (cover_confidence, variant_confidence)."""
    if user_upload:
        return 1.0, 1.0
    if retailer_cover:
        if variant_letter_matched is True:
            return 0.92, 0.88
        if variant_letter_matched is False:
            return 0.75, 0.45
        return 0.88, 0.72

    has_letter = bool((item.get("cover_name") or "").strip()) or _has_cover_letter(item)

    if legacy_source == "external_catalog_variant":
        if variant_letter_matched is True:
            return 0.88, 0.92
        if variant_letter_matched is False:
            return 0.55, 0.35
        return 0.78, 0.65 if not has_letter else 0.55

    if legacy_source == "external_catalog_issue" or used_issue_fallback:
        if has_letter:
            return 0.42, 0.28
        return 0.68, 0.55

    return 0.5, 0.5


def _has_cover_letter(item: dict[str, Any]) -> bool:
    from app.services.import_cover_resolver import _item_cover_letter

    return _item_cover_letter(item) is not None


def auto_verification_fields(
    *,
    cover_confidence: float,
    variant_confidence: float,
    existing_verified_by: str | None,
) -> dict[str, Any]:
    if existing_verified_by == "USER":
        return {}
    if (
        cover_confidence >= COVER_AUTO_VERIFY_COVER_CONFIDENCE
        and variant_confidence >= COVER_AUTO_VERIFY_VARIANT_CONFIDENCE
    ):
        return {
            "cover_verified_by": "SYSTEM",
            "cover_verified_at": utc_now(),
        }
    return {
        "cover_verified_by": None,
        "cover_verified_at": None,
    }


def cover_fields_from_item_snapshot(item: dict[str, Any]) -> dict[str, Any]:
    """Rebuild resolver payload from persisted line when user-locked."""
    return {
        "cover_image_url": item.get("cover_image_url"),
        "cover_thumbnail_url": item.get("cover_thumbnail_url"),
        "cover_image_source": item.get("cover_image_source"),
        "cover_image_source_id": item.get("cover_image_source_id"),
        "has_cover_image": item.get("has_cover_image"),
        "cover_source": item.get("cover_source"),
        "cover_confidence": item.get("cover_confidence"),
        "variant_confidence": item.get("variant_confidence"),
        "cover_source_url": item.get("cover_source_url"),
        "cover_source_sku": item.get("cover_source_sku"),
        "cover_verified_at": item.get("cover_verified_at"),
        "cover_verified_by": item.get("cover_verified_by"),
        "cover_resolution_debug": item.get("cover_resolution_debug"),
    }


def item_cover_user_locked(item: dict[str, Any]) -> bool:
    from app.services.import_cover_display import item_has_verified_cover_lock

    return item_has_verified_cover_lock(item)


def build_cover_item_updates(
    payload: dict[str, Any],
    *,
    session: Any = None,
    external_issue_id: int | None = None,
    item: dict[str, Any],
    variant_letter_matched: bool | None = None,
    used_issue_fallback: bool = False,
    retailer_cover: bool = False,
    source_url: str | None = None,
    source_sku: str | None = None,
) -> dict[str, Any]:
    legacy = payload.get("cover_image_source")
    user_upload = legacy in {"draft_cover_image", "line_upload"} or payload.get("outcome") == "line_upload"
    cover_conf, variant_conf = confidence_for_resolution(
        legacy_source=legacy,
        item=item,
        variant_letter_matched=variant_letter_matched,
        used_issue_fallback=used_issue_fallback,
        user_upload=user_upload,
        retailer_cover=retailer_cover,
    )
    kind = cover_source_kind_for_legacy(
        legacy,
        session=session,
        external_issue_id=external_issue_id,
        retailer_cover=retailer_cover,
    )
    updates = {
        **payload,
        "cover_source": kind,
        "cover_confidence": cover_conf,
        "variant_confidence": variant_conf,
        "cover_source_url": source_url or item.get("cover_source_url") or item.get("retailer_product_url"),
        "cover_source_sku": source_sku or item.get("cover_source_sku") or item.get("retailer_sku"),
    }
    if user_upload and legacy == "line_upload":
        updates["cover_verified_by"] = "USER"
        updates["cover_verified_at"] = utc_now()
    else:
        updates.update(
            auto_verification_fields(
                cover_confidence=cover_conf,
                variant_confidence=variant_conf,
                existing_verified_by=item.get("cover_verified_by"),
            )
        )
    return updates
