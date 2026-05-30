from __future__ import annotations

from sqlmodel import Session, select

from app.models import AgentDefinition
from app.schemas.agent import AgentCapabilityDeclaration, AgentDefinitionCreate
from app.services.agent_registry import register_agent
from test_inventory import auth_headers, register_and_login


def _agent_id(session: Session, *, code: str) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def test_agent_security_api_supports_policy_crud_audit_listing_and_permission_checks(
    client,
    session: Session,
) -> None:
    token = register_and_login(client, "agent-security-admin@example.com")
    register_agent(
        session,
        payload=AgentDefinitionCreate(
            code="security_api_agent",
            name="SecurityApiAgent",
            description="Security API agent",
            version="1.0.0",
            enabled=False,
            capabilities=[AgentCapabilityDeclaration(capability_code="inventory.read", capability_name="Inventory Read")],
        ),
    )
    agent_id = _agent_id(session, code="security_api_agent")

    initial_check = client.post(
        "/api/v1/agent-security/check",
        headers=auth_headers(token),
        json={
            "agent_id": agent_id,
            "capability_code": "inventory.read",
            "permission_scope": "read",
            "action_code": "api_check",
            "event_payload_json": {"source": "api-test"},
        },
    )
    assert initial_check.status_code == 200, initial_check.text
    assert initial_check.json()["data"]["allowed"] is False
    assert initial_check.json()["data"]["reason"] == "missing_policy"

    created = client.post(
        "/api/v1/agent-security/policies",
        headers=auth_headers(token),
        json={
            "agent_id": agent_id,
            "capability_code": "inventory.read",
            "permission_scope": "read",
            "allowed": True,
        },
    )
    assert created.status_code == 201, created.text
    policy_id = created.json()["data"]["id"]

    policy_list = client.get(
        f"/api/v1/agent-security/policies?agent_id={agent_id}&limit=20&offset=0",
        headers=auth_headers(token),
    )
    assert policy_list.status_code == 200, policy_list.text
    assert [row["id"] for row in policy_list.json()["data"]["items"]] == [policy_id]

    allowed_check = client.post(
        "/api/v1/agent-security/check",
        headers=auth_headers(token),
        json={
            "agent_id": agent_id,
            "capability_code": "inventory.read",
            "permission_scope": "read",
            "action_code": "api_check",
            "event_payload_json": {"source": "api-test"},
        },
    )
    assert allowed_check.status_code == 200, allowed_check.text
    assert allowed_check.json()["data"]["allowed"] is True
    assert allowed_check.json()["data"]["decision"] == "allowed"

    audit_list = client.get(
        f"/api/v1/agent-security/audit-events?agent_id={agent_id}&limit=20&offset=0",
        headers=auth_headers(token),
    )
    assert audit_list.status_code == 200, audit_list.text
    audit_items = audit_list.json()["data"]["items"]
    assert audit_items
    assert audit_items[0]["decision"] == "denied"
    assert audit_items[0]["capability_code"] == "inventory.read"

    deleted = client.delete(
        f"/api/v1/agent-security/policies/{policy_id}",
        headers=auth_headers(token),
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["data"]["deleted"] is True

    after_delete = client.get(
        f"/api/v1/agent-security/policies?agent_id={agent_id}&limit=20&offset=0",
        headers=auth_headers(token),
    )
    assert after_delete.status_code == 200, after_delete.text
    assert after_delete.json()["data"]["items"] == []
