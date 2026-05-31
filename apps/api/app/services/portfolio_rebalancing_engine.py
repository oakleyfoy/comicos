"""P56-04 Portfolio Rebalancing Intelligence — concentration and capital efficiency (no trades)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, col, select

from app.models.asset_ledger import InventoryCopy, InventoryFmvSnapshot
from app.models.portfolio_rebalancing import (
    CHARACTER_EXPOSURE_THRESHOLD,
    DUPLICATE_MIN_COPIES,
    DUPLICATE_MIN_FMV,
    MODERN_SPEC_THRESHOLD,
    MODERN_SPEC_YEAR,
    PUBLISHER_EXPOSURE_THRESHOLD,
    TITLE_EXPOSURE_THRESHOLD,
)
from app.services.exit_candidate_engine import generate_exit_candidates
from app.services.hold_sell_engine import generate_hold_sell_recommendations
from app.services.sell_candidate_engine import _split_identity_key, generate_sell_candidates

ACTION_REDUCE = "REDUCE_EXPOSURE"
ACTION_REVIEW = "REVIEW_POSITION"
ACTION_HOLD = "HOLD"

TYPE_TITLE = "TITLE_OVEREXPOSURE"
TYPE_PUBLISHER = "PUBLISHER_OVEREXPOSURE"
TYPE_CHARACTER = "CHARACTER_OVEREXPOSURE"
TYPE_MODERN = "MODERN_SPEC_OVEREXPOSURE"
TYPE_DUPLICATE = "DUPLICATE_CAPITAL"
TYPE_LOW_EFF = "LOW_EFFICIENCY_CAPITAL"

_CHARACTER_TAGS = ("batman", "spider-man", "superman", "x-men", "wonder woman", "iron man")


@dataclass(frozen=True)
class PortfolioRebalanceResult:
    rebalance_type: str
    target_key: str
    target_label: str
    exposure_value: float
    exposure_percent: float
    recommended_action: str
    priority_score: float
    confidence_score: float
    rationale: str
    publisher: str = ""


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _money(value: Decimal | float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _latest_fmv(session: Session, *, inventory_item_id: int, copy: InventoryCopy) -> float:
    row = session.exec(
        select(InventoryFmvSnapshot)
        .where(InventoryFmvSnapshot.inventory_copy_id == inventory_item_id)
        .order_by(col(InventoryFmvSnapshot.changed_at).desc())
        .order_by(col(InventoryFmvSnapshot.id).desc())
    ).first()
    if row is not None:
        return _money(row.new_fmv)
    return _money(copy.current_fmv)


def _title_priority(pct: float) -> float:
    if pct >= 0.30:
        return round(min(100.0, 90.0 + (pct - 0.30) * 50.0), 1)
    if pct >= TITLE_EXPOSURE_THRESHOLD:
        return round(70.0 + (pct - TITLE_EXPOSURE_THRESHOLD) / 0.10 * 19.0, 1)
    return 0.0


def _publisher_priority(pct: float) -> float:
    if pct >= 0.50:
        return round(min(100.0, 80.0 + (pct - 0.50) * 40.0), 1)
    if pct >= PUBLISHER_EXPOSURE_THRESHOLD:
        return round(70.0 + (pct - PUBLISHER_EXPOSURE_THRESHOLD) / 0.10 * 10.0, 1)
    return 0.0


def _confidence(*, fmv_coverage: float, signal_count: int, record_count: int) -> float:
    base = 0.42 + 0.18 * fmv_coverage
    base += min(0.22, signal_count * 0.04)
    base += min(0.12, record_count / 200.0)
    return round(_clamp01(base), 4)


def _character_tag(series: str) -> str | None:
    lowered = series.lower()
    for tag in _CHARACTER_TAGS:
        if tag in lowered:
            return tag
    return None


def _action_for_title_exposure(pct: float) -> str:
    if pct >= 0.28:
        return ACTION_REDUCE
    if pct >= TITLE_EXPOSURE_THRESHOLD:
        return ACTION_REVIEW
    return ACTION_HOLD


def generate_portfolio_rebalancing_recommendations(session: Session, *, owner_user_id: int) -> list[PortfolioRebalanceResult]:
    copies = list(
        session.exec(
            select(InventoryCopy)
            .where(InventoryCopy.user_id == owner_user_id)
            .order_by(InventoryCopy.id.asc())
        ).all()
    )
    if not copies:
        return []

    exit_by_id = {r.inventory_item_id: r for r in generate_exit_candidates(session, owner_user_id=owner_user_id)}
    hold_by_id = {r.inventory_item_id: r for r in generate_hold_sell_recommendations(session, owner_user_id=owner_user_id)}
    sell_by_id = {r.inventory_item_id: r for r in generate_sell_candidates(session, owner_user_id=owner_user_id)}

    fmv_by_id: dict[int, float] = {}
    total_fmv = 0.0
    fmv_positive = 0
    for copy in copies:
        assert copy.id is not None
        fmv = _latest_fmv(session, inventory_item_id=int(copy.id), copy=copy)
        fmv_by_id[int(copy.id)] = fmv
        total_fmv += fmv
        if fmv > 0:
            fmv_positive += 1
    fmv_coverage = fmv_positive / len(copies) if copies else 0.0

    title_fmv: dict[str, float] = {}
    title_label: dict[str, str] = {}
    title_publisher: dict[str, str] = {}
    publisher_fmv: dict[str, float] = {}
    publisher_label: dict[str, str] = {}
    character_fmv: dict[str, float] = {}
    character_label: dict[str, str] = {}
    modern_fmv = 0.0
    identity_groups: dict[str, list[InventoryCopy]] = {}

    for copy in copies:
        assert copy.id is not None
        inv_id = int(copy.id)
        fmv = fmv_by_id[inv_id]
        publisher, series, issue_number, _variant = _split_identity_key(copy.metadata_identity_key)
        title_key = f"{publisher}|{series}".strip().lower()
        if not series:
            title_key = f"unknown|{copy.id}"
        title_fmv[title_key] = title_fmv.get(title_key, 0.0) + fmv
        title_label[title_key] = series or "Unknown title"
        title_publisher[title_key] = publisher

        pub_key = (publisher or "unknown").strip().lower()
        publisher_fmv[pub_key] = publisher_fmv.get(pub_key, 0.0) + fmv
        publisher_label[pub_key] = publisher or "Unknown publisher"

        tag = _character_tag(series)
        if tag:
            character_fmv[tag] = character_fmv.get(tag, 0.0) + fmv
            character_label[tag] = tag.title()

        if copy.release_year is not None and int(copy.release_year) >= MODERN_SPEC_YEAR:
            modern_fmv += fmv

        id_key = (copy.metadata_identity_key or f"variant:{copy.variant_id}").strip()
        identity_groups.setdefault(id_key, []).append(copy)

    results: list[PortfolioRebalanceResult] = []
    signal_count = len(exit_by_id) + len([h for h in hold_by_id.values() if h.recommendation == "SELL"])

    if total_fmv > 0:
        for title_key, value in sorted(title_fmv.items(), key=lambda x: -x[1]):
            pct = value / total_fmv
            if pct < TITLE_EXPOSURE_THRESHOLD:
                continue
            label = title_label[title_key]
            priority = _title_priority(pct)
            action = _action_for_title_exposure(pct)
            pct_display = round(pct * 100.0, 1)
            rationale = f"{label} represents {pct_display}% of current portfolio FMV."
            if action == ACTION_REDUCE:
                rationale += " Capital may be better deployed into higher-conviction targets."
            results.append(
                PortfolioRebalanceResult(
                    rebalance_type=TYPE_TITLE,
                    target_key=f"title:{title_key}",
                    target_label=label,
                    exposure_value=round(value, 2),
                    exposure_percent=pct_display,
                    recommended_action=action,
                    priority_score=priority,
                    confidence_score=_confidence(
                        fmv_coverage=fmv_coverage,
                        signal_count=signal_count,
                        record_count=len(copies),
                    ),
                    rationale=rationale,
                    publisher=title_publisher.get(title_key, ""),
                )
            )

        for pub_key, value in sorted(publisher_fmv.items(), key=lambda x: -x[1]):
            pct = value / total_fmv
            if pct < PUBLISHER_EXPOSURE_THRESHOLD:
                continue
            label = publisher_label[pub_key]
            priority = _publisher_priority(pct)
            action = ACTION_REDUCE if pct >= 0.50 else ACTION_REVIEW
            pct_display = round(pct * 100.0, 1)
            rationale = f"Publisher exposure exceeds preferred threshold ({label} at {pct_display}%)."
            results.append(
                PortfolioRebalanceResult(
                    rebalance_type=TYPE_PUBLISHER,
                    target_key=f"publisher:{pub_key}",
                    target_label=label,
                    exposure_value=round(value, 2),
                    exposure_percent=pct_display,
                    recommended_action=action,
                    priority_score=priority,
                    confidence_score=_confidence(
                        fmv_coverage=fmv_coverage,
                        signal_count=signal_count,
                        record_count=len(copies),
                    ),
                    rationale=rationale,
                    publisher=label,
                )
            )

        for tag, value in sorted(character_fmv.items(), key=lambda x: -x[1]):
            pct = value / total_fmv
            if pct < CHARACTER_EXPOSURE_THRESHOLD:
                continue
            label = character_label[tag]
            priority = round(min(100.0, 75.0 + pct * 80.0), 1)
            action = ACTION_REDUCE if pct >= 0.30 else ACTION_REVIEW
            pct_display = round(pct * 100.0, 1)
            rationale = f"{label} character/franchise exposure is {pct_display}% of portfolio FMV."
            results.append(
                PortfolioRebalanceResult(
                    rebalance_type=TYPE_CHARACTER,
                    target_key=f"character:{tag}",
                    target_label=label,
                    exposure_value=round(value, 2),
                    exposure_percent=pct_display,
                    recommended_action=action,
                    priority_score=priority,
                    confidence_score=_confidence(
                        fmv_coverage=fmv_coverage,
                        signal_count=signal_count,
                        record_count=len(copies),
                    ),
                    rationale=rationale,
                    publisher="",
                )
            )

        modern_pct = modern_fmv / total_fmv
        if modern_pct >= MODERN_SPEC_THRESHOLD:
            pct_display = round(modern_pct * 100.0, 1)
            priority = round(min(100.0, 68.0 + modern_pct * 60.0), 1)
            results.append(
                PortfolioRebalanceResult(
                    rebalance_type=TYPE_MODERN,
                    target_key="modern_spec:2010_plus",
                    target_label="Modern / spec (2010+)",
                    exposure_value=round(modern_fmv, 2),
                    exposure_percent=pct_display,
                    recommended_action=ACTION_REVIEW,
                    priority_score=priority,
                    confidence_score=_confidence(
                        fmv_coverage=fmv_coverage,
                        signal_count=signal_count,
                        record_count=len(copies),
                    ),
                    rationale=f"Modern/spec inventory represents {pct_display}% of portfolio FMV.",
                    publisher="",
                )
            )

    for id_key, rows in sorted(identity_groups.items()):
        if len(rows) < DUPLICATE_MIN_COPIES:
            continue
        group_fmv = sum(fmv_by_id[int(r.id or 0)] for r in rows)
        if group_fmv < DUPLICATE_MIN_FMV:
            continue
        publisher, series, issue_number, _ = _split_identity_key(id_key if "|" in id_key else rows[0].metadata_identity_key)
        sell_signals = sum(
            1
            for r in rows
            if sell_by_id.get(int(r.id or 0)) and sell_by_id[int(r.id or 0)].recommendation in {"SELL", "STRONG_SELL"}
        )
        exit_signals = sum(1 for r in rows if exit_by_id.get(int(r.id or 0)))
        priority = 72.0
        if sell_signals >= 2 or exit_signals >= 2:
            priority = 85.0
        if len(rows) >= 5:
            priority = min(100.0, priority + 8.0)
        action = ACTION_REDUCE if sell_signals >= 1 or len(rows) >= 4 else ACTION_REVIEW
        pct_display = round((group_fmv / total_fmv) * 100.0, 1) if total_fmv > 0 else 0.0
        label = f"{series} #{issue_number}".strip() if series else id_key[:80]
        rationale = (
            f"{len(rows)} duplicate copies are tying up capital."
        )
        if sell_signals:
            rationale += " Exit and sell signals support reducing duplicate exposure."
        results.append(
            PortfolioRebalanceResult(
                rebalance_type=TYPE_DUPLICATE,
                target_key=f"duplicate:{id_key[:200]}",
                target_label=label,
                exposure_value=round(group_fmv, 2),
                exposure_percent=pct_display,
                recommended_action=action,
                priority_score=round(priority, 1),
                confidence_score=_confidence(
                    fmv_coverage=fmv_coverage,
                    signal_count=signal_count + sell_signals,
                    record_count=len(copies),
                ),
                rationale=rationale,
                publisher=publisher,
            )
        )

    for copy in copies:
        assert copy.id is not None
        inv_id = int(copy.id)
        fmv = fmv_by_id[inv_id]
        cost = _money(copy.acquisition_cost)
        if cost <= 0 and fmv <= 0:
            continue
        gain = fmv - cost
        ratio = gain / cost if cost > 0 else 0.0
        hold = hold_by_id.get(inv_id)
        sell = sell_by_id.get(inv_id)
        weak_exit = (
            hold is not None
            and hold.recommendation in {"HOLD", "WATCH"}
            and hold.conviction_score < 55.0
        ) or (sell is not None and sell.recommendation in {"HOLD", "REVIEW"})
        if fmv < 8.0:
            continue
        if ratio > 0.05:
            continue
        if not weak_exit:
            continue
        publisher, series, issue_number, _ = _split_identity_key(copy.metadata_identity_key)
        priority = round(50.0 + min(20.0, max(0.0, 8.0 - gain)), 1)
        label = f"{series} #{issue_number}".strip() if series else f"Copy {inv_id}"
        pct_display = round((fmv / total_fmv) * 100.0, 1) if total_fmv > 0 else 0.0
        results.append(
            PortfolioRebalanceResult(
                rebalance_type=TYPE_LOW_EFF,
                target_key=f"inventory:{inv_id}",
                target_label=label,
                exposure_value=round(fmv, 2),
                exposure_percent=pct_display,
                recommended_action=ACTION_REVIEW,
                priority_score=priority,
                confidence_score=_confidence(
                    fmv_coverage=fmv_coverage,
                    signal_count=signal_count,
                    record_count=len(copies),
                ),
                rationale="Low gain with weak exit conviction; capital may be better deployed into higher-conviction targets.",
                publisher=publisher,
            )
        )

    results.sort(key=lambda r: (-r.priority_score, r.rebalance_type, r.target_key))
    return results
