"""P91-03 lightweight collector home setup progress (existence counts only)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.models.asset_ledger import DraftImport, InventoryCopy, Order
from app.models.p77_collector_profile import P77CollectorBudget, P77CollectorProfile
from app.models.pull_list import PullList
from app.schemas.p91_collector_home_setup import (
    P91CollectorHomeSetupDismissRead,
    P91CollectorHomeSetupStatusRead,
    P91RecommendationsViewedRead,
)

SETUP_TOTAL = 6


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _profile_row(session: Session, *, owner_user_id: int) -> P77CollectorProfile | None:
    return session.exec(
        select(P77CollectorProfile).where(P77CollectorProfile.owner_user_id == owner_user_id)
    ).first()


def _ensure_profile(session: Session, *, owner_user_id: int) -> P77CollectorProfile:
    row = _profile_row(session, owner_user_id=owner_user_id)
    if row is not None:
        return row
    row = P77CollectorProfile(owner_user_id=owner_user_id)
    session.add(row)
    session.flush()
    return row


def mark_recommendations_viewed(session: Session, *, owner_user_id: int) -> P91RecommendationsViewedRead:
    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    if profile.recommendations_first_viewed_at is None:
        profile.recommendations_first_viewed_at = _utc_now()
        profile.updated_at = _utc_now()
        session.add(profile)
        session.flush()
    return P91RecommendationsViewedRead(
        recommendations_viewed=profile.recommendations_first_viewed_at is not None,
        recommendations_first_viewed_at=profile.recommendations_first_viewed_at,
    )


def _setup_flags(session: Session, *, owner_user_id: int) -> dict[str, bool]:
    order_count = int(
        session.scalar(select(func.count()).select_from(Order).where(Order.user_id == owner_user_id)) or 0
    )
    any_import_count = int(
        session.scalar(select(func.count()).select_from(DraftImport).where(DraftImport.user_id == owner_user_id)) or 0
    )
    confirmed_import_count = int(
        session.scalar(
            select(func.count())
            .select_from(DraftImport)
            .where(DraftImport.user_id == owner_user_id)
            .where(DraftImport.status == "confirmed")
        )
        or 0
    )
    has_any_import = order_count > 0 or any_import_count > 0
    imported_first_order = order_count > 0 or confirmed_import_count > 0

    pending_import_count = int(
        session.scalar(
            select(func.count())
            .select_from(DraftImport)
            .where(DraftImport.user_id == owner_user_id)
            .where(DraftImport.status == "draft")
        )
        or 0
    )
    has_unmatched_imports = pending_import_count > 0
    imports_review_complete = has_any_import and not has_unmatched_imports

    inventory_count = int(
        session.scalar(select(func.count()).select_from(InventoryCopy).where(InventoryCopy.user_id == owner_user_id))
        or 0
    )
    has_inventory = inventory_count > 0

    pull_count = int(
        session.scalar(
            select(func.count())
            .select_from(PullList)
            .where(PullList.owner_user_id == owner_user_id)
            .where(PullList.status == "ACTIVE")
        )
        or 0
    )
    has_pull_list = pull_count > 0

    profile = _profile_row(session, owner_user_id=owner_user_id)
    recommendations_viewed = profile is not None and profile.recommendations_first_viewed_at is not None

    budget_row = session.exec(
        select(P77CollectorBudget).where(P77CollectorBudget.owner_user_id == owner_user_id)
    ).first()
    has_budget = budget_row is not None and float(budget_row.monthly_budget) > 0

    return {
        "imported_first_order": imported_first_order,
        "has_any_import": has_any_import,
        "has_unmatched_imports": has_unmatched_imports,
        "imports_review_complete": imports_review_complete,
        "has_inventory": has_inventory,
        "has_pull_list": has_pull_list,
        "recommendations_viewed": recommendations_viewed,
        "has_budget": has_budget,
    }


def _completed_count(flags: dict[str, bool]) -> int:
    return sum(
        [
            1 if flags["imported_first_order"] else 0,
            1 if flags["imports_review_complete"] else 0,
            1 if flags["has_inventory"] else 0,
            1 if flags["has_pull_list"] else 0,
            1 if flags["recommendations_viewed"] else 0,
            1 if flags["has_budget"] else 0,
        ]
    )


def get_collector_home_setup_status(session: Session, *, owner_user_id: int) -> P91CollectorHomeSetupStatusRead:
    flags = _setup_flags(session, owner_user_id=owner_user_id)
    completed = _completed_count(flags)
    percent = round(100.0 * completed / SETUP_TOTAL) if SETUP_TOTAL else 0
    profile = _profile_row(session, owner_user_id=owner_user_id)
    dismissed_at = profile.collector_home_checklist_dismissed_at if profile else None
    can_dismiss = completed >= 4
    return P91CollectorHomeSetupStatusRead(
        imported_first_order=flags["imported_first_order"],
        has_any_import=flags["has_any_import"],
        has_unmatched_imports=flags["has_unmatched_imports"],
        imports_review_complete=flags["imports_review_complete"],
        has_inventory=flags["has_inventory"],
        has_pull_list=flags["has_pull_list"],
        recommendations_viewed=flags["recommendations_viewed"],
        has_budget=flags["has_budget"],
        completed_count=completed,
        total_count=SETUP_TOTAL,
        percent_complete=percent,
        checklist_dismissed=dismissed_at is not None,
        checklist_dismissed_at=dismissed_at,
        can_dismiss_checklist=can_dismiss,
    )


def dismiss_collector_home_checklist(session: Session, *, owner_user_id: int) -> P91CollectorHomeSetupDismissRead:
    status = get_collector_home_setup_status(session, owner_user_id=owner_user_id)
    if status.completed_count < 4:
        raise HTTPException(status_code=400, detail="Complete at least 4 setup steps before hiding the checklist.")
    profile = _ensure_profile(session, owner_user_id=owner_user_id)
    profile.collector_home_checklist_dismissed_at = _utc_now()
    session.add(profile)
    session.flush()
    refreshed = get_collector_home_setup_status(session, owner_user_id=owner_user_id)
    return P91CollectorHomeSetupDismissRead(
        checklist_dismissed=refreshed.checklist_dismissed,
        checklist_dismissed_at=refreshed.checklist_dismissed_at,
        completed_count=refreshed.completed_count,
        can_dismiss_checklist=refreshed.can_dismiss_checklist,
    )
