from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.models.marketplace_acquisition import MarketplaceAcquisitionCandidate, MarketplaceSource
from app.models.want_list import WantListItem
from app.schemas.acquisition_dashboard import (
    AcquisitionDashboardActionsRead,
    AcquisitionDashboardItemRead,
    AcquisitionDashboardRead,
    AcquisitionDashboardSummaryRead,
)
from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows
from app.services.collection_gaps import latest_collection_gap_rows
from app.services.marketplace_acquisitions import ensure_marketplace_acquisition_sources

SECTION_TOP_GAPS = "TOP_COLLECTION_GAPS"
SECTION_WANT_LIST = "TOP_WANT_LIST_ITEMS"
SECTION_OPPORTUNITIES = "TOP_OPPORTUNITIES"
SECTION_MARKETPLACE = "MARKETPLACE_CANDIDATES"
SECTION_BELOW_TARGET = "BELOW_TARGET_PRICE"
SECTION_REVIEW = "REVIEW_REQUIRED"

ACTIVE_WANT_STATUSES = frozenset({"WANTED", "FOUND"})
WANT_LIST_TOP_PRIORITIES = frozenset({"CRITICAL", "HIGH"})

PRIORITY_SEVERITY = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
REC_STRENGTH = {"BUY": 3, "WATCH": 2, "PASS": 1}
LOW_MATCH_THRESHOLD = 0.55
TOP_N = 15


@dataclass(frozen=True)
class _SortableItem:
    payload: AcquisitionDashboardItemRead
    priority_rank: float
    rec_rank: int
    confidence: float
    created_at: datetime
    item_id: int


def _priority_rank_from_label(label: str | None) -> float:
    if not label:
        return 0.0
    return float(PRIORITY_SEVERITY.get(label.strip().upper(), 0))


def _sort_key(row: _SortableItem) -> tuple:
    return (
        -row.priority_rank,
        -row.rec_rank,
        -row.confidence,
        row.created_at.isoformat(),
        row.item_id,
    )


def _apply_filters(
    *,
    publisher: str | None,
    priority: str | None,
    recommendation: str | None,
    source_type: str | None,
    item: AcquisitionDashboardItemRead,
) -> bool:
    if publisher and publisher.strip().lower() not in item.publisher.lower():
        if publisher.strip().lower() not in item.title.lower():
            return False
    if priority:
        pl = (item.priority_label or "").upper()
        p = priority.strip().upper()
        if pl != p:
            if item.item_type == "acquisition_opportunity":
                min_score = {"CRITICAL": 90.0, "HIGH": 75.0, "MEDIUM": 50.0, "LOW": 25.0}.get(p, 0.0)
                if (item.priority_score or 0.0) < min_score:
                    return False
            else:
                return False
    if recommendation and (item.recommendation or "").upper() != recommendation.strip().upper():
        return False
    if source_type and (item.source_type or "").upper() != source_type.strip().upper():
        return False
    return True


def _sort_and_trim(items: list[_SortableItem], *, limit: int = TOP_N) -> list[AcquisitionDashboardItemRead]:
    ordered = sorted(items, key=_sort_key)
    return [row.payload for row in ordered[:limit]]


def _source_type_map(session: Session) -> dict[int, str]:
    ensure_marketplace_acquisition_sources(session)
    rows = session.exec(select(MarketplaceSource)).all()
    return {int(r.id or 0): r.source_type for r in rows}


def _build_context(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None,
    priority: str | None,
    recommendation: str | None,
    source_type: str | None,
) -> tuple[
    list[_SortableItem],
    list[_SortableItem],
    list[_SortableItem],
    list[_SortableItem],
    list[_SortableItem],
    list[_SortableItem],
    AcquisitionDashboardSummaryRead,
]:
    source_types = _source_type_map(session)

    gap_items: list[_SortableItem] = []
    gaps = latest_collection_gap_rows(session, owner_user_id=owner_user_id)
    for gap in gaps.values():
        if not gap.issue_number:
            continue
        payload = AcquisitionDashboardItemRead(
            section=SECTION_TOP_GAPS,
            item_type="collection_gap",
            item_id=int(gap.id or 0),
            publisher=gap.publisher,
            series_name=gap.series_name,
            issue_number=gap.issue_number,
            title=f"{gap.series_name} #{gap.issue_number}",
            priority_label=gap.priority,
            priority_score=float(gap.completion_percent),
            rationale=gap.rationale,
            created_at=gap.created_at.isoformat(),
        )
        if not _apply_filters(
            publisher=publisher,
            priority=priority,
            recommendation=recommendation,
            source_type=source_type,
            item=payload,
        ):
            continue
        gap_items.append(
            _SortableItem(
                payload=payload,
                priority_rank=_priority_rank_from_label(gap.priority),
                rec_rank=0,
                confidence=float(gap.completion_percent) / 100.0,
                created_at=gap.created_at,
                item_id=int(gap.id or 0),
            )
        )

    want_items: list[_SortableItem] = []
    want_rows = session.exec(select(WantListItem).where(WantListItem.owner_user_id == owner_user_id)).all()
    total_want = 0
    critical_want = 0
    for row in want_rows:
        if row.status not in ACTIVE_WANT_STATUSES:
            continue
        total_want += 1
        if row.priority == "CRITICAL":
            critical_want += 1
        if row.priority not in WANT_LIST_TOP_PRIORITIES:
            continue
        payload = AcquisitionDashboardItemRead(
            section=SECTION_WANT_LIST,
            item_type="want_list_item",
            item_id=int(row.id or 0),
            publisher=row.publisher or "",
            series_name=row.series_name,
            issue_number=row.issue_number,
            title=f"{row.series_name} #{row.issue_number}",
            priority_label=row.priority,
            rationale=row.notes or f"Want-list item ({row.status}).",
            created_at=row.created_at.isoformat(),
        )
        if not _apply_filters(
            publisher=publisher,
            priority=priority,
            recommendation=recommendation,
            source_type=source_type,
            item=payload,
        ):
            continue
        want_items.append(
            _SortableItem(
                payload=payload,
                priority_rank=_priority_rank_from_label(row.priority),
                rec_rank=0,
                confidence=_priority_rank_from_label(row.priority) / 4.0,
                created_at=row.created_at,
                item_id=int(row.id or 0),
            )
        )

    opp_by_id = {
        int(o.id or 0): o for o in latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id).values()
    }

    opp_items: list[_SortableItem] = []
    high_priority_opps = 0
    for opp in opp_by_id.values():
        if float(opp.priority_score) >= 75.0:
            high_priority_opps += 1
        payload = AcquisitionDashboardItemRead(
            section=SECTION_OPPORTUNITIES,
            item_type="acquisition_opportunity",
            item_id=int(opp.id or 0),
            publisher=opp.publisher,
            series_name=opp.series_name,
            issue_number=opp.issue_number,
            title=f"{opp.series_name} #{opp.issue_number}",
            priority_score=float(opp.priority_score),
            confidence_score=float(opp.confidence_score),
            target_price=float(opp.target_price) if opp.target_price is not None else None,
            rationale=opp.rationale,
            created_at=opp.created_at.isoformat(),
        )
        if not _apply_filters(
            publisher=publisher,
            priority=priority,
            recommendation=recommendation,
            source_type=source_type,
            item=payload,
        ):
            continue
        opp_items.append(
            _SortableItem(
                payload=payload,
                priority_rank=float(opp.priority_score),
                rec_rank=0,
                confidence=float(opp.confidence_score),
                created_at=opp.created_at,
                item_id=int(opp.id or 0),
            )
        )

    marketplace_items: list[_SortableItem] = []
    below_target_items: list[_SortableItem] = []
    review_items: list[_SortableItem] = []
    buy_count = watch_count = pass_count = below_count = review_count = 0

    mac_rows = list(
        session.exec(
            select(MarketplaceAcquisitionCandidate)
            .where(MarketplaceAcquisitionCandidate.owner_user_id == owner_user_id)
            .where(MarketplaceAcquisitionCandidate.status != "IGNORED")
        ).all()
    )
    for row in mac_rows:
        st = source_types.get(int(row.marketplace_source_id or 0))
        target: float | None = None
        if row.acquisition_opportunity_id is not None:
            linked = opp_by_id.get(int(row.acquisition_opportunity_id))
            if linked is not None and linked.target_price is not None:
                target = float(linked.target_price)

        payload = AcquisitionDashboardItemRead(
            section=SECTION_MARKETPLACE,
            item_type="marketplace_candidate",
            item_id=int(row.id or 0),
            publisher=row.publisher or "",
            series_name=row.series_name or "",
            issue_number=row.issue_number or "",
            title=row.title,
            recommendation=row.recommendation,
            confidence_score=float(row.match_confidence),
            total_price=float(row.total_price) if row.total_price is not None else None,
            target_price=target,
            source_type=st,
            rationale=row.rationale,
            created_at=row.created_at.isoformat(),
        )
        if not _apply_filters(
            publisher=publisher,
            priority=priority,
            recommendation=recommendation,
            source_type=source_type,
            item=payload,
        ):
            continue

        sortable = _SortableItem(
            payload=payload,
            priority_rank=float(row.value_score),
            rec_rank=REC_STRENGTH.get(row.recommendation, 0),
            confidence=float(row.match_confidence),
            created_at=row.created_at,
            item_id=int(row.id or 0),
        )
        if row.recommendation == "BUY":
            buy_count += 1
        elif row.recommendation == "WATCH":
            watch_count += 1
        elif row.recommendation == "PASS":
            pass_count += 1

        marketplace_items.append(sortable)

        is_below = (
            row.total_price is not None
            and target is not None
            and float(row.total_price) <= float(target)
        )
        if is_below:
            below_count += 1
            below_payload = payload.model_copy(update={"section": SECTION_BELOW_TARGET})
            below_target_items.append(
                _SortableItem(
                    payload=below_payload,
                    priority_rank=sortable.priority_rank,
                    rec_rank=sortable.rec_rank,
                    confidence=sortable.confidence,
                    created_at=sortable.created_at,
                    item_id=sortable.item_id,
                )
            )

        needs_review = row.recommendation == "WATCH" or float(row.match_confidence) < LOW_MATCH_THRESHOLD
        if needs_review:
            review_count += 1
            review_payload = payload.model_copy(update={"section": SECTION_REVIEW})
            review_items.append(
                _SortableItem(
                    payload=review_payload,
                    priority_rank=sortable.priority_rank,
                    rec_rank=sortable.rec_rank,
                    confidence=sortable.confidence,
                    created_at=sortable.created_at,
                    item_id=sortable.item_id,
                )
            )

    summary = AcquisitionDashboardSummaryRead(
        total_want_list_items=total_want,
        critical_want_list_items=critical_want,
        open_collection_gaps=len(gaps),
        high_priority_opportunities=high_priority_opps,
        buy_candidates=buy_count,
        watch_candidates=watch_count,
        pass_candidates=pass_count,
        below_target_candidates=below_count,
        review_required_candidates=review_count,
    )
    return gap_items, want_items, opp_items, marketplace_items, below_target_items, review_items, summary


def get_acquisition_dashboard(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None = None,
    priority: str | None = None,
    recommendation: str | None = None,
    source_type: str | None = None,
) -> AcquisitionDashboardRead:
    gap_items, want_items, opp_items, marketplace_items, below_target_items, review_items, summary = _build_context(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        priority=priority,
        recommendation=recommendation,
        source_type=source_type,
    )
    return AcquisitionDashboardRead(
        summary=summary,
        top_collection_gaps=_sort_and_trim(gap_items),
        top_want_list_items=_sort_and_trim(want_items),
        top_opportunities=_sort_and_trim(opp_items),
        marketplace_candidates=_sort_and_trim(marketplace_items),
        below_target_price=_sort_and_trim(below_target_items),
        review_required=_sort_and_trim(review_items),
    )


def get_acquisition_dashboard_summary(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None = None,
    priority: str | None = None,
    recommendation: str | None = None,
    source_type: str | None = None,
) -> AcquisitionDashboardSummaryRead:
    *_, summary = _build_context(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        priority=priority,
        recommendation=recommendation,
        source_type=source_type,
    )
    return summary


def get_acquisition_dashboard_actions(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str | None = None,
    priority: str | None = None,
    recommendation: str | None = None,
    source_type: str | None = None,
) -> AcquisitionDashboardActionsRead:
    dashboard = get_acquisition_dashboard(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        priority=priority,
        recommendation=recommendation,
        source_type=source_type,
    )
    urgent: list[AcquisitionDashboardItemRead] = []
    urgent.extend(dashboard.below_target_price)
    urgent.extend([i for i in dashboard.marketplace_candidates if i.recommendation == "BUY"])
    urgent.extend([i for i in dashboard.top_want_list_items if i.priority_label == "CRITICAL"])
    urgent.extend([i for i in dashboard.top_collection_gaps if i.priority_label == "CRITICAL"])
    urgent.extend(dashboard.review_required)

    seen: set[tuple[str, int]] = set()
    deduped: list[AcquisitionDashboardItemRead] = []
    for item in urgent:
        key = (item.item_type, item.item_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    sortable: list[_SortableItem] = []
    for item in deduped:
        try:
            created = datetime.fromisoformat(item.created_at.replace("Z", "+00:00"))
        except ValueError:
            created = datetime.fromisoformat("1970-01-01T00:00:00+00:00")
        sortable.append(
            _SortableItem(
                payload=item,
                priority_rank=item.priority_score or _priority_rank_from_label(item.priority_label) * 25.0,
                rec_rank=REC_STRENGTH.get(item.recommendation or "", 0),
                confidence=float(item.confidence_score or 0),
                created_at=created,
                item_id=item.item_id,
            )
        )
    return AcquisitionDashboardActionsRead(urgent_acquisition_actions=_sort_and_trim(sortable, limit=25))
