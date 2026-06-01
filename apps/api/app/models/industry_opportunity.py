from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


INDUSTRY_OPPORTUNITY_RISK_LEVELS = ("LOW", "MEDIUM", "HIGH")


class IndustryOpportunityScore(SQLModel, table=True):
    __tablename__ = "industry_opportunity_score"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "candidate_id", name="uq_industry_opportunity_owner_candidate"),
        SAIndex("ix_industry_opportunity_owner_score", "owner_user_id", "opportunity_score", "id"),
        SAIndex("ix_industry_opportunity_scan_run", "scan_run_id", "opportunity_score", "id"),
        SAIndex("ix_industry_opportunity_owner_risk", "owner_user_id", "risk_level", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    candidate_id: int = Field(foreign_key="industry_release_candidate.id", nullable=False, index=True)
    scan_run_id: int = Field(foreign_key="industry_release_scan_run.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    publisher_code: str = Field(max_length=32, nullable=False, index=True)
    publisher_name: str = Field(max_length=120, nullable=False)
    series_name: str = Field(max_length=200, nullable=False, index=True)
    issue_number: str = Field(max_length=32, nullable=False)
    opportunity_score: float = Field(default=0.0, nullable=False, index=True)
    confidence_score: float = Field(default=0.0, nullable=False)
    risk_level: str = Field(default="MEDIUM", max_length=16, nullable=False, index=True)
    rationale: str = Field(default="", sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
