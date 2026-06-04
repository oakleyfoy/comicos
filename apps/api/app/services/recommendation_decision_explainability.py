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
    SuppressedVariantRow,
)
from app.services.collector_ratio_strategy import (
    CollectorRatioStrategySettings,
    effective_ratio_value,
    has_exceptional_variant_signal,
    is_high_ratio,
    is_moderate_ratio,
    parse_ratio_from_label,
    variant_signal_active,
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


def _suppress_high_ratio(
    candidates: list[_CoverCandidate],
    *,
    threshold: int,
    exceptional: bool,
    allocated: dict[str, int],
) -> list[SuppressedVariantRow]:
    suppressed: list[SuppressedVariantRow] = []
    for c in candidates:
        ratio = effective_ratio_value(c.ratio_value, c.cover_label)
        if not is_high_ratio(ratio, threshold=threshold):
            continue
        if allocated.get(c.cover_label, 0) > 0:
            continue
        if exceptional and allocated.get(c.cover_label, 0) == 0:
            continue
        suppressed.append(
            SuppressedVariantRow(
                cover_label=c.cover_label,
                reason_code="HIGH_RATIO_REQUIRES_EXCEPTION",
                reason_summary=(
                    "High-ratio variants are suppressed by conservative collector settings "
                    "unless exceptional signals are present."
                ),
            )
        )
    return suppressed


def _allocate_conservative_quantity(
    total_quantity: int,
    *,
    primary: _CoverCandidate,
    non_ratio_alternates: list[_CoverCandidate],
    moderate_ratios: list[_CoverCandidate],
    variant_signal_active: bool,
    exceptional: bool,
    threshold: int,
    strategy: str,
) -> dict[str, int]:
    allocations: dict[str, int] = {}

    def add(label: str, qty: int) -> None:
        if qty <= 0:
            return
        allocations[label] = allocations.get(label, 0) + qty

    if strategy == "avoid":
        add(primary.cover_label, total_quantity)
        return allocations

    best_alt = non_ratio_alternates[0] if non_ratio_alternates else None
    if total_quantity <= 1:
        add(primary.cover_label, total_quantity)
        return allocations

    if total_quantity == 2:
        add(primary.cover_label, 2)
        return allocations

    if total_quantity == 3:
        if best_alt is not None and variant_signal_active:
            add(primary.cover_label, 2)
            add(best_alt.cover_label, 1)
        else:
            add(primary.cover_label, 3)
        return allocations

    if total_quantity == 4:
        if best_alt is not None:
            add(primary.cover_label, 3)
            add(best_alt.cover_label, 1)
        else:
            add(primary.cover_label, 4)
        return allocations

    # BUY 5+: mostly Cover A
    cover_a_qty = max(1, total_quantity - 1)
    add(primary.cover_label, cover_a_qty)
    remaining = total_quantity - cover_a_qty
    if remaining > 0 and best_alt is not None:
        add(best_alt.cover_label, 1)
        remaining -= 1
    if remaining > 0:
        add(primary.cover_label, remaining)

    primary_qty = allocations.get(primary.cover_label, 0)
    if variant_signal_active and moderate_ratios:
        mod = moderate_ratios[0]
        ratio = effective_ratio_value(mod.ratio_value, mod.cover_label)
        if is_moderate_ratio(ratio, threshold=threshold):
            add(mod.cover_label, 1)
            if allocations.get(mod.cover_label, 0) > primary_qty:
                allocations[mod.cover_label] = primary_qty
            if primary_qty >= 2 and allocations.get(primary.cover_label, 0) > 0:
                allocations[primary.cover_label] = max(1, allocations[primary.cover_label] - 1)

    if exceptional and moderate_ratios:
        for mod in moderate_ratios:
            ratio = effective_ratio_value(mod.ratio_value, mod.cover_label)
            if is_high_ratio(ratio, threshold=threshold):
                if sum(
                    allocations.get(c.cover_label, 0)
                    for c in moderate_ratios
                    if is_high_ratio(effective_ratio_value(c.ratio_value, c.cover_label), threshold=threshold)
                ) >= 1:
                    break
                add(mod.cover_label, 1)
                if allocations.get(mod.cover_label, 0) > primary_qty:
                    allocations[mod.cover_label] = min(1, primary_qty)
                break

    # Cap: ratio never exceeds Cover A under conservative
    primary_qty = allocations.get(primary.cover_label, 0)
    for label, qty in list(allocations.items()):
        if label == primary.cover_label:
            continue
        cand = next((c for c in moderate_ratios + non_ratio_alternates if c.cover_label == label), None)
        if cand is None:
            continue
        ratio = effective_ratio_value(cand.ratio_value, cand.cover_label)
        if ratio is not None and qty > primary_qty:
            allocations[label] = min(qty, primary_qty)
        if is_high_ratio(ratio, threshold=threshold) and qty > 1:
            allocations[label] = 1

    # Reconcile total
    current = sum(allocations.values())
    while current > total_quantity:
        for label in sorted(allocations.keys(), key=lambda x: (x != primary.cover_label, x)):
            if allocations[label] > 0 and label != primary.cover_label:
                allocations[label] -= 1
                current -= 1
                if current <= total_quantity:
                    break
        if current > total_quantity and allocations.get(primary.cover_label, 0) > 1:
            allocations[primary.cover_label] -= 1
            current -= 1
    while current < total_quantity:
        allocations[primary.cover_label] = allocations.get(primary.cover_label, 0) + 1
        current += 1

    if sum(allocations.values()) != total_quantity:
        allocations = {primary.cover_label: total_quantity}

    return allocations


def build_cover_purchase_plan(
    *,
    total_quantity: int,
    action: str,
    candidates: list[_CoverCandidate],
    signal_set: set[str],
    reason_codes: list[str],
    strategy_settings: CollectorRatioStrategySettings | None = None,
    exceptional_variant_signal: bool = False,
) -> tuple[list[CoverPurchasePlanRow], list[SuppressedVariantRow]]:
    settings = strategy_settings or CollectorRatioStrategySettings()
    threshold = settings.high_ratio_threshold
    strategy = settings.ratio_variant_strategy

    if action in {"WATCH", "PASS"} or total_quantity <= 0:
        rows = [
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
        return rows, []

    incentive_ok = _incentive_allowed(signal_set=signal_set, reason_codes=reason_codes)
    specialty_ok = _specialty_allowed(signal_set=signal_set, reason_codes=reason_codes)
    var_active = variant_signal_active(signal_set=signal_set, reason_codes=reason_codes)

    usable: list[_CoverCandidate] = []
    for c in candidates:
        if c.is_incentive and not incentive_ok:
            continue
        if c.is_specialty and not specialty_ok:
            continue
        usable.append(c)
    if not usable:
        usable = [_primary_candidate(candidates)]

    primary = _primary_candidate(usable)
    non_ratio = [
        c
        for c in usable
        if c.cover_label != primary.cover_label
        and effective_ratio_value(c.ratio_value, c.cover_label) is None
        and not c.is_incentive
    ]
    non_ratio.sort(key=lambda c: -c.strength)
    ratio_candidates = [
        c for c in usable if c.cover_label != primary.cover_label and effective_ratio_value(c.ratio_value, c.cover_label)
    ]
    ratio_candidates.sort(key=lambda c: effective_ratio_value(c.ratio_value, c.cover_label) or 999)

    exceptional = exceptional_variant_signal
    if settings.high_ratio_exception_required and not exceptional:
        ratio_candidates = [
            c
            for c in ratio_candidates
            if not is_high_ratio(effective_ratio_value(c.ratio_value, c.cover_label), threshold=threshold)
        ]

    moderate_ratios = [
        c
        for c in ratio_candidates
        if is_moderate_ratio(effective_ratio_value(c.ratio_value, c.cover_label), threshold=threshold)
    ]

    allocations = _allocate_conservative_quantity(
        total_quantity,
        primary=primary,
        non_ratio_alternates=non_ratio,
        moderate_ratios=moderate_ratios if var_active else [],
        variant_signal_active=var_active,
        exceptional=exceptional,
        threshold=threshold,
        strategy=strategy,
    )

    suppressed = _suppress_high_ratio(
        candidates,
        threshold=threshold,
        exceptional=exceptional,
        allocated=allocations,
    )
    for c in candidates:
        ratio = effective_ratio_value(c.ratio_value, c.cover_label)
        if ratio is None:
            continue
        if allocations.get(c.cover_label, 0) > 0:
            continue
        if is_high_ratio(ratio, threshold=threshold):
            if not any(s.cover_label == c.cover_label for s in suppressed):
                suppressed.append(
                    SuppressedVariantRow(
                        cover_label=c.cover_label,
                        reason_code="HIGH_RATIO_REQUIRES_EXCEPTION",
                        reason_summary=(
                            "High-ratio variants are suppressed by conservative collector settings "
                            "unless exceptional signals are present."
                        ),
                    )
                )

    rows: list[CoverPurchasePlanRow] = []
    for label, qty in sorted(allocations.items(), key=lambda item: (-item[1], item[0])):
        if qty <= 0:
            continue
        cand = next((c for c in usable if c.cover_label == label), primary)
        ratio = effective_ratio_value(cand.ratio_value, cand.cover_label)
        if label == primary.cover_label:
            codes = ["BASE_HOLD_COPY", "PRIMARY_COVER_LIQUIDITY"]
            summary = "Primary cover is usually the safest liquidity copy."
        elif ratio is not None:
            codes = ["RATIO_OPPORTUNITY", "SCARCITY_PREMIUM"]
            summary = "Ratio variant included with conservative cap."
        else:
            codes = ["VARIANT_DIVERSIFICATION"]
            summary = "Secondary cover adds collector optionality without overexposure."
        rows.append(
            CoverPurchasePlanRow(
                cover_label=label,
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
    return rows, suppressed


def build_quantity_reasoning(
    *,
    final_quantity: int,
    action: str,
    priority: float,
    confidence: float,
    reason_codes: list[str],
    signal_set: set[str],
    cover_plan: list[CoverPurchasePlanRow] | None = None,
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

    plan = cover_plan or []

    def _row_is_variant(row: CoverPurchasePlanRow) -> bool:
        if row.recommended_quantity <= 0:
            return False
        if parse_ratio_from_label(row.cover_label) is not None:
            return True
        codes = {c.upper() for c in row.reason_codes}
        return bool(codes.intersection({"RATIO_OPPORTUNITY", "SCARCITY_PREMIUM"}))

    variant_copies = sum(row.recommended_quantity for row in plan if _row_is_variant(row))
    non_primary_variant = sum(
        row.recommended_quantity
        for row in plan
        if row.recommended_quantity > 0 and "PRIMARY_COVER_LIQUIDITY" not in row.reason_codes
    )
    if variant_copies > 0 and running < final_quantity:
        delta = min(variant_copies, final_quantity - running)
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
        label = (
            "Priority band supports additional Cover A liquidity copy"
            if non_primary_variant == 0
            else "Priority band supports additional copy"
        )
        adjustments.append(
            QuantityAdjustmentRow(
                label=label,
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
