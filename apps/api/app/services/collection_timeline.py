"""Aggregate deterministic timeline events across inventory-backed tables (read-only)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime
from datetime import time as time_cls
from datetime import timezone

from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    ComicIssue,
    ComicTitle,
    CoverImage,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    CoverImageOcrResult,
    CoverRelationshipConflict,
    DuplicateCandidateReview,
    InventoryCopy,
    OcrReplayItem,
    Order,
    OrderItem,
    Publisher,
    RelationshipReplayItem,
    Variant,
)
from app.schemas.collection_timeline import (
    CollectionTimelineEvent,
    CollectionTimelineEventGroup,
    CollectionTimelineEventsResponse,
    CollectionTimelineEventType,
    CollectionTimelineFiltersEcho,
    CollectionTimelineGrouping,
    CollectionTimelineSort,
    CollectionTimelineSummary,
    OwnershipStateFilter,
)
from app.schemas.inventory_intelligence import KeyedCount
from app.services.inventory_intelligence import normalize_ownership_state


UTC = timezone.utc
MAX_TIMELINE_EVENTS = 500
DEFAULT_TIMELINE_LIMIT = 280


def utc_today() -> date_cls:
    return datetime.now(UTC).date()


def _dt_from_date(d: date_cls) -> datetime:
    return datetime.combine(d, time_cls.min, tzinfo=UTC)


def _norm_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _week_key(dt: datetime) -> str:
    iso = dt.astimezone(UTC).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _month_key(dt: datetime) -> str:
    d = dt.astimezone(UTC).date()
    return f"{d.year}-{d.month:02d}"


def _day_key(dt: datetime) -> str:
    return dt.astimezone(UTC).date().isoformat()


@dataclass(frozen=True)
class _CopyBrief:
    publisher: str
    series_title: str
    issue_number: str
    release_status: str
    order_status: str
    metadata_identity_key: str | None
    preorder_track: bool
    ownership: OwnershipStateFilter


def _brief_from_inventory_row(
    ic: InventoryCopy,
    *,
    publisher: str,
    series_title: str,
    issue_number: str | int | None,
) -> _CopyBrief:
    ownership = normalize_ownership_state(
        release_status=ic.release_status,
        order_status=ic.order_status,
        received_at=ic.received_at,
    )
    preorder_track = ownership == "preorder"
    return _CopyBrief(
        publisher=publisher or "",
        series_title=series_title or "",
        issue_number=str(issue_number or ""),
        release_status=str(ic.release_status),
        order_status=str(ic.order_status),
        metadata_identity_key=ic.metadata_identity_key,
        preorder_track=preorder_track,
        ownership=ownership,
    )


def _publisher_match(name: str, needle: str | None) -> bool:
    if not needle:
        return True
    return needle.casefold().strip() in name.casefold()


def _ownership_match_scope(
    *,
    preorder_only: bool,
    in_hand_only: bool,
    ownership_filter: OwnershipStateFilter | None,
    brief: _CopyBrief,
) -> bool:
    if preorder_only and brief.ownership != "preorder":
        return False
    if in_hand_only and brief.ownership != "in_hand":
        return False
    if ownership_filter and brief.ownership != ownership_filter:
        return False
    return True


def _release_match(release_filter: str | None, rs: str) -> bool:
    if not release_filter:
        return True
    return rs == release_filter


def _mk_event(
    *,
    stable_id: str,
    event_type: CollectionTimelineEventType,
    occurred_at: datetime | None,
    copy_id: int,
    brief: _CopyBrief,
    evidence_json: dict,
) -> CollectionTimelineEvent | None:
    oc = _norm_dt(occurred_at if isinstance(occurred_at, datetime) else None)
    if oc is None:
        return None
    return CollectionTimelineEvent(
        stable_id=stable_id,
        event_type=event_type,
        occurred_at=oc,
        inventory_copy_id=copy_id,
        publisher=brief.publisher,
        series_title=brief.series_title,
        issue_number=brief.issue_number,
        ownership_state_snapshot=brief.ownership,
        release_status_snapshot=brief.release_status,
        preorder_track=brief.preorder_track,
        evidence_json=dict(evidence_json),
    )


def _sort_key(ev: CollectionTimelineEvent) -> tuple[datetime, str, str]:
    return ev.occurred_at, ev.event_type, ev.stable_id


def _group_timeline_events(
    events: list[CollectionTimelineEvent],
    grouping: CollectionTimelineGrouping,
) -> tuple[list[CollectionTimelineEvent], list[CollectionTimelineEventGroup]]:
    if grouping == "none":
        return events, []
    buckets: defaultdict[str, list[CollectionTimelineEvent]] = defaultdict(list)
    order_keys: list[str] = []

    def push(key: str, ev: CollectionTimelineEvent) -> None:
        if key not in buckets:
            order_keys.append(key)
        buckets[key].append(ev)

    for ev in events:
        if grouping == "day":
            push(_day_key(ev.occurred_at), ev)
        elif grouping == "week":
            push(_week_key(ev.occurred_at), ev)
        elif grouping == "month":
            push(_month_key(ev.occurred_at), ev)
        elif grouping == "publisher":
            push(ev.publisher or "__unknown_publisher__", ev)
        elif grouping == "series":
            push(f"{ev.publisher}|{ev.series_title}", ev)
        elif grouping == "ownership_state":
            push(ev.ownership_state_snapshot, ev)
        elif grouping == "preorder_vs_in_hand":
            push("preorder" if ev.preorder_track else "not_preorder_track", ev)
        elif grouping == "inventory_item":
            push(str(ev.inventory_copy_id), ev)

    grouped = [CollectionTimelineEventGroup(group_key=k, events=list(buckets[k])) for k in order_keys]
    flattened: list[CollectionTimelineEvent] = [ev for grp in grouped for ev in grp.events]
    return flattened, grouped


def _order_date_scalar(session: Session, inventory_copy_id: int) -> date_cls | datetime | None:
    return session.exec(
        select(Order.order_date)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .join(InventoryCopy, InventoryCopy.order_item_id == OrderItem.id)
        .where(InventoryCopy.id == inventory_copy_id)
        .limit(1),
    ).one_or_none()


def timeline_events_for_scope(
    session: Session,
    *,
    scope_user_id: int | None,
    event_type_filter: CollectionTimelineEventType | None = None,
    publisher: str | None = None,
    ownership_filter: OwnershipStateFilter | None = None,
    release_status: str | None = None,
    start_date: date_cls | None = None,
    end_date: date_cls | None = None,
    preorder_only: bool = False,
    in_hand_only: bool = False,
    inventory_copy_id: int | None = None,
    grouping: CollectionTimelineGrouping = "none",
    sort: CollectionTimelineSort = "desc",
    limit: int = DEFAULT_TIMELINE_LIMIT,
    return_events: bool = True,
) -> CollectionTimelineEventsResponse:
    resolved_limit = max(1, min(int(limit), MAX_TIMELINE_EVENTS))
    scope_token = "owner" if scope_user_id is not None else "ops_global"

    stmt = (
        select(
            InventoryCopy,
            Order.order_date,
            ComicTitle.name.label("series_title"),
            ComicIssue.issue_number,
            Publisher.name,
        )
        .join(OrderItem, InventoryCopy.order_item_id == OrderItem.id)
        .join(Order, OrderItem.order_id == Order.id)
        .join(Variant, InventoryCopy.variant_id == Variant.id)
        .join(ComicIssue, Variant.comic_issue_id == ComicIssue.id)
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
    )
    if scope_user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == int(scope_user_id))
    if inventory_copy_id is not None:
        stmt = stmt.where(InventoryCopy.id == int(inventory_copy_id))
    stmt = stmt.order_by(InventoryCopy.id.asc())

    inventory_rows = session.exec(stmt).all()

    brief_by_id: dict[int, _CopyBrief] = {}
    order_date_by_inventory: dict[int, date_cls | datetime] = {}
    inventory_objects: dict[int, InventoryCopy] = {}

    for ic, od, series_title_cell, issue_num, pname in inventory_rows:
        name = pname or ""
        if not _publisher_match(name, publisher):
            continue
        brief = _brief_from_inventory_row(
            ic,
            publisher=name,
            series_title=series_title_cell or "",
            issue_number=issue_num,
        )
        if not _ownership_match_scope(
            preorder_only=preorder_only,
            in_hand_only=in_hand_only,
            ownership_filter=ownership_filter,
            brief=brief,
        ):
            continue
        if not _release_match(release_status, brief.release_status):
            continue

        cid = int(ic.id or 0)
        brief_by_id[cid] = brief
        inventory_objects[cid] = ic
        if od is not None:
            order_date_by_inventory[cid] = od

    inventory_set = set(brief_by_id.keys())
    raw_events: list[CollectionTimelineEvent] = []

    for cid in sorted(inventory_set):
        ic = inventory_objects[cid]
        bf = brief_by_id[cid]

        ia = _mk_event(
            stable_id=f"inventory_added:{cid}",
            event_type="inventory_added",
            occurred_at=_norm_dt(ic.created_at),
            copy_id=cid,
            brief=bf,
            evidence_json={"inventory_copy_id": cid},
        )
        if ia:
            raw_events.append(ia)

        od_cell = order_date_by_inventory.get(cid)
        if od_cell is None:
            od_cell = _order_date_scalar(session, cid)
            if od_cell is not None:
                order_date_by_inventory[cid] = od_cell

        anchor_dt: datetime | None = None
        if isinstance(od_cell, datetime):
            anchor_dt = _norm_dt(od_cell)
        elif isinstance(od_cell, date_cls):
            anchor_dt = _dt_from_date(od_cell)

        if anchor_dt is not None and ic.order_status == "preordered":
            ev_pc = _mk_event(
                stable_id=f"preorder_created:{cid}",
                event_type="preorder_created",
                occurred_at=anchor_dt,
                copy_id=cid,
                brief=bf,
                evidence_json={"inventory_copy_id": cid, "order_item_id": ic.order_item_id},
            )
            if ev_pc:
                raw_events.append(ev_pc)

        if ic.release_date:
            rd = _mk_event(
                stable_id=f"release_day:{cid}:{ic.release_date}",
                event_type="release_day",
                occurred_at=_dt_from_date(ic.release_date),
                copy_id=cid,
                brief=bf,
                evidence_json={"release_date": str(ic.release_date), "inventory_copy_id": cid},
            )
            if rd:
                raw_events.append(rd)
        if ic.expected_ship_date:
            es = _mk_event(
                stable_id=f"expected_ship_window:{cid}:{ic.expected_ship_date}",
                event_type="expected_ship_window",
                occurred_at=_dt_from_date(ic.expected_ship_date),
                copy_id=cid,
                brief=bf,
                evidence_json={
                    "expected_ship_date": str(ic.expected_ship_date),
                    "inventory_copy_id": cid,
                },
            )
            if es:
                raw_events.append(es)

        recv = _mk_event(
            stable_id=f"inventory_received:{cid}",
            event_type="inventory_received",
            occurred_at=_norm_dt(ic.received_at),
            copy_id=cid,
            brief=bf,
            evidence_json={"inventory_copy_id": cid},
        )
        if recv:
            raw_events.append(recv)

    covers = []
    if inventory_set:
        covers = session.exec(
            select(CoverImage).where(
                CoverImage.inventory_copy_id.is_not(None),
                CoverImage.inventory_copy_id.in_(list(inventory_set)),
            ),
        ).all()

    inventory_by_cover: dict[int, int] = {}
    for c in covers:
        if c.inventory_copy_id:
            inventory_by_cover[int(c.id)] = int(c.inventory_copy_id)

    for cover in covers:
        cid_cover = inventory_by_cover.get(int(cover.id))
        if cid_cover is None or cid_cover not in brief_by_id:
            continue
        bf = brief_by_id[cid_cover]
        if cover.processing_status == "processed" and cover.processed_at:
            sc = _mk_event(
                stable_id=f"scan_completed:{cover.id}",
                event_type="scan_completed",
                occurred_at=_norm_dt(cover.processed_at),
                copy_id=cid_cover,
                brief=bf,
                evidence_json={
                    "cover_image_id": int(cover.id),
                    "processing_status": cover.processing_status,
                },
            )
            if sc:
                raw_events.append(sc)

        ocr_rows = session.exec(
            select(CoverImageOcrResult).where(CoverImageOcrResult.cover_image_id == int(cover.id)),
        ).all()
        for ocr_row in ocr_rows:
            if ocr_row.processing_status == "processed" and ocr_row.processed_at:
                oev = _mk_event(
                    stable_id=f"ocr_completed:{ocr_row.id}",
                    event_type="ocr_completed",
                    occurred_at=_norm_dt(ocr_row.processed_at),
                    copy_id=cid_cover,
                    brief=bf,
                    evidence_json={
                        "cover_image_id": int(cover.id),
                        "ocr_result_id": int(ocr_row.id),
                        "replay_of_ocr_result_id": ocr_row.replay_of_ocr_result_id,
                    },
                )
                if oev:
                    raw_events.append(oev)
            elif ocr_row.processing_status == "failed":
                ferr = (
                    _norm_dt(ocr_row.processed_at)
                    or _norm_dt(ocr_row.processing_started_at)
                    or _norm_dt(ocr_row.created_at)
                )
                fe = _mk_event(
                    stable_id=f"ocr_failed:{ocr_row.id}",
                    event_type="ocr_failed",
                    occurred_at=ferr,
                    copy_id=cid_cover,
                    brief=bf,
                    evidence_json={
                        "cover_image_id": int(cover.id),
                        "ocr_result_id": int(ocr_row.id),
                        "processing_error_fragment": (
                            (ocr_row.processing_error or "")[:200] if ocr_row.processing_error else None
                        ),
                    },
                )
                if fe:
                    raw_events.append(fe)

        replay_rows = session.exec(
            select(OcrReplayItem).where(OcrReplayItem.cover_image_id == int(cover.id)),
        ).all()
        for rpi in replay_rows:
            rr_at = _norm_dt(rpi.completed_at) or _norm_dt(rpi.updated_at)
            if rr_at:
                oe2 = _mk_event(
                    stable_id=f"ocr_replay_completed:{rpi.id}",
                    event_type="ocr_completed",
                    occurred_at=rr_at,
                    copy_id=cid_cover,
                    brief=bf,
                    evidence_json={
                        "replay_item_kind": "ocr_replay_item",
                        "ocr_replay_item_id": int(rpi.id),
                        "replay_run_id": int(rpi.replay_run_id),
                        "cover_image_id": int(cover.id),
                    },
                )
                if oe2:
                    raw_events.append(oe2)

    cover_ids_owned = sorted(inventory_by_cover.keys())

    if cover_ids_owned:
        decisions = session.exec(
            select(CoverImageLinkDecision).where(
                or_(
                    CoverImageLinkDecision.source_cover_image_id.in_(cover_ids_owned),
                    CoverImageLinkDecision.candidate_cover_image_id.in_(cover_ids_owned),
                ),
            ),
        ).all()
        for ld in decisions:
            src_iv = inventory_by_cover.get(int(ld.source_cover_image_id))
            cand_iv = inventory_by_cover.get(int(ld.candidate_cover_image_id))
            copy_attach = src_iv if src_iv is not None else cand_iv
            if not copy_attach or copy_attach not in brief_by_id:
                continue
            bf = brief_by_id[copy_attach]
            rr = _mk_event(
                stable_id=f"link_decision:{ld.id}",
                event_type="relationship_reviewed",
                occurred_at=_norm_dt(ld.created_at),
                copy_id=copy_attach,
                brief=bf,
                evidence_json={
                    "link_decision_id": int(ld.id),
                    "decision_type": ld.decision_type,
                    "relationship_type": ld.relationship_type,
                    "decision_state": ld.decision_state,
                },
            )
            if rr:
                raw_events.append(rr)

        replay_rel = session.exec(
            select(RelationshipReplayItem).where(RelationshipReplayItem.cover_image_id.in_(cover_ids_owned)),
        ).all()
        for ritr in replay_rel:
            if not ritr.cover_image_id:
                continue
            cid_r = inventory_by_cover.get(int(ritr.cover_image_id))
            if not cid_r or cid_r not in brief_by_id:
                continue
            bf = brief_by_id[cid_r]
            rr2_at = _norm_dt(ritr.completed_at) or _norm_dt(ritr.updated_at)
            if rr2_at:
                rr2 = _mk_event(
                    stable_id=f"relationship_replay_item:{ritr.id}",
                    event_type="relationship_reviewed",
                    occurred_at=rr2_at,
                    copy_id=cid_r,
                    brief=bf,
                    evidence_json={
                        "replay_item_kind": "relationship_replay_item",
                        "relationship_replay_item_id": int(ritr.id),
                        "relationship_key": ritr.relationship_key,
                        "replay_run_id": int(ritr.replay_run_id),
                    },
                )
                if rr2:
                    raw_events.append(rr2)

        sug_rows = session.exec(
            select(CanonicalIssueLinkSuggestion).where(
                CanonicalIssueLinkSuggestion.cover_image_id.in_(cover_ids_owned),
            ),
        ).all()
        for sg in sug_rows:
            via_cover = inventory_by_cover.get(int(sg.cover_image_id))
            target_cid = int(sg.inventory_copy_id) if sg.inventory_copy_id else via_cover
            if not target_cid or target_cid not in brief_by_id:
                continue
            bf = brief_by_id[target_cid]
            if sg.reviewed_at:
                csr = _mk_event(
                    stable_id=f"canonical_reviewed:{sg.id}",
                    event_type="canonical_suggestion_reviewed",
                    occurred_at=_norm_dt(sg.reviewed_at),
                    copy_id=target_cid,
                    brief=bf,
                    evidence_json={
                        "canonical_issue_link_suggestion_id": int(sg.id),
                        "review_state": sg.review_state,
                    },
                )
                if csr:
                    raw_events.append(csr)

        conflicts = session.exec(
            select(CoverRelationshipConflict).where(
                or_(
                    CoverRelationshipConflict.source_cover_image_id.in_(cover_ids_owned),
                    CoverRelationshipConflict.related_cover_image_id.in_(cover_ids_owned),
                ),
            ),
        ).all()
        for cf in conflicts:
            src_iv = (
                inventory_by_cover.get(int(cf.source_cover_image_id))
                if cf.source_cover_image_id
                else None
            )
            rel_iv = (
                inventory_by_cover.get(int(cf.related_cover_image_id))
                if cf.related_cover_image_id
                else None
            )
            target_copies = sorted({tcx for tcx in (src_iv, rel_iv) if tcx and tcx in brief_by_id})
            for tcx in target_copies:
                bf = brief_by_id[tcx]
                cd_ev = _mk_event(
                    stable_id=f"conflict_detected:{cf.id}:{tcx}",
                    event_type="conflict_detected",
                    occurred_at=_norm_dt(cf.created_at),
                    copy_id=tcx,
                    brief=bf,
                    evidence_json={
                        "conflict_id": int(cf.id),
                        "conflict_type": cf.conflict_type,
                        "severity": cf.severity,
                        "status": cf.status,
                    },
                )
                if cd_ev:
                    raw_events.append(cd_ev)

                res_ts = _norm_dt(cf.resolved_at) or _norm_dt(cf.dismissed_at) or _norm_dt(cf.acknowledged_at)
                if res_ts is not None:
                    cr_ev = _mk_event(
                        stable_id=f"conflict_resolved:{cf.id}:{tcx}:{cf.status}",
                        event_type="conflict_resolved",
                        occurred_at=res_ts,
                        copy_id=tcx,
                        brief=bf,
                        evidence_json={
                            "conflict_id": int(cf.id),
                            "status": cf.status,
                        },
                    )
                    if cr_ev:
                        raw_events.append(cr_ev)

        vf_candidates = session.exec(
            select(CoverImageMatchCandidate).where(CoverImageMatchCandidate.source_cover_image_id.in_(cover_ids_owned)),
        ).all()
        for mc in vf_candidates:
            if mc.grouping_type != "probable_variant_family":
                continue
            src_iv = inventory_by_cover.get(int(mc.source_cover_image_id))
            candidate_iv = inventory_by_cover.get(int(mc.candidate_cover_image_id))
            for tcx in sorted({sid for sid in (src_iv, candidate_iv) if sid and sid in brief_by_id}):
                bf = brief_by_id[tcx]
                vf = _mk_event(
                    stable_id=f"variant_family:{mc.id}:{tcx}",
                    event_type="variant_family_detected",
                    occurred_at=_norm_dt(mc.created_at),
                    copy_id=tcx,
                    brief=bf,
                    evidence_json={
                        "match_candidate_id": int(mc.id),
                        "grouping_type": mc.grouping_type,
                        "source_cover_image_id": int(mc.source_cover_image_id),
                        "candidate_cover_image_id": int(mc.candidate_cover_image_id),
                    },
                )
                if vf:
                    raw_events.append(vf)

    identity_map: dict[str, list[int]] = defaultdict(list)
    for cid_inner, bf_inner in brief_by_id.items():
        mik = bf_inner.metadata_identity_key
        if mik:
            identity_map[mik].append(cid_inner)

    if identity_map:
        ids_keys = tuple(identity_map.keys())
        reviews = session.exec(
            select(DuplicateCandidateReview).where(DuplicateCandidateReview.metadata_identity_key.in_(ids_keys)),
        ).all()
        for dr in reviews:
            cand_copies = identity_map.get(dr.metadata_identity_key)
            if not cand_copies:
                continue
            dup_at = _norm_dt(dr.created_at)
            for tcx in sorted(cand_copies):
                bf = brief_by_id[tcx]
                de = _mk_event(
                    stable_id=f"duplicate_detected:{dr.id}:{tcx}",
                    event_type="duplicate_detected",
                    occurred_at=dup_at,
                    copy_id=tcx,
                    brief=bf,
                    evidence_json={
                        "duplicate_candidate_review_id": int(dr.id),
                        "review_status": dr.review_status,
                        "metadata_identity_key_fragment": dr.metadata_identity_key[:120],
                    },
                )
                if de:
                    raw_events.append(de)

    def _occurrence_in_window(ev: CollectionTimelineEvent) -> bool:
        d = ev.occurred_at.astimezone(UTC).date()
        if start_date is not None and d < start_date:
            return False
        if end_date is not None and d > end_date:
            return False
        return True

    filtered: list[CollectionTimelineEvent] = [
        ev for ev in raw_events if _occurrence_in_window(ev) and (not event_type_filter or ev.event_type == event_type_filter)
    ]

    filtered.sort(key=_sort_key)
    if sort == "desc":
        filtered.reverse()

    total_after_filter = len(filtered)
    counts = Counter(e.event_type for e in filtered)
    earliest = min((e.occurred_at for e in filtered), default=None)
    latest = max((e.occurred_at for e in filtered), default=None)

    if return_events:
        truncated = filtered[:resolved_limit]
        flattened, groups = _group_timeline_events(truncated, grouping)
    else:
        truncated = []
        flattened, groups = [], []

    keyed_counts = sorted(
        (KeyedCount(key=str(kt), count=cnt) for kt, cnt in counts.items()),
        key=lambda row: (-row.count, row.key or ""),
    )

    display_truncation = min(resolved_limit, total_after_filter)

    summary_model = CollectionTimelineSummary(
        scope_user_id=int(scope_user_id) if scope_user_id is not None else None,
        scope=scope_token,
        generated_as_of_date=utc_today(),
        total_events_present=int(total_after_filter),
        truncated_to=display_truncation,
        earliest_occurrence=earliest,
        latest_occurrence=latest,
        counts_by_event_type=keyed_counts,
    )

    filters_echo = CollectionTimelineFiltersEcho(
        event_type=event_type_filter,
        publisher=publisher,
        ownership_state=ownership_filter,
        release_status=release_status,
        start_date=start_date,
        end_date=end_date,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
        inventory_copy_id=inventory_copy_id,
        grouping=grouping,
        sort=sort,
    )

    return CollectionTimelineEventsResponse(
        scope_user_id=int(scope_user_id) if scope_user_id is not None else None,
        scope=scope_token,
        generated_as_of_date=utc_today(),
        summary=summary_model,
        filters=filters_echo,
        events=flattened,
        groups=groups,
    )
