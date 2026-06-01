from __future__ import annotations

from sqlmodel import Session, select

from app.models.operations_reliability import RecoveryRecommendation
from app.schemas.operations_reliability import (
    OperationsReliabilityDashboardRead,
    OperationsReliabilitySummaryRead,
    RecoveryRecommendationRead,
)
from app.services.platform_health import list_health_checks_for_owner
from app.services.reliability_monitor import (
    _owner_from_payload,
    list_job_metrics,
    list_queue_metrics,
    list_reliability_issues_for_owner,
)


def rank_recommendations(recommendations: list[RecoveryRecommendationRead]) -> list[RecoveryRecommendationRead]:
    return sorted(recommendations, key=lambda row: (-row.priority_score, row.created_at), reverse=False)


def generate_recovery_recommendations(session: Session, *, owner_user_id: int) -> list[RecoveryRecommendationRead]:
    issues, _ = list_reliability_issues_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    open_issues = [issue for issue in issues if issue.issue_status == "OPEN"]
    recommendations: list[RecoveryRecommendation] = []

    templates = {
        "failed_job": ("Review failed background jobs", "Inspect failed job logs and retry manually after root-cause review."),
        "stuck_job": ("Investigate stuck jobs", "Review long-running jobs and confirm worker health before retrying."),
        "queue_backlog": ("Investigate queue backlog", "Review queue depth and worker capacity; scale workers if needed."),
        "repeated_failure": ("Review repeated forecast jobs", "Inspect repeated failures for the same job type before re-running pipelines."),
        "platform_degradation": ("Validate backup integrity", "Review subsystem health checks and validate backup integrity before major changes."),
    }

    seen_types: set[str] = set()
    for issue in open_issues:
        if issue.issue_type in seen_types:
            continue
        seen_types.add(issue.issue_type)
        title, description = templates.get(
            issue.issue_type,
            ("Review operational issue", f"Investigate {issue.issue_type} in {issue.subsystem}."),
        )
        priority = 0.9 if issue.severity == "HIGH" else 0.6
        row = RecoveryRecommendation(
            subsystem=issue.subsystem,
            recommendation_type=issue.issue_type,
            title=title,
            description=f"[owner:{owner_user_id}] {description}",
            priority_score=priority,
        )
        session.add(row)
        recommendations.append(row)

    health_checks = list_health_checks_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    if any(check.subsystem == "data_protection" and check.health_status == "WARNING" for check in health_checks):
        row = RecoveryRecommendation(
            subsystem="data_protection",
            recommendation_type="integrity_review",
            title="Run data integrity validation",
            description=f"[owner:{owner_user_id}] Execute a data integrity check and review open issues before production changes.",
            priority_score=0.75,
        )
        session.add(row)
        recommendations.append(row)

    if not recommendations:
        row = RecoveryRecommendation(
            subsystem="platform",
            recommendation_type="routine_monitoring",
            title="Continue routine monitoring",
            description=f"[owner:{owner_user_id}] No open reliability issues detected. Continue scheduled health and reliability checks.",
            priority_score=0.2,
        )
        session.add(row)
        recommendations.append(row)

    session.commit()
    for row in recommendations:
        session.refresh(row)
    return rank_recommendations([RecoveryRecommendationRead.model_validate(row) for row in recommendations])


def _recommendation_owner(description: str) -> int | None:
    prefix = "[owner:"
    if not description.startswith(prefix):
        return None
    try:
        return int(description.split("]", 1)[0].replace(prefix, ""))
    except (TypeError, ValueError):
        return None


def list_recommendations_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RecoveryRecommendationRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(RecoveryRecommendation).order_by(RecoveryRecommendation.created_at.desc(), RecoveryRecommendation.id.desc())
    ).all()
    filtered = [row for row in rows if _recommendation_owner(row.description) == owner_user_id]
    items = [RecoveryRecommendationRead.model_validate(row) for row in filtered[offset : offset + limit]]
    return items, len(filtered)


def build_operations_summary(session: Session, *, owner_user_id: int) -> OperationsReliabilitySummaryRead:
    health_checks = list_health_checks_for_owner(session, owner_user_id=owner_user_id, limit=50, offset=0)
    issues, open_count = list_reliability_issues_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)
    open_count = sum(1 for issue in issues if issue.issue_status == "OPEN")
    recommendations, rec_count = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=200, offset=0)

    if not health_checks:
        readiness = 50.0
        platform_status = "WARNING"
    else:
        avg_score = sum(check.health_score for check in health_checks) / len(health_checks)
        readiness = max(0.0, min(100.0, avg_score - open_count * 5))
        if any(check.health_status == "FAILED" for check in health_checks):
            platform_status = "FAILED"
        elif any(check.health_status == "WARNING" for check in health_checks) or open_count:
            platform_status = "WARNING"
        else:
            platform_status = "HEALTHY"

    return OperationsReliabilitySummaryRead(
        readiness_score=round(readiness, 1),
        platform_health_status=platform_status,
        open_issue_count=open_count,
        recommendation_count=rec_count,
    )


def build_operations_dashboard(session: Session, *, owner_user_id: int) -> OperationsReliabilityDashboardRead:
    from app.schemas.operations_reliability import PlatformHealthCheckRead, ReliabilityIssueRead
    from app.services.pull_list_health import build_pull_list_automation_ops_panel
    from app.services.pull_list_certification import build_pull_list_certification_ops_panel
    from app.services.portfolio_certification import build_portfolio_certification_ops_panel
    from app.services.acquisition_certification import build_acquisition_certification_ops_panel
    from app.services.exit_certification import build_exit_certification_ops_panel
    from app.services.final_platform_certification import build_final_platform_certification_ops_panel
    from app.services.production_readiness_validation import build_production_readiness_ops_panel
    from app.services.future_release_certification import build_future_release_certification_ops_panel
    from app.services.industry_scanner_automation import build_industry_scanner_automation_ops_panel
    from app.services.industry_scanner_certification import build_industry_scanner_certification_ops_panel
    from app.services.spec_automation import build_spec_automation_ops_panel
    from app.services.ai_spec_certification import build_ai_spec_certification_ops_panel

    summary = build_operations_summary(session, owner_user_id=owner_user_id)
    health_checks = list_health_checks_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    issues, _ = list_reliability_issues_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    job_metrics, _ = list_job_metrics(session, limit=20, offset=0)
    queue_metrics, _ = list_queue_metrics(session, limit=20, offset=0)
    recommendations, _ = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=20, offset=0)
    pull_list_automation = build_pull_list_automation_ops_panel(session, owner_user_id=owner_user_id)
    pull_list_certification = build_pull_list_certification_ops_panel(session, owner_user_id=owner_user_id)
    portfolio_certification = build_portfolio_certification_ops_panel(session, owner_user_id=owner_user_id)
    acquisition_certification = build_acquisition_certification_ops_panel(session, owner_user_id=owner_user_id)
    exit_certification = build_exit_certification_ops_panel(session, owner_user_id=owner_user_id)
    final_platform_certification = build_final_platform_certification_ops_panel(session, owner_user_id=owner_user_id)
    production_readiness = build_production_readiness_ops_panel(session, owner_user_id=owner_user_id)
    future_release_certification = build_future_release_certification_ops_panel(session, owner_user_id=owner_user_id)
    industry_scanner_automation = build_industry_scanner_automation_ops_panel(session, owner_user_id=owner_user_id)
    industry_scanner_certification = build_industry_scanner_certification_ops_panel(session, owner_user_id=owner_user_id)
    spec_automation = build_spec_automation_ops_panel(session, owner_user_id=owner_user_id)
    ai_spec_certification = build_ai_spec_certification_ops_panel(session, owner_user_id=owner_user_id)

    # Latest subsystem health only
    latest: dict[str, PlatformHealthCheckRead] = {}
    for check in health_checks:
        if check.subsystem not in latest:
            latest[check.subsystem] = check

    return OperationsReliabilityDashboardRead(
        summary=summary,
        health_checks=list(latest.values()),
        issues=issues,
        job_metrics=job_metrics,
        queue_metrics=queue_metrics,
        recommendations=rank_recommendations(recommendations),
        pull_list_automation=pull_list_automation,
        pull_list_certification=pull_list_certification,
        portfolio_certification=portfolio_certification,
        acquisition_certification=acquisition_certification,
        exit_certification=exit_certification,
        final_platform_certification=final_platform_certification,
        production_readiness=production_readiness,
        future_release_certification=future_release_certification,
        industry_scanner_automation=industry_scanner_automation,
        industry_scanner_certification=industry_scanner_certification,
        spec_automation=spec_automation,
        ai_spec_certification=ai_spec_certification,
    )
