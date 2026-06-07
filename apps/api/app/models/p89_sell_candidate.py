"""P89-01 Sell Candidate Intelligence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Index as SAIndex, Text, UniqueConstraint
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


P89_RECOMMENDATIONS = ("SELL_NOW", "HOLD", "GRADE_FIRST", "MONITOR")
P89_CONFIDENCE = ("HIGH", "MEDIUM", "LOW")
P89_STATUS = ("ACTIVE", "ARCHIVED")


class P89SellCandidate(SQLModel, table=True):
    __tablename__ = "p89_sell_candidate"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "inventory_copy_id", name="uq_p89_sell_candidate_copy"),
        SAIndex("ix_p89_sell_cand_owner_rec", "owner_user_id", "recommendation", "status"),
        SAIndex("ix_p89_sell_cand_owner_score", "owner_user_id", "sell_score", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    inventory_copy_id: int = Field(foreign_key="inventory_copy.id", nullable=False, index=True)
    recommendation: str = Field(max_length=16, nullable=False, index=True)
    sell_score: float = Field(default=0.0, nullable=False)
    hold_score: float = Field(default=0.0, nullable=False)
    grade_first_score: float = Field(default=0.0, nullable=False)
    monitor_score: float = Field(default=0.0, nullable=False)
    confidence: str = Field(default="MEDIUM", max_length=8, nullable=False, index=True)
    estimated_sale_value: float = Field(default=0.0, nullable=False)
    estimated_profit: float = Field(default=0.0, nullable=False)
    reason_summary: str = Field(default="", sa_column=Column(Text, nullable=False))
    reasons_json: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))  # type: ignore[name-defined]
    status: str = Field(default="ACTIVE", max_length=16, nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
