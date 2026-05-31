from __future__ import annotations

from decimal import Decimal

from sqlmodel import Session, select

from app.models import AgentDefinition, InventoryCopy, MarketTrendSnapshot
from app.models.marketplace_listing import MarketplaceListing
from app.schemas.marketplace_operations import MarketplaceOperationsRunResponse
from app.services.agent_execution import complete_execution, start_execution
from app.services.marketplace_operations import create_recommendation_with_evidence, get_operations_dashboard

AGENT_CODE = "pricing_opportunity_agent"
RECOMMENDATION_TYPE = "PRICING_OPPORTUNITY"


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("Pricing opportunity agent is not registered.")
    return int(row.id)


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def run_pricing_opportunity_agent(session: Session, *, owner_user_id: int) -> MarketplaceOperationsRunResponse:
    execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="marketplace_operations.pricing_opportunities",
        enforce_permissions=False,
    )
    created: list = []
    listings = session.exec(
        select(MarketplaceListing).where(MarketplaceListing.owner_id == owner_user_id).order_by(MarketplaceListing.id.asc())
    ).all()
    trend = session.exec(select(MarketTrendSnapshot).order_by(MarketTrendSnapshot.created_at.desc()).limit(1)).first()
    trend_direction = trend.trend_direction.lower() if trend is not None else None
    for listing in listings:
        listing_id = int(listing.id or 0)
        asking = _decimal(listing.asking_price)
        fmv: Decimal | None = None
        if listing.inventory_copy_id is not None:
            inv = session.get(InventoryCopy, listing.inventory_copy_id)
            if inv is not None and inv.current_fmv is not None:
                fmv = _decimal(inv.current_fmv)
        if fmv is not None and fmv > 0:
            ratio = float(asking / fmv)
            if ratio < 0.85:
                created.append(
                    create_recommendation_with_evidence(
                        session,
                        agent_execution_id=execution.execution.id,
                        recommendation_key=f"{listing_id}:underpriced",
                        recommendation_type=RECOMMENDATION_TYPE,
                        title="Underpriced listing",
                        description="Asking price is materially below current FMV.",
                        listing_id=listing_id,
                        inventory_copy_id=listing.inventory_copy_id,
                        evidence=[
                            {
                                "evidence_type": "underpriced_listing",
                                "evidence_source": "fmv_comparison",
                                "evidence_payload_json": {
                                    "asking_price": str(asking),
                                    "fmv": str(fmv),
                                    "ratio": ratio,
                                },
                                "evidence_score": 0.82,
                            }
                        ],
                        severity=0.7,
                    )
                )
            elif ratio > 1.25:
                created.append(
                    create_recommendation_with_evidence(
                        session,
                        agent_execution_id=execution.execution.id,
                        recommendation_key=f"{listing_id}:overpriced",
                        recommendation_type=RECOMMENDATION_TYPE,
                        title="Overpriced listing",
                        description="Asking price is materially above current FMV.",
                        listing_id=listing_id,
                        inventory_copy_id=listing.inventory_copy_id,
                        evidence=[
                            {
                                "evidence_type": "overpriced_listing",
                                "evidence_source": "fmv_comparison",
                                "evidence_payload_json": {
                                    "asking_price": str(asking),
                                    "fmv": str(fmv),
                                    "ratio": ratio,
                                },
                                "evidence_score": 0.8,
                            }
                        ],
                        severity=0.65,
                    )
                )
            if trend_direction == "rising":
                created.append(
                    create_recommendation_with_evidence(
                        session,
                        agent_execution_id=execution.execution.id,
                        recommendation_key=f"{listing_id}:rapid_appreciation",
                        recommendation_type=RECOMMENDATION_TYPE,
                        title="Rapid appreciation opportunity",
                        description="Market trend signals upward movement for related inventory.",
                        listing_id=listing_id,
                        inventory_copy_id=listing.inventory_copy_id,
                        evidence=[
                            {
                                "evidence_type": "rapid_appreciation_opportunity",
                                "evidence_source": "market_trend",
                                "evidence_payload_json": {"direction": trend_direction},
                                "evidence_score": 0.7,
                            }
                        ],
                        severity=0.55,
                    )
                )
            elif trend_direction == "falling":
                created.append(
                    create_recommendation_with_evidence(
                        session,
                        agent_execution_id=execution.execution.id,
                        recommendation_key=f"{listing_id}:rapid_decline",
                        recommendation_type=RECOMMENDATION_TYPE,
                        title="Rapid decline risk",
                        description="Market trend signals downward movement for related inventory.",
                        listing_id=listing_id,
                        inventory_copy_id=listing.inventory_copy_id,
                        evidence=[
                            {
                                "evidence_type": "rapid_decline_risk",
                                "evidence_source": "market_trend",
                                "evidence_payload_json": {"direction": trend_direction},
                                "evidence_score": 0.72,
                            }
                        ],
                        severity=0.6,
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
