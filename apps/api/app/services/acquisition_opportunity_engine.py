from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.collection_gap import CollectionGap
from app.models.want_list import WantListItem
from app.services.collection_gaps import latest_collection_gap_rows
from app.services.sell_candidate_engine import _split_identity_key

PRIORITY_ANCHORS = {
    "CRITICAL": 95.0,
    "HIGH": 82.0,
    "MEDIUM": 62.0,
    "LOW": 37.0,
}

WANT_LIST_ACTIVE_STATUSES = frozenset({"WANTED", "FOUND"})


@dataclass(frozen=True)
class AcquisitionOpportunityCandidate:
    source_type: str
    source_reference_id: int | None
    publisher: str
    series_name: str
    issue_number: str
    variant_description: str | None
    opportunity_type: str
    priority_score: float
    confidence_score: float
    estimated_fmv: float | None
    target_price: float | None
    value_gap: float | None
    rationale: str


def _money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _target_value_fields(estimated_fmv: float | None) -> tuple[float | None, float | None]:
    if estimated_fmv is None or estimated_fmv <= 0:
        return None, None
    target = _money(estimated_fmv * 0.80)
    gap = _money(estimated_fmv - (target or 0))
    return target, gap


def _priority_score_from_label(label: str, *, completion_bonus: float = 0.0) -> float:
    base = PRIORITY_ANCHORS.get(label.strip().upper(), 50.0)
    score = min(100.0, round(base + completion_bonus, 1))
    if label.strip().upper() == "CRITICAL":
        score = max(score, 90.0)
    elif label.strip().upper() == "HIGH":
        score = max(score, 75.0)
    elif label.strip().upper() == "MEDIUM":
        score = max(min(score, 74.0), 50.0)
    elif label.strip().upper() == "LOW":
        score = max(min(score, 49.0), 25.0)
    return score


def _confidence_from_completion(completion_percent: float) -> float:
    return round(min(1.0, max(0.35, completion_percent / 100.0)), 2)


def _confidence_from_want_priority(priority: str) -> float:
    mapping = {"CRITICAL": 0.92, "HIGH": 0.78, "MEDIUM": 0.58, "LOW": 0.42}
    return mapping.get(priority.strip().upper(), 0.5)


def _opportunity_type_for_gap(gap: CollectionGap) -> str:
    if gap.gap_type == "KEY_MISSING":
        return "KEY_TARGET"
    if gap.gap_type == "MILESTONE_MISSING":
        return "MILESTONE_TARGET"
    if float(gap.completion_percent) >= 80.0 and gap.issue_number:
        return "RUN_COMPLETION_TARGET"
    return "COLLECTION_GAP"


def _build_fmv_index(session: Session, *, owner_user_id: int) -> tuple[dict[tuple[str, str, str], float], dict[tuple[str, str], list[float]]]:
    exact: dict[tuple[str, str, str], float] = {}
    series_values: dict[tuple[str, str], list[float]] = {}
    copies = list(session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all())
    for copy in copies:
        fmv = copy.current_fmv
        if fmv is None or float(fmv) <= 0:
            continue
        val = float(fmv)
        pub, series, issue, _variant = _split_identity_key(copy.metadata_identity_key)
        if not series:
            continue
        pub_key = pub.strip().lower()
        series_key = series.strip().lower()
        issue_key = issue.strip().lower()
        series_values.setdefault((pub_key, series_key), []).append(val)
        if issue_key:
            exact[(pub_key, series_key, issue_key)] = val
    return exact, series_values


def _estimate_fmv(
    *,
    publisher: str,
    series_name: str,
    issue_number: str,
    exact_index: dict[tuple[str, str, str], float],
    series_index: dict[tuple[str, str], list[float]],
) -> float | None:
    pub_key = publisher.strip().lower()
    series_key = series_name.strip().lower()
    issue_key = issue_number.strip().lower()
    if issue_key:
        hit = exact_index.get((pub_key, series_key, issue_key))
        if hit is not None:
            return hit
    values = series_index.get((pub_key, series_key))
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _rationale_for_gap_opportunity(
    *,
    gap: CollectionGap,
    opportunity_type: str,
    target_price: float | None,
    estimated_fmv: float | None,
) -> str:
    parts: list[str] = []
    if opportunity_type == "RUN_COMPLETION_TARGET":
        parts.append(f"Completes a {gap.completion_percent:.0f}% complete {gap.series_name} run.")
    elif opportunity_type == "KEY_TARGET":
        parts.append("Missing key issue.")
    elif opportunity_type == "MILESTONE_TARGET":
        parts.append("Missing milestone issue.")
    else:
        parts.append(gap.rationale)
    if gap.issue_number:
        parts.append(f"Gap impact on {gap.series_name} #{gap.issue_number}.")
    if target_price is not None and estimated_fmv is not None:
        parts.append("Target price set at 80% of current FMV.")
    return " ".join(parts)


def _rationale_for_want_item(*, item: WantListItem, target_price: float | None, estimated_fmv: float | None) -> str:
    parts = [f"Critical want-list item." if item.priority == "CRITICAL" else f"Want-list target ({item.priority} priority)."]
    parts.append(f"{item.series_name} #{item.issue_number}.")
    if item.notes.strip():
        parts.append(item.notes.strip())
    if target_price is not None and estimated_fmv is not None:
        parts.append("Target price set at 80% of current FMV.")
    return " ".join(parts)


def generate_acquisition_opportunities(session: Session, *, owner_user_id: int) -> list[AcquisitionOpportunityCandidate]:
    exact_index, series_index = _build_fmv_index(session, owner_user_id=owner_user_id)
    candidates: list[AcquisitionOpportunityCandidate] = []

    for gap in latest_collection_gap_rows(session, owner_user_id=owner_user_id).values():
        if not gap.issue_number and gap.gap_type != "RUN_GAP":
            continue
        opportunity_type = _opportunity_type_for_gap(gap)
        completion_bonus = min(5.0, float(gap.completion_percent) * 0.05)
        priority_score = _priority_score_from_label(gap.priority, completion_bonus=completion_bonus)
        confidence_score = _confidence_from_completion(float(gap.completion_percent))
        estimated_fmv = _estimate_fmv(
            publisher=gap.publisher,
            series_name=gap.series_name,
            issue_number=gap.issue_number or "",
            exact_index=exact_index,
            series_index=series_index,
        )
        target_price, value_gap = _target_value_fields(estimated_fmv)
        rationale = _rationale_for_gap_opportunity(
            gap=gap,
            opportunity_type=opportunity_type,
            target_price=target_price,
            estimated_fmv=estimated_fmv,
        )
        candidates.append(
            AcquisitionOpportunityCandidate(
                source_type="COLLECTION_GAP",
                source_reference_id=int(gap.id or 0) or None,
                publisher=gap.publisher,
                series_name=gap.series_name,
                issue_number=gap.issue_number or "",
                variant_description=None,
                opportunity_type=opportunity_type,
                priority_score=priority_score,
                confidence_score=confidence_score,
                estimated_fmv=_money(estimated_fmv),
                target_price=target_price,
                value_gap=value_gap,
                rationale=rationale,
            )
        )

    want_items = session.exec(
        select(WantListItem)
        .where(WantListItem.owner_user_id == owner_user_id)
        .where(WantListItem.status.in_(["WANTED", "FOUND"]))  # type: ignore[attr-defined]
    ).all()
    for item in want_items:
        opportunity_type = "WANT_LIST_ITEM"
        priority_score = _priority_score_from_label(item.priority)
        confidence_score = _confidence_from_want_priority(item.priority)
        variant = item.variant_description.strip() or None
        estimated_fmv = _estimate_fmv(
            publisher=item.publisher,
            series_name=item.series_name,
            issue_number=item.issue_number,
            exact_index=exact_index,
            series_index=series_index,
        )
        target_price, value_gap = _target_value_fields(estimated_fmv)
        rationale = _rationale_for_want_item(item=item, target_price=target_price, estimated_fmv=estimated_fmv)
        candidates.append(
            AcquisitionOpportunityCandidate(
                source_type="WANT_LIST",
                source_reference_id=int(item.id or 0) or None,
                publisher=item.publisher,
                series_name=item.series_name,
                issue_number=item.issue_number,
                variant_description=variant,
                opportunity_type=opportunity_type,
                priority_score=priority_score,
                confidence_score=confidence_score,
                estimated_fmv=_money(estimated_fmv),
                target_price=target_price,
                value_gap=value_gap,
                rationale=rationale,
            )
        )

    candidates.sort(key=lambda c: (-c.priority_score, c.publisher.lower(), c.series_name.lower(), c.issue_number))
    return candidates
