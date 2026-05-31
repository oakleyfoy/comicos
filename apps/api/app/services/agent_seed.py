from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from app.models import AgentDefinition
from app.schemas.agent import AgentCapabilityDeclaration, AgentDefinitionCreate, AgentDefinitionRead
from app.schemas.agent_security import AgentPermissionPolicyCreate
from app.services.agent_permissions import grant_permission
from app.services.agent_registry import register_agent, update_agent


@dataclass(frozen=True)
class AgentSeedDefinition:
    code: str
    name: str
    description: str
    version: str
    capabilities: tuple[AgentCapabilityDeclaration, ...]


FOUNDATIONAL_AGENT_SEEDS: tuple[AgentSeedDefinition, ...] = (
    AgentSeedDefinition(
        code="inventory_agent",
        name="InventoryAgent",
        description="Placeholder registry record for future inventory-oriented agent workflows.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
            AgentCapabilityDeclaration(capability_code="inventory.write", capability_name="Inventory Write"),
        ),
    ),
    AgentSeedDefinition(
        code="pricing_agent",
        name="PricingAgent",
        description="Placeholder registry record for future pricing-oriented agent workflows.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="pricing.read", capability_name="Pricing Read"),
            AgentCapabilityDeclaration(capability_code="pricing.write", capability_name="Pricing Write"),
        ),
    ),
    AgentSeedDefinition(
        code="market_agent",
        name="MarketAgent",
        description="Placeholder registry record for future market-oriented agent workflows.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="market.write", capability_name="Market Write"),
        ),
    ),
    AgentSeedDefinition(
        code="analytics_agent",
        name="AnalyticsAgent",
        description="Placeholder registry record for future analytics-oriented agent workflows.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="analytics.read", capability_name="Analytics Read"),
            AgentCapabilityDeclaration(capability_code="analytics.write", capability_name="Analytics Write"),
        ),
    ),
    AgentSeedDefinition(
        code="marketplace_research_agent",
        name="MarketplaceResearchAgent",
        description="Read-only marketplace research agent that produces internal recommendation candidates and evidence snapshots.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
            AgentCapabilityDeclaration(capability_code="analytics.read", capability_name="Analytics Read"),
        ),
    ),
    AgentSeedDefinition(
        code="new_release_research_agent",
        name="NewReleaseResearchAgent",
        description="Read-only release research agent that turns internal release and arrival signals into reviewable findings.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
            AgentCapabilityDeclaration(capability_code="analytics.read", capability_name="Analytics Read"),
        ),
    ),
    AgentSeedDefinition(
        code="pricing_intelligence_agent",
        name="PricingIntelligenceAgent",
        description="Advisory pricing intelligence agent that emits evidence-backed pricing recommendations without mutating inventory or prices.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
            AgentCapabilityDeclaration(capability_code="pricing.read", capability_name="Pricing Read"),
            AgentCapabilityDeclaration(capability_code="analytics.read", capability_name="Analytics Read"),
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
        ),
    ),
    AgentSeedDefinition(
        code="catalog_intelligence_agent",
        name="CatalogIntelligenceAgent",
        description="Advisory catalog intelligence agent that emits evidence-backed metadata and catalog review recommendations.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
            AgentCapabilityDeclaration(capability_code="pricing.read", capability_name="Pricing Read"),
            AgentCapabilityDeclaration(capability_code="analytics.read", capability_name="Analytics Read"),
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
        ),
    ),
    AgentSeedDefinition(
        code="listing_quality_agent",
        name="ListingQualityAgent",
        description="Read-only marketplace operations agent that detects listing quality gaps and emits advisory recommendations.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
        ),
    ),
    AgentSeedDefinition(
        code="inventory_health_agent",
        name="InventoryHealthAgent",
        description="Read-only marketplace operations agent that detects inventory reservation and availability health issues.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
        ),
    ),
    AgentSeedDefinition(
        code="pricing_opportunity_agent",
        name="PricingOpportunityAgent",
        description="Advisory marketplace pricing agent that compares listing prices to FMV and trend signals without mutating prices.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="pricing.read", capability_name="Pricing Read"),
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
        ),
    ),
    AgentSeedDefinition(
        code="unsold_inventory_agent",
        name="UnsoldInventoryAgent",
        description="Read-only marketplace operations agent that detects stale or unexposed inventory listings.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read"),
        ),
    ),
    AgentSeedDefinition(
        code="marketplace_audit_agent",
        name="MarketplaceAuditAgent",
        description="Read-only marketplace operations agent that audits mappings, accounts, and publish lifecycle consistency.",
        version="1.0.0",
        capabilities=(
            AgentCapabilityDeclaration(capability_code="market.read", capability_name="Market Read"),
            AgentCapabilityDeclaration(capability_code="analytics.read", capability_name="Analytics Read"),
        ),
    ),
)


def _seed_safe_read_permissions(session: Session) -> None:
    for definition in FOUNDATIONAL_AGENT_SEEDS:
        existing = session.exec(select(AgentDefinition).where(AgentDefinition.code == definition.code)).first()
        if existing is None or existing.id is None:
            continue
        for capability in definition.capabilities:
            if capability.capability_code.endswith(".read"):
                grant_permission(
                    session,
                    payload=AgentPermissionPolicyCreate(
                        agent_id=int(existing.id),
                        capability_code=capability.capability_code,
                        permission_scope="read",
                        allowed=True,
                    ),
                )


def seed_foundational_agents(session: Session) -> list[AgentDefinitionRead]:
    seeded: list[AgentDefinitionRead] = []
    for definition in FOUNDATIONAL_AGENT_SEEDS:
        existing = session.exec(select(AgentDefinition).where(AgentDefinition.code == definition.code)).first()
        if existing is None:
            seeded.append(
                register_agent(
                    session,
                    payload=AgentDefinitionCreate(
                        code=definition.code,
                        name=definition.name,
                        description=definition.description,
                        version=definition.version,
                        enabled=False,
                        capabilities=list(definition.capabilities),
                    ),
                )
            )
            continue
        seeded.append(
            update_agent(
                session,
                agent_id=int(existing.id or 0),
                name=definition.name,
                description=definition.description,
                version=definition.version,
                enabled=False,
                capabilities=list(definition.capabilities),
            )
        )
    _seed_safe_read_permissions(session)
    return seeded
