from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from app.schemas.agent import AgentCapabilityDeclaration


@dataclass(frozen=True)
class AgentCapabilityDefinition:
    capability_code: str
    capability_name: str


AGENT_CAPABILITY_DEFINITIONS: tuple[AgentCapabilityDefinition, ...] = (
    AgentCapabilityDefinition(capability_code="inventory.read", capability_name="Inventory Read"),
    AgentCapabilityDefinition(capability_code="inventory.write", capability_name="Inventory Write"),
    AgentCapabilityDefinition(capability_code="pricing.read", capability_name="Pricing Read"),
    AgentCapabilityDefinition(capability_code="pricing.write", capability_name="Pricing Write"),
    AgentCapabilityDefinition(capability_code="market.read", capability_name="Market Read"),
    AgentCapabilityDefinition(capability_code="market.write", capability_name="Market Write"),
    AgentCapabilityDefinition(capability_code="analytics.read", capability_name="Analytics Read"),
    AgentCapabilityDefinition(capability_code="analytics.write", capability_name="Analytics Write"),
)


def list_capability_declarations() -> list[AgentCapabilityDeclaration]:
    return [
        AgentCapabilityDeclaration(
            capability_code=definition.capability_code,
            capability_name=definition.capability_name,
        )
        for definition in AGENT_CAPABILITY_DEFINITIONS
    ]


def normalize_capability_declarations(
    declarations: list[AgentCapabilityDeclaration],
) -> list[AgentCapabilityDeclaration]:
    normalized: dict[str, AgentCapabilityDeclaration] = {}
    for declaration in declarations:
        capability_code = declaration.capability_code.strip().lower()
        capability_name = declaration.capability_name.strip()
        if not capability_code:
            raise HTTPException(status_code=422, detail="Capability code is required.")
        if not capability_name:
            raise HTTPException(status_code=422, detail="Capability name is required.")
        existing = normalized.get(capability_code)
        if existing is not None and existing.capability_name != capability_name:
            raise HTTPException(status_code=409, detail=f"Capability code {capability_code} has conflicting names.")
        normalized[capability_code] = AgentCapabilityDeclaration(
            capability_code=capability_code,
            capability_name=capability_name,
        )
    return [normalized[key] for key in sorted(normalized.keys())]
