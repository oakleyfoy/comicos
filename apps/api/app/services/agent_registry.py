from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, func, select

from app.models import AgentCapability, AgentDefinition
from app.schemas.agent import (
    AgentCapabilityDeclaration,
    AgentCapabilityRead,
    AgentDefinitionCreate,
    AgentDefinitionListResponse,
    AgentDefinitionRead,
)
from app.services.agent_capabilities import normalize_capability_declarations


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_agent_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 200), max(offset, 0)


def _get_agent_row(session: Session, *, agent_id: int) -> AgentDefinition:
    row = session.get(AgentDefinition, agent_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent definition not found.")
    return row


def _get_agent_by_code(session: Session, *, code: str) -> AgentDefinition | None:
    return session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()


def _list_capability_rows(session: Session, *, agent_id: int) -> list[AgentCapability]:
    return session.exec(
        select(AgentCapability)
        .where(AgentCapability.agent_id == agent_id)
        .order_by(AgentCapability.capability_code.asc(), AgentCapability.capability_name.asc(), AgentCapability.id.asc())
    ).all()


def _replace_capabilities(
    session: Session,
    *,
    agent_id: int,
    declarations: list[AgentCapabilityDeclaration],
) -> None:
    existing_rows = _list_capability_rows(session, agent_id=agent_id)
    for row in existing_rows:
        session.delete(row)
    if existing_rows:
        session.flush()
    normalized = normalize_capability_declarations(declarations)
    for declaration in normalized:
        session.add(
            AgentCapability(
                agent_id=agent_id,
                capability_code=declaration.capability_code,
                capability_name=declaration.capability_name,
            )
        )
    session.flush()


def _capability_read(row: AgentCapability) -> AgentCapabilityRead:
    return AgentCapabilityRead(
        id=int(row.id or 0),
        capability_code=row.capability_code,
        capability_name=row.capability_name,
    )


def _agent_read(session: Session, row: AgentDefinition) -> AgentDefinitionRead:
    return AgentDefinitionRead(
        id=int(row.id or 0),
        code=row.code,
        name=row.name,
        description=row.description,
        version=row.version,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
        capabilities=[_capability_read(capability) for capability in _list_capability_rows(session, agent_id=int(row.id or 0))],
    )


def register_agent(session: Session, *, payload: AgentDefinitionCreate) -> AgentDefinitionRead:
    code = payload.code.strip().lower()
    if _get_agent_by_code(session, code=code) is not None:
        raise HTTPException(status_code=409, detail=f"Agent code {code} is already registered.")
    now = utc_now()
    row = AgentDefinition(
        code=code,
        name=payload.name.strip(),
        description=payload.description.strip(),
        version=payload.version.strip(),
        enabled=payload.enabled,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    assert row.id is not None
    _replace_capabilities(session, agent_id=int(row.id), declarations=payload.capabilities)
    session.commit()
    session.refresh(row)
    return _agent_read(session, row)


def update_agent(
    session: Session,
    *,
    agent_id: int,
    name: str | None = None,
    description: str | None = None,
    version: str | None = None,
    enabled: bool | None = None,
    capabilities: list[AgentCapabilityDeclaration] | None = None,
) -> AgentDefinitionRead:
    row = _get_agent_row(session, agent_id=agent_id)
    if name is not None:
        row.name = name.strip()
    if description is not None:
        row.description = description.strip()
    if version is not None:
        row.version = version.strip()
    if enabled is not None:
        row.enabled = enabled
    row.updated_at = utc_now()
    session.add(row)
    session.flush()
    if capabilities is not None:
        _replace_capabilities(session, agent_id=int(row.id or 0), declarations=capabilities)
    session.commit()
    session.refresh(row)
    return _agent_read(session, row)


def list_agents(
    session: Session,
    *,
    limit: int = 50,
    offset: int = 0,
    enabled: bool | None = None,
) -> AgentDefinitionListResponse:
    limit, offset = clamp_agent_pagination(limit=limit, offset=offset)
    filters = []
    if enabled is not None:
        filters.append(AgentDefinition.enabled == enabled)
    total_items = int(session.exec(select(func.count()).select_from(AgentDefinition).where(*filters)).one())
    rows = session.exec(
        select(AgentDefinition)
        .where(*filters)
        .order_by(AgentDefinition.created_at.asc(), AgentDefinition.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    return AgentDefinitionListResponse(
        items=[_agent_read(session, row) for row in rows],
        total_items=total_items,
        limit=limit,
        offset=offset,
    )


def get_agent(session: Session, *, agent_id: int) -> AgentDefinitionRead:
    return _agent_read(session, _get_agent_row(session, agent_id=agent_id))


def enable_agent(session: Session, *, agent_id: int) -> AgentDefinitionRead:
    return update_agent(session, agent_id=agent_id, enabled=True)


def disable_agent(session: Session, *, agent_id: int) -> AgentDefinitionRead:
    return update_agent(session, agent_id=agent_id, enabled=False)
