"""Deterministic series run detection and missing-issue visibility."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    CanonicalSeries,
    ComicIssue,
    ComicTitle,
    CoverImage,
    InventoryCopy,
    Order,
    OrderItem,
    Publisher,
    User,
    Variant,
)
from app.services.catalog_registry_rows import load_catalog_registry_issue_rows
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.services.legacy_spine_availability import legacy_comic_issue_table_exists
from app.schemas.run_detection import (
    MissingIssueClassification,
    MissingIssueListRead,
    MissingIssueRead,
    RunDetectionCopyAttachment,
    RunDetectionListRead,
    RunDetectionSeriesDetailRead,
    RunDetectionSeriesRead,
    RunDetectionSeriesStatus,
    RunDetectionSummary,
)
from app.services.canonical_series import compute_series_key
from app.services.inventory_intelligence import normalize_ownership_state

_NUMERIC_ISSUE_PATTERN = re.compile(r"^0*(\d+)(?:\.(\d+))?$")
_NUMERIC_SUFFIX_PATTERN = re.compile(r"^0*(\d+)(?:\.(\d+))?([A-Za-z][A-Za-z0-9]*)$")
_ANNUAL_PATTERN = re.compile(r"^annual\s+(.+)$", re.IGNORECASE)
_SPECIAL_NAMES = {
    "alpha": "Alpha",
    "omega": "Omega",
    "one shot": "One-Shot",
    "one-shot": "One-Shot",
    "special": "Special",
    "tpb": "TPB",
    "hc": "HC",
}


@dataclass(frozen=True)
class ParsedIssueNumber:
    raw_value: str
    display_value: str
    kind: str
    numeric_value: Decimal | None
    sortable_key: tuple[object, ...]


@dataclass(frozen=True)
class InventoryRunRow:
    inventory_copy_id: int
    owner_user_id: int
    canonical_series_id: int | None
    publisher: str
    title: str
    issue_number: str
    release_status: str
    order_status: str
    received_at: object | None


@dataclass(frozen=True)
class RegistryIssueRow:
    canonical_series_id: int | None
    publisher: str
    title: str
    issue_number: str
    release_date: date | None


def parse_issue_number_for_run_detection(value: str | None) -> ParsedIssueNumber:
    raw = str(value or "").strip()
    if not raw:
        return ParsedIssueNumber(
            raw_value="",
            display_value="",
            kind="unknown",
            numeric_value=None,
            sortable_key=(99, ""),
        )

    annual_match = _ANNUAL_PATTERN.match(raw)
    if annual_match:
        nested = parse_issue_number_for_run_detection(annual_match.group(1))
        display = f"Annual {nested.display_value or annual_match.group(1).strip()}"
        nested_sort = nested.numeric_value if nested.numeric_value is not None else Decimal("0")
        return ParsedIssueNumber(
            raw_value=raw,
            display_value=display,
            kind="annual",
            numeric_value=None,
            sortable_key=(20, nested_sort, nested.display_value),
        )

    lowered = raw.lower()
    if lowered in _SPECIAL_NAMES:
        display = _SPECIAL_NAMES[lowered]
        return ParsedIssueNumber(
            raw_value=raw,
            display_value=display,
            kind="special",
            numeric_value=None,
            sortable_key=(30, display),
        )

    suffix_match = _NUMERIC_SUFFIX_PATTERN.fullmatch(raw)
    if suffix_match:
        integer_part = str(int(suffix_match.group(1)))
        decimal_part = (suffix_match.group(2) or "").rstrip("0")
        suffix = suffix_match.group(3).upper()
        numeric_text = integer_part if not decimal_part else f"{integer_part}.{decimal_part}"
        numeric_value = Decimal(numeric_text)
        return ParsedIssueNumber(
            raw_value=raw,
            display_value=f"{numeric_text}{suffix}",
            kind="numeric_suffix",
            numeric_value=numeric_value,
            sortable_key=(10, numeric_value, suffix),
        )

    numeric_match = _NUMERIC_ISSUE_PATTERN.fullmatch(raw)
    if numeric_match:
        integer_part = str(int(numeric_match.group(1)))
        decimal_part = (numeric_match.group(2) or "").rstrip("0")
        numeric_text = integer_part if not decimal_part else f"{integer_part}.{decimal_part}"
        numeric_value = Decimal(numeric_text)
        kind = "decimal" if decimal_part else "integer"
        return ParsedIssueNumber(
            raw_value=raw,
            display_value=numeric_text,
            kind=kind,
            numeric_value=numeric_value,
            sortable_key=(0, numeric_value, ""),
        )

    if raw.lower().startswith("annual"):
        return ParsedIssueNumber(
            raw_value=raw,
            display_value=raw,
            kind="annual",
            numeric_value=None,
            sortable_key=(20, raw),
        )

    return ParsedIssueNumber(
        raw_value=raw,
        display_value=raw,
        kind="special",
        numeric_value=None,
        sortable_key=(40, raw.upper()),
    )


def _inventory_projection_rows(session: Session, *, user_id: int | None) -> list[InventoryRunRow]:
    stmt = apply_inventory_spine_joins(
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.user_id.label("owner_user_id"),
            InventoryCopy.canonical_series_id.label("canonical_series_id"),
            publisher_expr().label("publisher"),
            title_expr().label("title"),
            issue_number_expr().label("issue_number"),
            InventoryCopy.release_status.label("release_status"),
            InventoryCopy.order_status.label("order_status"),
            InventoryCopy.received_at.label("received_at"),
        ).select_from(InventoryCopy)
    )
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    stmt = stmt.order_by(
        InventoryCopy.user_id.asc(),
        publisher_expr().asc(),
        title_expr().asc(),
        InventoryCopy.id.asc(),
    )
    rows = session.exec(stmt).all()
    return [
        InventoryRunRow(
            inventory_copy_id=int(row.inventory_copy_id),
            owner_user_id=int(row.owner_user_id),
            canonical_series_id=int(row.canonical_series_id) if row.canonical_series_id is not None else None,
            publisher=str(row.publisher),
            title=str(row.title),
            issue_number=str(row.issue_number),
            release_status=str(row.release_status),
            order_status=str(row.order_status),
            received_at=row.received_at,
        )
        for row in rows
        if row.owner_user_id is not None
    ]


def _registry_issue_rows(session: Session) -> list[RegistryIssueRow]:
    catalog_rows = load_catalog_registry_issue_rows(session)
    if catalog_rows:
        out: list[RegistryIssueRow] = []
        for row in catalog_rows:
            release_date = None
            if row.cover_date:
                try:
                    release_date = date.fromisoformat(row.cover_date[:10])
                except ValueError:
                    release_date = None
            out.append(
                RegistryIssueRow(
                    canonical_series_id=row.catalog_series_id,
                    publisher=row.publisher,
                    title=row.series,
                    issue_number=row.issue_number,
                    release_date=release_date,
                )
            )
        return out
    if not legacy_comic_issue_table_exists(session):
        return []
    stmt = (
        select(
            CanonicalSeries.id.label("canonical_series_id"),
            Publisher.name.label("publisher"),
            ComicTitle.name.label("title"),
            ComicIssue.issue_number.label("issue_number"),
            ComicIssue.release_date.label("release_date"),
            ComicIssue.cover_date.label("cover_date"),
        )
        .select_from(ComicIssue)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .join(
            CanonicalSeries,
            (CanonicalSeries.canonical_title == ComicTitle.name)
            & (CanonicalSeries.canonical_publisher == Publisher.name),
            isouter=True,
        )
        .order_by(Publisher.name.asc(), ComicTitle.name.asc(), ComicIssue.issue_number.asc(), ComicIssue.id.asc())
    )
    rows = session.exec(stmt).all()
    out: list[RegistryIssueRow] = []
    for row in rows:
        release_date = row.release_date or row.cover_date
        out.append(
            RegistryIssueRow(
                canonical_series_id=int(row.canonical_series_id) if row.canonical_series_id is not None else None,
                publisher=str(row.publisher),
                title=str(row.title),
                issue_number=str(row.issue_number),
                release_date=release_date,
            )
        )
    return out


def _bucket_key_for_series(
    *,
    canonical_series_id: int | None,
    publisher: str,
    title: str,
) -> tuple[int | None, str]:
    return canonical_series_id, compute_series_key(publisher, title)


def _pending_canonical_series_flags(session: Session) -> dict[int, set[str]]:
    rows = session.exec(
        apply_inventory_spine_joins(
            select(
                InventoryCopy.user_id,
                InventoryCopy.canonical_series_id,
                publisher_expr(),
                title_expr(),
                CanonicalIssueLinkSuggestion.id,
            )
            .select_from(CanonicalIssueLinkSuggestion)
            .join(InventoryCopy, CanonicalIssueLinkSuggestion.inventory_copy_id == InventoryCopy.id)
        )
        .where(
            CanonicalIssueLinkSuggestion.review_state == "pending",
            CanonicalIssueLinkSuggestion.inventory_copy_id.is_not(None),
        )
    ).all()

    out: dict[int, set[str]] = defaultdict(set)
    for user_id, canonical_series_id, publisher, title, _ in rows:
        if user_id is None:
            continue
        series_key = _bucket_key_for_series(
            canonical_series_id=int(canonical_series_id) if canonical_series_id is not None else None,
            publisher=str(publisher),
            title=str(title),
        )[1]
        out[int(user_id)].add(series_key)
    return out


def _sort_unique_issue_labels(labels: set[str]) -> list[str]:
    return [item.display_value for item in sorted((parse_issue_number_for_run_detection(v) for v in labels), key=lambda p: p.sortable_key)]


def _series_status_for_group(
    *,
    missing_items: list[MissingIssueRead],
    numeric_owned_values: list[Decimal],
    numeric_released_registry_count: int,
    isolated_issue_labels: list[str],
) -> RunDetectionSeriesStatus:
    has_future = any(item.classification in ("unreleased_future_issue", "preorder_pending") for item in missing_items)
    has_confirmed = any(item.classification == "confirmed_missing" for item in missing_items)
    has_likely = any(item.classification == "likely_missing" for item in missing_items)
    has_unresolved = any(item.classification == "unresolved_identity_gap" for item in missing_items)

    if not numeric_owned_values and isolated_issue_labels:
        return "isolated_special_annual"
    if has_future:
        return "probable_ongoing_series"
    if numeric_released_registry_count and len(numeric_owned_values) == numeric_released_registry_count and not missing_items:
        return "complete_limited_series"
    if has_confirmed or has_unresolved:
        return "incomplete_limited_series"
    if has_likely:
        return "partial_run"
    if numeric_released_registry_count and len(numeric_owned_values) < numeric_released_registry_count:
        return "partial_run"
    return "isolated_special_annual" if isolated_issue_labels else "complete_limited_series"


def _missing_issue_summary(
    groups: list[RunDetectionSeriesRead],
) -> RunDetectionSummary:
    summary = RunDetectionSummary()
    summary.total_series_groups = len(groups)
    for group in groups:
        if group.series_status == "partial_run":
            summary.partial_run_groups += 1
        elif group.series_status == "complete_limited_series":
            summary.complete_limited_series_groups += 1
        elif group.series_status == "incomplete_limited_series":
            summary.incomplete_limited_series_groups += 1
        elif group.series_status == "probable_ongoing_series":
            summary.probable_ongoing_series_groups += 1
        elif group.series_status == "isolated_special_annual":
            summary.isolated_special_annual_groups += 1

        for item in group.missing_issues:
            summary.total_missing_issue_rows += 1
            if item.classification == "confirmed_missing":
                summary.confirmed_missing_rows += 1
            elif item.classification == "likely_missing":
                summary.likely_missing_rows += 1
            elif item.classification == "unreleased_future_issue":
                summary.unreleased_future_issue_rows += 1
            elif item.classification == "preorder_pending":
                summary.preorder_pending_rows += 1
            elif item.classification == "unresolved_identity_gap":
                summary.unresolved_identity_gap_rows += 1
    return summary


def run_detection_groups_for_user(
    session: Session,
    *,
    owner_user_id: int,
) -> list[RunDetectionSeriesRead]:
    today = date.today()
    inventory_rows = _inventory_projection_rows(session, user_id=owner_user_id)
    if not inventory_rows:
        return []

    registry_rows = _registry_issue_rows(session)
    pending_by_user = _pending_canonical_series_flags(session)
    pending_series_keys = pending_by_user.get(owner_user_id, set())

    registry_by_bucket: dict[tuple[int | None, str], dict[str, date | None]] = defaultdict(dict)
    for reg in registry_rows:
        bucket = _bucket_key_for_series(
            canonical_series_id=reg.canonical_series_id,
            publisher=reg.publisher,
            title=reg.title,
        )
        registry_by_bucket[bucket].setdefault(reg.issue_number, reg.release_date)
        # Fallback series-key bucket for rows whose inventory lacks canonical_series_id.
        fallback_bucket = _bucket_key_for_series(
            canonical_series_id=None,
            publisher=reg.publisher,
            title=reg.title,
        )
        registry_by_bucket[fallback_bucket].setdefault(reg.issue_number, reg.release_date)

    grouped_inventory: dict[tuple[int | None, str], list[InventoryRunRow]] = defaultdict(list)
    for row in inventory_rows:
        grouped_inventory[
            _bucket_key_for_series(
                canonical_series_id=row.canonical_series_id,
                publisher=row.publisher,
                title=row.title,
            )
        ].append(row)

    groups: list[RunDetectionSeriesRead] = []

    for bucket, items in sorted(grouped_inventory.items(), key=lambda item: item[0][1]):
        canonical_series_id, series_key = bucket
        first = items[0]
        owned_by_issue: dict[str, list[InventoryRunRow]] = defaultdict(list)
        for row in items:
            parsed = parse_issue_number_for_run_detection(row.issue_number)
            owned_by_issue[parsed.display_value].append(row)

        registry_issue_map = registry_by_bucket.get(bucket, {})
        for owned_issue in owned_by_issue:
            registry_issue_map.setdefault(owned_issue, None)

        parsed_registry = {
            issue_label: parse_issue_number_for_run_detection(issue_label)
            for issue_label in registry_issue_map
        }
        owned_issue_labels = set(owned_by_issue.keys())
        isolated_issue_labels = sorted(
            {
                label
                for label, parsed in parsed_registry.items()
                if parsed.kind in {"annual", "special", "numeric_suffix"}
                and label in owned_issue_labels
            },
            key=lambda value: parse_issue_number_for_run_detection(value).sortable_key,
        )

        issue_ownership_state: dict[str, str] = {}
        for issue_label, rows in owned_by_issue.items():
            states = {
                normalize_ownership_state(
                    release_status=row.release_status,
                    order_status=row.order_status,
                    received_at=row.received_at,
                )
                for row in rows
            }
            if "in_hand" in states:
                issue_ownership_state[issue_label] = "in_hand"
            elif "preorder" in states:
                issue_ownership_state[issue_label] = "preorder"
            elif "ordered_not_received" in states:
                issue_ownership_state[issue_label] = "ordered_not_received"
            elif "cancelled" in states:
                issue_ownership_state[issue_label] = "cancelled"
            else:
                issue_ownership_state[issue_label] = "unknown_state"

        numeric_registry_values: list[tuple[Decimal, str, date | None]] = []
        for issue_label, parsed in parsed_registry.items():
            if parsed.kind not in {"integer", "decimal"} or parsed.numeric_value is None:
                continue
            numeric_registry_values.append((parsed.numeric_value, issue_label, registry_issue_map.get(issue_label)))
        numeric_registry_values.sort(key=lambda item: item[0])

        numeric_owned_values = sorted(
            {
                parsed_registry[label].numeric_value
                for label in owned_issue_labels
                if label in parsed_registry
                and parsed_registry[label].kind in {"integer", "decimal"}
                and parsed_registry[label].numeric_value is not None
                and issue_ownership_state.get(label) != "cancelled"
            }
        )
        comparative_values = sorted(
            {
                parsed_registry[label].numeric_value
                for label in owned_issue_labels
                if label in parsed_registry
                and parsed_registry[label].kind in {"integer", "decimal"}
                and parsed_registry[label].numeric_value is not None
                and issue_ownership_state.get(label) in {"in_hand", "preorder"}
            }
        )

        min_anchor = comparative_values[0] if comparative_values else None
        max_anchor = comparative_values[-1] if comparative_values else None

        missing_items: list[MissingIssueRead] = []
        related_inventory_ids = sorted(int(row.inventory_copy_id) for row in items)
        sorted_owned_labels = _sort_unique_issue_labels(set(owned_issue_labels))

        for issue_label in sorted(owned_issue_labels):
            state = issue_ownership_state.get(issue_label)
            if state != "preorder":
                continue
            missing_items.append(
                MissingIssueRead(
                    series_key=series_key,
                    owner_user_id=owner_user_id,
                    publisher=first.publisher,
                    title=first.title,
                    issue_number=issue_label,
                    classification="preorder_pending",
                    issue_release_date=registry_issue_map.get(issue_label),
                    related_inventory_copy_ids=sorted(int(row.inventory_copy_id) for row in owned_by_issue[issue_label]),
                    related_owned_issue_numbers=sorted_owned_labels,
                    reason="Issue is already present in your ownership pipeline as a preorder.",
                )
            )

        for numeric_value, issue_label, release_date_value in numeric_registry_values:
            if issue_label in owned_issue_labels:
                continue
            if release_date_value is not None and release_date_value > today:
                missing_items.append(
                    MissingIssueRead(
                        series_key=series_key,
                        owner_user_id=owner_user_id,
                        publisher=first.publisher,
                        title=first.title,
                        issue_number=issue_label,
                        classification="unreleased_future_issue",
                        issue_release_date=release_date_value,
                        related_inventory_copy_ids=related_inventory_ids,
                        related_owned_issue_numbers=sorted_owned_labels,
                        reason="Known issue exists in the registry but is not released yet.",
                    )
                )
                continue
            if min_anchor is not None and max_anchor is not None and min_anchor < numeric_value < max_anchor:
                cls: MissingIssueClassification = "confirmed_missing"
            elif numeric_owned_values:
                cls = "likely_missing"
            else:
                continue
            missing_items.append(
                MissingIssueRead(
                    series_key=series_key,
                    owner_user_id=owner_user_id,
                    publisher=first.publisher,
                    title=first.title,
                    issue_number=issue_label,
                    classification=cls,
                    issue_release_date=release_date_value,
                    related_inventory_copy_ids=related_inventory_ids,
                    related_owned_issue_numbers=sorted_owned_labels,
                    reason=(
                        "Issue falls between owned series anchors."
                        if cls == "confirmed_missing"
                        else "Issue is outside the current owned slice but present in the known registry."
                    ),
                )
            )

        if series_key in pending_series_keys:
            missing_items.append(
                MissingIssueRead(
                    series_key=series_key,
                    owner_user_id=owner_user_id,
                    publisher=first.publisher,
                    title=first.title,
                    issue_number=None,
                    classification="unresolved_identity_gap",
                    related_inventory_copy_ids=related_inventory_ids,
                    related_owned_issue_numbers=sorted_owned_labels,
                    reason="Pending canonical issue suggestions prevent fully closed deterministic run math.",
                )
            )

        missing_items.sort(
            key=lambda item: (
                0 if item.issue_number is not None else 1,
                parse_issue_number_for_run_detection(item.issue_number).sortable_key if item.issue_number else (99, "identity"),
                item.classification,
            )
        )

        numeric_released_registry_count = sum(
            1
            for _, _, release_date_value in numeric_registry_values
            if release_date_value is None or release_date_value <= today
        )
        series_status = _series_status_for_group(
            missing_items=missing_items,
            numeric_owned_values=numeric_owned_values,
            numeric_released_registry_count=numeric_released_registry_count,
            isolated_issue_labels=isolated_issue_labels,
        )
        groups.append(
            RunDetectionSeriesRead(
                series_key=series_key,
                owner_user_id=owner_user_id,
                publisher=first.publisher,
                title=first.title,
                canonical_series_id=canonical_series_id,
                series_status=series_status,
                owned_issue_numbers=sorted_owned_labels,
                isolated_issue_numbers=isolated_issue_labels,
                inventory_copy_ids=related_inventory_ids,
                distinct_issue_count=len(owned_issue_labels),
                known_issue_count=len(parsed_registry),
                missing_issues=missing_items,
                signal_flags={
                    "has_confirmed_gaps": any(item.classification == "confirmed_missing" for item in missing_items),
                    "has_likely_gaps": any(item.classification == "likely_missing" for item in missing_items),
                    "has_unreleased_future_issues": any(
                        item.classification == "unreleased_future_issue" for item in missing_items
                    ),
                    "has_preorder_pending_issues": any(item.classification == "preorder_pending" for item in missing_items),
                    "has_unresolved_identity_gaps": any(
                        item.classification == "unresolved_identity_gap" for item in missing_items
                    ),
                    "has_isolated_special_or_annual_issues": bool(isolated_issue_labels),
                    "variant_aware_issue_ownership": any(len(rows) > 1 for rows in owned_by_issue.values()),
                    "uses_canonical_series_identity": canonical_series_id is not None,
                },
            )
        )

    groups.sort(key=lambda group: (int(group.owner_user_id or -1), group.publisher, group.title, group.series_key))
    return groups


def run_detection_inventory_attach_map(
    groups: list[RunDetectionSeriesRead],
) -> dict[int, RunDetectionCopyAttachment]:
    out: dict[int, RunDetectionCopyAttachment] = {}
    for group in groups:
        missing_labels = [row.issue_number for row in group.missing_issues if row.issue_number and row.classification in ("confirmed_missing", "likely_missing")]
        pending_labels = [row.issue_number for row in group.missing_issues if row.issue_number and row.classification in ("preorder_pending", "unreleased_future_issue")]
        for inventory_id in group.inventory_copy_ids:
            out[int(inventory_id)] = RunDetectionCopyAttachment(
                series_key=group.series_key,
                series_status=group.series_status,
                missing_issue_numbers=missing_labels,
                pending_issue_numbers=pending_labels,
                owned_issue_numbers=group.owned_issue_numbers,
            )
    return out


def run_detection_inventory_context_for_owner(
    session: Session,
    *,
    user: User,
) -> tuple[list[RunDetectionSeriesRead], dict[int, RunDetectionCopyAttachment]]:
    assert user.id is not None
    groups = run_detection_groups_for_user(session, owner_user_id=int(user.id))
    return groups, run_detection_inventory_attach_map(groups)


def list_run_detection_owner(
    session: Session,
    *,
    user: User,
    series_status: RunDetectionSeriesStatus | None = None,
) -> RunDetectionListRead:
    groups, _ = run_detection_inventory_context_for_owner(session, user=user)
    if series_status is not None:
        groups = [group for group in groups if group.series_status == series_status]
    return RunDetectionListRead(summary=_missing_issue_summary(groups), series_groups=groups)


def list_missing_issues_owner(
    session: Session,
    *,
    user: User,
    classification: MissingIssueClassification | None = None,
) -> MissingIssueListRead:
    groups, _ = run_detection_inventory_context_for_owner(session, user=user)
    summary = _missing_issue_summary(groups)
    items = [item for group in groups for item in group.missing_issues]
    if classification is not None:
        items = [item for item in items if item.classification == classification]
    return MissingIssueListRead(summary=summary, items=items)


def get_run_detection_detail_owner(
    session: Session,
    *,
    user: User,
    series_key: str,
) -> RunDetectionSeriesDetailRead:
    groups, _ = run_detection_inventory_context_for_owner(session, user=user)
    match = next((group for group in groups if group.series_key == series_key), None)
    if match is None:
        raise HTTPException(status_code=404, detail="Run detection series not found")
    return RunDetectionSeriesDetailRead(
        series_key=match.series_key,
        publisher=match.publisher,
        title=match.title,
        owner_groups=[match],
        missing_issues=match.missing_issues,
    )


def list_run_detection_ops(
    session: Session,
    *,
    series_status: RunDetectionSeriesStatus | None = None,
) -> RunDetectionListRead:
    user_ids = session.exec(select(InventoryCopy.user_id)).all()
    groups: list[RunDetectionSeriesRead] = []
    for user_id in sorted({int(item) for item in user_ids if item is not None}):
        groups.extend(run_detection_groups_for_user(session, owner_user_id=user_id))
    if series_status is not None:
        groups = [group for group in groups if group.series_status == series_status]
    return RunDetectionListRead(summary=_missing_issue_summary(groups), series_groups=groups)


def list_missing_issues_ops(
    session: Session,
    *,
    classification: MissingIssueClassification | None = None,
) -> MissingIssueListRead:
    rollup = list_run_detection_ops(session, series_status=None)
    items = [item for group in rollup.series_groups for item in group.missing_issues]
    if classification is not None:
        items = [item for item in items if item.classification == classification]
    return MissingIssueListRead(summary=rollup.summary, items=items)


def get_run_detection_detail_ops(
    session: Session,
    *,
    series_key: str,
) -> RunDetectionSeriesDetailRead:
    rollup = list_run_detection_ops(session, series_status=None)
    owner_groups = [group for group in rollup.series_groups if group.series_key == series_key]
    if not owner_groups:
        raise HTTPException(status_code=404, detail="Run detection series not found")
    first = owner_groups[0]
    missing_issues = [item for group in owner_groups for item in group.missing_issues]
    missing_issues.sort(
        key=lambda item: (
            int(item.owner_user_id or -1),
            parse_issue_number_for_run_detection(item.issue_number).sortable_key if item.issue_number else (99, "identity"),
            item.classification,
        )
    )
    return RunDetectionSeriesDetailRead(
        series_key=series_key,
        publisher=first.publisher,
        title=first.title,
        owner_groups=owner_groups,
        missing_issues=missing_issues,
    )
