from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index as SAIndex
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EbayAccountDeletionAuditLog(SQLModel, table=True):
    """No-op compliance audit trail for eBay Marketplace Account Deletion notifications."""

    __tablename__ = "ebay_account_deletion_audit_log"
    __table_args__ = (
        SAIndex("ix_ebay_acct_del_audit_kind_created", "event_kind", "created_at", "id"),
        SAIndex("ix_ebay_acct_del_audit_notif_id", "external_notification_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event_kind: str = Field(max_length=64, nullable=False, index=True)
    external_notification_id: str | None = Field(default=None, max_length=128, nullable=True)
    payload_digest: str | None = Field(default=None, max_length=128, nullable=True)
    noop_action: str = Field(
        default="acknowledged_no_user_data_retained",
        max_length=120,
        nullable=False,
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
