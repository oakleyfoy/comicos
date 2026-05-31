from __future__ import annotations

from collections import defaultdict

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.market_intelligence import MarketAgentExecution, MarketSignal, utc_now
from app.models.marketplace import MarketplaceAccount, MarketplaceExecution
from app.models.marketplace_listing import MarketplaceListing
from app.models.marketplace_sync import MarketplaceInventoryAvailability
from app.schemas.market_intelligence import (
    MarketAgentExecutionRead,
    MarketSignalRead,
    MarketSignalRunResponse,
)

AGENT_CODE = "market_signal_agent"
_PUBLISHABLE_LISTING_STATUSES = {"READY_TO_PUBLISH", "PUBLISHED"}


def _execution_read(row: MarketAgentExecution) -> MarketAgentExecutionRead:
    return MarketAgentExecutionRead.model_validate(row)


def _signal_read(row: MarketSignal) -> MarketSignalRead:
    return MarketSignalRead.model_validate(row)


def _start_execution(session: Session, *, owner_user_id: int) -> MarketAgentExecution:
    row = MarketAgentExecution(
        owner_user_id=owner_user_id,
        agent_code=AGENT_CODE,
        status="RUNNING",
        started_at=utc_now(),
        created_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def _finish_execution(session: Session, *, execution: MarketAgentExecution, status: str) -> None:
    completed_at = utc_now()
    execution.status = status
    execution.completed_at = completed_at
    execution.duration_ms = max(int((completed_at - execution.started_at).total_seconds() * 1000), 0)
    session.add(execution)
    session.flush()


def collect_fmv_signals(session: Session, *, owner_user_id: int) -> list[MarketSignal]:
    observed_at = utc_now()
    rows = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id)).all()
    created: list[MarketSignal] = []
    for row in rows:
        if row.current_fmv is None or row.id is None:
            continue
        created.append(
            MarketSignal(
                owner_user_id=owner_user_id,
                signal_type="FMV_SIGNAL",
                signal_source="inventory_fmv",
                asset_type="inventory_copy",
                asset_id=int(row.id),
                signal_value=float(row.current_fmv),
                confidence_score=0.75,
                observed_at=observed_at,
                created_at=observed_at,
            )
        )
    for row in created:
        session.add(row)
    session.flush()
    return created


def collect_listing_signals(session: Session, *, owner_user_id: int) -> list[MarketSignal]:
    observed_at = utc_now()
    listings = session.exec(select(MarketplaceListing).where(MarketplaceListing.owner_id == owner_user_id)).all()
    created: list[MarketSignal] = []
    for listing in listings:
        if listing.id is None:
            continue
        signal_type = "LISTING_PUBLISHABLE" if listing.status in _PUBLISHABLE_LISTING_STATUSES else "LISTING_DRAFT"
        confidence = 0.8 if signal_type == "LISTING_PUBLISHABLE" else 0.55
        created.append(
            MarketSignal(
                owner_user_id=owner_user_id,
                signal_type=signal_type,
                signal_source="marketplace_listing",
                asset_type="marketplace_listing",
                asset_id=int(listing.id),
                signal_value=float(listing.asking_price),
                confidence_score=confidence,
                observed_at=observed_at,
                created_at=observed_at,
            )
        )
    for row in created:
        session.add(row)
    session.flush()
    return created


def collect_inventory_signals(session: Session, *, owner_user_id: int) -> list[MarketSignal]:
    observed_at = utc_now()
    availability_rows = session.exec(
        select(MarketplaceInventoryAvailability).where(MarketplaceInventoryAvailability.owner_id == owner_user_id)
    ).all()
    created: list[MarketSignal] = []
    for availability in availability_rows:
        if availability.listing_id is None:
            continue
        signal_type = "INVENTORY_CONSTRAINED" if availability.available_quantity <= 0 else "INVENTORY_HEALTHY"
        confidence = 0.9 if signal_type == "INVENTORY_CONSTRAINED" else 0.7
        created.append(
            MarketSignal(
                owner_user_id=owner_user_id,
                signal_type=signal_type,
                signal_source="inventory_availability",
                asset_type="marketplace_listing",
                asset_id=int(availability.listing_id),
                signal_value=float(availability.available_quantity),
                confidence_score=confidence,
                observed_at=observed_at,
                created_at=observed_at,
            )
        )
    for row in created:
        session.add(row)
    session.flush()
    return created


def collect_marketplace_signals(session: Session, *, owner_user_id: int) -> list[MarketSignal]:
    observed_at = utc_now()
    accounts = session.exec(select(MarketplaceAccount).where(MarketplaceAccount.owner_id == owner_user_id)).all()
    account_ids = [int(row.id) for row in accounts if row.id is not None]
    if not account_ids:
        return []

    execution_rows = session.exec(
        select(MarketplaceExecution).where(MarketplaceExecution.account_id.in_(account_ids))  # type: ignore[attr-defined]
    ).all()
    by_account: dict[int, list[MarketplaceExecution]] = defaultdict(list)
    for row in execution_rows:
        if row.account_id is not None:
            by_account[int(row.account_id)].append(row)

    created: list[MarketSignal] = []
    for account in accounts:
        if account.id is None:
            continue
        rows = by_account.get(int(account.id), [])
        total = len(rows)
        completed = sum(1 for row in rows if row.status == "COMPLETED")
        success_rate = completed / total if total else 1.0
        created.append(
            MarketSignal(
                owner_user_id=owner_user_id,
                signal_type="MARKETPLACE_EXECUTION_HEALTH",
                signal_source="marketplace_execution",
                asset_type="marketplace_account",
                asset_id=int(account.id),
                signal_value=round(success_rate, 4),
                confidence_score=0.8 if total else 0.5,
                observed_at=observed_at,
                created_at=observed_at,
            )
        )
    for row in created:
        session.add(row)
    session.flush()
    return created


def collect_market_signals(session: Session, *, owner_user_id: int) -> MarketSignalRunResponse:
    execution = _start_execution(session, owner_user_id=owner_user_id)
    try:
        created = [
            *collect_fmv_signals(session, owner_user_id=owner_user_id),
            *collect_listing_signals(session, owner_user_id=owner_user_id),
            *collect_inventory_signals(session, owner_user_id=owner_user_id),
            *collect_marketplace_signals(session, owner_user_id=owner_user_id),
        ]
        _finish_execution(session, execution=execution, status="COMPLETED")
        session.commit()
        return MarketSignalRunResponse(
            execution=_execution_read(execution),
            created_count=len(created),
            signals=[_signal_read(row) for row in created],
        )
    except Exception:
        _finish_execution(session, execution=execution, status="FAILED")
        session.commit()
        raise
