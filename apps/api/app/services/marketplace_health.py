from __future__ import annotations

from collections import Counter

from sqlmodel import Session, select

from app.models.marketplace import MarketplaceAccount, MarketplaceCredential, MarketplaceDefinition, MarketplaceExecution
from app.models.marketplace_publish import MarketplacePublishJob
from app.models.marketplace_sync import MarketplaceInventorySyncPlan, MarketplaceOrder
from app.schemas.marketplace_dashboard import MarketplaceHealthComponentRead, MarketplaceHealthRead
from app.services.marketplace_seed import ensure_marketplace_definitions

HEALTH_STATUS_HEALTHY = "HEALTHY"
HEALTH_STATUS_WARNING = "WARNING"
HEALTH_STATUS_FAILED = "FAILED"
HEALTH_STATUS_DISABLED = "DISABLED"

_EXECUTION_SUCCESS = {"COMPLETED"}
_EXECUTION_FAILURE = {"FAILED"}


def _aggregate_health(statuses: list[str]) -> str:
    if any(status == HEALTH_STATUS_FAILED for status in statuses):
        return HEALTH_STATUS_FAILED
    if any(status == HEALTH_STATUS_WARNING for status in statuses):
        return HEALTH_STATUS_WARNING
    if statuses and all(status == HEALTH_STATUS_DISABLED for status in statuses):
        return HEALTH_STATUS_DISABLED
    return HEALTH_STATUS_HEALTHY


def _execution_health(rows: list[MarketplaceExecution]) -> str:
    if not rows:
        return HEALTH_STATUS_WARNING
    failures = [row for row in rows if row.status in _EXECUTION_FAILURE]
    successes = [row for row in rows if row.status in _EXECUTION_SUCCESS]
    if failures and not successes:
        return HEALTH_STATUS_FAILED
    if failures:
        return HEALTH_STATUS_WARNING
    return HEALTH_STATUS_HEALTHY


def _component(
    *,
    component_code: str,
    title: str,
    health_status: str,
    summary: str,
    details_json: dict[str, object] | None = None,
) -> MarketplaceHealthComponentRead:
    return MarketplaceHealthComponentRead(
        component_code=component_code,
        title=title,
        health_status=health_status,
        summary=summary,
        details_json=details_json or {},
    )


def get_connector_health(session: Session, *, owner_id: int) -> MarketplaceHealthComponentRead:
    ensure_marketplace_definitions(session)
    definitions = session.exec(select(MarketplaceDefinition).order_by(MarketplaceDefinition.marketplace_code.asc())).all()
    accounts = session.exec(select(MarketplaceAccount).where(MarketplaceAccount.owner_id == owner_id)).all()
    account_ids = {int(row.id or 0) for row in accounts}
    if account_ids:
        executions = session.exec(
            select(MarketplaceExecution).where(MarketplaceExecution.account_id.in_(account_ids))  # type: ignore[attr-defined]
        ).all()
    else:
        executions = []

    enabled_count = sum(1 for row in definitions if row.enabled)
    status = _execution_health(executions)
    if enabled_count == 0 and accounts:
        status = HEALTH_STATUS_WARNING if status == HEALTH_STATUS_HEALTHY else status

    return _component(
        component_code="connector_health",
        title="Connector Health",
        health_status=status,
        summary=f"{len(definitions)} connectors registered; {enabled_count} enabled for platform use.",
        details_json={
            "owner_id": owner_id,
            "marketplace_count": len(definitions),
            "enabled_marketplace_count": enabled_count,
            "execution_count": len(executions),
            "execution_status_counts": dict(Counter(row.status for row in executions)),
        },
    )


def get_account_health(session: Session, *, owner_id: int) -> MarketplaceHealthComponentRead:
    accounts = session.exec(
        select(MarketplaceAccount).where(MarketplaceAccount.owner_id == owner_id).order_by(MarketplaceAccount.id.asc())
    ).all()
    credential_rows = session.exec(select(MarketplaceCredential)).all()
    creds_by_account = {int(row.account_id or 0) for row in credential_rows}
    statuses: list[str] = []
    for account in accounts:
        if account.status != "ACTIVE":
            statuses.append(HEALTH_STATUS_DISABLED)
        elif int(account.id or 0) not in creds_by_account:
            statuses.append(HEALTH_STATUS_FAILED)
        else:
            statuses.append(HEALTH_STATUS_HEALTHY)
    if not accounts:
        statuses.append(HEALTH_STATUS_WARNING)

    return _component(
        component_code="account_health",
        title="Account Health",
        health_status=_aggregate_health(statuses),
        summary=f"{len(accounts)} linked marketplace accounts reviewed.",
        details_json={
            "owner_id": owner_id,
            "account_count": len(accounts),
            "active_account_count": sum(1 for row in accounts if row.status == "ACTIVE"),
        },
    )


def get_publish_job_health(session: Session, *, owner_id: int) -> MarketplaceHealthComponentRead:
    jobs = session.exec(select(MarketplacePublishJob).where(MarketplacePublishJob.owner_id == owner_id)).all()
    counts = Counter(row.status for row in jobs)
    status = HEALTH_STATUS_HEALTHY
    if counts.get("FAILED", 0) > 0:
        status = HEALTH_STATUS_WARNING
    if not jobs:
        status = HEALTH_STATUS_WARNING

    return _component(
        component_code="publish_health",
        title="Publish Health",
        health_status=status,
        summary=f"{len(jobs)} publish jobs tracked for this owner.",
        details_json={"owner_id": owner_id, "publish_jobs_by_status": dict(counts)},
    )


def get_sync_plan_health(session: Session, *, owner_id: int) -> MarketplaceHealthComponentRead:
    plans = session.exec(
        select(MarketplaceInventorySyncPlan).where(MarketplaceInventorySyncPlan.owner_id == owner_id)
    ).all()
    counts = Counter(row.status for row in plans)
    status = HEALTH_STATUS_HEALTHY
    if counts.get("FAILED", 0) > 0:
        status = HEALTH_STATUS_FAILED
    elif not plans:
        status = HEALTH_STATUS_WARNING

    return _component(
        component_code="sync_health",
        title="Sync Health",
        health_status=status,
        summary=f"{len(plans)} inventory sync plans tracked.",
        details_json={"owner_id": owner_id, "sync_plans_by_status": dict(counts)},
    )


def get_order_import_health(session: Session, *, owner_id: int) -> MarketplaceHealthComponentRead:
    orders = session.exec(select(MarketplaceOrder).where(MarketplaceOrder.owner_id == owner_id)).all()
    accounts = session.exec(select(MarketplaceAccount).where(MarketplaceAccount.owner_id == owner_id)).all()
    account_ids = {int(row.id or 0) for row in accounts}
    import_executions: list[MarketplaceExecution] = []
    if account_ids:
        import_executions = session.exec(
            select(MarketplaceExecution)
            .where(MarketplaceExecution.account_id.in_(account_ids))  # type: ignore[attr-defined]
            .where(MarketplaceExecution.execution_type == "IMPORT_ORDERS")
        ).all()

    status = _execution_health(import_executions)
    if not orders and status == HEALTH_STATUS_HEALTHY:
        status = HEALTH_STATUS_WARNING

    return _component(
        component_code="order_import_health",
        title="Order Import Health",
        health_status=status,
        summary=f"{len(orders)} imported orders and {len(import_executions)} import executions reviewed.",
        details_json={
            "owner_id": owner_id,
            "order_count": len(orders),
            "import_execution_count": len(import_executions),
        },
    )


def get_marketplace_health(session: Session, *, owner_id: int) -> MarketplaceHealthRead:
    components = [
        get_connector_health(session, owner_id=owner_id),
        get_account_health(session, owner_id=owner_id),
        get_publish_job_health(session, owner_id=owner_id),
        get_sync_plan_health(session, owner_id=owner_id),
        get_order_import_health(session, owner_id=owner_id),
    ]
    return MarketplaceHealthRead(
        overall_status=_aggregate_health([component.health_status for component in components]),
        components=components,
    )
