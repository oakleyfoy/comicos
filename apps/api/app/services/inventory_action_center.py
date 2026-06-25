from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

from sqlmodel import Session

from app.models import User
from app.schemas.inventory_action_center import (
    InventoryActionCenterAttachment,
    InventoryActionCenterGrouping,
    InventoryActionCenterItem,
    InventoryActionCenterListResponse,
    InventoryActionCenterSummary,
    InventoryActionCenterTopInventoryItem,
    InventoryActionLanePriority,
    InventoryReleaseStatusFilter,
)
from app.schemas.inventory_intelligence import KeyedCount
from app.schemas.inventory_risks import InventoryRiskPriority, InventoryRiskRead, InventoryRiskType
from app.schemas.order_arrival_intelligence import OrderArrivalClassification
from app.services.inventory_intelligence import (
    InventoryCopyIntelligenceSignals,
    compute_inventory_intelligence,
    normalize_ownership_state,
)
from app.services.inventory_risks import RiskProjectionRow, _covers_by_inventory, _inventory_projection_rows, compute_inventory_risks
from app.services.order_arrival_intelligence import batch_order_arrival_classifications

_PRIORITY_ORDER: dict[str, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "info": 4,
}

_CATEGORY_ORDER = (
    "review_relationship_conflict",
    "review_canonical_suggestion",
    "review_duplicate_ownership",
    "review_duplicate_scan",
    "review_variant_family",
    "retry_ocr",
    "review_cover_processing",
    "scan_missing_cover",
    "update_preorder_metadata",
    "review_run_gap",
    "review_high_confidence_match",
)


_RISK_TYPE_TO_CATEGORY: dict[InventoryRiskType, str] = {
    "needs_conflict_review": "review_relationship_conflict",
    "needs_canonical_review": "review_canonical_suggestion",
    "duplicate_uncertainty": "review_duplicate_ownership",
    "needs_scan": "scan_missing_cover",
    "needs_ocr_retry": "retry_ocr",
    "needs_cover_processing_review": "review_cover_processing",
    "preorder_missing_release_date": "update_preorder_metadata",
    "released_not_received": "update_preorder_metadata",
    "run_gap_detected": "review_run_gap",
    "low_quality_scan": "retry_ocr",
    "high_confidence_match_unreviewed": "review_high_confidence_match",
}

_ORDER_ARRIVAL_ACTIONABLE: dict[str, InventoryActionLanePriority] = {
    "missing_release_date": "medium",
    "missing_expected_ship_date": "medium",
    "overdue_expected_ship": "high",
}


def _series_key(title: str, publisher: str) -> str:
    return f"{publisher}\u241e{title}"


def _worst_lane(items: Iterable[InventoryActionCenterItem]) -> InventoryActionLanePriority | None:
    lane: InventoryActionLanePriority | None = None
    for it in items:
        if lane is None or _PRIORITY_ORDER[it.priority] < _PRIORITY_ORDER[lane]:
            lane = it.priority
    return lane


def attachment_from_items(items: Sequence[InventoryActionCenterItem]) -> InventoryActionCenterAttachment | None:
    if not items:
        return InventoryActionCenterAttachment()
    ls = sorted(
        items,
        key=lambda a: (_PRIORITY_ORDER[a.priority], _CATEGORY_ORDER.index(str(a.action_category)), str(a.action_key)),
    )
    worst = _worst_lane(ls)
    urgent = worst is not None and worst in ("critical", "high")
    cats_sorted = sorted({x.action_category for x in ls}, key=lambda c: (_CATEGORY_ORDER.index(c), c))
    keys_sorted = sorted({x.action_key for x in ls})
    return InventoryActionCenterAttachment(
        action_keys=keys_sorted,
        action_categories=list(cats_sorted),
        highest_lane_priority=worst,
        urgent_lane=urgent,
    )


def _coerce_release_status(val: str) -> InventoryReleaseStatusFilter:
    if val in ("released", "not_released_yet", "unknown"):
        return val  # type: ignore[return-value]
    return "unknown"


def _primary_cover_image_id(proj: RiskProjectionRow, covers_by_inventory: Mapping[int, list[Any]]) -> int | None:
    covers = covers_by_inventory.get(proj.inventory_copy_id, [])
    if proj.primary_cover_image_id is not None:
        pid = int(proj.primary_cover_image_id)
        for item in covers:
            if item.id is not None and int(item.id) == pid:
                return int(item.id)
    if covers:
        first = covers[0]
        return int(first.id) if first.id is not None else None
    return None


def _evidence_lines(evidence: dict[str, Any], *, limit: int = 4) -> list[str]:
    lines: list[str] = []
    for key in sorted(evidence.keys()):
        if len(lines) >= limit:
            break
        value = evidence[key]
        if isinstance(value, (list, tuple, set)):
            rendered = ", ".join(str(x) for x in sorted(value, key=lambda z: str(z))[:8])
        else:
            rendered = str(value)
        lines.append(f"{key}: {rendered}")
    return lines


def _item_from_risk(risk: InventoryRiskRead, *, release_status_raw: str) -> InventoryActionCenterItem:
    rs = _coerce_release_status(release_status_raw)
    lbl = f"{risk.ownership_state}|{rs}"
    return InventoryActionCenterItem(
        action_key=f"risk:{risk.risk_key}",
        action_category=_RISK_TYPE_TO_CATEGORY[risk.risk_type],  # type: ignore[arg-type]
        priority=risk.priority,  # type: ignore[arg-type]
        inventory_copy_id=int(risk.inventory_copy_id),
        cover_image_id=risk.cover_image_id,
        publisher=risk.publisher,
        title=risk.title,
        issue_number=risk.issue_number,
        ownership_state=risk.ownership_state,  # type: ignore[arg-type]
        release_status=rs,
        preorder_release_state_label=lbl,
        evidence_summary_lines=_evidence_lines(risk.evidence_json),
        evidence_json=dict(sorted(risk.evidence_json.items())),
        source="inventory_risk",
    )


def build_inventory_action_items(
    session: Session,
    *,
    risk_rows: Sequence[InventoryRiskRead],
    signals_map: Mapping[int, InventoryCopyIntelligenceSignals],
    arrival_map: Mapping[int, list[OrderArrivalClassification]],
    user_id_scope: int | None,
    inventory_copy_ids: Sequence[int] | None = None,
) -> list[InventoryActionCenterItem]:
    projections = list(
        _inventory_projection_rows(
            session,
            user_id=user_id_scope,
            inventory_copy_ids=inventory_copy_ids,
        ),
    )
    if not projections:
        return []

    proj_by_inv = {int(r.inventory_copy_id): r for r in projections}
    inv_ids_sorted = sorted(proj_by_inv.keys())
    covers_by = _covers_by_inventory(session, inv_ids_sorted)

    risk_types_by_inv: defaultdict[int, set[str]] = defaultdict(set)
    for rk in risk_rows:
        risk_types_by_inv[int(rk.inventory_copy_id)].add(str(rk.risk_type))

    actions: list[InventoryActionCenterItem] = []

    ordered_risk = sorted(
        risk_rows,
        key=lambda r: (
            _PRIORITY_ORDER[str(r.priority)],
            str(r.risk_type),
            int(r.inventory_copy_id),
            r.risk_key,
        ),
    )
    for risk in ordered_risk:
        row_meta = proj_by_inv.get(risk.inventory_copy_id)
        rel_raw = row_meta.release_status if row_meta is not None else "unknown"
        actions.append(_item_from_risk(risk, release_status_raw=str(rel_raw)))

    for inv_id in inv_ids_sorted:
        sig = signals_map.get(inv_id)
        proj = proj_by_inv[inv_id]
        ow_raw = normalize_ownership_state(
            release_status=str(proj.release_status),
            order_status=str(proj.order_status),
            received_at=proj.received_at,
        )
        rs = _coerce_release_status(str(proj.release_status))
        meta = dict(
            inventory_copy_id=int(inv_id),
            cover_image_id=_primary_cover_image_id(proj, covers_by),
            publisher=proj.publisher,
            title=proj.title,
            issue_number=proj.issue_number,
            ownership_state=ow_raw,
            release_status=rs,
            preorder_release_state_label=f"{ow_raw}|{rs}",
        )
        if sig and sig.touches_probable_duplicate_scan_cluster:
            actions.append(
                InventoryActionCenterItem(
                    action_key=f"intel:inv:{inv_id}:duplicate_scan_cluster",
                    action_category="review_duplicate_scan",
                    priority="medium",
                    evidence_summary_lines=["duplicate_scan_cluster_touch: deterministic intelligence signal"],
                    evidence_json={"touches_probable_duplicate_scan_cluster": True},
                    source="intelligence_duplicate_scan",
                    **meta,
                )
            )
        if sig and sig.touches_probable_variant_family_cluster:
            actions.append(
                InventoryActionCenterItem(
                    action_key=f"intel:inv:{inv_id}:variant_family_cluster",
                    action_category="review_variant_family",
                    priority="medium",
                    evidence_summary_lines=["variant_family_cluster_touch: deterministic intelligence signal"],
                    evidence_json={"touches_probable_variant_family_cluster": True},
                    source="intelligence_variant_family",
                    **meta,
                )
            )

        if inv_id not in arrival_map:
            continue
        for cls_name in sorted({str(item) for item in arrival_map[inv_id]}):
            cls_typed = cls_name if cls_name in _ORDER_ARRIVAL_ACTIONABLE else None
            if cls_typed is None:
                continue
            if cls_name == "released_not_received":
                continue
            rt = risk_types_by_inv.get(inv_id, set())
            if cls_name == "missing_release_date" and "preorder_missing_release_date" in rt:
                continue
            prio = _ORDER_ARRIVAL_ACTIONABLE[cls_name]
            actions.append(
                InventoryActionCenterItem(
                    action_key=f"order_arrival:inv:{inv_id}:{cls_name}",
                    action_category="update_preorder_metadata",
                    priority=prio,
                    evidence_summary_lines=[f"classification:{cls_name}"],
                    evidence_json={"order_arrival_classification": cls_name},
                    source="order_arrival",
                    **meta,
                )
            )

    return sorted(
        actions,
        key=lambda a: (
            _PRIORITY_ORDER[str(a.priority)],
            _CATEGORY_ORDER.index(str(a.action_category)),
            str(a.publisher),
            str(a.title),
            str(a.issue_number),
            int(a.inventory_copy_id),
            str(a.action_key),
        ),
    )


def filter_inventory_actions(
    actions: Sequence[InventoryActionCenterItem],
    *,
    priority: InventoryRiskPriority | None,
    action_category: str | None,
    ownership_state: str | None,
    publisher: str | None,
    release_status: str | None,
    in_hand_only: bool,
    inventory_copy_id_filter: int | None,
) -> list[InventoryActionCenterItem]:
    out = []
    for a in actions:
        if inventory_copy_id_filter is not None and int(a.inventory_copy_id) != int(inventory_copy_id_filter):
            continue
        if priority is not None and str(a.priority) != str(priority):
            continue
        if action_category is not None and str(a.action_category) != action_category:
            continue
        if ownership_state is not None and str(a.ownership_state) != ownership_state:
            continue
        if publisher is not None and str(a.publisher) != publisher:
            continue
        if release_status is not None and release_status != "all" and str(a.release_status) != release_status:
            continue
        if in_hand_only and str(a.ownership_state) != "in_hand":
            continue
        out.append(a)
    return out


def _by_category_deterministic_keys(by_cat: Mapping[str, int]) -> list[str]:
    """Primary sort: descending counts; ties follow workflow category precedence, then lexical key."""

    def sort_key(cat: str) -> tuple[int, int, str]:
        try:
            cat_idx = _CATEGORY_ORDER.index(cat)
        except ValueError:
            cat_idx = len(_CATEGORY_ORDER)
        return (-int(by_cat[cat]), cat_idx, cat)

    return sorted(by_cat.keys(), key=sort_key)


def _summary_from_filtered(
    *,
    scope_user_id: int | None,
    scope: str,
    filtered: Sequence[InventoryActionCenterItem],
    total_inventory_copies: int,
) -> InventoryActionCenterSummary:
    by_lane: defaultdict[str, int] = defaultdict(int)
    by_cat: defaultdict[str, int] = defaultdict(int)
    for item in filtered:
        by_lane[str(item.priority)] += 1
        by_cat[str(item.action_category)] += 1

    inv_groups: defaultdict[int, list[InventoryActionCenterItem]] = defaultdict(list)
    for item in filtered:
        inv_groups[item.inventory_copy_id].append(item)

    top_entries: list[InventoryActionCenterTopInventoryItem] = []
    for inv_id, grp in sorted(inv_groups.items()):
        grp_sorted = sorted(
            grp,
            key=lambda a: (_PRIORITY_ORDER[str(a.priority)], _CATEGORY_ORDER.index(str(a.action_category)), str(a.action_key)),
        )
        worst = _worst_lane(grp_sorted) or "info"
        first = grp_sorted[0]
        cats = sorted({x.action_category for x in grp}, key=lambda c: (_CATEGORY_ORDER.index(str(c)), str(c)))
        top_entries.append(
            InventoryActionCenterTopInventoryItem(
                inventory_copy_id=int(inv_id),
                publisher=str(first.publisher),
                title=str(first.title),
                issue_number=str(first.issue_number),
                highest_lane_priority=str(worst),  # type: ignore[arg-type]
                ownership_state=first.ownership_state,  # type: ignore[arg-type]
                action_count=len(grp_sorted),
                action_categories=list(cats),
            )
        )
    top_entries.sort(
        key=lambda row: (_PRIORITY_ORDER[str(row.highest_lane_priority)], -row.action_count, row.publisher, row.title, row.inventory_copy_id),
    )

    return InventoryActionCenterSummary(
        scope_user_id=scope_user_id,
        scope=scope,
        generated_as_of_date=date.today().isoformat(),
        total_inventory_copies=total_inventory_copies,
        total_actions=len(filtered),
        copies_with_actions=len(inv_groups),
        critical_actions=int(by_lane.get("critical", 0)),
        high_actions=int(by_lane.get("high", 0)),
        medium_actions=int(by_lane.get("medium", 0)),
        low_actions=int(by_lane.get("low", 0)),
        info_actions=int(by_lane.get("info", 0)),
        by_category=[KeyedCount(key=k, count=by_cat[k]) for k in _by_category_deterministic_keys(by_cat)],
        by_priority_lane=[KeyedCount(key=k, count=by_lane[k]) for k in ("critical", "high", "medium", "low", "info") if k in by_lane],
        top_unresolved_inventory=top_entries[:10],
    )


def build_action_center_grouping(actions: Sequence[InventoryActionCenterItem]) -> InventoryActionCenterGrouping:
    by_inv: defaultdict[int, set[str]] = defaultdict(set)
    by_cover: defaultdict[int, set[str]] = defaultdict(set)
    by_series: defaultdict[str, set[str]] = defaultdict(set)
    by_pub: defaultdict[str, set[str]] = defaultdict(set)
    by_own: defaultdict[str, set[str]] = defaultdict(set)
    by_pre_rel: defaultdict[str, set[str]] = defaultdict(set)
    ordered = sorted(
        actions,
        key=lambda a: (
            _PRIORITY_ORDER[str(a.priority)],
            _CATEGORY_ORDER.index(str(a.action_category)),
            a.action_key,
        ),
    )
    for a in ordered:
        by_inv[a.inventory_copy_id].add(a.action_key)
        series_k = _series_key(a.title, a.publisher)
        by_series[series_k].add(a.action_key)
        by_pub[a.publisher].add(a.action_key)
        by_own[str(a.ownership_state)].add(a.action_key)
        by_pre_rel[str(a.preorder_release_state_label)].add(a.action_key)
        cid = a.cover_image_id
        if cid is not None:
            by_cover[int(cid)].add(a.action_key)

    return InventoryActionCenterGrouping(
        action_keys_by_inventory_copy_id={k: sorted(v) for k, v in sorted(by_inv.items())},
        action_keys_by_cover_image_id=dict(sorted((k, sorted(v)) for k, v in by_cover.items())),
        action_keys_by_series_key=dict(sorted((k, sorted(v)) for k, v in by_series.items())),
        action_keys_by_publisher=dict(sorted((k, sorted(v)) for k, v in by_pub.items())),
        action_keys_by_ownership_state=dict(sorted((k, sorted(v)) for k, v in by_own.items())),
        action_keys_by_preorder_release_state=dict(sorted((k, sorted(v)) for k, v in by_pre_rel.items())),
    )


def get_inventory_action_center_response(
    session: Session,
    *,
    current_user: User | None,
    priority: InventoryRiskPriority | None = None,
    action_category_str: str | None = None,
    ownership_state: str | None = None,
    publisher: str | None = None,
    release_status_filter: str | None = None,
    unresolved_only: bool = True,
    in_hand_only: bool = False,
    inventory_copy_id_filter: int | None = None,
) -> InventoryActionCenterListResponse:
    uid = int(current_user.id) if current_user is not None and current_user.id is not None else None
    scope = "owner" if uid is not None else "ops"
    projections = list(_inventory_projection_rows(session, user_id=uid))
    total_inventory = len(projections)

    _, risks, _risks_map = compute_inventory_risks(session, current_user=current_user)
    _, _, _, signals = compute_inventory_intelligence(session, current_user=current_user, include_signals=True)
    arrival_map = batch_order_arrival_classifications(session, user_id=uid)

    ledger = build_inventory_action_items(
        session,
        risk_rows=risks,
        signals_map=signals,
        arrival_map=arrival_map,
        user_id_scope=uid,
    )
    filt = filter_inventory_actions(
        ledger,
        priority=priority,
        action_category=action_category_str,
        ownership_state=ownership_state,
        publisher=publisher,
        release_status=release_status_filter,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id_filter,
    )
    grp = build_action_center_grouping(filt)
    summary_obj = _summary_from_filtered(
        scope_user_id=uid,
        scope=scope,
        filtered=filt,
        total_inventory_copies=total_inventory,
    )

    return InventoryActionCenterListResponse(
        scope_user_id=uid,
        scope=scope,
        generated_as_of_date=summary_obj.generated_as_of_date,
        priority=priority if priority is not None else "all",
        action_category=action_category_str if action_category_str is not None else "all",
        ownership_state=ownership_state if ownership_state is not None else "all",
        publisher=publisher,
        release_status=release_status_filter if release_status_filter is not None else "all",
        unresolved_only=unresolved_only,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id_filter,
        summary=summary_obj,
        grouping=grp,
        actions=filt,
    )