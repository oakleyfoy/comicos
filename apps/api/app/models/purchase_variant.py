from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


PURCHASE_VARIANT_RECOMMENDATIONS = ("BUY", "WATCH", "AVOID")

PURCHASE_VARIANT_TYPES = (
    "COVER_A",
    "OPEN_ORDER",
    "INCENTIVE",
    "RATIO",
    "STORE_EXCLUSIVE",
    "UNKNOWN",
)


class PurchaseVariantRecommendation(SQLModel, table=True):
    __tablename__ = "purchase_variant_recommendation"
    __table_args__ = (
        SAIndex(
            "ix_purchase_var_rec_owner_release_variant",
            "owner_user_id",
            "release_id",
            "variant_id",
            "created_at",
            "id",
        ),
        SAIndex("ix_purchase_var_rec_owner_rec", "owner_user_id", "recommendation", "id"),
        SAIndex("ix_purchase_var_rec_owner_type", "owner_user_id", "variant_type", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    owner_user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    release_id: int = Field(foreign_key="release_issue.id", nullable=False, index=True)
    variant_id: int | None = Field(default=None, foreign_key="release_variant.id", nullable=True, index=True)
    cover_label: str = Field(default="", max_length=160, nullable=False)
    variant_type: str = Field(max_length=32, nullable=False)
    recommendation: str = Field(max_length=16, nullable=False)
    confidence_score: float = Field(nullable=False)
    rationale: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
