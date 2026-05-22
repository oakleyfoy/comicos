from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Column, DateTime, Numeric, String
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Publisher(SQLModel, table=True):
    __tablename__ = "publisher"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=255)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ComicTitle(SQLModel, table=True):
    __tablename__ = "comic_title"

    id: int | None = Field(default=None, primary_key=True)
    publisher_id: int = Field(foreign_key="publisher.id", nullable=False, index=True)
    name: str = Field(index=True, max_length=255)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class ComicIssue(SQLModel, table=True):
    __tablename__ = "comic_issue"

    id: int | None = Field(default=None, primary_key=True)
    comic_title_id: int = Field(foreign_key="comic_title.id", nullable=False, index=True)
    issue_number: str = Field(max_length=50, nullable=False)
    cover_date: date | None = Field(default=None, nullable=True)
    release_date: date | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Variant(SQLModel, table=True):
    __tablename__ = "variant"

    id: int | None = Field(default=None, primary_key=True)
    comic_issue_id: int = Field(foreign_key="comic_issue.id", nullable=False, index=True)
    cover_name: str | None = Field(default=None, max_length=255)
    printing: str | None = Field(default=None, max_length=100)
    ratio: str | None = Field(default=None, max_length=100)
    variant_type: str | None = Field(default=None, max_length=100)
    cover_artist: str | None = Field(default=None, max_length=255)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class Order(SQLModel, table=True):
    __tablename__ = "customer_order"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    retailer: str = Field(max_length=255, nullable=False)
    order_date: date = Field(nullable=False)
    source_type: str | None = Field(default=None, max_length=100)
    shipping_amount: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    tax_amount: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    total_amount: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OrderItem(SQLModel, table=True):
    __tablename__ = "order_item"

    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="customer_order.id", nullable=False, index=True)
    variant_id: int = Field(foreign_key="variant.id", nullable=False, index=True)
    quantity: int = Field(nullable=False)
    raw_item_price: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    allocated_shipping: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    allocated_tax: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(12, 2), nullable=False, default=Decimal("0")),
    )
    all_in_unit_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class InventoryCopy(SQLModel, table=True):
    __tablename__ = "inventory_copy"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    order_item_id: int = Field(foreign_key="order_item.id", nullable=False, index=True)
    variant_id: int = Field(foreign_key="variant.id", nullable=False, index=True)
    copy_number: int = Field(nullable=False)
    acquisition_cost: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    condition_notes: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    grade_status: str = Field(default="raw", max_length=50, nullable=False)
    hold_status: str = Field(default="hold", max_length=50, nullable=False)
    current_fmv: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(12, 2), nullable=True),
    )
    star_rating: int | None = Field(default=None, nullable=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class InventoryFmvSnapshot(SQLModel, table=True):
    __tablename__ = "inventory_fmv_snapshot"

    id: int | None = Field(default=None, primary_key=True)
    inventory_copy_id: int = Field(
        foreign_key="inventory_copy.id",
        nullable=False,
        index=True,
    )
    previous_fmv: Decimal | None = Field(
        default=None,
        sa_column=Column(Numeric(12, 2), nullable=True),
    )
    new_fmv: Decimal = Field(sa_column=Column(Numeric(12, 2), nullable=False))
    changed_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    source: str = Field(default="manual", max_length=50, nullable=False)


class DraftImport(SQLModel, table=True):
    __tablename__ = "draft_import"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True)
    raw_text: str = Field(sa_column=Column(String, nullable=False))
    parsed_payload_json: dict = Field(sa_column=Column(JSON, nullable=False))
    confidence_score: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(4, 2), nullable=False, default=Decimal("0")),
    )
    status: str = Field(default="draft", max_length=20, nullable=False)
    linked_order_id: int | None = Field(default=None, foreign_key="customer_order.id", index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    password_hash: str = Field(max_length=255, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class GmailAccount(SQLModel, table=True):
    __tablename__ = "gmail_account"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", nullable=False, index=True, unique=True)
    gmail_email: str = Field(max_length=320, nullable=False)
    google_subject_id: str = Field(max_length=255, nullable=False, unique=True, index=True)
    access_token_encrypted: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    refresh_token_encrypted: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True),
    )
    auto_sync_enabled: bool = Field(default=False, nullable=False)
    token_expires_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_sync_started_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_sync_completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    last_sync_status: str | None = Field(default=None, max_length=50)
    last_sync_error: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class GmailImportRecord(SQLModel, table=True):
    __tablename__ = "gmail_import_record"

    id: int | None = Field(default=None, primary_key=True)
    gmail_account_id: int = Field(foreign_key="gmail_account.id", nullable=False, index=True)
    external_message_id: str = Field(max_length=255, nullable=False, unique=True, index=True)
    draft_import_id: int = Field(foreign_key="draft_import.id", nullable=False, index=True)
    imported_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class OpsEvent(SQLModel, table=True):
    __tablename__ = "ops_event"

    id: int | None = Field(default=None, primary_key=True)
    event_type: str = Field(max_length=100, nullable=False, index=True)
    status: str = Field(max_length=50, nullable=False, index=True)
    user_id: int | None = Field(default=None, foreign_key="user.id", index=True)
    job_id: str | None = Field(default=None, max_length=255, index=True)
    queue_name: str | None = Field(default=None, max_length=100)
    gmail_account_id: int | None = Field(default=None, foreign_key="gmail_account.id", index=True)
    draft_import_id: int | None = Field(default=None, foreign_key="draft_import.id", index=True)
    order_id: int | None = Field(default=None, foreign_key="customer_order.id", index=True)
    external_message_id: str | None = Field(default=None, max_length=255, index=True)
    message: str | None = Field(default=None, sa_column=Column(String, nullable=True))
    details_json: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
