from __future__ import annotations

from sqlmodel import select

from app.models import AgentDefinition, WorkflowDefinition
from app.services.agent_seed import seed_foundational_agents
from app.services.workflow_seed import seed_foundational_workflows
from test_inventory import auth_headers, register_and_login


def _agent_id(session, code: str) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == code)).first()
    assert row is not None and row.id is not None
    return int(row.id)


def test_workflow_registry_routes_create_duplicate_enable_disable_and_listing(client, session) -> None:
    token = register_and_login(client, "workflow-registry@example.com")
    seed_foundational_agents(session)
    inventory_agent_id = _agent_id(session, "inventory_agent")
    pricing_agent_id = _agent_id(session, "pricing_agent")
    existing = session.exec(
        select(WorkflowDefinition).where(WorkflowDefinition.workflow_code == "pricing_refresh_runtime")
    ).first()

    if existing is None:
        created = client.post(
            "/api/v1/workflows",
            headers=auth_headers(token),
            json={
                "workflow_code": "Pricing_Refresh_Runtime",
                "workflow_name": "Pricing Refresh Runtime",
                "description": "Deterministic pricing refresh workflow placeholder.",
                "enabled": False,
                "schedule_enabled": True,
                "cron_expression": "0 * * * *",
                "steps": [
                    {
                        "step_order": 1,
                        "agent_definition_id": inventory_agent_id,
                        "step_name": "InventoryAgent",
                        "step_code": "inventory_agent",
                        "required_success": True,
                        "timeout_seconds": 300,
                    },
                    {
                        "step_order": 2,
                        "agent_definition_id": pricing_agent_id,
                        "step_name": "PricingAgent",
                        "step_code": "pricing_agent",
                        "required_success": True,
                        "timeout_seconds": 300,
                    },
                ],
            },
        )
        assert created.status_code == 201, created.text
        data = created.json()["data"]
        workflow_id = data["id"]
    else:
        workflow_id = int(existing.id or 0)
        detail_existing = client.get(f"/api/v1/workflows/{workflow_id}", headers=auth_headers(token))
        assert detail_existing.status_code == 200, detail_existing.text
        data = detail_existing.json()["data"]
    assert data["workflow_code"] == "pricing_refresh_runtime"
    assert data["schedule_enabled"] is True
    assert data["cron_expression"] == "0 * * * *"
    assert [row["step_order"] for row in data["steps"]] == [1, 2]

    listing = client.get("/api/v1/workflows?limit=20&offset=0", headers=auth_headers(token))
    assert listing.status_code == 200, listing.text
    assert "pricing_refresh_runtime" in [row["workflow_code"] for row in listing.json()["data"]["items"]]

    detail = client.get(f"/api/v1/workflows/{workflow_id}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["data"]["id"] == workflow_id

    duplicate = client.post(
        "/api/v1/workflows",
        headers=auth_headers(token),
        json={
            "workflow_code": "pricing_refresh_runtime",
            "workflow_name": "Duplicate Workflow",
            "description": "Should fail.",
            "enabled": False,
            "schedule_enabled": False,
            "steps": [
                {
                    "step_order": 1,
                    "agent_definition_id": inventory_agent_id,
                    "step_name": "InventoryAgent",
                    "step_code": "inventory_agent",
                    "required_success": True,
                    "timeout_seconds": 300,
                }
            ],
        },
    )
    assert duplicate.status_code == 409, duplicate.text

    enabled = client.post(f"/api/v1/workflows/{workflow_id}/enable", headers=auth_headers(token))
    disabled = client.post(f"/api/v1/workflows/{workflow_id}/disable", headers=auth_headers(token))
    assert enabled.status_code == 200, enabled.text
    assert disabled.status_code == 200, disabled.text
    assert enabled.json()["data"]["enabled"] is True
    assert disabled.json()["data"]["enabled"] is False


def test_workflow_seed_service_is_deterministic_and_disabled_by_default(session) -> None:
    first = seed_foundational_workflows(session)
    second = seed_foundational_workflows(session)

    assert [row.workflow_code for row in first] == [
        "inventory_refresh_workflow",
        "pricing_refresh_workflow",
        "market_refresh_workflow",
        "analytics_refresh_workflow",
    ]
    assert [row.id for row in first] == [row.id for row in second]
    assert all(row.enabled is False for row in second)
    assert [len(row.steps) for row in second] == [1, 2, 3, 4]
