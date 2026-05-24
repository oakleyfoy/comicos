from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DuplicateReviewStatus = Literal["pending", "confirmed_duplicate", "not_duplicate"]


class DuplicateCandidateReviewCreate(BaseModel):
    metadata_identity_key: str = Field(min_length=1, max_length=1024)
    review_status: Literal["confirmed_duplicate", "not_duplicate"]
    notes: str | None = Field(default=None, max_length=8192)


class DuplicateCandidateNotesUpdate(BaseModel):
    metadata_identity_key: str = Field(min_length=1, max_length=1024)
    notes: str | None = Field(..., max_length=8192)

class DuplicateCandidateReviewRead(BaseModel):
    metadata_identity_key: str
    review_status: DuplicateReviewStatus
    notes: str | None
    reviewed_by_user_id: int | None
    reviewed_by_email: str | None
    reviewed_at: datetime | None
    created_at: datetime
