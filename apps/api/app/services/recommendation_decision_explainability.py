"""Cover allocation, quantity reasoning, signal matrix, and deduped reasons for decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.purchase_variant import PurchaseVariantRecommendation
from app.models.release_intelligence import ReleaseVariant
from app.schemas.recommendation_decision import (
    CoverPurchasePlanRow,
    QuantityAdjustmentRow,
    QuantityReasoningRead,
    ScoreBreakdownRow,
    SignalAbbreviationRead,
    SignalMatrixRead,
)
from app.services.recommendation_intelligence_enrichment import (
    CollectorSignificanceEnrichment,
    CollectorSignificanceScoreBreakdown,
)

SIGNAL_ABBREVIATIONS: tuple[SignalAbbreviationRead, ...] = tuple(
    SignalAbbreviationRead(key=key, label=label, description=desc)
    for key, label, desc in (
        ("issue_launch", "#1", "Launch or first issue"),
        ("milestone_issue", "MS", "Milestone issue"),
        ("first_appearance", "FA", "First appearance"),
        ("death_or_major_event", "EV", "Death, reveal, or major story event"),
        ("anniversary_legacy", "ANN", "Anniversary or legacy issue"),
        ("creator_significance", "CR", "Creator significance"),
        ("homage_cover", "HM", "Homage or tribute cover"),
        ("franchise_strength", "FR", "Franchise strength"),
        ("active_collector_audience", "AUD", "Active collector audience"),
        ("ratio_variant_opportunity", "VAR", "Ratio or variant opportunity"),
        ("market_heat", "HOT", "Market/spec heat"),
        ("user_profile_match", "YOU", "Matches user strategy"),
        ("pull_list_relevance", "PL", "Pull list relevance"),
        ("not_in_inventory", "NEW", "Not currently owned"),
        ("foc_window", "FOC", "FOC timing window"),
    )
)

_SPECIALTY_PATTERN = re.compile(
    r"\b(signed|sketch|virgin|foil|metallic|embossed|artist\s+edition|exclusive\s+edition)\b",
    re.IGNORECASE,
)

_INCENTIVE_PATTERN = re.compile(r"\b(incentive|retailer\s+exclusive|store\s+exclusive)\b", re.IGNORECASE)


@dataclass(frozen=True)
class _CoverCandidate:
    cover_label: str
    variant_type: str
    ratio_value: int | None
    is_incentive: bool
    is_specialty: bool
    strength: float


def _normalize_cover_label(variant: ReleaseVariant) -> str:
    if variant.ratio_value:
        return f"1:{int(variant.ratio_value)}"
    name = (variant.variant_name or "Cover A").strip()
    if name.lower().startswith("cover"):
        return name
    return f"Cover {name}"


def _label_from_purchase_rec(rec: PurchaseVariantRecommendation) -> str:
    label = (rec.cover_label or "").strip()
    return label or "Cover A"


def _build_cover_candidates(
    *,
    variant_recs: list[PurchaseVariantRecommendation],
    release_variants: list[ReleaseVariant],
) -> list[_CoverCandidate]:
    candidates: list[_CoverCandidate] = []
    seen: set[str] = set()

    for rec in variant_recs:
        if rec.recommendation.strip().upper() not in {"BUY", "STRONG_BUY", "MUST_BUY"}:
            continue
        label = _label_from_purchase_rec(rec)
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        vtype = (rec.variant_type or "UNKNOWN").upper()
        candidates.append(
            _CoverCandidate(
                cover_label=label,
                variant_type=vtype,
                ratio_value=None,
                is_incentive=vtype == "INCENTIVE" or bool(_INCENTIVE_PATTERN.search(label)),
                is_specialty=bool(_SPECIALTY_PATTERN.search(label)),
                strength=float(rec.confidence_score or 0.65),
            )
        )

    for variant in release_variants:
        label = _normalize_cover_label(variant)
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        vtype = (variant.variant_type or "").upper()
        ratio = int(variant.ratio_value) if variant.ratio_value else None
        candidates.append(
            _CoverCandidate(
                cover_label=label,
                variant_type=vtype,
                ratio_value=ratio,
                is_incentive=bool(variant.is_incentive_variant) or vtype == "INCENTIVE",
                is_specialty=bool(_SPECIALTY_PATTERN.search(label)),
                strength=0.55 if ratio else 0.7,
            )
        )

    if not candidates:
        candidates.append(
            _CoverCandidate(
                cover_label="Cover A",
                variant_type="COVER_A",
                ratio_value=None,
                is_incentive=False,
                is_specialty=False,
                strength=0.75,
            )
        )
    return candidates


def _primary_candidate(candidates: list[_CoverCandidate]) -> _CoverCandidate:
    for c in candidates:
        if c.cover_label.lower().startswith("cover a") and not c.ratio_value and not c.is_incentive:
            return c
    for c in candidates:
        if not c.ratio_value and not c.is_incentive and not c.is_specialty:
            return c
    return candidates[0]


def _ratio_allowed(*, signal_set: set[str], reason_codes: list[str]) -> bool:
    codes = {c.upper() for c in reason_codes}
    return bool(
        signal_set.intersection({"RATIO_VARIANT", "INCENTIVE_VARIANT", "VARIANT_HOT"})
        or codes.intersection({"RATIO_OPPORTUNITY", "SCARCITY"})
    )


def _incentive_allowed(*, signal_set: set[str], reason_codes: list[str]) -> bool:
    codes = {c.upper() for c in reason_codes}
    return "INCENTIVE_VARIANT" in signal_set or "RATIO_OPPORTUNITY" in codes or "SCARCITY" in codes


def _specialty_allowed(*, signal_set: set[str], reason_codes: list[str]) -> bool:
    codes = {c.upper() for c in reason_codes}
    return "SCARCITY" in codes or "VARIANT_HOT" in signal_set or "RATIO_OPPORTUNITY" in codes


def build_cover_purchase_plan(
    *,
    total_quantity: int,
    action: str,
    candidates: list[_CoverCandidate],
    signal_set: set[str],
    reason_codes: list[str],
) -> list[CoverPurchasePlanRow]:
    if action in {"WATCH", "PASS"} or total_quantity <= 0:
        return [
            CoverPurchasePlanRow(
                cover_label=c.cover_label,
                recommended_quantity=0,
                reason_codes=["MONITOR_ONLY"] if action == "WATCH" else [],
                reason_summary="Monitor only — no purchase quantity allocated.",
            )
            for c in candidates[:3]
        ] or [
            CoverPurchasePlanRow(
                cover_label="Cover A",
                recommended_quantity=0,
                reason_codes=["MONITOR_ONLY"],
                reason_summary="Monitor only.",
            )
        ]

    ratio_ok = _ratio_allowed(signal_set=signal_set, reason_codes=reason_codes)
    incentive_ok = _incentive_allowed(signal_set=signal_set, reason_codes=reason_codes)
    specialty_ok = _specialty_allowed(signal_set=signal_set, reason_codes=reason_codes)

    usable: list[_CoverCandidate] = []
    for c in candidates:
        if c.is_incentive and not incentive_ok:
            continue
        if c.ratio_value and not ratio_ok:
            continue
        if c.is_specialty and not specialty_ok:
            continue
        usable.append(c)
    if not usable:
        usable = [_primary_candidate(candidates)]

    primary = _primary_candidate(usable)
    alternates = [c for c in usable if c.cover_label != primary.cover_label]
    alternates.sort(key=lambda c: (-(c.ratio_value or 0), -c.strength))

    allocations: dict[str, int] = {}

    def add(label: str, qty: int) -> None:
        if qty <= 0:
            return
        allocations[label] = allocations.get(label, 0) + qty

    remaining = total_quantity
    if total_quantity == 1:
        add(primary.cover_label, 1)
        remaining = 0
    elif total_quantity == 2:
        strong_ratio = next((c for c in alternates if c.ratio_value and ratio_ok), None)
        if strong_ratio:
            add(primary.cover_label, 1)
            add(strong_ratio.cover_label, 1)
        else:
            add(primary.cover_label, 2)
        remaining = 0
    else:
        add(primary.cover_label, min(2, remaining))
        remaining -= min(2, remaining)
        if remaining > 0 and alternates:
            alt = alternates[0]
            add(alt.cover_label, 1)
            remaining -= 1
        ratio_alt = next((c for c in alternates if c.ratio_value and ratio_ok), None)
        while remaining > 0 and ratio_alt:
            add(ratio_alt.cover_label, min(2, remaining))
            remaining -= min(2, remaining)
        while remaining > 0:
            add(primary.cover_label, 1)
            remaining -= 1

    rows: list[CoverPurchasePlanRow] = []
    for c in usable:
        qty = allocations.get(c.cover_label, 0)
        if qty <= 0:
            continue
        codes: list[str] = []
        summary = ""
        if c.cover_label == primary.cover_label:
            codes.extend(["BASE_HOLD_COPY", "PRIMARY_COVER_LIQUIDITY"])
            summary = "Primary cover is usually the safest liquidity copy."
        elif c.ratio_value:
            codes.extend(["RATIO_OPPORTUNITY", "SCARCITY_PREMIUM"])
            summary = "Ratio variant flagged because scarcity signal is active."
        else:
            codes.append("VARIANT_DIVERSIFICATION")
            summary = "Secondary cover adds collector optionality without overexposure."
        rows.append(
            CoverPurchasePlanRow(
                cover_label=c.cover_label,
                recommended_quantity=qty,
                reason_codes=codes,
                reason_summary=summary,
            )
        )
    if not rows:
        rows.append(
            CoverPurchasePlanRow(
                cover_label=primary.cover_label,
                recommended_quantity=total_quantity,
                reason_codes=["BASE_HOLD_COPY", "PRIMARY_COVER_LIQUIDITY"],
                reason_summary="Allocated to primary cover for liquidity.",
            )
        )
    return rows


def build_quantity_reasoning(
    *,
    final_quantity: int,
    action: str,
    priority: float,
    confidence: float,
    reason_codes: list[str],
    signal_set: set[str],
) -> QuantityReasoningRead | None:
    if action in {"WATCH", "PASS"} or final_quantity <= 0:
        return QuantityReasoningRead(base_quantity=0, adjustments=[], final_quantity=0)

    base = 2 if priority >= 78.0 else 1
    adjustments: list[QuantityAdjustmentRow] = []
    running = base

    if confidence >= 0.78 and final_quantity > running:
        delta = min(1, final_quantity - running)
        if delta:
            adjustments.append(
                QuantityAdjustmentRow(
                    label="High recommendation confidence",
                    delta=delta,
                    reason_code="HIGH_CONFIDENCE",
                )
            )
            running += delta

    codes = {c.upper() for c in reason_codes}
    if ("SPEC_HEAT" in codes or "MARKET_DEMAND" in codes) and running < final_quantity:
        delta = min(1, final_quantity - running)
        if delta:
            adjustments.append(
                QuantityAdjustmentRow(
                    label="Strong market/spec signal",
                    delta=delta,
                    reason_code="MARKET_HEAT",
                )
            )
            running += delta

    if _ratio_allowed(signal_set=signal_set, reason_codes=reason_codes) and running < final_quantity:
        delta = min(1, final_quantity - running)
        if delta:
            adjustments.append(
                QuantityAdjustmentRow(
                    label="Variant opportunity detected",
                    delta=delta,
                    reason_code="RATIO_OPPORTUNITY",
                )
            )
            running += delta

    while running < final_quantity:
        delta = min(1, final_quantity - running)
        adjustments.append(
            QuantityAdjustmentRow(
                label="Priority band supports additional copy",
                delta=delta,
                reason_code="HIGH_CONFIDENCE",
            )
        )
        running += delta

    if final_quantity <= 2 and adjustments:
        return QuantityReasoningRead(base_quantity=base, adjustments=[], final_quantity=final_quantity)

    return QuantityReasoningRead(
        base_quantity=base,
        adjustments=adjustments,
        final_quantity=final_quantity,
    )


def build_signal_matrix(
    *,
    signal_set: set[str],
    reason_codes: list[str],
    collector_intel: CollectorSignificanceEnrichment | None,
    rationale: str,
    source_systems: list[str],
    owns_run: bool,
    foc_active: bool,
) -> SignalMatrixRead:
    codes = {c.upper() for c in reason_codes}
    blob = rationale.lower()
    return SignalMatrixRead(
        issue_launch=bool(signal_set.intersection({"NEW_NUMBER_ONE", "UNIVERSE_LAUNCH", "RELAUNCH"})),
        milestone_issue="MILESTONE_ISSUE" in codes
        or (collector_intel is not None and collector_intel.milestone_issue_number is not None),
        first_appearance=bool(signal_set.intersection({"FIRST_APPEARANCE", "FIRST_FULL_APPEARANCE", "FIRST_CAMEO"})),
        death_or_major_event="KEY_ISSUE" in codes or "origin" in blob,
        anniversary_legacy=any(
            t in blob for t in ("anniversary", "legacy numbering", "years of")
        ),
        creator_significance="CREATOR_SIGNIFICANCE" in codes or "CREATOR_HEAT" in codes,
        homage_cover="HOMAGE_TRIBUTE" in codes,
        franchise_strength="FRANCHISE_STRENGTH" in codes or "HISTORICAL_FRANCHISE" in codes,
        active_collector_audience="COLLECTOR_AUDIENCE" in codes,
        ratio_variant_opportunity=_ratio_allowed(signal_set=signal_set, reason_codes=reason_codes),
        market_heat="SPEC_HEAT" in codes or "MARKET_DEMAND" in codes,
        user_profile_match="COLLECTOR_CONTINUITY" in codes or "v2" in blob or "profile" in blob,
        pull_list_relevance="P52_PULL_LIST" in source_systems,
        not_in_inventory=not owns_run and ("inventory" in blob or "acquisition" in blob or "forward" in blob),
        foc_window=foc_active or "FOC_URGENCY" in codes or "foc" in blob,
    )


def build_score_breakdown(
    breakdown: CollectorSignificanceScoreBreakdown | None,
    *,
    priority: float,
) -> list[ScoreBreakdownRow]:
    if breakdown is None:
        return [
            ScoreBreakdownRow(label="Priority (composite)", points=round(priority, 1), max_points=100.0),
        ]

    def row(label: str, points: float, max_pts: float) -> ScoreBreakdownRow:
        if points <= 0 and max_pts <= 0:
            return ScoreBreakdownRow(label=label, not_available=True)
        return ScoreBreakdownRow(label=label, points=round(points, 1), max_points=max_pts)

    return [
        row("Milestone", breakdown.milestone_score * 1.25, 22.0),
        row("Creator", breakdown.creator_score * 1.2, 18.0),
        row("Homage", breakdown.homage_score * 1.2, 12.0),
        row("Franchise", breakdown.franchise_score * 0.42, 15.0),
        row("Publisher", breakdown.publisher_score * 0.38, 12.0),
        row("Audience", breakdown.audience_score, 5.5),
        row("Market demand", breakdown.historical_demand_score * 0.32, 8.0),
        row("Continuity", breakdown.continuity_score * 0.28, 6.0),
        row("Collector boost", breakdown.ranking_boost, 22.0),
    ]


def normalize_top_reasons(
    *,
    reason_codes: list[str],
    reason_summary: list[str],
    collector_intel: CollectorSignificanceEnrichment | None,
    rationale: str,
) -> list[str]:
    seen_norm: set[str] = set()
    bullets: list[str] = []

    def add(text: str) -> None:
        clean = text.strip().rstrip(".")
        if not clean or len(clean) < 4:
            return
        norm = clean.lower()
        if norm in seen_norm:
            return
        if any(
            norm in other or other in norm
            for other in seen_norm
            if len(other) > 12
        ):
            return
        seen_norm.add(norm)
        bullets.append(f"{clean}.")

    code_to_bullet = {
        "MILESTONE_ISSUE": "Milestone issue detected.",
        "FRANCHISE_STRENGTH": "Strong franchise collector base.",
        "HISTORICAL_FRANCHISE": "Historical franchise relevance.",
        "RATIO_OPPORTUNITY": "Ratio or variant opportunity present.",
        "SPEC_HEAT": "Market or spec heat is elevated.",
        "COLLECTOR_AUDIENCE": "Active collector audience match.",
        "CREATOR_SIGNIFICANCE": "Notable creator significance.",
        "HOMAGE_TRIBUTE": "Homage or tribute cover signal.",
        "FOC_URGENCY": "FOC window is active.",
        "MULTI_SOURCE": "Multiple intelligence systems agree.",
        "COLLECTOR_CONTINUITY": "Matches your collected run strategy.",
        "FIRST_APPEARANCE": "First appearance signal.",
        "KEY_ISSUE": "Key issue signal.",
    }
    for code in reason_codes:
        add(code_to_bullet.get(code, ""))

    if collector_intel is not None:
        for line in collector_intel.investment_thesis:
            if line.lower().startswith("why this matters"):
                continue
            add(line)

    skip_fragments = (
        "franchise strength",
        "foc window",
        "not in inventory",
        "core publisher",
        "historical series",
        "resolved conflicting",
    )
    for line in reason_summary:
        low = line.lower()
        if any(frag in low for frag in skip_fragments):
            continue
        add(line)

    if len(bullets) < 2 and rationale:
        for part in re.split(r"[.;]\s+", rationale):
            if len(bullets) >= 5:
                break
            low = part.lower()
            if any(frag in low for frag in skip_fragments):
                continue
            add(part)

    return bullets[:5]


def decision_headline_total(action: str, quantity: int) -> str:
    if action == "BUY_AGGRESSIVE":
        return f"BUY {quantity} TOTAL" if quantity > 1 else "BUY AGGRESSIVE"
    if action == "BUY":
        return f"BUY {quantity} TOTAL" if quantity != 1 else "BUY 1 TOTAL"
    if action == "WATCH":
        return "WATCH"
    return "PASS"


def strategy_allocation_hint(strategy: str, quantity: int, action: str) -> str | None:
    if action in {"WATCH", "PASS"} or quantity <= 0:
        return "Monitor — no purchase allocation."
    if strategy == "SELL_ONE_KEEP_ONE" and quantity >= 3:
        sell = max(1, quantity // 2)
        keep = quantity - sell
        return f"Sell {sell} / Keep {keep}"
    if strategy == "FLIP" and quantity >= 2:
        return f"Flip {max(1, quantity - 1)} / Hold 1"
    if strategy == "LONG_TERM_HOLD":
        return f"Hold all {quantity}"
    return None
