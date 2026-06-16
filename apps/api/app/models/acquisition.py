"""P98 Acquisition model.

An Acquisition (a.k.a. Purchase) is the parent record that every manually
entered inventory copy must belong to. The acquisition captures where the books
came from (source/seller), what was paid (total/shipping/tax), and how cost
basis is allocated across the child inventory copies.

See also `app.models.asset_ledger.InventoryCopy.acquisition_id`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Column, DateTime, Index as SAIndex, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Acquisition source/type (P98-01).
ACQUISITION_TYPE_FACEBOOK = "FACEBOOK"
ACQUISITION_TYPE_EBAY = "EBAY"
ACQUISITION_TYPE_WHATNOT = "WHATNOT"
ACQUISITION_TYPE_LCS = "LCS"
ACQUISITION_TYPE_CONVENTION = "CONVENTION"
ACQUISITION_TYPE_FRIEND = "FRIEND"
ACQUISITION_TYPE_GIFT = "GIFT"
ACQUISITION_TYPE_INHERITED = "INHERITED"
ACQUISITION_TYPE_UNKNOWN = "UNKNOWN"
ACQUISITION_TYPE_OTHER = "OTHER"

ACQUISITION_TYPES = (
    ACQUISITION_TYPE_FACEBOOK,
    ACQUISITION_TYPE_EBAY,
    ACQUISITION_TYPE_WHATNOT,
    ACQUISITION_TYPE_LCS,
    ACQUISITION_TYPE_CONVENTION,
    ACQUISITION_TYPE_FRIEND,
    ACQUISITION_TYPE_GIFT,
    ACQUISITION_TYPE_INHERITED,
    ACQUISITION_TYPE_UNKNOWN,
    ACQUISITION_TYPE_OTHER,
)

# Acquisition lifecycle status (P98-01).
ACQUISITION_STATUS_OPEN = "OPEN"
ACQUISITION_STATUS_COMPLETE = "COMPLETE"
ACQUISITION_STATUSES = (ACQUISITION_STATUS_OPEN, ACQUISITION_STATUS_COMPLETE)

# Cost allocation modes (P98-12). FMV weighted is reserved for the future.
ALLOCATION_MODE_EVEN = "EVEN"
ALLOCATION_MODE_MANUAL = "MANUAL"
ALLOCATION_MODE_FMV_WEIGHTED = "FMV_WEIGHTED"
ALLOCATION_MODES = (
    ALLOCATION_MODE_EVEN,
    ALLOCATION_MODE_MANUAL,
    ALLOCATION_MODE_FMV_WEIGHTED,
)

LEGACY_ACQUISITION_SELLER_NAME = "Legacy / Unknown Source"


class Acquisition(SQLModel, table=True):
    __tablename__ = "acquisitions"
    __table_args__ = (
        SAIndex("ix_acquisitions_user_id", "user_id"),
        SAIndex("ix_acquisitions_acquisition_type", "acquisition_type"),
        SAIndex("ix_acquisitions_purchase_date", "purchase_date"),
        SAIndex("ix_acquisitions_status", "status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False)
    acquisition_type: str = Field(default=ACQUISITION_TYPE_UNKNOWN, max_length=40, nullable=False)
    purchase_date: date | None = Field(default=None, nullable=True)
    seller_name: str | None = Field(default=None, max_length=255, nullable=True)
    seller_username: str | None = Field(default=None, max_length=255, nullable=True)
    total_paid: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(12, 2), nullable=False))
    shipping_paid: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(12, 2), nullable=False))
    tax_paid: Decimal = Field(default=Decimal("0.00"), sa_column=Column(Numeric(12, 2), nullable=False))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    expected_book_count: int | None = Field(default=None, nullable=True)
    actual_book_count: int = Field(default=0, nullable=False)
    status: str = Field(default=ACQUISITION_STATUS_OPEN, max_length=16, nullable=False)
    allocation_mode: str = Field(default=ALLOCATION_MODE_EVEN, max_length=16, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    @property
    def total_acquisition_cost(self) -> Decimal:
        """total_paid + shipping_paid + tax_paid (P98-12)."""
        return (
            (self.total_paid or Decimal("0.00"))
            + (self.shipping_paid or Decimal("0.00"))
            + (self.tax_paid or Decimal("0.00"))
        )
