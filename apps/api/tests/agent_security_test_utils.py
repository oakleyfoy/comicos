from __future__ import annotations

from sqlmodel import Session, select

from app.models import AgentDefinition
from app.schemas.agent_security import AgentPermissionPolicyCreate
from app.services.agent_permissions import EXECUTE_PERMISSION_CAPABILITY, RECOMMENDATION_REVIEW_CAPABILITY, grant_permission


def agent_id_by_code(session: Session, code: str) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def grant_agent_execute(session: Session, *, agent_id: int) -> None:
    grant_permission(
        session,
        payload=AgentPermissionPolicyCreate(
            agent_id=agent_id,
            capability_code=EXECUTE_PERMISSION_CAPABILITY,
            permission_scope="execute",
            allowed=True,
        ),
    )


def grant_agent_review(session: Session, *, agent_id: int, admin: bool = False) -> None:
    grant_permission(
        session,
        payload=AgentPermissionPolicyCreate(
            agent_id=agent_id,
            capability_code=RECOMMENDATION_REVIEW_CAPABILITY,
            permission_scope="review",
            allowed=True,
        ),
    )
    if admin:
        grant_permission(
            session,
            payload=AgentPermissionPolicyCreate(
                agent_id=agent_id,
                capability_code=RECOMMENDATION_REVIEW_CAPABILITY,
                permission_scope="admin",
                allowed=True,
            ),
        )
