from __future__ import annotations

from pydantic import BaseModel, Field


class EbayAccountDeletionChallengeResponse(BaseModel):
    challengeResponse: str = Field(description="SHA-256 hex digest per eBay endpoint verification spec.")


class EbayAccountDeletionAckResponse(BaseModel):
    status: str = "ok"
    noop_action: str = "acknowledged_no_user_data_retained"
