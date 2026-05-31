from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ExitCandidateReason = Literal[
    "DUPLICATE",
    "PROFITABLE",
    "GRADED",
    "OVEREXPOSED",
    "CAPITAL_RECOVERY",
    "MULTIPLE_SIGNALS",
]


class ExitCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    inventory_item_id: int
    candidate_score: float
    confidence_score: float
    estimated_fmv: float
    acquisition_cost: float
    unrealized_gain: float
    candidate_reason: ExitCandidateReason
    created_at: str
    title: str = ""
    issue_number: str = ""
    publisher: str = ""


class ExitCandidateListRead(BaseModel):
    items: list[ExitCandidateRead]
    total_items: int
    limit: int
    offset: int


class ExitCandidateSummaryRead(BaseModel):
    total_candidates: int
    duplicate_count: int
    profitable_count: int
    graded_count: int
    overexposed_count: int
    capital_recovery_count: int
    multiple_signals_count: int
    total_unrealized_gain: float
    average_candidate_score: float
