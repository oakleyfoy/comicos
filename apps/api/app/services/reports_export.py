"""Deterministic CSV/JSON report exports (read-only).

Inventory snapshots intentionally omit valuation fields ``current_fmv`` and ``gain_loss``.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlmodel import Session, select

from app.models import InventoryCopy, User
from app.schemas.collection_timeline import CollectionTimelineEventType, OwnershipStateFilter
from app.schemas.inventory import InventoryRow
from app.schemas.inventory_action_center import InventoryActionCenterCategory
from app.schemas.inventory_risks import InventoryRiskPriority, InventoryRiskType
from app.schemas.order_arrival_intelligence import OrderArrivalClassification
from app.schemas.run_detection import RunDetectionSeriesStatus
from app.services.collection_analytics import analyze_collection_summary
from app.services.collection_timeline import MAX_TIMELINE_EVENTS, timeline_events_for_scope
from app.services.duplicate_ownership_intelligence import (
    duplicate_ownership_inventory_context_for_owner,
    list_duplicate_ownership_ops,
    list_duplicate_ownership_owner,
)
from app.services.inventory import ReleaseCalendarPresence, list_inventory
from app.services.inventory_action_center import attachment_from_items, build_inventory_action_items
from app.services.inventory_action_center import get_inventory_action_center_response
from app.services.inventory_intelligence import compute_inventory_intelligence
from app.services.inventory_risks import compute_inventory_risks
from app.services.ops_admin import _build_reconciliation_summary
from app.services.order_arrival_intelligence import batch_order_arrival_classifications
from app.services.order_arrival_intelligence import compute_order_arrival_intelligence
from app.services.run_detection import list_run_detection_ops, run_detection_inventory_attach_map
from app.services.run_detection import run_detection_inventory_context_for_owner

INVENTORY_OWNER_CSV_COLUMNS: tuple[str, ...] = (
    "inventory_copy_id",
    "title",
    "publisher",
    "issue_number",
    "cover_name",
    "printing",
    "ratio",
    "variant_type",
    "cover_artist",
    "retailer",
    "order_date",
    "purchase_date",
    "acquisition_cost",
    "grade_status",
    "hold_status",
    "star_rating",
    "condition_notes",
    "release_date",
    "release_year",
    "release_status",
    "order_status",
    "expected_ship_date",
    "received_at",
    "asset_state",
    "is_in_hand",
    "order_arrival_classifications",
    "risk_types",
    "duplicate_ownership_group_keys",
    "inventory_intelligence_json",
    "duplicate_ownership_json",
    "run_detection_json",
    "inventory_risks_json",
    "inventory_action_center_json",
)
INVENTORY_OPS_CSV_COLUMNS: tuple[str, ...] = ("inventory_copy_id", "owner_user_id") + INVENTORY_OWNER_CSV_COLUMNS[1:]
ACTION_CENTER_CSV_COLUMNS: tuple[str, ...] = (
    "action_key",
    "action_category",
    "priority",
    "inventory_copy_id",
    "publisher",
    "title",
    "issue_number",
    "ownership_state",
    "release_status",
    "preorder_release_state_label",
    "source",
    "evidence_summary_lines",
    "evidence_json",
)
ORDER_ARRIVAL_CSV_COLUMNS: tuple[str, ...] = (
    "intel_key",
    "inventory_copy_id",
    "classification",
    "retailer",
    "publisher",
    "title",
    "issue_number",
    "order_status",
    "release_status",
    "asset_state",
    "purchase_date",
    "release_date",
    "expected_ship_date",
    "received_at",
    "evidence_json",
)
RUN_DETECTION_SERIES_CSV_COLUMNS: tuple[str, ...] = (
    "owner_user_id",
    "series_key",
    "publisher",
    "title",
    "canonical_series_id",
    "series_status",
    "distinct_issue_count",
    "known_issue_count",
    "inventory_copy_ids",
    "owned_issue_numbers",
    "missing_issue_digest",
)
TIMELINE_CSV_COLUMNS: tuple[str, ...] = (
    "stable_id",
    "event_type",
    "occurred_at",
    "inventory_copy_id",
    "publisher",
    "series_title",
    "issue_number",
    "ownership_state_snapshot",
    "release_status_snapshot",
    "preorder_track",
    "evidence_json",
)


def sanitize_report_filename(fragment: str) -> str:
    stripped = fragment.strip().replace("\x00", "").replace("\r", "-").replace("\n", "-").replace("\t", "-")
    cleaned = re.sub(r"[^\w\-]+", "-", stripped, flags=re.ASCII)
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-").lower()
    return cleaned[:120] if cleaned else "report"


def _sorted_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_csv(headers: tuple[str, ...], rows: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow([_csv_cell(row.get(col)) for col in headers])
    return buf.getvalue()


def _ownership_from_intel(data: dict[str, Any]) -> str | None:
    ij = data.get("inventory_intelligence")
    if not isinstance(ij, dict):
        return None
    v = ij.get("ownership_state")
    return str(v) if v is not None else None


def finalize_inventory_plain(data: dict[str, Any], *, dup_extra_keys: str = "") -> dict[str, Any]:
    risks = data.get("inventory_risks") or []
    data["risk_types"] = "|".join(sorted({str(r.get("risk_type")) for r in risks if isinstance(r, dict)}))

    classifications = data.get("order_arrival_classifications") or []
    data["order_arrival_classifications"] = "|".join(sorted(str(c) for c in classifications))

    grp = dup_extra_keys
    if not grp:
        dop = data.get("duplicate_ownership")
        if isinstance(dop, dict) and dop.get("group_key"):
            grp = str(dop["group_key"])
    data["duplicate_ownership_group_keys"] = grp

    for src, dst in (
        ("inventory_intelligence", "inventory_intelligence_json"),
        ("duplicate_ownership", "duplicate_ownership_json"),
        ("run_detection", "run_detection_json"),
        ("inventory_risks", "inventory_risks_json"),
        ("inventory_action_center", "inventory_action_center_json"),
    ):
        payload = data.get(src)
        data[dst] = _sorted_json(payload) if payload is not None else ""
        data.pop(src, None)

    return data


def apply_inventory_plain_filters(
    rows: list[dict[str, Any]],
    *,
    release_status: str | None,
    order_status: str | None,
    preorder_only: bool,
    in_hand_only: bool,
    start_date: date | None,
    end_date: date | None,
    ownership_state: str | None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []

    def _cmp_iso(row: dict[str, Any]) -> str | None:
        rd = row.get("release_date")
        cand = rd if rd not in (None, "") else (row.get("purchase_date") or row.get("order_date"))
        if cand in (None, ""):
            return None
        return str(cand)[:10]

    for raw in rows:
        if ownership_state:
            ow = _ownership_from_intel(raw)
            if ow != ownership_state:
                continue
        if release_status and str(raw.get("release_status")) != release_status:
            continue
        if order_status and str(raw.get("order_status")) != order_status:
            continue
        if preorder_only:
            ast = str(raw.get("asset_state"))
            ow2 = _ownership_from_intel(raw) or ""
            if not (ast == "preorder_not_released_yet" or ow2 == "preorder"):
                continue
        if in_hand_only:
            ok = raw.get("is_in_hand") is True
            if not ok:
                ow3 = _ownership_from_intel(raw) or ""
                ok = ow3 == "in_hand"
            if not ok:
                continue

        iso = _cmp_iso(raw)
        if start_date and (iso is None or iso < start_date.isoformat()):
            continue
        if end_date and (iso is None or iso > end_date.isoformat()):
            continue

        filtered.append(raw)

    if filtered and "owner_user_id" in filtered[0]:
        filtered.sort(key=lambda r: (int(r["owner_user_id"]), int(r["inventory_copy_id"])))
        return filtered
    filtered.sort(
        key=lambda r: (str(r.get("publisher") or ""), str(r.get("title") or ""), int(r["inventory_copy_id"])),
    )
    return filtered


class InventoryExportFilters:
    """Parity knobs with ``GET /inventory`` plus post-row filters."""

    def __init__(
        self,
        *,
        search: str | None = None,
        publisher: str | None = None,
        hold_status: str | None = None,
        grade_status: str | None = None,
        release_year: int | None = None,
        release_calendar: ReleaseCalendarPresence | None = None,
        asset_state: str | None = None,
        intelligence_health: str | None = None,
        ownership_intel: str | None = None,
        risk_priority: InventoryRiskPriority | None = None,
        risk_type: InventoryRiskType | None = None,
        needs_attention: bool = False,
        action_attention: bool = False,
        action_center_category: InventoryActionCenterCategory | None = None,
        arrival_classification: OrderArrivalClassification | None = None,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        page_size: int = 125,
        release_status: str | None = None,
        order_status: str | None = None,
        preorder_only: bool = False,
        in_hand_only: bool = False,
        start_date: date | None = None,
        end_date: date | None = None,
        export_ownership_state: str | None = None,
    ) -> None:
        self.search = search
        self.publisher = publisher
        self.hold_status = hold_status
        self.grade_status = grade_status
        self.release_year = release_year
        self.release_calendar = release_calendar
        self.asset_state = asset_state
        self.intelligence_health = intelligence_health
        self.ownership_intel = ownership_intel
        self.risk_priority = risk_priority
        self.risk_type = risk_type
        self.needs_attention = needs_attention
        self.action_attention = action_attention
        self.action_center_category = action_center_category
        self.arrival_classification = arrival_classification
        self.sort_by = sort_by if sort_by else "purchase_date"
        self.sort_dir = sort_dir
        self.page_size = min(max(page_size, 1), 250)
        self.release_status = release_status
        self.order_status = order_status
        self.preorder_only = preorder_only
        self.in_hand_only = in_hand_only
        self.start_date = start_date
        self.end_date = end_date
        self.export_ownership_state = export_ownership_state

    def echo(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


def _inventory_pages(session: Session, *, scoped_user: User, filt: InventoryExportFilters) -> list[InventoryRow]:
    rows: list[InventoryRow] = []
    page = 1
    while True:
        resp = list_inventory(
            session,
            scoped_user,
            page=page,
            page_size=filt.page_size,
            search=filt.search,
            publisher=filt.publisher,
            hold_status=filt.hold_status,
            grade_status=filt.grade_status,
            release_year=filt.release_year,
            release_calendar=filt.release_calendar,
            asset_state=filt.asset_state,
            intelligence_health=filt.intelligence_health,
            ownership_intel=filt.ownership_intel,
            risk_priority=filt.risk_priority,
            risk_type=filt.risk_type,
            needs_attention=filt.needs_attention,
            action_attention=filt.action_attention,
            action_center_category=filt.action_center_category,
            arrival_classification=filt.arrival_classification,
            sort_by=filt.sort_by,
            sort_dir=filt.sort_dir,
        )
        rows.extend(resp.items)
        if not resp.items or len(resp.items) < filt.page_size:
            break
        page += 1
    return rows


def hydrate_inventory_rows(session: Session, *, rows: list[InventoryRow], owner_user_id: int) -> None:
    phantom = User(id=owner_user_id)
    _, _, _, intel_signals = compute_inventory_intelligence(session, current_user=phantom, include_signals=True)
    _, dup_attachments = duplicate_ownership_inventory_context_for_owner(
        session,
        user=phantom,
        dup_scan_classification="all",
    )
    _, run_attachments = run_detection_inventory_context_for_owner(session, user=phantom)
    _, all_risk_rows, risks_by_inventory = compute_inventory_risks(session, current_user=phantom)
    arrival_map = batch_order_arrival_classifications(session, user_id=owner_user_id)

    acts: defaultdict[int, list] = defaultdict(list)
    for act in build_inventory_action_items(
        session,
        risk_rows=all_risk_rows,
        signals_map=intel_signals,
        arrival_map=arrival_map,
        user_id_scope=owner_user_id,
    ):
        acts[act.inventory_copy_id].append(act)

    for row in rows:
        inv_pk = int(row.inventory_copy_id)
        row.inventory_intelligence = intel_signals.get(inv_pk)
        row.duplicate_ownership = dup_attachments.get(inv_pk)
        row.run_detection = run_attachments.get(inv_pk)
        row.inventory_risks = risks_by_inventory.get(inv_pk, [])
        row.order_arrival_classifications = arrival_map.get(inv_pk, [])
        row.inventory_action_center = attachment_from_items(acts.get(inv_pk, []))


def _inventory_user_ids_sorted(session: Session) -> list[int]:
    ids = session.exec(select(InventoryCopy.user_id)).all()
    return sorted({int(uid) for uid in ids if uid is not None})


def duplicate_key_map_global(session: Session) -> dict[int, str]:
    rollup = list_duplicate_ownership_ops(
        session,
        dup_scan_classification="all",
        classification=None,
    )
    bucket: defaultdict[int, list[str]] = defaultdict(list)
    for group in rollup.groups:
        for cid in group.inventory_copy_ids:
            bucket[int(cid)].append(group.group_key)
    return {cid: '|'.join(sorted(set(keys))) for cid, keys in sorted(bucket.items())}

def inventory_export_rows_owner(session: Session, *, owner: User, filt: InventoryExportFilters) -> tuple[list[dict[str, Any]], date]:
    assert owner.id is not None
    rows = _inventory_pages(session, scoped_user=owner, filt=filt)
    hydrate_inventory_rows(session, rows=rows, owner_user_id=int(owner.id))

    nested_rows: list[dict[str, Any]] = []
    for row in rows:
        blob = json.loads(row.model_dump_json())
        blob.pop("current_fmv", None)
        blob.pop("gain_loss", None)
        nested_rows.append(blob)

    filtered = apply_inventory_plain_filters(
        nested_rows,
        release_status=filt.release_status,
        order_status=filt.order_status,
        preorder_only=filt.preorder_only,
        in_hand_only=filt.in_hand_only,
        start_date=filt.start_date,
        end_date=filt.end_date,
        ownership_state=filt.export_ownership_state,
    )

    finalized = [finalize_inventory_plain(dict(row)) for row in filtered]
    return finalized, date.today()


def inventory_export_rows_ops(
    session: Session,
    *,
    filt: InventoryExportFilters,
    series_status: RunDetectionSeriesStatus | None,
) -> tuple[list[dict[str, Any]], date]:
    dup_map = duplicate_key_map_global(session)
    run_bundle = list_run_detection_ops(session, series_status=series_status)
    run_attach_global = run_detection_inventory_attach_map(run_bundle.series_groups)

    nested_rows: list[dict[str, Any]] = []
    for uid in _inventory_user_ids_sorted(session):
        phantom = User(id=uid)
        rows = _inventory_pages(session, scoped_user=phantom, filt=filt)
        hydrate_inventory_rows(session, rows=rows, owner_user_id=uid)

        for row in rows:
            blob = json.loads(row.model_dump_json())
            blob.pop("current_fmv", None)
            blob.pop("gain_loss", None)
            blob["owner_user_id"] = uid
            nested_rows.append(blob)

    filtered = apply_inventory_plain_filters(
        nested_rows,
        release_status=filt.release_status,
        order_status=filt.order_status,
        preorder_only=filt.preorder_only,
        in_hand_only=filt.in_hand_only,
        start_date=filt.start_date,
        end_date=filt.end_date,
        ownership_state=filt.export_ownership_state,
    )

    finalized: list[dict[str, Any]] = []
    for blob in filtered:
        inv_id = int(blob["inventory_copy_id"])
        dup_join = dup_map.get(inv_id, "")
        flat = finalize_inventory_plain(dict(blob), dup_extra_keys=dup_join)
        runner = run_attach_global.get(inv_id)
        if runner is not None:
            flat["run_detection_json"] = _sorted_json(runner.model_dump(mode="json"))
        finalized.append(flat)

    finalized.sort(key=lambda r: (int(r["owner_user_id"]), int(r["inventory_copy_id"])))
    return finalized, date.today()


def action_center_export_rows(
    session: Session,
    *,
    current_user: User | None,
    priority: InventoryRiskPriority | None,
    category: InventoryActionCenterCategory | None,
    ownership_state_filter: str | None,
    publisher: str | None,
    release_status_filter: str | None,
    in_hand_only: bool,
    inventory_copy_id_filter: int | None,
) -> tuple[list[dict[str, Any]], date]:
    body = get_inventory_action_center_response(
        session,
        current_user=current_user,
        priority=priority,
        action_category_str=category,
        ownership_state=ownership_state_filter,
        publisher=publisher,
        release_status_filter=release_status_filter,
        unresolved_only=True,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id_filter,
    )

    rows_out = []
    for item in sorted(
        body.actions,
        key=lambda a: (a.inventory_copy_id, str(a.priority), str(a.action_category), a.action_key),
    ):
        rows_out.append(
            {
                "action_key": item.action_key,
                "action_category": item.action_category,
                "priority": item.priority,
                "inventory_copy_id": item.inventory_copy_id,
                "publisher": item.publisher,
                "title": item.title,
                "issue_number": item.issue_number,
                "ownership_state": item.ownership_state,
                "release_status": item.release_status,
                "preorder_release_state_label": item.preorder_release_state_label,
                "source": item.source,
                "evidence_summary_lines": "|".join(item.evidence_summary_lines),
                "evidence_json": _sorted_json(item.evidence_json),
            },
        )

    return rows_out, date.fromisoformat(body.generated_as_of_date)


def order_arrival_export_rows(
    session: Session,
    *,
    current_user: User | None,
    classification: OrderArrivalClassification | None,
    retailer: str | None,
    publisher: str | None,
    release_date_from: date | None,
    release_date_to: date | None,
    expected_ship_date_from: date | None,
    expected_ship_date_to: date | None,
    order_status: str | None,
    in_hand_only: bool,
) -> tuple[list[dict[str, Any]], date]:
    response, _pair = compute_order_arrival_intelligence(
        session,
        current_user=current_user,
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )

    def _serialize(item: Any) -> dict[str, Any]:
        blob = item.model_dump(mode="json")
        blob["evidence_json"] = _sorted_json(item.evidence_json)
        return blob

    ordered = sorted(
        response.items,
        key=lambda r: (
            str(r.publisher),
            str(r.title),
            str(r.issue_number),
            r.inventory_copy_id,
            str(r.classification),
            r.intel_key,
        ),
    )
    return [_serialize(it) for it in ordered], date.fromisoformat(response.generated_as_of_date)


def run_detection_series_rows(
    session: Session,
    *,
    current_user: User | None,
    ops_scope: bool,
    series_status: RunDetectionSeriesStatus | None,
) -> tuple[list[dict[str, Any]], date]:
    if ops_scope:
        bundle = list_run_detection_ops(session, series_status=series_status)
        groups = bundle.series_groups
    else:
        assert current_user is not None

        from app.services.run_detection import list_run_detection_owner

        bundle = list_run_detection_owner(session, user=current_user, series_status=series_status)
        groups = bundle.series_groups

    rows_out: list[dict[str, Any]] = []

    sorted_groups = sorted(
        groups,
        key=lambda g: (int(g.owner_user_id or -1), g.publisher, g.title, g.series_key),
    )
    for group in sorted_groups:
        inv_part = "|".join(str(i) for i in sorted(group.inventory_copy_ids))

        owns = "|".join(str(x) for x in sorted(group.owned_issue_numbers, key=lambda s: str(s)))

        miss_bits = []
        for miss in sorted(
            group.missing_issues,
            key=lambda m: (str(m.issue_number), str(m.classification)),
        ):
            label = miss.issue_number or ""
            miss_bits.append(f"{miss.classification}:{label}")

        rows_out.append(
            {
                "owner_user_id": group.owner_user_id,
                "series_key": group.series_key,
                "publisher": group.publisher,
                "title": group.title,
                "canonical_series_id": group.canonical_series_id,
                "series_status": group.series_status,
                "distinct_issue_count": group.distinct_issue_count,
                "known_issue_count": group.known_issue_count,
                "inventory_copy_ids": inv_part,
                "owned_issue_numbers": owns,
                "missing_issue_digest": "|".join(miss_bits),
            },
        )

    return rows_out, date.today()


def timeline_export_rows(
    session: Session,
    *,
    ops_scope: bool,
    scoped_user_id: int | None,
    event_type_filter: CollectionTimelineEventType | None,
    publisher: str | None,
    ownership_filter: OwnershipStateFilter | None,
    release_status_tl: str | None,
    start_date_tl: date | None,
    end_date_tl: date | None,
    preorder_only: bool,
    in_hand_only: bool,
) -> tuple[list[dict[str, Any]], date]:
    uid = None if ops_scope else scoped_user_id

    payload = timeline_events_for_scope(
        session,
        scope_user_id=uid,
        event_type_filter=event_type_filter,
        publisher=publisher,
        ownership_filter=ownership_filter,
        release_status=release_status_tl,
        start_date=start_date_tl,
        end_date=end_date_tl,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
        inventory_copy_id=None,
        grouping="none",
        sort="asc",
        limit=MAX_TIMELINE_EVENTS,
        return_events=True,
    )

    rows_src = sorted(
        payload.events,
        key=lambda ev: (
            ev.occurred_at.isoformat(),
            str(ev.event_type),
            ev.stable_id,
        ),
    )

    serialized: list[dict[str, Any]] = []

    for ev in rows_src:
        serialized.append(
            {
                "stable_id": ev.stable_id,
                "event_type": ev.event_type,
                "occurred_at": ev.occurred_at.isoformat(),
                "inventory_copy_id": ev.inventory_copy_id,
                "publisher": ev.publisher,
                "series_title": ev.series_title,
                "issue_number": ev.issue_number,
                "ownership_state_snapshot": ev.ownership_state_snapshot,
                "release_status_snapshot": ev.release_status_snapshot,
                "preorder_track": ev.preorder_track,
                "evidence_json": _sorted_json(ev.evidence_json),
            },
        )

    return serialized, date.fromisoformat(payload.generated_as_of_date)


def collection_summary_payload(
    session: Session,
    *,
    projection_user_filter: int | None,
    intel_user: User | None,
    include_reconciliation: bool,
) -> dict[str, Any]:
    analytics, intelligence_summary = analyze_collection_summary(
        session,
        projection_user_filter=projection_user_filter,
        intel_user=intel_user,
        as_of_date=None,
    )
    risks_summary = compute_inventory_risks(session, current_user=intel_user, open_only=True)[0]

    duplicate_payload: dict[str, Any]

    if intel_user is not None and intel_user.id is not None:
        duplicate_payload = list_duplicate_ownership_owner(
            session,
            user=intel_user,
            dup_scan_classification="all",
            classification=None,
        ).model_dump(mode="json")
    else:

        duplicate_payload = list_duplicate_ownership_ops(
            session,
            dup_scan_classification="all",
            classification=None,
        ).model_dump(mode="json")

    recon = _build_reconciliation_summary(session).model_dump(mode="json") if include_reconciliation else None

    return {
        "generated_as_of_date": analytics.generated_as_of_date.isoformat(),
        "collection_analytics_summary": analytics.model_dump(mode="json"),
        "inventory_intelligence_summary": intelligence_summary.model_dump(mode="json"),
        "inventory_risk_summary": risks_summary.model_dump(mode="json"),
        "duplicate_ownership": duplicate_payload,
        "reconciliation_summary": recon,
    }


def dumps_report_json(data: dict[str, Any]) -> bytes:
    """Deterministic JSON bytes (sorted keys recursively, compact separators)."""

    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def inventory_export_json_document(
    rows: list[dict[str, Any]],
    filt: InventoryExportFilters,
    columns: tuple[str, ...],
    as_of_date: date,
) -> bytes:
    payload = {
        "schema": "comic-os.reports.inventory.v1",
        "generated_as_of_date": as_of_date.isoformat(),
        "columns": list(columns),
        "filters": json.loads(json.dumps(filt.echo(), default=str, sort_keys=True)),
        "rows": rows,
    }
    return dumps_report_json(payload)
