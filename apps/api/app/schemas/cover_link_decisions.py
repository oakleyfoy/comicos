from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

CoverLinkDecisionType = Literal["approved_link", "rejected_link", "needs_review"]
CoverLinkRelationshipType = Literal[
    "same_cover",
    "same_issue",
    "duplicate_scan",
    "variant_family",
    "unrelated",
]
CoverLinkDecisionState = Literal["active", "superseded", "reverted"]
CoverLinkDecisionSource = Literal["human", "system_seeded"]


class CoverImageLinkDecisionCreate(BaseModel):
    source_cover_image_id: int = Field(ge=1)
    candidate_cover_image_id: int = Field(ge=1)
    source_match_candidate_id: int | None = Field(default=None, ge=1)
    decision_type: CoverLinkDecisionType
    relationship_type: CoverLinkRelationshipType
    decision_reason: str | None = Field(default=None, max_length=4000)


class CoverImageLinkDecisionRead(BaseModel):
    id: int
    source_cover_image_id: int
    candidate_cover_image_id: int
    pair_key: str
    source_match_candidate_id: int | None = None
    decision_type: CoverLinkDecisionType
    relationship_type: CoverLinkRelationshipType
    decision_state: CoverLinkDecisionState
    reviewer_user_id: int | None = None
    reviewer_user_email: str | None = None
    decision_reason: str | None = None
    decision_source: CoverLinkDecisionSource
    created_at: datetime
    updated_at: datetime
    reverted_at: datetime | None = None
    superseded_by_decision_id: int | None = None

