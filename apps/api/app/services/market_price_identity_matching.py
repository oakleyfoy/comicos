"""P68-04 Price matching / identity resolution."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.market_pricing_engine import P68MarketPriceObservation
from app.services.printing_intelligence import PRINTING_KIND_FIRST, PRINTING_KIND_FACSIMILE


@dataclass(frozen=True)
class IdentityTarget:
    title: str
    publisher: str
    issue_number: str
    variant_label: str | None
    printing_number: int | None
    printing_kind: str | None
    raw_or_graded: str
    grade: str | None


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def score_observation_match(obs: P68MarketPriceObservation, target: IdentityTarget) -> tuple[float, str | None, str | None, list[str]]:
    warnings: list[str] = []
    if _norm(obs.publisher) != _norm(target.publisher) and target.publisher:
        return 0.0, None, "publisher_mismatch", warnings
    if _norm(obs.issue_number) != _norm(target.issue_number) and target.issue_number:
        return 0.0, None, "issue_number_mismatch", warnings
    title_score = 1.0 if _norm(obs.title) in _norm(target.title) or _norm(target.title) in _norm(obs.title) else 0.6
    if title_score < 0.7:
        return 0.0, None, "title_mismatch", warnings

    obs_pk = obs.printing_number
    tgt_pk = target.printing_number
    obs_kind = obs.printing_kind or PRINTING_KIND_FIRST
    tgt_kind = target.printing_kind or PRINTING_KIND_FIRST
    if obs_kind != tgt_kind:
        if obs_kind == PRINTING_KIND_FACSIMILE or tgt_kind == PRINTING_KIND_FACSIMILE:
            return 0.0, None, "facsimile_identity_blocked", warnings
        if obs_pk != tgt_pk:
            warnings.append("printing_number_mismatch")
            return 0.0, None, "printing_mismatch", warnings

    if obs.raw_or_graded != target.raw_or_graded:
        warnings.append("raw_graded_split")
        if obs.raw_or_graded == "graded" and target.raw_or_graded == "raw":
            return 0.0, None, "raw_vs_graded_without_normalization", warnings

    if obs.variant_label and target.variant_label and _norm(obs.variant_label) != _norm(target.variant_label):
        return 0.0, None, "variant_label_mismatch", warnings

    score = min(1.0, title_score + 0.2)
    reason = "publisher_issue_title_match"
    if warnings:
        reason = f"{reason};{';'.join(warnings)}"
    return score, reason, None, warnings
