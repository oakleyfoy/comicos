"""Collector ratio-variant strategy defaults and profile loading."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from sqlmodel import Session, select

from app.models.purchase_profile import PurchasePreference
from app.schemas.recommendation_decision import SignalMatrixRead
from app.services.recommendation_intelligence_enrichment import (
    CollectorSignificanceEnrichment,
    CollectorSignificanceScoreBreakdown,
)

RatioVariantStrategy = Literal["avoid", "conservative", "balanced", "aggressive"]

_DEFAULT_STRATEGY: RatioVariantStrategy = "conservative"
_RATIO_LABEL = re.compile(r"1\s*:\s*(\d+)", re.IGNORECASE)
_LOW_PRINT_PATTERN = re.compile(
    r"\b(low\s+print|limited\s+print|print\s+run|scarcity|sold\s+out|allocation)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CollectorRatioStrategySettings:
    ratio_variant_strategy: RatioVariantStrategy = "conservative"
    max_ratio_variant_price: float = 25.0
    high_ratio_exception_required: bool = True
    high_ratio_threshold: int = 50


def parse_ratio_from_label(cover_label: str) -> int | None:
    m = _RATIO_LABEL.search(cover_label or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def effective_ratio_value(candidate_ratio: int | None, cover_label: str) -> int | None:
    if candidate_ratio is not None and candidate_ratio > 0:
        return candidate_ratio
    return parse_ratio_from_label(cover_label)


def is_high_ratio(ratio: int | None, *, threshold: int) -> bool:
    if ratio is None:
        return False
    return ratio >= threshold


def is_moderate_ratio(ratio: int | None, *, threshold: int) -> bool:
    if ratio is None:
        return False
    return 10 <= ratio < threshold


def load_collector_ratio_strategy(session: Session, *, owner_user_id: int) -> CollectorRatioStrategySettings:
    row = session.exec(
        select(PurchasePreference).where(PurchasePreference.owner_user_id == owner_user_id)
    ).first()
    if row is None:
        return CollectorRatioStrategySettings()
    strategy = (getattr(row, "ratio_variant_strategy", None) or _DEFAULT_STRATEGY).strip().lower()
    if strategy not in {"avoid", "conservative", "balanced", "aggressive"}:
        strategy = _DEFAULT_STRATEGY
    return CollectorRatioStrategySettings(
        ratio_variant_strategy=strategy,  # type: ignore[arg-type]
        max_ratio_variant_price=float(getattr(row, "max_ratio_variant_price", 25.0) or 25.0),
        high_ratio_exception_required=bool(getattr(row, "high_ratio_exception_required", True)),
        high_ratio_threshold=int(getattr(row, "high_ratio_threshold", 50) or 50),
    )


def variant_signal_active(*, signal_set: set[str], reason_codes: list[str]) -> bool:
    """Catalog/key signals — not reason-code-only 'variant opportunity'."""
    if signal_set.intersection({"RATIO_VARIANT", "INCENTIVE_VARIANT", "VARIANT_HOT"}):
        return True
    codes = {c.upper() for c in reason_codes}
    return bool(codes.intersection({"SCARCITY", "FIRST_APPEARANCE", "KEY_ISSUE"}))


def has_exceptional_variant_signal(
    *,
    signal_matrix: SignalMatrixRead | None,
    score_breakdown: CollectorSignificanceScoreBreakdown | None,
    collector_intel: CollectorSignificanceEnrichment | None,
    confidence: float,
    rationale: str,
    owns_run: bool,
    pull_list_relevance: bool,
) -> bool:
    """At least 2 exceptional criteria; generic variant opportunity alone does not qualify."""
    checks = 0
    if signal_matrix is not None:
        if signal_matrix.first_appearance:
            checks += 1
        if signal_matrix.death_or_major_event:
            checks += 1
        if signal_matrix.market_heat and confidence >= 0.90:
            checks += 1
        if (
            signal_matrix.homage_cover
            and signal_matrix.franchise_strength
            and signal_matrix.active_collector_audience
        ):
            checks += 1
    if score_breakdown is not None:
        if score_breakdown.milestone_score >= 3.0:
            checks += 1
        if score_breakdown.creator_score >= 3.0:
            checks += 1
    elif collector_intel is not None:
        if collector_intel.milestone_bonus >= 3.0:
            checks += 1
        if collector_intel.creator_bonus >= 3.0:
            checks += 1
    if _LOW_PRINT_PATTERN.search(rationale or ""):
        checks += 1
    if owns_run or pull_list_relevance:
        checks += 1
    return checks >= 2
