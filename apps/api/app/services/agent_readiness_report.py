from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, func, select

from app.models import AgentDefinition, AgentExecution, IntelligenceRecommendation, ResearchSnapshot, WorkflowDefinition
from app.schemas.agent_platform import (
    AgentPlatformReadinessRead,
    AgentPlatformReadinessSectionRead,
)
from app.services.agent_analytics import get_latest_snapshot
from app.services.agent_platform_validation import (
    PLATFORM_STATUS_PASS,
    PLATFORM_STATUS_WARNING,
    _aggregate_status,
    validate_agents,
    validate_analytics,
    validate_dashboard,
    validate_permissions,
    validate_recommendations,
    validate_workflows,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _section(
    *,
    section_code: str,
    title: str,
    status: str,
    summary: str,
    details_json: dict[str, object],
) -> AgentPlatformReadinessSectionRead:
    return AgentPlatformReadinessSectionRead(
        section_code=section_code,
        title=title,
        status=status,
        summary=summary,
        details_json=details_json,
    )


def _test_coverage_section() -> AgentPlatformReadinessSectionRead:
    root = _repo_root()
    required_paths = [
        root / "apps" / "api" / "tests" / "test_agent_registry.py",
        root / "apps" / "api" / "tests" / "test_agent_execution.py",
        root / "apps" / "api" / "tests" / "test_workflow_registry.py",
        root / "apps" / "api" / "tests" / "test_workflow_orchestrator.py",
        root / "apps" / "api" / "tests" / "test_research_agent_base.py",
        root / "apps" / "api" / "tests" / "test_marketplace_research_agent.py",
        root / "apps" / "api" / "tests" / "test_new_release_research_agent.py",
        root / "apps" / "api" / "tests" / "test_research_agent_api.py",
        root / "apps" / "api" / "tests" / "test_pricing_intelligence_agent.py",
        root / "apps" / "api" / "tests" / "test_catalog_intelligence_agent.py",
        root / "apps" / "api" / "tests" / "test_intelligence_engine.py",
        root / "apps" / "api" / "tests" / "test_intelligence_api.py",
        root / "apps" / "api" / "tests" / "test_agent_dashboard.py",
        root / "apps" / "api" / "tests" / "test_agent_permissions.py",
        root / "apps" / "api" / "tests" / "test_agent_security_api.py",
        root / "apps" / "api" / "tests" / "test_agent_analytics.py",
        root / "apps" / "api" / "tests" / "test_agent_platform.py",
        root / "apps" / "api" / "tests" / "test_recommendation_outcomes.py",
        root / "apps" / "web" / "src" / "pages" / "AgentDashboardPage.test.tsx",
    ]
    missing = sorted(str(path.relative_to(root)).replace("\\", "/") for path in required_paths if not path.exists())
    status = PLATFORM_STATUS_PASS if not missing else PLATFORM_STATUS_WARNING
    return _section(
        section_code="test_coverage",
        title="Test Coverage",
        status=status,
        summary=f"{len(required_paths) - len(missing)}/{len(required_paths)} closeout test modules are present.",
        details_json={
            "required_test_modules": [str(path.relative_to(root)).replace("\\", "/") for path in required_paths],
            "missing_test_modules": missing,
        },
    )


def generate_agent_platform_readiness_report(session: Session, *, owner_user_id: int) -> AgentPlatformReadinessRead:
    agent_check = validate_agents(session, owner_user_id=owner_user_id)
    workflow_check = validate_workflows(session, owner_user_id=owner_user_id)
    recommendation_check = validate_recommendations(session, owner_user_id=owner_user_id)
    dashboard_check = validate_dashboard(session, owner_user_id=owner_user_id)
    security_check = validate_permissions(session, owner_user_id=owner_user_id)
    analytics_check = validate_analytics(session, owner_user_id=owner_user_id)
    test_coverage = _test_coverage_section()

    research_agent_codes = {"marketplace_research_agent", "new_release_research_agent"}
    intelligence_agent_codes = {"pricing_intelligence_agent", "catalog_intelligence_agent"}
    agent_rows = session.exec(select(AgentDefinition).order_by(AgentDefinition.code.asc())).all()
    workflow_count = int(session.exec(select(func.count()).select_from(WorkflowDefinition)).one())
    research_snapshot_count = int(
        session.exec(
            select(func.count())
            .select_from(ResearchSnapshot)
            .join(AgentExecution, AgentExecution.id == ResearchSnapshot.agent_execution_id)
            .where(AgentExecution.triggered_by == str(owner_user_id))
        ).one()
    )
    recommendation_count = int(
        session.exec(
            select(func.count())
            .select_from(IntelligenceRecommendation)
            .join(AgentExecution, AgentExecution.id == IntelligenceRecommendation.agent_execution_id)
            .where(AgentExecution.triggered_by == str(owner_user_id))
        ).one()
    )
    latest_analytics = get_latest_snapshot(session, owner_user_id=owner_user_id)

    research_agents_present = sorted(row.code for row in agent_rows if row.code in research_agent_codes)
    intelligence_agents_present = sorted(row.code for row in agent_rows if row.code in intelligence_agent_codes)

    sections = [
        _section(
            section_code="agent_registry",
            title="Agent Registry",
            status=agent_check.status,
            summary=agent_check.summary,
            details_json=agent_check.details_json,
        ),
        _section(
            section_code="workflow_engine",
            title="Workflow Engine",
            status=workflow_check.status,
            summary=workflow_check.summary,
            details_json={**workflow_check.details_json, "workflow_count": workflow_count},
        ),
        _section(
            section_code="research_agents",
            title="Research Agents",
            status=PLATFORM_STATUS_PASS if len(research_agents_present) == len(research_agent_codes) else PLATFORM_STATUS_WARNING,
            summary=(
                f"{len(research_agents_present)}/{len(research_agent_codes)} research agents registered; "
                f"{research_snapshot_count} research snapshots recorded."
            ),
            details_json={
                "required_agent_codes": sorted(research_agent_codes),
                "registered_agent_codes": research_agents_present,
                "research_snapshot_count": research_snapshot_count,
            },
        ),
        _section(
            section_code="intelligence_agents",
            title="Intelligence Agents",
            status=PLATFORM_STATUS_PASS if len(intelligence_agents_present) == len(intelligence_agent_codes) else PLATFORM_STATUS_WARNING,
            summary=(
                f"{len(intelligence_agents_present)}/{len(intelligence_agent_codes)} intelligence agents registered; "
                f"{recommendation_count} recommendations recorded."
            ),
            details_json={
                "required_agent_codes": sorted(intelligence_agent_codes),
                "registered_agent_codes": intelligence_agents_present,
                "recommendation_count": recommendation_count,
                "validation": recommendation_check.details_json,
            },
        ),
        _section(
            section_code="dashboard",
            title="Dashboard",
            status=dashboard_check.status,
            summary=dashboard_check.summary,
            details_json=dashboard_check.details_json,
        ),
        _section(
            section_code="security",
            title="Security",
            status=security_check.status,
            summary=security_check.summary,
            details_json=security_check.details_json,
        ),
        _section(
            section_code="analytics",
            title="Analytics",
            status=analytics_check.status,
            summary=analytics_check.summary,
            details_json={
                **analytics_check.details_json,
                "latest_snapshot_present": latest_analytics.latest_snapshot is not None,
            },
        ),
        test_coverage,
    ]

    return AgentPlatformReadinessRead(
        report_name="Agent Platform Readiness Report",
        overall_status=_aggregate_status([section.status for section in sections]),
        sections=sections,
    )
