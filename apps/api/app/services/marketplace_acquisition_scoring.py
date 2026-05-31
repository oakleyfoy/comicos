from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from app.models.acquisition_opportunity import AcquisitionOpportunity
from app.models.marketplace_acquisition import MarketplaceAcquisitionCandidate


@dataclass(frozen=True)
class MarketplaceScoreResult:
    value_score: float
    recommendation: str
    rationale: str


def _money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def score_marketplace_candidate(session: Session, *, candidate_id: int) -> MarketplaceScoreResult:
    candidate = session.get(MarketplaceAcquisitionCandidate, candidate_id)
    if candidate is None:
        raise LookupError("Marketplace acquisition candidate not found.")

    total_price = _money(candidate.total_price)
    target_price: float | None = None
    estimated_fmv: float | None = None
    if candidate.acquisition_opportunity_id is not None:
        opp = session.get(AcquisitionOpportunity, candidate.acquisition_opportunity_id)
        if opp is not None:
            target_price = _money(opp.target_price)
            estimated_fmv = _money(opp.estimated_fmv)

    if total_price is None:
        return MarketplaceScoreResult(
            value_score=40.0,
            recommendation="WATCH",
            rationale="No listing price captured; default to watch.",
        )

    if target_price is not None and total_price <= target_price:
        gap = target_price - total_price
        value_score = min(100.0, round(70.0 + min(30.0, gap / max(target_price, 1.0) * 100.0), 1))
        return MarketplaceScoreResult(
            value_score=value_score,
            recommendation="BUY",
            rationale=f"Total price ${total_price:.2f} is at or below target ${target_price:.2f}.",
        )

    if estimated_fmv is not None and total_price > estimated_fmv:
        return MarketplaceScoreResult(
            value_score=15.0,
            recommendation="PASS",
            rationale=f"Total price ${total_price:.2f} exceeds estimated FMV ${estimated_fmv:.2f}.",
        )

    if estimated_fmv is not None and total_price <= estimated_fmv:
        return MarketplaceScoreResult(
            value_score=55.0,
            recommendation="WATCH",
            rationale=f"Total price ${total_price:.2f} is within estimated FMV ${estimated_fmv:.2f}; monitor for target.",
        )

    return MarketplaceScoreResult(
        value_score=45.0,
        recommendation="WATCH",
        rationale="No target price or FMV available; advisory watch.",
    )
