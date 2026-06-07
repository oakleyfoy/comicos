"""P89-01 Sell Candidate Intelligence engine (dedicated; does not modify P54 engine)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy, InventoryFmvSnapshot
from app.models.grading_candidate import GradingCandidate
from app.models.hold_sell_intelligence import HoldSellRecommendation
from app.models.p89_sell_candidate import P89SellCandidate, utc_now
from app.services.sell_candidate_confidence import ConfidenceInputs, score_exit_confidence
from app.services.sell_candidate_reason_service import build_reason_summary

logger = logging.getLogger(__name__)

KEEP_COPIES = 2
CONCENTRATION_THRESHOLD = 0.16


@dataclass(frozen=True)
class SellCandidateEvaluation:
    inventory_copy_id: int
    recommendation: str
    sell_score: float
    hold_score: float
    grade_first_score: float
    monitor_score: float
    confidence: str
    estimated_sale_value: float
    estimated_profit: float
    reason_summary: str
    reasons: list[str]
    title: str
    issue_number: str
    publisher: str


def _money(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _split_identity(key: str | None) -> tuple[str, str, str]:
    if not key:
        return "", "", ""
    parts = key.split("|")
    while len(parts) < 3:
        parts.append("")
    return parts[0], parts[1], parts[2]


def _latest_fmv(session: Session, *, copy: InventoryCopy) -> float:
    assert copy.id is not None
    row = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id == int(copy.id))
        .order_by(col(InventoryFmvSnapshot.changed_at).desc())
        .order_by(col(InventoryFmvSnapshot.id).desc())
    ).first()
    if row is not None:
        return _money(row.new_fmv)
    return _money(copy.current_fmv)


def _hold_sell_signal(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> str | None:
    row = session.exec(
        select(HoldSellRecommendation)
        .where(HoldSellRecommendation.owner_user_id == owner_user_id)
        .where(HoldSellRecommendation.inventory_item_id == inventory_copy_id)
        .order_by(col(HoldSellRecommendation.created_at).desc())
    ).first()
    return row.recommendation if row else None


def _grading_candidate(session: Session, *, owner_user_id: int, inventory_copy_id: int) -> GradingCandidate | None:
    return session.exec(
        select(GradingCandidate)
        .where(GradingCandidate.owner_user_id == owner_user_id)
        .where(GradingCandidate.inventory_item_id == inventory_copy_id)
        .order_by(col(GradingCandidate.updated_at).desc())
    ).first()


def _hold_duration_days(copy: InventoryCopy) -> int:
    if copy.received_at is None:
        return 0
    received = copy.received_at
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - received).days)


def evaluate_inventory_copy(
    session: Session,
    *,
    owner_user_id: int,
    copy: InventoryCopy,
    group_size: int,
    copy_index: int,
    is_excess: bool,
    concentration: float,
) -> SellCandidateEvaluation:
    assert copy.id is not None
    inv_id = int(copy.id)
    fmv = _latest_fmv(session, copy=copy)
    cost = _money(copy.acquisition_cost)
    profit = round(fmv - cost, 2)
    profit_ratio = (profit / cost) if cost > 0 else (1.0 if profit > 0 else 0.0)
    graded = copy.grade_status and copy.grade_status.lower() not in {"raw", "ungraded", ""}
    grading = _grading_candidate(session, owner_user_id=owner_user_id, inventory_copy_id=inv_id)
    hold_sell = _hold_sell_signal(session, owner_user_id=owner_user_id, inventory_copy_id=inv_id)
    hold_days = _hold_duration_days(copy)

    grade_signal = (
        not graded
        and (
            (copy.star_rating is not None and int(copy.star_rating) >= 4)
            or (grading is not None and grading.candidate_priority in {"HIGH", "CRITICAL"})
        )
    )

    sell_score = 25.0
    if profit_ratio >= 0.5:
        sell_score += 35
    elif profit_ratio >= 0.2:
        sell_score += 22
    elif profit > 0:
        sell_score += 10
    if is_excess:
        sell_score += 18
    if concentration >= CONCENTRATION_THRESHOLD:
        sell_score += 12
    if graded and profit > 0:
        sell_score += 8
    if hold_sell == "SELL":
        sell_score += 10
    if fmv >= 40:
        sell_score += 5

    hold_score = 30.0
    if profit <= 0:
        hold_score += 25
    if group_size == 1:
        hold_score += 15
    if hold_days >= 365:
        hold_score += 8
    if hold_sell == "HOLD":
        hold_score += 12
    if concentration < 0.08:
        hold_score += 6

    grade_first_score = 15.0
    if grade_signal:
        grade_first_score += 40
    if fmv >= 75 and not graded:
        grade_first_score += 20
    if profit > 0 and not graded:
        grade_first_score += 10

    monitor_score = 35.0
    if 0.05 < profit_ratio < 0.2:
        monitor_score += 15
    if hold_sell == "WATCH":
        monitor_score += 12

    sell_score = _clamp_score(sell_score)
    hold_score = _clamp_score(hold_score)
    grade_first_score = _clamp_score(grade_first_score)
    monitor_score = _clamp_score(monitor_score)

    scores = {
        "SELL_NOW": sell_score,
        "HOLD": hold_score,
        "GRADE_FIRST": grade_first_score,
        "MONITOR": monitor_score,
    }
    recommendation = max(scores, key=scores.get)  # type: ignore[arg-type]

    agrees: bool | None = None
    if hold_sell == "SELL" and recommendation == "SELL_NOW":
        agrees = True
    elif hold_sell == "HOLD" and recommendation == "HOLD":
        agrees = True
    elif hold_sell and hold_sell not in {"SELL", "HOLD"}:
        agrees = None
    elif hold_sell:
        agrees = False

    confidence = score_exit_confidence(
        ConfidenceInputs(
            has_fmv=fmv > 0,
            has_cost=cost > 0,
            has_identity=bool(copy.metadata_identity_key),
            has_grade_status=bool(copy.grade_status),
            hold_sell_agrees=agrees,
            grade_signal=grade_signal,
            profit_ratio=profit_ratio if cost > 0 else None,
        )
    )

    publisher, series, issue = _split_identity(copy.metadata_identity_key)
    summary, reasons = build_reason_summary(
        recommendation=recommendation,
        profit=profit,
        cost=cost,
        confidence=confidence,
        duplicate_count=group_size,
        concentration=concentration,
        grade_first_signal=grade_signal,
        hold_sell_signal=hold_sell,
    )

    return SellCandidateEvaluation(
        inventory_copy_id=inv_id,
        recommendation=recommendation,
        sell_score=sell_score,
        hold_score=hold_score,
        grade_first_score=grade_first_score,
        monitor_score=monitor_score,
        confidence=confidence,
        estimated_sale_value=round(fmv, 2),
        estimated_profit=profit,
        reason_summary=summary,
        reasons=reasons,
        title=series or "Unknown",
        issue_number=issue,
        publisher=publisher,
    )


def generate_evaluations(session: Session, *, owner_user_id: int) -> list[SellCandidateEvaluation]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .where(InventoryCopy.hold_status != "sold")
            .order_by(InventoryCopy.metadata_identity_key.asc(), InventoryCopy.copy_number.asc())
        ).all()
    )
    if not copies:
        return []

    fmv_by_id = {int(c.id or 0): _latest_fmv(session, copy=c) for c in copies if c.id}
    total_fmv = sum(fmv_by_id.values())

    groups: dict[str, list[InventoryCopy]] = {}
    for copy in copies:
        key = (copy.metadata_identity_key or f"variant:{copy.variant_id}").strip()
        groups.setdefault(key, []).append(copy)

    group_fmv = {k: sum(fmv_by_id[int(r.id or 0)] for r in rows) for k, rows in groups.items()}

    evaluations: list[SellCandidateEvaluation] = []
    for key, rows in groups.items():
        concentration = (group_fmv[key] / total_fmv) if total_fmv > 0 else 0.0
        sorted_rows = sorted(rows, key=lambda r: (r.copy_number, int(r.id or 0)))
        excess_ids = set()
        if len(sorted_rows) > KEEP_COPIES:
            for row in sorted_rows[KEEP_COPIES:]:
                excess_ids.add(int(row.id or 0))
        for idx, copy in enumerate(sorted_rows):
            evaluations.append(
                evaluate_inventory_copy(
                    session,
                    owner_user_id=owner_user_id,
                    copy=copy,
                    group_size=len(sorted_rows),
                    copy_index=idx,
                    is_excess=int(copy.id or 0) in excess_ids,
                    concentration=concentration,
                )
            )
    return evaluations


def recalculate_sell_candidates(
    session: Session,
    *,
    owner_user_id: int,
    dry_run: bool = False,
) -> dict[str, int]:
    evaluations = generate_evaluations(session, owner_user_id=owner_user_id)
    counts = {"candidates": 0, "sell_now": 0, "hold": 0, "grade_first": 0, "monitor": 0, "created": 0, "updated": 0}
    now = utc_now()
    for ev in evaluations:
        counts["candidates"] += 1
        if ev.recommendation == "SELL_NOW":
            counts["sell_now"] += 1
        elif ev.recommendation == "HOLD":
            counts["hold"] += 1
        elif ev.recommendation == "GRADE_FIRST":
            counts["grade_first"] += 1
        elif ev.recommendation == "MONITOR":
            counts["monitor"] += 1
        if dry_run:
            continue
        existing = session.exec(
            select(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.inventory_copy_id == ev.inventory_copy_id)
        ).first()
        if existing is None:
            session.add(
                P89SellCandidate(
                    owner_user_id=owner_user_id,
                    inventory_copy_id=ev.inventory_copy_id,
                    recommendation=ev.recommendation,
                    sell_score=ev.sell_score,
                    hold_score=ev.hold_score,
                    grade_first_score=ev.grade_first_score,
                    monitor_score=ev.monitor_score,
                    confidence=ev.confidence,
                    estimated_sale_value=ev.estimated_sale_value,
                    estimated_profit=ev.estimated_profit,
                    reason_summary=ev.reason_summary,
                    reasons_json=ev.reasons,
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                )
            )
            counts["created"] += 1
        else:
            unchanged = (
                existing.recommendation == ev.recommendation
                and existing.confidence == ev.confidence
                and abs(existing.sell_score - ev.sell_score) < 0.05
                and abs(existing.estimated_profit - ev.estimated_profit) < 0.01
            )
            if unchanged:
                continue
            existing.recommendation = ev.recommendation
            existing.sell_score = ev.sell_score
            existing.hold_score = ev.hold_score
            existing.grade_first_score = ev.grade_first_score
            existing.monitor_score = ev.monitor_score
            existing.confidence = ev.confidence
            existing.estimated_sale_value = ev.estimated_sale_value
            existing.estimated_profit = ev.estimated_profit
            existing.reason_summary = ev.reason_summary
            existing.reasons_json = ev.reasons
            existing.status = "ACTIVE"
            existing.updated_at = now
            session.add(existing)
            counts["updated"] += 1
    if not dry_run:
        session.flush()
        _maybe_notify_sell_candidates(session, owner_user_id=owner_user_id, counts=counts)
    return counts


def _maybe_notify_sell_candidates(session: Session, *, owner_user_id: int, counts: dict[str, int]) -> None:
    try:
        from app.services.collector_notification_service import _upsert_notification

        sell_now = int(counts.get("sell_now") or 0)
        if sell_now <= 0:
            return
        _upsert_notification(
            session,
            owner_user_id=owner_user_id,
            notification_type="SELL_CANDIDATE",
            priority="NORMAL",
            title=f"ComicOS identified {sell_now} books as strong sell candidates.",
            message="Review Sell Candidates for exit opportunities.",
            action_url="/sell-candidates",
            related_entity_type="sell_candidate",
            reasons=[f"sell_now={sell_now}"],
        )
    except Exception:  # noqa: BLE001
        logger.debug("SELL_CANDIDATE notification skipped", exc_info=True)


def count_active_sell_candidates(session: Session, *, owner_user_id: int) -> int:
    from sqlalchemy import func

    n = session.exec(
        select(func.count())
        .select_from(P89SellCandidate)
        .where(P89SellCandidate.owner_user_id == owner_user_id)
        .where(P89SellCandidate.status == "ACTIVE")
    ).one()
    if isinstance(n, tuple):
        n = n[0]
    return int(n or 0)


def build_sell_candidate_briefing_highlights(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[str, str | None]:
    rows = list(
        session.exec(
            select(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.status == "ACTIVE")
        ).all()
    )
    if not rows:
        return {
            "top_sell_candidate": None,
            "highest_profit_candidate": None,
            "highest_confidence_candidate": None,
        }
    enriched = [_to_read(session, row=row) for row in rows]
    top_sell = max(enriched, key=lambda r: (r.sell_score, r.estimated_profit, _confidence_rank(r.confidence)))
    top_profit = max(enriched, key=lambda r: (r.estimated_profit, r.sell_score))
    top_conf = max(enriched, key=lambda r: (_confidence_rank(r.confidence), r.sell_score))
    return {
        "top_sell_candidate": _display_title(top_sell),
        "highest_profit_candidate": _display_title(top_profit),
        "highest_confidence_candidate": _display_title(top_conf),
    }


def _confidence_rank(confidence: str) -> int:
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(confidence, 0)


def _display_title(read) -> str:
    if read.issue_number:
        return f"{read.title} #{read.issue_number}".strip()
    return read.title or "Comic"


def _to_read(session: Session, *, row: P89SellCandidate):
    from app.schemas.p89_sell_candidate import P89SellCandidateRead

    copy = session.get(InventoryCopy, row.inventory_copy_id)
    publisher, series, issue = _split_identity(copy.metadata_identity_key if copy else None)
    title = series or "Unknown"
    pricing = None
    if copy is not None:
        from app.services.p89_market_pricing_service import lookup_latest_snapshot
        from app.services.sales_velocity_service import velocity_display_label

        pricing = lookup_latest_snapshot(
            session,
            owner_user_id=int(row.owner_user_id),
            series=title,
            issue_number=issue,
            variant="",
        )
    return P89SellCandidateRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        inventory_copy_id=int(row.inventory_copy_id),
        recommendation=row.recommendation,  # type: ignore[arg-type]
        sell_score=float(row.sell_score),
        hold_score=float(row.hold_score),
        grade_first_score=float(row.grade_first_score),
        monitor_score=float(row.monitor_score),
        confidence=row.confidence,  # type: ignore[arg-type]
        estimated_sale_value=float(row.estimated_sale_value),
        estimated_profit=float(row.estimated_profit),
        reason_summary=row.reason_summary,
        reasons=list(row.reasons_json or []),
        status=row.status,
        title=title,
        issue_number=issue,
        publisher=publisher,
        cover_image_url="",
        created_at=row.created_at,
        updated_at=row.updated_at,
        is_top_opportunity=False,
        quick_sale_price=float(pricing.quick_sale_price) if pricing else None,
        market_price=float(pricing.market_price) if pricing else None,
        premium_price=float(pricing.premium_price) if pricing else None,
        pricing_confidence=pricing.pricing_confidence if pricing else None,
        sales_velocity=pricing.sales_velocity if pricing else None,
        sales_velocity_label=velocity_display_label(pricing.sales_velocity) if pricing else None,
    )


def list_p89_sell_candidates(
    session: Session,
    *,
    owner_user_id: int,
    recommendation: str | None = None,
    confidence: str | None = None,
    minimum_score: float | None = None,
    sort: str = "sell_score",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list, int]:
    from app.schemas.p89_sell_candidate import P89SellCandidateRead

    lim = min(max(limit, 1), 200)
    off = max(offset, 0)
    rows = list(
        session.exec(
            select(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.status == "ACTIVE")
        ).all()
    )
    items: list[P89SellCandidateRead] = []
    for row in rows:
        if recommendation and row.recommendation != recommendation.strip().upper():
            continue
        if confidence and row.confidence != confidence.strip().upper():
            continue
        if minimum_score is not None and row.sell_score < float(minimum_score):
            continue
        items.append(_to_read(session, row=row))
    sort_key = sort.strip().lower()
    if sort_key == "estimated_profit":
        items.sort(key=lambda r: (-r.estimated_profit, -r.sell_score, r.id))
    elif sort_key == "estimated_sale_value":
        items.sort(key=lambda r: (-r.estimated_sale_value, -r.sell_score, r.id))
    else:
        items.sort(key=lambda r: (-r.sell_score, -r.estimated_profit, r.id))
    total = len(items)
    if items:
        top_id = max(
            items,
            key=lambda r: (r.sell_score, r.estimated_profit, _confidence_rank(r.confidence)),
        ).id
        items = [
            P89SellCandidateRead(**{**r.model_dump(), "is_top_opportunity": r.id == top_id}) for r in items
        ]
    return items[off : off + lim], total


def build_p89_sell_candidate_summary(session: Session, *, owner_user_id: int):
    from app.schemas.p89_sell_candidate import P89SellCandidateSummaryRead

    rows = list(
        session.exec(
            select(P89SellCandidate)
            .where(P89SellCandidate.owner_user_id == owner_user_id)
            .where(P89SellCandidate.status == "ACTIVE")
        ).all()
    )
    counts = {"SELL_NOW": 0, "HOLD": 0, "GRADE_FIRST": 0, "MONITOR": 0}
    total_profit = 0.0
    total_value = 0.0
    top: P89SellCandidate | None = None
    for row in rows:
        counts[row.recommendation] = counts.get(row.recommendation, 0) + 1
        total_profit += float(row.estimated_profit)
        total_value += float(row.estimated_sale_value)
        if top is None or (row.sell_score, row.estimated_profit) > (top.sell_score, top.estimated_profit):
            top = row
    top_read = _to_read(session, row=top) if top else None
    return P89SellCandidateSummaryRead(
        total_candidates=len(rows),
        sell_now_count=int(counts.get("SELL_NOW", 0)),
        hold_count=int(counts.get("HOLD", 0)),
        grade_first_count=int(counts.get("GRADE_FIRST", 0)),
        monitor_count=int(counts.get("MONITOR", 0)),
        total_estimated_profit=round(total_profit, 2),
        total_estimated_sale_value=round(total_value, 2),
        top_opportunity=top_read,
    )
