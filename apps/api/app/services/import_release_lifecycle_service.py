"""P90-09A import draft release lifecycle enrichment."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Literal

from sqlmodel import Session

from app.services.import_catalog_resolution_service import (
    catalog_match_fields_for_item,
    imported_release_date_is_placeholder,
    resolve_import_catalog_match,
)
from app.services.order_states import default_release_status

OVERDUE_GRACE_DAYS = 21

LifecycleStatus = Literal["PREORDER", "RELEASED_NOT_RECEIVED", "RECEIVED", "OVERDUE", "UNKNOWN"]

_LIFECYCLE_LABELS: dict[str, str] = {
    "PREORDER": "Upcoming Release",
    "RELEASED_NOT_RECEIVED": "Released - Not Received",
    "OVERDUE": "Possibly Missing",
    "RECEIVED": "Received",
    "UNKNOWN": "Unknown",
}

_SORT_BUCKETS: dict[str, int] = {
    "PREORDER": 10,
    "RELEASED_NOT_RECEIVED": 20,
    "OVERDUE": 30,
    "UNKNOWN": 40,
    "RECEIVED": 50,
}


def resolve_best_release_date(
    *,
    catalog_match_date: date | None,
    parsed_import_date: date | None,
    draft_release_date: date | None,
) -> date | None:
    for candidate in (catalog_match_date, parsed_import_date, draft_release_date):
        if candidate is not None:
            return candidate
    return None


def _is_received(*, order_status: str | None, received_at: Any) -> bool:
    if received_at is not None:
        return True
    return (order_status or "").lower() == "received"


def compute_import_release_lifecycle(
    *,
    best_release_date: date | None,
    today: date | None = None,
    order_status: str | None = None,
    received_at: Any = None,
) -> dict[str, Any]:
    resolved_today = today or date.today()
    if _is_received(order_status=order_status, received_at=received_at):
        status: LifecycleStatus = "RECEIVED"
    elif best_release_date is None:
        status = "UNKNOWN"
    elif best_release_date > resolved_today:
        status = "PREORDER"
    elif best_release_date <= resolved_today - timedelta(days=OVERDUE_GRACE_DAYS):
        status = "OVERDUE"
    else:
        status = "RELEASED_NOT_RECEIVED"

    days_until = (
        (best_release_date - resolved_today).days
        if best_release_date and best_release_date > resolved_today
        else None
    )
    days_since = (
        (resolved_today - best_release_date).days
        if best_release_date and best_release_date <= resolved_today
        else None
    )

    detail = _lifecycle_detail(status, best_release_date, days_until, days_since, resolved_today)
    legacy_release_status = _map_legacy_release_status(status, best_release_date, resolved_today)

    return {
        "release_date": best_release_date.isoformat() if best_release_date else None,
        "release_status": legacy_release_status,
        "release_lifecycle_status": status,
        "days_until_release": days_until,
        "days_since_release": days_since,
        "is_preorder": status == "PREORDER",
        "is_released_not_received": status == "RELEASED_NOT_RECEIVED",
        "is_overdue": status == "OVERDUE",
        "lifecycle_sort_bucket": _SORT_BUCKETS[status],
        "lifecycle_display_label": _LIFECYCLE_LABELS[status],
        "lifecycle_display_detail": detail,
    }


def _map_legacy_release_status(status: LifecycleStatus, best: date | None, today: date) -> str:
    if status == "PREORDER":
        return "not_released_yet"
    if status in {"RELEASED_NOT_RECEIVED", "OVERDUE", "RECEIVED"}:
        return "released"
    if best is not None:
        return default_release_status(release_date=best, today=today)
    return "unknown"


def _lifecycle_detail(
    status: LifecycleStatus,
    best: date | None,
    days_until: int | None,
    days_since: int | None,
    today: date,
) -> str:
    if status == "PREORDER" and best:
        formatted = best.strftime("%b %d, %Y")
        if best == today:
            return "Releases today"
        if days_until == 1:
            return f"Releases {formatted} · 1 day remaining"
        if days_until is not None and days_until > 0:
            return f"Releases {formatted} · {days_until} days remaining"
        return f"Releases {formatted}"
    if status == "RELEASED_NOT_RECEIVED" and best:
        return f"Released {best.strftime('%b %d, %Y')} · awaiting receipt"
    if status == "OVERDUE" and best:
        return f"Released {best.strftime('%b %d, %Y')} · possibly missing"
    if status == "RECEIVED":
        return "Received in collection"
    return "No verified release date"


def enrich_import_item_lifecycle(
    session: Session | None,
    *,
    owner_user_id: int | None,
    item: dict[str, Any],
    today: date | None = None,
    include_catalog_debug: bool = False,
) -> dict[str, Any]:
    """Mutates and returns item dict with lifecycle fields."""
    from app.services.metadata_enrichment import parse_release_date

    parsed = item.get("parsed_release_date")
    if isinstance(parsed, str):
        try:
            parsed = date.fromisoformat(parsed)
        except ValueError:
            parsed = parse_release_date(parsed).parsed_date
    elif parsed is None:
        raw = item.get("release_date") or item.get("raw_release_date")
        parsed = parse_release_date(str(raw) if raw else None).parsed_date

    draft_date = parsed if isinstance(parsed, date) else None
    raw_release = item.get("release_date") or item.get("raw_release_date")
    placeholder = imported_release_date_is_placeholder(
        raw_release_date=str(raw_release) if raw_release is not None else None,
        parsed_release_date=draft_date,
        parsed_release_year=item.get("parsed_release_year"),
    )
    trusted_draft_date = None if placeholder else draft_date

    resolution = resolve_import_catalog_match(session, owner_user_id=owner_user_id, item=item)
    catalog_date = resolution.release_date if resolution.matched else None
    item.update(catalog_match_fields_for_item(resolution, include_debug=include_catalog_debug))
    if resolution.matched and resolution.publisher:
        item["publisher"] = resolution.publisher
        item["canonical_publisher"] = resolution.publisher

    best = resolve_best_release_date(
        catalog_match_date=catalog_date,
        parsed_import_date=trusted_draft_date,
        draft_release_date=trusted_draft_date,
    )

    lifecycle = compute_import_release_lifecycle(
        best_release_date=best,
        today=today,
        order_status=item.get("order_status"),
        received_at=item.get("received_at"),
    )

    item.update(lifecycle)
    if best is not None:
        item["parsed_release_date"] = best.isoformat()
        item["release_date"] = best.isoformat()
    item["release_status"] = lifecycle["release_status"]
    if lifecycle["is_preorder"] and not item.get("order_status"):
        item["order_status"] = "preordered"
    return item


def enrich_parse_order_payload_lifecycle(
    session: Session | None,
    *,
    owner_user_id: int | None,
    payload: dict[str, Any],
    today: date | None = None,
) -> dict[str, Any]:
    from app.services.import_locg_hydrate_service import import_locg_hydrate_request_scope

    items = payload.get("items") or []
    with import_locg_hydrate_request_scope():
        enriched_items = [
            enrich_import_item_lifecycle(session, owner_user_id=owner_user_id, item=dict(item), today=today)
            for item in items
        ]
    payload["items"] = enriched_items
    payload["lifecycle_enrichment_json"] = {
        "item_count": len(enriched_items),
        "preorder_count": sum(1 for i in enriched_items if i.get("is_preorder")),
    }
    return payload


def sort_key_for_lifecycle_item(item: dict[str, Any]) -> tuple[int, str, int]:
    bucket = int(item.get("lifecycle_sort_bucket") or 40)
    rel = str(item.get("release_date") or item.get("parsed_release_date") or "9999-99-99")
    return (bucket, rel, 0)


_LIFECYCLE_ITEM_KEYS = (
    "release_date",
    "release_status",
    "release_lifecycle_status",
    "days_until_release",
    "days_since_release",
    "is_preorder",
    "is_released_not_received",
    "is_overdue",
    "lifecycle_sort_bucket",
    "lifecycle_display_label",
    "lifecycle_display_detail",
    "parsed_release_date",
    "order_status",
    "catalog_match_matched",
    "catalog_match_possible",
    "catalog_match_source",
    "catalog_match_source_id",
    "catalog_match_score",
    "catalog_match_title",
    "catalog_match_publisher",
    "catalog_match_issue_number",
    "catalog_match_release_date",
    "catalog_match_diagnostics",
    "catalog_release_source_text",
    "catalog_resolution_debug",
)


def should_expose_catalog_debug(*, explicit_debug: bool) -> bool:
    if explicit_debug:
        return True
    from app.core.config import get_settings

    env = get_settings().app_env.lower()
    return env in {"development", "dev", "local", "test"}


def lifecycle_fields_from_item_dict(enriched: dict[str, Any]) -> dict[str, Any]:
    return {key: enriched.get(key) for key in _LIFECYCLE_ITEM_KEYS if key in enriched}


def apply_release_lifecycle_to_parse_order(
    parsed: Any,
    *,
    session: Session | None,
    owner_user_id: int | None,
    today: date | None = None,
    sort_items: bool = True,
    debug_catalog: bool = False,
) -> Any:
    from app.schemas.ai import ParseOrderResponse

    if not isinstance(parsed, ParseOrderResponse):
        parsed = ParseOrderResponse.model_validate(parsed)

    include_debug = should_expose_catalog_debug(explicit_debug=debug_catalog)
    enriched_items = []
    for item in parsed.items:
        item_dict = item.model_dump(mode="json")
        enriched = enrich_import_item_lifecycle(
            session,
            owner_user_id=owner_user_id,
            item=item_dict,
            today=today,
            include_catalog_debug=include_debug,
        )
        updates = lifecycle_fields_from_item_dict(enriched)
        parsed_release = enriched.get("parsed_release_date")
        if parsed_release:
            if isinstance(parsed_release, str):
                updates["parsed_release_date"] = date.fromisoformat(parsed_release)
            else:
                updates["parsed_release_date"] = parsed_release
        if enriched.get("release_date"):
            updates["release_date"] = str(enriched["release_date"])
        enriched_items.append(item.model_copy(update=updates))

    if sort_items:
        enriched_items = sorted(
            enriched_items,
            key=lambda row: (
                row.lifecycle_sort_bucket or 40,
                row.parsed_release_date.isoformat() if row.parsed_release_date else "9999-99-99",
            ),
        )

    lifecycle_json = {
        "item_count": len(enriched_items),
        "preorder_count": sum(1 for row in enriched_items if row.is_preorder),
    }
    extra: dict[str, Any] = {"items": enriched_items, "lifecycle_enrichment_json": lifecycle_json}
    return parsed.model_copy(update=extra)
