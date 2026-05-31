from __future__ import annotations

import re
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.acquisition_opportunity import AcquisitionOpportunity
from app.models.marketplace_acquisition import MarketplaceAcquisitionCandidate
from app.models.want_list import WantListItem
from app.services.acquisition_opportunities import latest_acquisition_opportunity_rows
from app.services.collection_gaps import latest_collection_gap_rows

_NORM_RE = re.compile(r"[^a-z0-9]+")


def _norm(value: str | None) -> str:
    return _NORM_RE.sub("", (value or "").strip().lower())


@dataclass(frozen=True)
class MarketplaceMatchResult:
    acquisition_opportunity_id: int | None
    match_confidence: float
    rationale: str


def _confidence_label(score: float) -> str:
    if score >= 0.85:
        return "high"
    if score >= 0.55:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def _score_opportunity_match(
    *,
    candidate: MarketplaceAcquisitionCandidate,
    opportunity: AcquisitionOpportunity,
) -> tuple[float, str]:
    c_series = _norm(candidate.series_name)
    c_issue = _norm(candidate.issue_number)
    o_series = _norm(opportunity.series_name)
    o_issue = _norm(opportunity.issue_number)
    c_title = _norm(candidate.title)

    if c_series and c_issue and c_series == o_series and c_issue == o_issue:
        return 0.92, "Exact normalized series and issue match to acquisition opportunity."
    if c_series and c_issue and c_title and c_series in c_title and c_issue in c_title:
        if o_series == c_series and o_issue == c_issue:
            return 0.68, "Title text contains series and issue; matched acquisition opportunity."
    if c_series and o_series == c_series:
        return 0.35, "Series-only match to acquisition opportunity."
    return 0.0, ""


def _opportunity_for_series_issue(
    opportunities: dict[tuple[str, int | None], AcquisitionOpportunity],
    *,
    series_name: str,
    issue_number: str,
) -> AcquisitionOpportunity | None:
    series = _norm(series_name)
    issue = _norm(issue_number)
    for opp in opportunities.values():
        if _norm(opp.series_name) == series and _norm(opp.issue_number) == issue:
            return opp
    return None


def match_candidate_to_opportunities(
    session: Session,
    *,
    owner_user_id: int,
    candidate_id: int,
) -> MarketplaceMatchResult:
    candidate = session.get(MarketplaceAcquisitionCandidate, candidate_id)
    if candidate is None or candidate.owner_user_id != owner_user_id:
        raise LookupError("Marketplace acquisition candidate not found.")

    opportunities = latest_acquisition_opportunity_rows(session, owner_user_id=owner_user_id)
    best_score = 0.0
    best_opp_id: int | None = None
    best_reason = "No match to acquisition opportunities."

    for opp in opportunities.values():
        score, reason = _score_opportunity_match(candidate=candidate, opportunity=opp)
        if score > best_score:
            best_score = score
            best_opp_id = int(opp.id or 0) or None
            best_reason = reason

    c_title = _norm(candidate.title)
    c_series = _norm(candidate.series_name)
    c_issue = _norm(candidate.issue_number)
    if c_title and c_series and c_issue and c_series in c_title and c_issue in c_title and best_score < 0.68:
        opp = _opportunity_for_series_issue(
            opportunities,
            series_name=candidate.series_name or "",
            issue_number=candidate.issue_number or "",
        )
        if opp is not None:
            best_score = max(best_score, 0.68)
            best_opp_id = int(opp.id or 0) or None
            best_reason = "Title text contains series and issue; matched acquisition opportunity."

    for gap in latest_collection_gap_rows(session, owner_user_id=owner_user_id).values():
        if not gap.issue_number:
            continue
        if _norm(gap.series_name) == c_series and _norm(gap.issue_number) == c_issue:
            opp = _opportunity_for_series_issue(
                opportunities,
                series_name=gap.series_name,
                issue_number=gap.issue_number,
            )
            if opp is not None:
                score, reason = _score_opportunity_match(candidate=candidate, opportunity=opp)
                if score >= best_score:
                    best_score = score
                    best_opp_id = int(opp.id or 0) or None
                    best_reason = f"Collection gap alignment. {reason or 'Matched opportunity.'}"

    want_items = session.exec(select(WantListItem).where(WantListItem.owner_user_id == owner_user_id)).all()
    for item in want_items:
        if item.status not in {"WANTED", "FOUND"}:
            continue
        if _norm(item.series_name) == c_series and _norm(item.issue_number) == c_issue:
            opp = _opportunity_for_series_issue(
                opportunities,
                series_name=item.series_name,
                issue_number=item.issue_number,
            )
            if opp is not None:
                score, reason = _score_opportunity_match(candidate=candidate, opportunity=opp)
                if score >= best_score:
                    best_score = score
                    best_opp_id = int(opp.id or 0) or None
                    best_reason = f"Want-list target alignment. {reason or 'Matched opportunity.'}"

    if best_score <= 0:
        return MarketplaceMatchResult(
            acquisition_opportunity_id=None,
            match_confidence=0.0,
            rationale="No match to opportunities, gaps, or want-list targets.",
        )
    return MarketplaceMatchResult(
        acquisition_opportunity_id=best_opp_id,
        match_confidence=round(best_score, 2),
        rationale=f"{best_reason} ({_confidence_label(best_score)} confidence).",
    )
