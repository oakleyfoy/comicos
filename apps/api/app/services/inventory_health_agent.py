from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models import AgentDefinition
from app.models.marketplace_listing import MarketplaceListing
from app.models.marketplace_sync import MarketplaceInventoryReservation
from app.schemas.marketplace_operations import MarketplaceOperationsRunResponse
from app.services.agent_execution import complete_execution, start_execution
from app.services.marketplace_inventory_availability import get_availability
from app.services.marketplace_operations import create_recommendation_with_evidence, get_operations_dashboard

AGENT_CODE = "inventory_health_agent"
RECOMMENDATION_TYPE = "INVENTORY_HEALTH"


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("Inventory health agent is not registered.")
    return int(row.id)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def run_inventory_health_agent(session: Session, *, owner_user_id: int) -> MarketplaceOperationsRunResponse:
    execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="marketplace_operations.inventory_health",
        enforce_permissions=False,
    )
    created: list = []
    listings = session.exec(
        select(MarketplaceListing)
        .where(MarketplaceListing.owner_id == owner_user_id)
        .order_by(MarketplaceListing.id.asc())
    ).all()
    now = datetime.now(timezone.utc)
    for listing in listings:
        listing_id = int(listing.id or 0)
        availability = get_availability(session, owner_id=owner_user_id, listing_id=listing_id)
        if availability.available_quantity < 0:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"{listing_id}:negative_availability",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Negative availability",
                    description="Available quantity is below zero.",
                    listing_id=listing_id,
                    inventory_copy_id=listing.inventory_copy_id,
                    evidence=[
                        {
                            "evidence_type": "negative_availability",
                            "evidence_source": "marketplace_inventory_availability",
                            "evidence_payload_json": availability.model_dump(),
                            "evidence_score": 0.95,
                        }
                    ],
                    severity=0.9,
                )
            )
        if availability.total_quantity != listing.quantity:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"{listing_id}:listing_quantity_mismatch",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Listing quantity mismatch",
                    description="Canonical listing quantity does not match availability total.",
                    listing_id=listing_id,
                    inventory_copy_id=listing.inventory_copy_id,
                    evidence=[
                        {
                            "evidence_type": "listing_quantity_mismatch",
                            "evidence_source": "marketplace_listing",
                            "evidence_payload_json": {
                                "listing_quantity": listing.quantity,
                                "availability_total": availability.total_quantity,
                            },
                            "evidence_score": 0.8,
                        }
                    ],
                    severity=0.7,
                )
            )
        reserved = session.exec(
            select(MarketplaceInventoryReservation)
            .where(MarketplaceInventoryReservation.owner_id == owner_user_id)
            .where(MarketplaceInventoryReservation.listing_id == listing_id)
            .where(MarketplaceInventoryReservation.status == "ACTIVE")
        ).all()
        stale = [
            row
            for row in reserved
            if row.expires_at is not None and _utc(row.expires_at) <= now
        ]
        if stale:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"{listing_id}:stale_reservations",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Stale reservations",
                    description="Active reservations exist past their expiration time.",
                    listing_id=listing_id,
                    inventory_copy_id=listing.inventory_copy_id,
                    evidence=[
                        {
                            "evidence_type": "stale_reservations",
                            "evidence_source": "marketplace_inventory_reservation",
                            "evidence_payload_json": {"reservation_ids": [int(r.id or 0) for r in stale]},
                            "evidence_score": 0.75,
                        }
                    ],
                    severity=0.65,
                )
            )
        if availability.reserved_quantity > availability.total_quantity:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"{listing_id}:allocation_conflict",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Inventory allocation conflict",
                    description="Reserved quantity exceeds total listing quantity.",
                    listing_id=listing_id,
                    inventory_copy_id=listing.inventory_copy_id,
                    evidence=[
                        {
                            "evidence_type": "inventory_allocation_conflict",
                            "evidence_source": "marketplace_inventory_availability",
                            "evidence_payload_json": {
                                "reserved_quantity": availability.reserved_quantity,
                                "total_quantity": availability.total_quantity,
                            },
                            "evidence_score": 0.9,
                        }
                    ],
                    severity=0.85,
                )
            )
    complete_execution(
        session,
        execution_id=execution.execution.id,
        event_payload_json={"recommendations_created": len(created)},
    )
    return MarketplaceOperationsRunResponse(
        agent_execution_id=execution.execution.id,
        recommendations_created=len(created),
        dashboard=get_operations_dashboard(session, owner_user_id=owner_user_id),
        recommendations=created,
    )
