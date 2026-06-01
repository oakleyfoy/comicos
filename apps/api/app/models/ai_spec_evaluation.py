from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


AI_SPEC_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")
AI_SPEC_EVALUATION_STATUSES = ("SUCCESS", "FALLBACK")


class AISpecEvaluation(SQLModel, table=True):
    __tablename__ = "ai_spec_evaluation"
    __table_args__ = (
        UniqueConstraint(
            "owner_user_id",
            "spec_input_id",
            "baseline_score_id",
            "prompt_version",
            name="uq_ai_spec_eval_owner_input_baseline_prompt",
        ),
        SAIndex("ix_ai_spec_eval_owner_created", "owner_user_id", "created_at", "id"),
        SAIndex("ix_ai_spec_eval_owner_score", "owner_user_id", "ai_score", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    spec_input_id: int = Field(foreign_key="spec_input.id", nullable=False, index=True)
    baseline_score_id: int = Field(foreign_key="spec_baseline_score.id", nullable=False, index=True)
    ai_score: float = Field(default=0.0, nullable=False, index=True)
    ai_confidence: float = Field(default=0.0, nullable=False)
    risk_level: str = Field(default="MEDIUM", max_length=16, nullable=False, index=True)
    ai_rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    model_name: str = Field(default="FALLBACK", max_length=64, nullable=False)
    prompt_version: str = Field(default="P60-03-v1", max_length=32, nullable=False, index=True)
    evaluation_status: str = Field(default="FALLBACK", max_length=16, nullable=False, index=True)
    prompt_inputs_hash: str = Field(default="", max_length=64, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
