from __future__ import annotations

from sqlmodel import Session, select

from app.models import AgentDefinition
from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingImage, MarketplaceListingMapping
from app.schemas.marketplace_operations import MarketplaceOperationsRunResponse
from app.services.agent_execution import complete_execution, start_execution
from app.services.marketplace_operations import create_recommendation_with_evidence, get_operations_dashboard
from app.services.marketplace_listings import list_listings

AGENT_CODE = "listing_quality_agent"
RECOMMENDATION_TYPE = "LISTING_QUALITY"


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("Listing quality agent is not registered.")
    return int(row.id)


def _weak_title(title: str) -> bool:
    normalized = title.strip().lower()
    return len(normalized) < 8 or normalized in {"comic", "listing", "item", "book"}


def run_listing_quality_agent(session: Session, *, owner_user_id: int) -> MarketplaceOperationsRunResponse:
    execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="marketplace_operations.listing_quality",
        enforce_permissions=False,
    )
    created: list = []
    listings = list_listings(session, owner_id=owner_user_id, limit=200, offset=0).items
    for listing in listings:
        listing_id = listing.id
        issues: list[tuple[str, str, str, dict]] = []
        title = listing.listing_title or ""
        if not title.strip():
            issues.append(("missing_title", "Missing listing title", "Listing has no title.", {}))
        elif _weak_title(title):
            issues.append(("weak_title", "Weak listing title", f"Title '{title}' may be too generic.", {"title": title}))
        if not (listing.listing_description or "").strip():
            issues.append(("missing_description", "Missing description", "Listing has no description.", {}))
        images = session.exec(
            select(MarketplaceListingImage).where(MarketplaceListingImage.listing_id == listing_id)
        ).all()
        if not images:
            issues.append(("missing_images", "Missing images", "Listing has no images.", {}))
        elif not any(img.is_primary for img in images):
            issues.append(("missing_primary_image", "Missing primary image", "No primary image is selected.", {}))
        if listing.asking_price is None or listing.asking_price <= 0:
            issues.append(("missing_price", "Missing price", "Listing price is missing or zero.", {}))
        if listing.quantity <= 0:
            issues.append(("missing_quantity", "Missing quantity", "Listing quantity is zero.", {}))
        mappings = session.exec(
            select(MarketplaceListingMapping).where(MarketplaceListingMapping.listing_id == listing_id)
        ).all()
        if not mappings:
            issues.append(("missing_marketplace_mapping", "Missing marketplace mapping", "No marketplace mapping exists.", {}))
        for issue_code, issue_title, issue_desc, payload in issues:
            read = create_recommendation_with_evidence(
                session,
                agent_execution_id=execution.execution.id,
                recommendation_key=f"{listing_id}:{issue_code}",
                recommendation_type=RECOMMENDATION_TYPE,
                title=issue_title,
                description=issue_desc,
                listing_id=listing_id,
                inventory_copy_id=listing.inventory_copy_id,
                evidence=[
                    {
                        "evidence_type": issue_code,
                        "evidence_source": "marketplace_listing",
                        "evidence_payload_json": {"listing_id": listing_id, **payload},
                        "evidence_score": 0.85,
                    }
                ],
                severity=0.6,
            )
            created.append(read)
    complete_execution(
        session,
        execution_id=execution.execution.id,
        event_payload_json={"recommendations_created": len(created), "recommendation_type": RECOMMENDATION_TYPE},
    )
    dashboard = get_operations_dashboard(session, owner_user_id=owner_user_id)
    return MarketplaceOperationsRunResponse(
        agent_execution_id=execution.execution.id,
        recommendations_created=len(created),
        dashboard=dashboard,
        recommendations=created,
    )
