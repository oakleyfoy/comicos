from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models import AgentDefinition
from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingMapping
from app.schemas.marketplace_operations import MarketplaceOperationsRunResponse
from app.services.agent_execution import complete_execution, start_execution
from app.services.marketplace_operations import create_recommendation_with_evidence, get_operations_dashboard

AGENT_CODE = "unsold_inventory_agent"
RECOMMENDATION_TYPE = "UNSOLD_INVENTORY"
STALE_DAYS = 30


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("Unsold inventory agent is not registered.")
    return int(row.id)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def run_unsold_inventory_agent(session: Session, *, owner_user_id: int) -> MarketplaceOperationsRunResponse:
    execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="marketplace_operations.unsold_inventory",
        enforce_permissions=False,
    )
    created: list = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS)
    listings = session.exec(
        select(MarketplaceListing)
        .where(MarketplaceListing.owner_id == owner_user_id)
        .order_by(MarketplaceListing.created_at.asc(), MarketplaceListing.id.asc())
    ).all()
    for listing in listings:
        listing_id = int(listing.id or 0)
        mappings = session.exec(
            select(MarketplaceListingMapping).where(MarketplaceListingMapping.listing_id == listing_id)
        ).all()
        if not mappings:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"{listing_id}:no_marketplace",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="No marketplace inventory",
                    description="Listing is not mapped to any marketplace account.",
                    listing_id=listing_id,
                    inventory_copy_id=listing.inventory_copy_id,
                    evidence=[
                        {
                            "evidence_type": "no_marketplace_inventory",
                            "evidence_source": "marketplace_listing_mapping",
                            "evidence_payload_json": {"listing_id": listing_id},
                            "evidence_score": 0.7,
                        }
                    ],
                    severity=0.5,
                )
            )
        if _utc(listing.created_at) <= cutoff and listing.status.upper() in {"READY", "DRAFT", "ACTIVE"}:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"{listing_id}:stale_listing",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Stale listing",
                    description="Listing has remained available for an extended period.",
                    listing_id=listing_id,
                    inventory_copy_id=listing.inventory_copy_id,
                    evidence=[
                        {
                            "evidence_type": "stale_listing",
                            "evidence_source": "marketplace_listing",
                            "evidence_payload_json": {
                                "created_at": listing.created_at.isoformat(),
                                "status": listing.status,
                            },
                            "evidence_score": 0.75,
                        }
                    ],
                    severity=0.55,
                )
            )
        if listing.quantity >= 1 and listing.status.upper() == "READY" and len(mappings) == 0:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"{listing_id}:long_listed",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Long-listed inventory",
                    description="Ready inventory lacks marketplace exposure.",
                    listing_id=listing_id,
                    inventory_copy_id=listing.inventory_copy_id,
                    evidence=[
                        {
                            "evidence_type": "long_listed_inventory",
                            "evidence_source": "marketplace_listing",
                            "evidence_payload_json": {"quantity": listing.quantity},
                            "evidence_score": 0.68,
                        }
                    ],
                    severity=0.5,
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
