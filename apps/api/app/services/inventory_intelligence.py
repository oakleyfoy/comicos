from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    CoverImage,
    CoverImageOcrResult,
    CoverRelationshipConflict,
    InventoryCopy,
    User,
)
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    publisher_expr,
)
from app.schemas.inventory_intelligence import (
    InventoryCopyIntelligenceSignals,
    InventoryHealthCategory,
    InventoryIntelligenceBreakdown,
    InventoryIntelligenceHealthSummary,
    InventoryIntelligenceSummary,
    KeyedCount,
    OwnershipState,
)
from app.services.duplicate_scan_intelligence import (
    list_duplicate_scan_clusters_for_ops,
    list_duplicate_scan_clusters_for_owner,
    owner_cover_scope,
)
from app.services.variant_family_intelligence import (
    list_variant_family_clusters_for_ops,
    list_variant_family_clusters_for_owner,
)

_YEAR_SENTINEL = "__unknown_year__"


def normalize_ownership_state(
    *,
    release_status: str,
    order_status: str,
    received_at: object | None,
) -> OwnershipState:
    if order_status == "cancelled":
        return "cancelled"
    if order_status == "received" or received_at is not None:
        return "in_hand"
    if release_status == "not_released_yet" or order_status == "preordered":
        return "preorder"
    if order_status in ("ordered", "shipped"):
        return "ordered_not_received"
    return "unknown_state"


def preorder_missing_release_calendar(
    *,
    ownership: OwnershipState,
    release_date: object | None,
    release_year: int | None,
) -> bool:
    return ownership == "preorder" and release_date is None and release_year is None


def classify_inventory_health(
    *,
    ownership: OwnershipState,
    has_cover_scan: bool,
    preorder_miss_cal: bool,
    cover_processing_failed: bool,
    ocr_failed: bool,
    open_conflict: bool,
    pending_canonical: bool,
    dup_inventory_pending: bool,
    probable_dup_cluster: bool,
    probable_vf_cluster: bool,
    ocr_complete: bool,
) -> InventoryHealthCategory:
    if ownership == "cancelled":
        return "blocked"

    review_surface = (
        open_conflict
        or pending_canonical
        or dup_inventory_pending
        or probable_dup_cluster
        or probable_vf_cluster
        or ocr_failed
        or cover_processing_failed
    )
    incomplete_surface = (
        (not has_cover_scan)
        or preorder_miss_cal
        or (
            has_cover_scan
            and not ocr_complete
            and not ocr_failed
            and not cover_processing_failed
        )
    )
    if review_surface:
        return "needs_review"
    if incomplete_surface:
        return "incomplete"
    return "healthy"


def projection_stmt(*, user_id: int | None):
    stmt = apply_inventory_spine_joins(
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.primary_cover_image_id,
            InventoryCopy.release_status,
            InventoryCopy.order_status,
            InventoryCopy.received_at,
            InventoryCopy.release_date,
            InventoryCopy.release_year,
            InventoryCopy.grade_status,
            publisher_expr().label("publisher_name"),
        ).select_from(InventoryCopy)
    )
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    return stmt.order_by(InventoryCopy.id.asc())


def _covers_by_inventory(session: Session, inventory_ids: Sequence[int]) -> dict[int, list[CoverImage]]:
    normalized = sorted({int(i) for i in inventory_ids})
    if not normalized:
        return {}
    rows = session.exec(select(CoverImage).where(CoverImage.inventory_copy_id.in_(normalized))).all()
    bucket: defaultdict[int, list[CoverImage]] = defaultdict(list)
    for cov in rows:
        if cov.inventory_copy_id is None:
            continue
        bucket[int(cov.inventory_copy_id)].append(cov)
    for lst in bucket.values():
        lst.sort(key=lambda c: int(c.id or 0))
    return dict(bucket)


def _cover_to_inventory_mapping(covers_by_inventory: Mapping[int, list[CoverImage]]) -> dict[int, int]:
    out: dict[int, int] = {}
    for inv_id, items in covers_by_inventory.items():
        for c in items:
            if c.id is not None:
                out[int(c.id)] = int(inv_id)
    return out


def _pick_primary_cover(primary_cover_id: int | None, covers: list[CoverImage]) -> CoverImage | None:
    if not covers:
        return None
    if primary_cover_id is not None:
        for c in covers:
            if int(c.id or -1) == int(primary_cover_id):
                return c
    return covers[0]


def _latest_ocr_map(session: Session, cover_ids: Sequence[int]) -> dict[int, CoverImageOcrResult | None]:
    ids_list = sorted({int(i) for i in cover_ids})
    if not ids_list:
        return {}
    rows = session.exec(select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id.in_(ids_list))).all()
    buckets: defaultdict[int, list[CoverImageOcrResult]] = defaultdict(list)
    for row in rows:
        buckets[int(row.cover_image_id)].append(row)
    latest: dict[int, CoverImageOcrResult | None] = {}
    for cid in ids_list:
        cand = buckets.get(cid, [])
        if not cand:
            latest[cid] = None
            continue
        cand.sort(key=lambda o: (o.processed_at or o.created_at, int(o.id or 0)), reverse=True)
        latest[cid] = cand[0]
    return latest


def duplicate_inventory_pending_touching_inventory_ids(session: Session, *, owner_user_id: int) -> set[int]:
    from app.services.inventory import find_duplicate_inventory_candidates

    out: set[int] = set()
    for group in find_duplicate_inventory_candidates(session, review_status="pending"):
        if any(copy_row.user_id == owner_user_id for copy_row in group.copies):
            for copy_row in group.copies:
                out.add(int(copy_row.inventory_copy_id))
    return out


def duplicate_inventory_pending_inventory_ids_for_scope(
    session: Session,
    *,
    owner_user_id: int,
    inventory_ids: set[int],
) -> set[int]:
    """Pending duplicate-review inventory ids within a bounded id set (detail / page scope)."""
    if not inventory_ids:
        return set()
    scoped_ids = sorted({int(i) for i in inventory_ids})
    rows = session.exec(
        select(InventoryCopy.id, InventoryCopy.metadata_identity_key).where(
            InventoryCopy.id.in_(scoped_ids),
            InventoryCopy.user_id == owner_user_id,
            InventoryCopy.metadata_identity_key.is_not(None),
            InventoryCopy.metadata_identity_key != "",
        ),
    ).all()
    if not rows:
        return set()
    keys = {str(row.metadata_identity_key) for row in rows if row.metadata_identity_key}
    if not keys:
        return set()
    dup_keys = session.exec(
        select(InventoryCopy.metadata_identity_key)
        .where(
            InventoryCopy.user_id == owner_user_id,
            InventoryCopy.metadata_identity_key.in_(list(keys)),
        )
        .group_by(InventoryCopy.metadata_identity_key)
        .having(func.count(InventoryCopy.id) >= 2),
    ).all()
    dup_key_set = {str(k) for k in dup_keys if k}
    if not dup_key_set:
        return set()
    from app.services.duplicate_candidate_reviews import load_reviews_for_keys

    reviews_map = load_reviews_for_keys(session, list(dup_key_set))
    pending_keys = {
        key
        for key in dup_key_set
        if reviews_map.get(key) is None or reviews_map.get(key).review_status == "pending"
    }
    if not pending_keys:
        return set()
    return {
        int(row.id)
        for row in rows
        if row.metadata_identity_key is not None and str(row.metadata_identity_key) in pending_keys
    }


def duplicate_inventory_pending_inventory_ids_ops(session: Session) -> set[int]:
    from app.services.inventory import find_duplicate_inventory_candidates

    touches: set[int] = set()
    for group in find_duplicate_inventory_candidates(session, review_status="pending"):
        for copy_row in group.copies:
            touches.add(int(copy_row.inventory_copy_id))
    return touches


def duplicate_inventory_pending_group_count(session: Session) -> int:
    from app.services.inventory import find_duplicate_inventory_candidates

    return len(find_duplicate_inventory_candidates(session, review_status="pending"))


def owner_pending_duplicate_inventory_group_count(session: Session, *, user_id: int) -> int:
    from app.services.inventory import find_duplicate_inventory_candidates

    counted = 0
    for group in find_duplicate_inventory_candidates(session, review_status="pending"):
        if any(copy_row.user_id == user_id for copy_row in group.copies):
            counted += 1
    return counted


def pending_canonical_inventory_ids(session: Session, *, inventory_ids: set[int]) -> set[int]:
    targets: set[int] = set()
    if not inventory_ids:
        return targets
    covers = session.exec(
        select(CoverImage.id, CoverImage.inventory_copy_id).where(
            CoverImage.inventory_copy_id.in_(sorted(inventory_ids)),
        ),
    ).all()
    cid_to_inv = {int(cid): int(inv) for cid, inv in covers if cid is not None and inv is not None}

    sug_rows = session.exec(
        select(CanonicalIssueLinkSuggestion).where(CanonicalIssueLinkSuggestion.review_state == "pending"),
    ).all()

    for sug in sug_rows:
        if sug.inventory_copy_id is not None and int(sug.inventory_copy_id) in inventory_ids:
            targets.add(int(sug.inventory_copy_id))

        if sug.cover_image_id is None:
            continue
        mapped = cid_to_inv.get(int(sug.cover_image_id))

        if mapped is not None and mapped in inventory_ids:
            targets.add(mapped)

    return targets


def count_owner_pending_canonical_rows(session: Session, *, inventory_ids: set[int]) -> int:
    if not inventory_ids:
        return 0
    covers = session.exec(
        select(CoverImage.id, CoverImage.inventory_copy_id).where(
            CoverImage.inventory_copy_id.in_(sorted(inventory_ids)),
        ),
    ).all()
    cid_to_inv = {int(cid): int(inv) for cid, inv in covers if cid is not None and inv is not None}
    sug_rows = session.exec(
        select(CanonicalIssueLinkSuggestion).where(CanonicalIssueLinkSuggestion.review_state == "pending"),
    ).all()
    counted: set[int] = set()
    for sug in sug_rows:
        if sug.id is None:
            continue
        touches = sug.inventory_copy_id is not None and int(sug.inventory_copy_id) in inventory_ids
        if not touches and sug.cover_image_id is not None:
            mapped = cid_to_inv.get(int(sug.cover_image_id))
            touches = mapped is not None and mapped in inventory_ids
        if touches:
            counted.add(int(sug.id))
    return len(counted)


def count_global_pending_canonical_rows(session: Session) -> int:
    stmt = select(func.count()).select_from(CanonicalIssueLinkSuggestion).where(
        CanonicalIssueLinkSuggestion.review_state == "pending",
    )
    return int(session.exec(stmt).one())


def inventory_ids_touching_cover_set(covers_map: Mapping[int, list[CoverImage]], touched: set[int]) -> set[int]:
    hits: set[int] = set()
    if not touched:
        return hits
    for inv_id, items in covers_map.items():
        for c in items:
            if c.id is not None and int(c.id) in touched:
                hits.add(int(inv_id))
                break

    return hits


def probable_cluster_cover_hits_owner(session: Session, *, user: User) -> tuple[int, set[int], int, set[int]]:
    dup = list_duplicate_scan_clusters_for_owner(session, current_user=user, classification_filter="probable")
    vf = list_variant_family_clusters_for_owner(session, current_user=user, classification_filter="probable")

    scope = owner_cover_scope(session, user_id=int(user.id))

    dup_hits: set[int] = set()
    dup_touch = 0
    for cluster in dup.clusters:
        intr = scope.intersection(set(cluster.cover_image_ids))
        if intr:
            dup_touch += 1
            dup_hits.update(intr)

    vf_hits: set[int] = set()
    vf_touch = 0
    for cluster in vf.clusters:
        intr = scope.intersection(set(cluster.cover_image_ids))
        if intr:
            vf_touch += 1
            vf_hits.update(intr)

    return dup_touch, dup_hits, vf_touch, vf_hits


def map_cover_inventory_global(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(CoverImage.id, CoverImage.inventory_copy_id).where(
            CoverImage.inventory_copy_id.is_not(None),
        ),
    ).all()
    return {int(cid): int(inv) for cid, inv in rows if cid is not None and inv is not None}


def count_distinct_open_conflicts_for_inventory_scope(
    *,
    inventory_ids: set[int],
    cid_to_inventory: Mapping[int, int],
    conflicts: Sequence[CoverRelationshipConflict],
) -> int:
    seen: set[int] = set()
    if not inventory_ids or not conflicts:
        return 0

    for row in conflicts:
        rid = getattr(row, "id", None)
        if rid is None:
            continue
        for cid in (row.source_cover_image_id, row.related_cover_image_id):
            if cid is None:
                continue
            cci = int(cid)
            mapped = cid_to_inventory.get(cci)
            if mapped is not None and int(mapped) in inventory_ids:
                seen.add(int(rid))
                break
    return len(seen)


def inventory_copy_ids_under_open_conflict(
    conflicts: Sequence[CoverRelationshipConflict],
    *,
    inventory_ids: set[int],
    cid_to_inventory: Mapping[int, int],
) -> set[int]:
    hits: set[int] = set()
    if not inventory_ids or not conflicts:
        return hits
    for row in conflicts:
        for cid in (row.source_cover_image_id, row.related_cover_image_id):
            if cid is None:
                continue
            inv = cid_to_inventory.get(int(cid))
            if inv is not None and inv in inventory_ids:
                hits.add(int(inv))
                break
    return hits


def _sorted_key_counts(counts: dict[str | None, int]) -> list[KeyedCount]:
    ordered = sorted(
        counts.keys(),
        key=lambda k: (1, "") if k is None else (0, str(k)),
    )
    return [KeyedCount(key=k, count=counts[k]) for k in ordered]


def _year_bucket_str(*, release_year: int | None) -> str:
    if release_year is None:
        return _YEAR_SENTINEL
    return str(int(release_year))


def _incr_bucket(dest: dict[str | None, int], key: str | None, weight: int = 1) -> None:
    dest[key] = dest.get(key, 0) + weight


def compute_inventory_intelligence(
    session: Session,
    *,
    current_user: User | None,
    include_signals: bool = True,
) -> tuple[
    InventoryIntelligenceSummary,
    InventoryIntelligenceHealthSummary,
    InventoryIntelligenceBreakdown,
    dict[int, InventoryCopyIntelligenceSignals],
]:
    """Read-only rollup for one owner (`current_user` set) or global ops (`current_user=None`)."""

    user_id_val: int | None = None
    owner_user_obj: User | None = None
    if current_user is not None and current_user.id is not None:
        user_id_val = int(current_user.id)
        owner_user_obj = current_user

    projections = session.exec(projection_stmt(user_id=user_id_val)).all()
    inventory_ids_ordered: list[int] = [int(r.inventory_copy_id) for r in projections]
    inventory_id_set = set(inventory_ids_ordered)

    summary = InventoryIntelligenceSummary()
    health = InventoryIntelligenceHealthSummary()

    covers_map = _covers_by_inventory(session, inventory_ids_ordered)
    cid_to_inventory_owner = _cover_to_inventory_mapping(covers_map)

    open_conflict_rows = session.exec(
        select(CoverRelationshipConflict).where(CoverRelationshipConflict.status == "open"),
    ).all()

    cid_for_conflict = map_cover_inventory_global(session) if owner_user_obj is None else cid_to_inventory_owner
    unresolved_conflict_ct = count_distinct_open_conflicts_for_inventory_scope(
        inventory_ids=inventory_id_set,
        cid_to_inventory=cid_for_conflict,
        conflicts=open_conflict_rows,
    )
    inventory_open_conflict_touch = inventory_copy_ids_under_open_conflict(
        open_conflict_rows,
        inventory_ids=inventory_id_set,
        cid_to_inventory=cid_for_conflict,
    )

    pending_canonical_inv = pending_canonical_inventory_ids(session, inventory_ids=inventory_id_set)

    if owner_user_obj is None:
        dup_pending_inv_touch = duplicate_inventory_pending_inventory_ids_ops(session)
        unresolved_dup_inventory_groups_ct = duplicate_inventory_pending_group_count(session)
        unresolved_canonical_rows_ct = count_global_pending_canonical_rows(session)

        dup_ops = list_duplicate_scan_clusters_for_ops(session, classification_filter="probable")
        vf_ops = list_variant_family_clusters_for_ops(session, classification_filter="probable")
        dup_cover_union: set[int] = set()
        for cls in dup_ops.clusters:
            dup_cover_union.update(int(x) for x in cls.cover_image_ids)
        vf_cover_union: set[int] = set()
        for cls in vf_ops.clusters:
            vf_cover_union.update(int(x) for x in cls.cover_image_ids)
        unresolved_duplicate_scan_clusters = len(dup_ops.clusters)
        unresolved_variant_family_clusters = len(vf_ops.clusters)
        dup_scan_inv_touch = inventory_ids_touching_cover_set(covers_map, dup_cover_union)
        vf_scan_inv_touch = inventory_ids_touching_cover_set(covers_map, vf_cover_union)
    else:
        assert user_id_val is not None
        dup_pending_inv_touch = duplicate_inventory_pending_touching_inventory_ids(
            session, owner_user_id=user_id_val,
        )
        unresolved_dup_inventory_groups_ct = owner_pending_duplicate_inventory_group_count(
            session, user_id=user_id_val,
        )
        unresolved_canonical_rows_ct = count_owner_pending_canonical_rows(session, inventory_ids=inventory_id_set)

        _dup_clusters, dup_hits_cover, _vf_clusters, vf_hits_cover = probable_cluster_cover_hits_owner(
            session,
            user=owner_user_obj,
        )
        unresolved_duplicate_scan_clusters = _dup_clusters
        unresolved_variant_family_clusters = _vf_clusters
        dup_scan_inv_touch = inventory_ids_touching_cover_set(covers_map, dup_hits_cover)
        vf_scan_inv_touch = inventory_ids_touching_cover_set(covers_map, vf_hits_cover)

    by_pub: defaultdict[str | None, int] = defaultdict(int)
    by_year: defaultdict[str | None, int] = defaultdict(int)
    by_release: defaultdict[str | None, int] = defaultdict(int)
    by_order: defaultdict[str | None, int] = defaultdict(int)
    by_grade: defaultdict[str | None, int] = defaultdict(int)
    by_ownership: defaultdict[str | None, int] = defaultdict(int)
    unhealthy_sample_ids: list[int] = []

    primary_cover_ids_for_ocr: set[int] = set()
    for row in projections:
        inv_id_prim = int(row.inventory_copy_id)
        covers_prim = covers_map.get(inv_id_prim, [])
        pcov = _pick_primary_cover(row.primary_cover_image_id, covers_prim)
        if pcov and pcov.id is not None:
            primary_cover_ids_for_ocr.add(int(pcov.id))

    latest_ocr = _latest_ocr_map(session, sorted(primary_cover_ids_for_ocr))
    signals: dict[int, InventoryCopyIntelligenceSignals] = {}

    for row in projections:
        inv_id = int(row.inventory_copy_id)
        covers = covers_map.get(inv_id, [])
        primary_cov = _pick_primary_cover(row.primary_cover_image_id, covers)
        has_cover_scan = len(covers) > 0

        ownership = normalize_ownership_state(
            release_status=str(row.release_status),
            order_status=str(row.order_status),
            received_at=row.received_at,
        )
        preorder_miss = preorder_missing_release_calendar(
            ownership=ownership,
            release_date=row.release_date,
            release_year=row.release_year,
        )

        primary_id = int(primary_cov.id) if primary_cov and primary_cov.id is not None else None
        ocr_row = latest_ocr.get(primary_id) if primary_id is not None else None
        cover_processing_failed = primary_cov is not None and getattr(primary_cov, "processing_status", "") == "failed"
        ocr_failed = (
            primary_id is not None
            and ocr_row is not None
            and getattr(ocr_row, "processing_status", "") == "failed"
        )
        ocr_complete = (
            primary_id is not None
            and not cover_processing_failed
            and ocr_row is not None
            and getattr(ocr_row, "processing_status", "") == "processed"
        )

        pending_canonical = inv_id in pending_canonical_inv
        dup_inventory_pending_flag = inv_id in dup_pending_inv_touch
        open_conflict = inv_id in inventory_open_conflict_touch
        probable_dup_cluster_flag = inv_id in dup_scan_inv_touch
        probable_vf_cluster_flag = inv_id in vf_scan_inv_touch

        inv_health = classify_inventory_health(
            ownership=ownership,
            has_cover_scan=has_cover_scan,
            preorder_miss_cal=preorder_miss,
            cover_processing_failed=cover_processing_failed,
            ocr_failed=ocr_failed,
            open_conflict=open_conflict,
            pending_canonical=pending_canonical,
            dup_inventory_pending=dup_inventory_pending_flag,
            probable_dup_cluster=probable_dup_cluster_flag,
            probable_vf_cluster=probable_vf_cluster_flag,
            ocr_complete=ocr_complete,
        )

        summary.total_inventory_copies += 1

        if ownership == "in_hand":
            summary.ownership_in_hand += 1
        elif ownership == "preorder":
            summary.ownership_preorder += 1
        elif ownership == "ordered_not_received":
            summary.ownership_ordered_not_received += 1
        elif ownership == "cancelled":
            summary.ownership_cancelled += 1
        else:
            summary.ownership_unknown_state += 1

        if str(row.grade_status) != "raw":
            summary.graded_copies += 1
        else:
            summary.raw_copies += 1

        if has_cover_scan:
            summary.scanned_copies += 1
        else:
            summary.unscanned_copies += 1

        if has_cover_scan and primary_id is not None and not cover_processing_failed:
            if ocr_complete:
                summary.ocr_complete_copies += 1
            elif not ocr_failed:
                summary.ocr_pending_copies += 1

        if cover_processing_failed:
            summary.cover_processing_failed_copies += 1
        if ocr_failed:
            summary.ocr_failed_copies += 1

        if inv_health == "healthy":
            health.healthy += 1
        elif inv_health == "needs_review":
            health.needs_review += 1
        elif inv_health == "incomplete":
            health.incomplete += 1
        else:
            health.blocked += 1

        if inv_health != "healthy" and len(unhealthy_sample_ids) < 50:
            unhealthy_sample_ids.append(inv_id)

        publisher_key = getattr(row, "publisher_name", None)
        _incr_bucket(by_pub, None if publisher_key is None else str(publisher_key))
        _incr_bucket(by_year, _year_bucket_str(release_year=row.release_year))
        _incr_bucket(by_release, str(row.release_status))
        _incr_bucket(by_order, str(row.order_status))
        _incr_bucket(by_grade, str(row.grade_status))
        _incr_bucket(by_ownership, str(ownership))

        if include_signals:
            signals[inv_id] = InventoryCopyIntelligenceSignals(
                ownership_state=ownership,
                inventory_health=inv_health,
                has_cover_scan=has_cover_scan,
                preorder_missing_release_calendar=preorder_miss,
                has_open_relationship_conflict=open_conflict,
                has_pending_canonical_suggestion=pending_canonical,
                in_pending_duplicate_inventory_group=dup_inventory_pending_flag,
                touches_probable_duplicate_scan_cluster=probable_dup_cluster_flag,
                touches_probable_variant_family_cluster=probable_vf_cluster_flag,
            )

    summary.unresolved_relationship_conflicts = unresolved_conflict_ct
    summary.unresolved_canonical_suggestions = unresolved_canonical_rows_ct
    summary.unresolved_duplicate_inventory_groups = unresolved_dup_inventory_groups_ct
    summary.unresolved_duplicate_scan_clusters = unresolved_duplicate_scan_clusters
    summary.unresolved_variant_family_clusters = unresolved_variant_family_clusters

    breakdown = InventoryIntelligenceBreakdown(
        by_publisher=_sorted_key_counts(dict(by_pub)),
        by_year=_sorted_key_counts(dict(by_year)),
        by_release_status=_sorted_key_counts(dict(by_release)),
        by_order_status=_sorted_key_counts(dict(by_order)),
        by_grade_status=_sorted_key_counts(dict(by_grade)),
        by_ownership_state=_sorted_key_counts(dict(by_ownership)),
        unhealthy_sample_inventory_copy_ids=unhealthy_sample_ids,
    )

    return summary, health, breakdown, signals


def inventory_intelligence_signals_for_ids(
    session: Session,
    current_user: User,
    inventory_copy_ids: Sequence[int],
    *,
    lightweight: bool = False,
) -> dict[int, InventoryCopyIntelligenceSignals]:
    """Build per-copy intelligence signals for a subset of rows (detail / targeted reads)."""
    ids = sorted({int(i) for i in inventory_copy_ids})
    if not ids:
        return {}
    if current_user.id is None:
        return {}

    user_id = int(current_user.id)
    inventory_id_set = set(ids)
    projections = session.exec(
        projection_stmt(user_id=user_id).where(InventoryCopy.id.in_(ids)),
    ).all()
    if not projections:
        return {}

    covers_map = _covers_by_inventory(session, ids)
    cid_to_inventory = _cover_to_inventory_mapping(covers_map)

    open_conflict_rows = session.exec(
        select(CoverRelationshipConflict).where(CoverRelationshipConflict.status == "open"),
    ).all()
    inventory_open_conflict_touch = inventory_copy_ids_under_open_conflict(
        open_conflict_rows,
        inventory_ids=inventory_id_set,
        cid_to_inventory=cid_to_inventory,
    )

    pending_canonical_inv = pending_canonical_inventory_ids(session, inventory_ids=inventory_id_set)
    if lightweight:
        dup_pending_inv_touch = duplicate_inventory_pending_inventory_ids_for_scope(
            session,
            owner_user_id=user_id,
            inventory_ids=inventory_id_set,
        )
        dup_scan_inv_touch: set[int] = set()
        vf_scan_inv_touch: set[int] = set()
    else:
        dup_pending_inv_touch = duplicate_inventory_pending_touching_inventory_ids(
            session,
            owner_user_id=user_id,
        )
        _dup_clusters, dup_hits_cover, _vf_clusters, vf_hits_cover = probable_cluster_cover_hits_owner(
            session,
            user=current_user,
        )
        dup_scan_inv_touch = inventory_ids_touching_cover_set(covers_map, dup_hits_cover)
        vf_scan_inv_touch = inventory_ids_touching_cover_set(covers_map, vf_hits_cover)

    primary_cover_ids_for_ocr: set[int] = set()
    for row in projections:
        inv_id_prim = int(row.inventory_copy_id)
        covers_prim = covers_map.get(inv_id_prim, [])
        pcov = _pick_primary_cover(row.primary_cover_image_id, covers_prim)
        if pcov and pcov.id is not None:
            primary_cover_ids_for_ocr.add(int(pcov.id))

    latest_ocr = _latest_ocr_map(session, sorted(primary_cover_ids_for_ocr))
    signals: dict[int, InventoryCopyIntelligenceSignals] = {}

    for row in projections:
        inv_id = int(row.inventory_copy_id)
        covers = covers_map.get(inv_id, [])
        primary_cov = _pick_primary_cover(row.primary_cover_image_id, covers)
        has_cover_scan = len(covers) > 0

        ownership = normalize_ownership_state(
            release_status=str(row.release_status),
            order_status=str(row.order_status),
            received_at=row.received_at,
        )
        preorder_miss = preorder_missing_release_calendar(
            ownership=ownership,
            release_date=row.release_date,
            release_year=row.release_year,
        )

        primary_id = int(primary_cov.id) if primary_cov and primary_cov.id is not None else None
        ocr_row = latest_ocr.get(primary_id) if primary_id is not None else None
        cover_processing_failed = primary_cov is not None and getattr(primary_cov, "processing_status", "") == "failed"
        ocr_failed = (
            primary_id is not None
            and ocr_row is not None
            and getattr(ocr_row, "processing_status", "") == "failed"
        )
        ocr_complete = (
            primary_id is not None
            and not cover_processing_failed
            and ocr_row is not None
            and getattr(ocr_row, "processing_status", "") == "processed"
        )

        pending_canonical = inv_id in pending_canonical_inv
        dup_inventory_pending_flag = inv_id in dup_pending_inv_touch
        open_conflict = inv_id in inventory_open_conflict_touch
        probable_dup_cluster_flag = inv_id in dup_scan_inv_touch
        probable_vf_cluster_flag = inv_id in vf_scan_inv_touch

        inv_health = classify_inventory_health(
            ownership=ownership,
            has_cover_scan=has_cover_scan,
            preorder_miss_cal=preorder_miss,
            cover_processing_failed=cover_processing_failed,
            ocr_failed=ocr_failed,
            open_conflict=open_conflict,
            pending_canonical=pending_canonical,
            dup_inventory_pending=dup_inventory_pending_flag,
            probable_dup_cluster=probable_dup_cluster_flag,
            probable_vf_cluster=probable_vf_cluster_flag,
            ocr_complete=ocr_complete,
        )

        signals[inv_id] = InventoryCopyIntelligenceSignals(
            ownership_state=ownership,
            inventory_health=inv_health,
            has_cover_scan=has_cover_scan,
            preorder_missing_release_calendar=preorder_miss,
            has_open_relationship_conflict=open_conflict,
            has_pending_canonical_suggestion=pending_canonical,
            in_pending_duplicate_inventory_group=dup_inventory_pending_flag,
            touches_probable_duplicate_scan_cluster=probable_dup_cluster_flag,
            touches_probable_variant_family_cluster=probable_vf_cluster_flag,
        )

    return signals
