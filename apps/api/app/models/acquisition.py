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

# Placeholder catalog status (P98 placeholder issues phase).
CATALOG_STATUS_PLACEHOLDER = "PLACEHOLDER"
CATALOG_STATUS_MATCHED = "MATCHED"
CATALOG_STATUS_LINKED = "LINKED"
CATALOG_STATUSES = (CATALOG_STATUS_PLACEHOLDER, CATALOG_STATUS_MATCHED, CATALOG_STATUS_LINKED)


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


class AcquisitionPlaceholderIssue(SQLModel, table=True):
    """A book added to an acquisition that does not yet exist in the catalog.

    Each placeholder row holds the freetext identity the collector typed in.
    One placeholder spawns ``quantity`` child ``InventoryCopy`` rows (via
    ``InventoryCopy.placeholder_issue_id``) so cost allocation works the same as
    catalog-backed copies. ``catalog_issue_id`` stays null until a future merge
    links it to a real catalog issue.
    """

    __tablename__ = "acquisition_placeholder_issue"
    __table_args__ = (
        SAIndex("ix_acq_placeholder_acquisition_id", "acquisition_id"),
        SAIndex("ix_acq_placeholder_user_id", "user_id"),
        SAIndex("ix_acq_placeholder_catalog_status", "catalog_status"),
    )

    id: int | None = Field(default=None, primary_key=True)
    acquisition_id: int = Field(foreign_key="acquisitions.id", nullable=False)
    user_id: int = Field(foreign_key="user.id", nullable=False)
    title: str = Field(max_length=500, nullable=False)
    issue_number: str = Field(default="", max_length=64, nullable=False)
    publisher: str | None = Field(default=None, max_length=255, nullable=True)
    quantity: int = Field(default=1, nullable=False)
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    catalog_status: str = Field(default=CATALOG_STATUS_PLACEHOLDER, max_length=20, nullable=False)
    catalog_issue_id: int | None = Field(
        default=None,
        foreign_key="catalog_issue.id",
        nullable=True,
        index=True,
    )
    comicvine_volume_id: int | None = Field(default=None, nullable=True, index=True)
    source_volume_id: int | None = Field(default=None, nullable=True, index=True)
    source_issue_id: str | None = Field(default=None, max_length=64, nullable=True)
    tree_linked: bool = Field(default=False, nullable=False)
    variant_label: str | None = Field(default=None, max_length=128, nullable=True)
    cover_type: str | None = Field(default=None, max_length=64, nullable=True)
    printing: str | None = Field(default=None, max_length=64, nullable=True)
    ratio_variant: str | None = Field(default=None, max_length=64, nullable=True)
    barcode: str | None = Field(default=None, max_length=64, nullable=True)
    cover_artist: str | None = Field(default=None, max_length=255, nullable=True)
    raw_variant_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
