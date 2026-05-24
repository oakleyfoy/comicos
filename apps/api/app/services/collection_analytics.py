"""Deterministic collection analytics — read-only portfolio rollups."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

from sqlmodel import Session, select

from app.models import ComicIssue, ComicTitle, InventoryCopy, Order, OrderItem, Publisher, User, Variant
from app.schemas.collection_analytics import (
    CollectionAnalyticsSummary,
    CollectionCompositionAnalytics,
    CollectionCompositionResponse,
    CollectionPublisherAnalyticsResponse,
    CollectionQualityAnalyticsResponse,
    CollectionTimelineAnalytics,
    CollectionTimelineResponse,
    CompositionSeriesSignals,
    InventoryQualityAnalytics,
    PercentRollup,
    PublisherAnalyticsRow,
    PublisherConcentration,
    PreorderPipelineBucket,
    TimelineYearBucket,
    UpcomingPreorderBucket,
)
from app.schemas.inventory_intelligence import InventoryIntelligenceSummary, KeyedCount
from app.services.duplicate_ownership_intelligence import (
    duplicate_ownership_inventory_attach_map,
    duplicate_ownership_inventory_context_for_owner,
    list_duplicate_ownership_ops as list_duplicate_ownership_global,
)
from app.services.inventory_intelligence import (
    _covers_by_inventory,
    _latest_ocr_map,
    _pick_primary_cover,
    compute_inventory_intelligence,
    preorder_missing_release_calendar,
)
from app.services.run_detection import list_run_detection_ops, list_run_detection_owner


_YEAR_UNKNOWN = "__unknown_year__"


def utc_today_deterministic() -> date:
    return datetime.now(timezone.utc).date()


def pct_value(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((10000 * numerator) / denominator) / 100


def percent_roll(numerator: int, denominator: int) -> PercentRollup:
    return PercentRollup(
        numerator=numerator,
        denominator=denominator,
        percent=pct_value(numerator, denominator),
    )


def collection_projection_stmt(*, user_id: int | None):
    stmt = (
        select(
            InventoryCopy.id.label("inventory_copy_id"),
            InventoryCopy.primary_cover_image_id,
            InventoryCopy.release_status,
            InventoryCopy.order_status,
            InventoryCopy.received_at,
            InventoryCopy.release_date,
            InventoryCopy.release_year,
            InventoryCopy.canonical_series_id,
            InventoryCopy.grade_status,
            Order.order_date.label("order_date"),
            ComicIssue.release_date.label("issue_release_date"),
            Publisher.name.label("publisher_name"),
        )
        .select_from(InventoryCopy)
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
    )
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    return stmt.order_by(InventoryCopy.id.asc())


def duplicate_touch_inventory_ids(session: Session, *, owner_scope_user_id: int | None) -> set[int]:
    if owner_scope_user_id is None:
        bundled = list_duplicate_ownership_global(
            session,
            dup_scan_classification="all",
            classification=None,
        )
        return set(duplicate_ownership_inventory_attach_map(bundled.groups).keys())

    phantom_user = User(id=int(owner_scope_user_id))
    grouped, _ = duplicate_ownership_inventory_context_for_owner(
        session,
        user=phantom_user,
        dup_scan_classification="all",
    )
    return set(duplicate_ownership_inventory_attach_map(grouped).keys())


def purchase_year_bucket(order_date: Any) -> str:
    if order_date is None:
        return _YEAR_UNKNOWN
    if isinstance(order_date, datetime):
        return str(order_date.year)
    yr = getattr(order_date, "year", None)
    return str(int(yr)) if yr is not None else _YEAR_UNKNOWN


def release_year_bucket(proj: Any) -> str:
    ry = getattr(proj, "release_year", None)
    if ry is not None:
        return str(int(ry))
    for candidate in (getattr(proj, "release_date", None), getattr(proj, "issue_release_date", None)):
        if candidate is None:
            continue
        if isinstance(candidate, datetime):
            return str(candidate.year)
        yr = getattr(candidate, "year", None)
        if yr is not None:
            return str(int(yr))
    return _YEAR_UNKNOWN


def received_year_bucket(proj: Any, ownership: str) -> str:
    if ownership != "in_hand":
        return "__not_in_hand__"
    recv = getattr(proj, "received_at", None)
    if recv is None:
        return "__in_hand_unknown_received_ts__"
    if isinstance(recv, datetime):
        return str(recv.year)
    yr = getattr(recv, "year", None)
    return str(int(yr)) if yr is not None else "__in_hand_unknown_received_ts__"


def preorder_pipeline_bucket(proj: Any) -> str:
    ry = getattr(proj, "release_year", None)
    if ry is not None:
        return f"release_year:{int(ry)}"
    for cand in (getattr(proj, "release_date", None), getattr(proj, "issue_release_date", None)):
        if cand is None:
            continue
        if isinstance(cand, datetime):
            return cand.date().isoformat()
        iso_fn = getattr(cand, "isoformat", None)
        if callable(iso_fn):
            return str(iso_fn())
        return str(cand)
    return "__unknown_calendar__"


def coerce_calendar_reference_date(proj: Any) -> date | None:
    for cand in (getattr(proj, "release_date", None), getattr(proj, "issue_release_date", None)):
        if cand is None:
            continue
        if isinstance(cand, datetime):
            return cand.date()
        if isinstance(cand, date):
            return cand
    ry = getattr(proj, "release_year", None)
    if ry is None:
        return None
    try:
        return date(int(ry), 12, 31)
    except Exception:
        return None


def upcoming_preorder_calendar_buckets(
    projections: Sequence[Any],
    signals_map: Mapping[int, Any],
    *,
    as_of_date: date,
) -> list[UpcomingPreorderBucket]:
    counts: defaultdict[str, int] = defaultdict(int)
    for row in projections:
        rid = int(getattr(row, "inventory_copy_id"))
        sig = signals_map.get(rid)
        if sig is None or getattr(sig, "ownership_state", None) != "preorder":
            continue
        anchor = coerce_calendar_reference_date(row)
        if anchor is None or anchor < as_of_date:
            continue
        counts[f"{anchor.year:04d}-{anchor.month:02d}"] += 1
    ordering = sorted(counts.keys())
    return [UpcomingPreorderBucket(preorder_copies=counts[b], first_release_bucket=b) for b in ordering]


def year_bucket_sort_key(bucket: str) -> tuple[int, str]:
    if bucket == _YEAR_UNKNOWN:
        return (2, bucket)
    try:
        return (0, f"{int(bucket):010d}")
    except ValueError:
        return (1, bucket)


def finalize_year_buckets(raw: defaultdict[str | None, int]) -> list[TimelineYearBucket]:
    unknown_total = raw.get(None, 0) + raw.get(_YEAR_UNKNOWN, 0)
    keys_sorted = sorted(
        (str(k) for k in raw if k not in (None, _YEAR_UNKNOWN)),
        key=lambda b: year_bucket_sort_key(b),
    )
    buckets = [TimelineYearBucket(year_key=k, copies=int(raw[k])) for k in keys_sorted]
    if unknown_total:
        buckets.append(TimelineYearBucket(year_key=_YEAR_UNKNOWN, copies=int(unknown_total)))
    return buckets


def _sorted_key_counts(counts: dict[str | None, int]) -> list[KeyedCount]:
    ordered = sorted(counts.keys(), key=lambda k: (1, "") if k is None else (0, str(k)))
    return [KeyedCount(key=k, count=counts[k]) for k in ordered]


def publisher_concentration_active(pub_counts: dict[str, int]) -> PublisherConcentration:
    denom = sum(pub_counts.values())
    if denom <= 0:
        return PublisherConcentration(top_publisher_share=percent_roll(0, 0), publishers_represented=0)
    winners = sorted(((p, pub_counts[p]) for p in sorted(pub_counts.keys())), key=lambda kv: (-kv[1], kv[0]))
    top_ct = winners[0][1]
    return PublisherConcentration(
        publishers_represented=len({p for p, c in pub_counts.items() if c > 0}),
        top_publisher_share=percent_roll(top_ct, denom),
    )


def analyze_collection_summary(
    session: Session,
    *,
    projection_user_filter: int | None,
    intel_user: User | None,
    as_of_date: date | None = None,
) -> tuple[CollectionAnalyticsSummary, InventoryIntelligenceSummary]:
    as_of = as_of_date or utc_today_deterministic()
    scope_tag = "ops_global" if projection_user_filter is None else "owner"
    intel_summary, _h, _b, signals_full = compute_inventory_intelligence(
        session, current_user=intel_user, include_signals=True
    )
    projections = list(session.exec(collection_projection_stmt(user_id=projection_user_filter)).all())

    preorder_cal_gap = 0
    unresolved_review = 0
    canonical_linked = 0
    released_counts: defaultdict[str | None, int] = defaultdict(int)
    order_counts: defaultdict[str | None, int] = defaultdict(int)
    ownership_counts: defaultdict[str | None, int] = defaultdict(int)

    for proj in projections:
        rid = int(getattr(proj, "inventory_copy_id"))
        sig = signals_full.get(rid)
        rs = getattr(proj, "release_status", None)
        os_stat = getattr(proj, "order_status", None)
        ow = getattr(sig, "ownership_state", "unknown_state") if sig else "unknown_state"
        released_counts[str(rs) if rs is not None else None] += 1
        order_counts[str(os_stat) if os_stat is not None else None] += 1
        ownership_counts[str(ow)] += 1

        if sig is None:
            continue
        if sig.inventory_health == "needs_review":
            unresolved_review += 1
        if preorder_missing_release_calendar(
            ownership=sig.ownership_state,
            release_date=getattr(proj, "release_date", None),
            release_year=getattr(proj, "release_year", None),
        ):
            preorder_cal_gap += 1
        if getattr(proj, "canonical_series_id", None) is not None:
            canonical_linked += 1

    summary_payload = CollectionAnalyticsSummary(
        scope_user_id=int(projection_user_filter) if projection_user_filter is not None else None,
        scope=scope_tag,
        generated_as_of_date=as_of,
        total_copies=intel_summary.total_inventory_copies,
        preorder_copies=intel_summary.ownership_preorder,
        in_hand_copies=intel_summary.ownership_in_hand,
        preorder_missing_calendar_copies=preorder_cal_gap,
        unscanned_primary_copies=intel_summary.unscanned_copies,
        unresolved_review_copies=unresolved_review,
        graded_copies=intel_summary.graded_copies,
        raw_copies=intel_summary.raw_copies,
        released_status_breakdown=_sorted_key_counts(dict(released_counts)),
        order_status_breakdown=_sorted_key_counts(dict(order_counts)),
        ownership_breakdown=_sorted_key_counts(dict(ownership_counts)),
        canonical_linked_copies=canonical_linked,
    )

    return summary_payload, intel_summary


def analyze_collection_publishers(
    session: Session,
    *,
    projection_user_filter: int | None,
    intel_user: User | None,
    as_of_date: date | None = None,
) -> CollectionPublisherAnalyticsResponse:
    as_of = as_of_date or utc_today_deterministic()
    scope_tag = "ops_global" if projection_user_filter is None else "owner"
    _, _, _, signals_full = compute_inventory_intelligence(session, current_user=intel_user, include_signals=True)
    projections = list(session.exec(collection_projection_stmt(user_id=projection_user_filter)).all())

    totals: defaultdict[str, int] = defaultdict(int)
    in_hand: defaultdict[str, int] = defaultdict(int)
    preorder: defaultdict[str, int] = defaultdict(int)
    reviews: defaultdict[str, int] = defaultdict(int)
    canon: defaultdict[str, int] = defaultdict(int)

    for row in projections:
        pname = str(getattr(row, "publisher_name"))
        rid = int(getattr(row, "inventory_copy_id"))
        sig = signals_full.get(rid)
        if sig is None:
            raise RuntimeError("collection analytics requires intelligence signals for every projected inventory row")
        totals[pname] += 1
        if sig.ownership_state == "in_hand":
            in_hand[pname] += 1
        elif sig.ownership_state == "preorder":
            preorder[pname] += 1
        if sig.inventory_health == "needs_review":
            reviews[pname] += 1
        if getattr(row, "canonical_series_id", None) is not None:
            canon[pname] += 1

    pubs = [
        PublisherAnalyticsRow(
            publisher_name=name,
            total_copies=int(totals[name]),
            in_hand_copies=int(in_hand[name]),
            preorder_copies=int(preorder[name]),
            unresolved_review_copies=int(reviews[name]),
            canonical_linked_copies=int(canon[name]),
        )
        for name in sorted(totals.keys())
    ]

    return CollectionPublisherAnalyticsResponse(
        scope_user_id=int(projection_user_filter) if projection_user_filter is not None else None,
        scope=scope_tag,
        generated_as_of_date=as_of,
        publishers=pubs,
    )


def analyze_collection_timeline(
    session: Session,
    *,
    projection_user_filter: int | None,
    intel_user: User | None,
    as_of_date: date | None = None,
) -> CollectionTimelineResponse:
    as_of = as_of_date or utc_today_deterministic()
    scope_tag = "ops_global" if projection_user_filter is None else "owner"
    projections = list(session.exec(collection_projection_stmt(user_id=projection_user_filter)).all())
    _, _, _, signals_full = compute_inventory_intelligence(session, current_user=intel_user, include_signals=True)

    purchase_counts: defaultdict[str | None, int] = defaultdict(int)
    release_counts: defaultdict[str | None, int] = defaultdict(int)
    recv_counts: defaultdict[str | None, int] = defaultdict(int)
    preorder_pipe: defaultdict[str | None, int] = defaultdict(int)

    for proj in projections:
        rid = int(getattr(proj, "inventory_copy_id"))
        sig = signals_full.get(rid)
        if sig is None:
            raise RuntimeError("collection analytics requires intelligence signals for every projected inventory row")
        ow = sig.ownership_state
        purchase_counts[purchase_year_bucket(getattr(proj, "order_date", None))] += 1
        release_counts[release_year_bucket(proj)] += 1
        recv_counts[received_year_bucket(proj, ow)] += 1
        if ow == "preorder":
            preorder_pipe[preorder_pipeline_bucket(proj)] += 1

    pipe_rows = sorted(preorder_pipe.keys(), key=lambda b: (1, "") if b is None else (0, str(b)))
    preorder_pipeline = [
        PreorderPipelineBucket(release_bucket_key=str(k), preorder_copies=int(preorder_pipe[k])) for k in pipe_rows
    ]

    timeline = CollectionTimelineAnalytics(
        generated_as_of_date=as_of,
        by_purchase_year=finalize_year_buckets(purchase_counts),
        by_release_year=finalize_year_buckets(release_counts),
        by_received_year=finalize_year_buckets(recv_counts),
        preorder_pipeline=preorder_pipeline,
        upcoming_preorder_calendar=upcoming_preorder_calendar_buckets(projections, signals_full, as_of_date=as_of),
    )

    return CollectionTimelineResponse(
        scope_user_id=int(projection_user_filter) if projection_user_filter is not None else None,
        scope=scope_tag,
        timeline=timeline,
    )


def analyze_collection_quality(
    session: Session,
    *,
    projection_user_filter: int | None,
    intel_user: User | None,
    as_of_date: date | None = None,
) -> CollectionQualityAnalyticsResponse:
    as_of = as_of_date or utc_today_deterministic()
    scope_tag = "ops_global" if projection_user_filter is None else "owner"
    projections = list(session.exec(collection_projection_stmt(user_id=projection_user_filter)).all())
    _, _, _, signals_full = compute_inventory_intelligence(session, current_user=intel_user, include_signals=True)

    dup_touch_all = duplicate_touch_inventory_ids(session, owner_scope_user_id=projection_user_filter)

    inv_ids = sorted({int(getattr(r, "inventory_copy_id")) for r in projections})
    covers_map = _covers_by_inventory(session, inv_ids)
    primary_cover_ids: set[int] = set()
    for proj in projections:
        rid = int(getattr(proj, "inventory_copy_id"))
        covs = covers_map.get(rid, [])
        pcov = _pick_primary_cover(getattr(proj, "primary_cover_image_id", None), covs)
        if pcov and pcov.id is not None:
            primary_cover_ids.add(int(pcov.id))
    latest_ocr = _latest_ocr_map(session, sorted(primary_cover_ids))

    active_total = 0
    canon_num = 0
    conflict_num = 0
    dup_touch_num = 0
    missing_scan = 0

    scanned_with_primary = 0
    proc_failed = 0

    eligible_ocr = 0
    ocr_done = 0
    ocr_failed = 0

    for proj in projections:
        rid = int(getattr(proj, "inventory_copy_id"))
        sig = signals_full.get(rid)
        if sig is None or sig.ownership_state == "cancelled":
            continue
        active_total += 1

        covs = covers_map.get(rid, [])
        prim = _pick_primary_cover(getattr(proj, "primary_cover_image_id", None), covs)
        has_scan = len(covs) > 0
        if not has_scan:
            missing_scan += 1

        cover_processing_failed = bool(prim and getattr(prim, "processing_status", "") == "failed")

        pid = int(prim.id) if prim and prim.id is not None else None

        if has_scan and pid is not None:

            scanned_with_primary += 1

            if cover_processing_failed:
                proc_failed += 1

        prim_ocr_latest = latest_ocr.get(pid) if pid is not None else None
        ocr_failed_flag = bool(
            pid is not None and prim_ocr_latest is not None and getattr(prim_ocr_latest, "processing_status", "") == "failed"
        )


        if has_scan and pid is not None and not cover_processing_failed:
            eligible_ocr += 1
            if prim_ocr_latest is not None and getattr(prim_ocr_latest, "processing_status", "") == "processed":
                ocr_done += 1



            elif ocr_failed_flag:
                ocr_failed += 1

        if getattr(proj, "canonical_series_id", None) is not None:
            canon_num += 1
        if sig.has_open_relationship_conflict:
            conflict_num += 1
        if rid in dup_touch_all:
            dup_touch_num += 1

    iq = InventoryQualityAnalytics(
        scope_active_copies_ex_cancelled=int(active_total),
        ocr_complete=percent_roll(ocr_done, eligible_ocr),
        canonical_linked=percent_roll(canon_num, active_total),
        unresolved_open_conflict_copies=percent_roll(conflict_num, active_total),
        duplicate_ownership_exposure_copies=percent_roll(dup_touch_num, active_total),
        missing_primary_scan=percent_roll(missing_scan, active_total),
        primary_cover_failed_processing=percent_roll(proc_failed, scanned_with_primary),
        primary_cover_failed_ocr=percent_roll(ocr_failed, eligible_ocr),
    )

    return CollectionQualityAnalyticsResponse(
        scope_user_id=int(projection_user_filter) if projection_user_filter is not None else None,

        scope=scope_tag,

        generated_as_of_date=as_of,
        inventory_quality=iq,
    )


def analyze_collection_composition(
    session: Session,
    *,
    projection_user_filter: int | None,

    intel_user: User | None,
    as_of_date: date | None = None,

) -> CollectionCompositionResponse:
    as_of = as_of_date or utc_today_deterministic()
    scope_tag = "ops_global" if projection_user_filter is None else "owner"
    projections = list(session.exec(collection_projection_stmt(user_id=projection_user_filter)).all())

    _, _, _, signals_full = compute_inventory_intelligence(session, current_user=intel_user, include_signals=True)

    rollout = (
        list_run_detection_ops(session, series_status=None)
        if intel_user is None
        else list_run_detection_owner(session, user=intel_user, series_status=None)
    )


    preorder_active = 0
    in_hand_active = 0
    graded_active = 0
    raw_active = 0
    cancelled = 0



    active_ids: set[int] = set()

    publisher_active: defaultdict[str, int] = defaultdict(int)



    for proj in projections:


        rid = int(getattr(proj, "inventory_copy_id"))
        sig = signals_full.get(rid)
        if sig is None:
            continue
        pname = str(getattr(proj, "publisher_name"))
        if sig.ownership_state == "cancelled":
            cancelled += 1



            continue
        active_ids.add(rid)
        publisher_active[pname] += 1
        if sig.ownership_state == "preorder":
            preorder_active += 1




        elif sig.ownership_state == "in_hand":


            in_hand_active += 1


        gst = getattr(proj, "grade_status", "raw")


        if str(gst).lower() == "raw":
            raw_active += 1
        else:
            graded_active += 1

    owned_active = len(active_ids)
    graded_vs_raw_den = graded_active + raw_active

    preorder_vs_in_hand = percent_roll(preorder_active, owned_active)
    graded_vs_raw = percent_roll(graded_active, graded_vs_raw_den)
    cancelled_vs_owned = percent_roll(cancelled, cancelled + owned_active)

    rd_summary = rollout.summary




    mini_den = rd_summary.complete_limited_series_groups + rd_summary.incomplete_limited_series_groups


    mini_pct = pct_value(rd_summary.complete_limited_series_groups, mini_den)



    ongoing_ids: set[int] = set()
    probable_groups_n = rd_summary.probable_ongoing_series_groups

    owner_filter_id = projection_user_filter
    for g in rollout.series_groups:
        if g.series_status != "probable_ongoing_series":
            continue




        if owner_filter_id is not None and getattr(g, "owner_user_id", None) is not None:
            if int(g.owner_user_id) != int(owner_filter_id):

                continue
        ongoing_ids.update(int(x) for x in g.inventory_copy_ids)







    overlap = len(ongoing_ids & active_ids)

    participation_pct = pct_value(overlap, owned_active) if owned_active else 0.0




    composition = CollectionCompositionAnalytics(
        graded_copies=graded_active,
        raw_copies=raw_active,
        preorder_active_copies=preorder_active,

        in_hand_active_copies=in_hand_active,

        cancelled_copies=cancelled,

        owned_active_copies=owned_active,
        preorder_vs_in_hand=preorder_vs_in_hand,
        graded_vs_raw=graded_vs_raw,
        cancelled_vs_owned=cancelled_vs_owned,
        publisher_concentration=publisher_concentration_active(dict(publisher_active)),
        series_signals=CompositionSeriesSignals(
            mini_series_limited_denominator_groups=int(mini_den),
            mini_series_completed_groups=int(rd_summary.complete_limited_series_groups),
            mini_series_completion_percent=float(mini_pct),
            probable_ongoing_series_groups=int(probable_groups_n),

            probable_ongoing_series_copy_touch_count=int(overlap),

            ongoing_series_participation_percent=float(participation_pct),
        ),

    )


    return CollectionCompositionResponse(
        scope_user_id=int(projection_user_filter) if projection_user_filter is not None else None,
        scope=scope_tag,
        generated_as_of_date=as_of,
        composition=composition,

    )

