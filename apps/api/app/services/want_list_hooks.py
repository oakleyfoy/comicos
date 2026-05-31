from __future__ import annotations

from sqlmodel import Session


def sync_missing_issues(session: Session, *, owner_user_id: int) -> None:
    """Future P55+ integration: collection gap → want list items."""
    raise NotImplementedError("sync_missing_issues is reserved for a future acquisition phase.")


def sync_marketplace_matches(session: Session, *, owner_user_id: int) -> None:
    """Future P55+ integration: marketplace listing matches for wanted issues."""
    raise NotImplementedError("sync_marketplace_matches is reserved for a future acquisition phase.")


def sync_acquisition_opportunities(session: Session, *, owner_user_id: int) -> None:
    """Future P55+ integration: deal and acquisition opportunity sync."""
    raise NotImplementedError("sync_acquisition_opportunities is reserved for a future acquisition phase.")
