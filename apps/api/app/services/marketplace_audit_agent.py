from __future__ import annotations

from sqlmodel import Session, select

from app.models import AgentDefinition
from app.models.marketplace import MarketplaceAccount as MarketplaceConnectorAccount
from app.models.marketplace import MarketplaceDefinition as MarketplaceConnectorDefinition
from app.models.marketplace_listing import MarketplaceListing, MarketplaceListingMapping
from app.models.marketplace_publish import MarketplacePublishJob, MarketplacePublishTarget
from app.schemas.marketplace_operations import MarketplaceOperationsRunResponse
from app.services.agent_execution import complete_execution, start_execution
from app.services.marketplace_operations import create_recommendation_with_evidence, get_operations_dashboard

AGENT_CODE = "marketplace_audit_agent"
RECOMMENDATION_TYPE = "MARKETPLACE_AUDIT"


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("Marketplace audit agent is not registered.")
    return int(row.id)


def run_marketplace_audit_agent(session: Session, *, owner_user_id: int) -> MarketplaceOperationsRunResponse:
    execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="marketplace_operations.audit",
        enforce_permissions=False,
    )
    created: list = []
    mappings = session.exec(
        select(MarketplaceListingMapping)
        .join(MarketplaceListing, MarketplaceListing.id == MarketplaceListingMapping.listing_id)
        .where(MarketplaceListing.owner_id == owner_user_id)
        .order_by(MarketplaceListingMapping.id.asc())
    ).all()
    for mapping in mappings:
        listing = session.get(MarketplaceListing, mapping.listing_id)
        if listing is None:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"mapping:{mapping.id}:orphan",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Orphan marketplace mapping",
                    description="Mapping references a listing that no longer exists.",
                    listing_id=mapping.listing_id,
                    marketplace_id=mapping.marketplace_id,
                    marketplace_account_id=mapping.marketplace_account_id,
                    evidence=[
                        {
                            "evidence_type": "orphan_mapping",
                            "evidence_source": "marketplace_listing_mapping",
                            "evidence_payload_json": {"mapping_id": int(mapping.id or 0)},
                            "evidence_score": 0.9,
                        }
                    ],
                    severity=0.8,
                )
            )
            continue
        account = session.get(MarketplaceConnectorAccount, mapping.marketplace_account_id)
        if account is None or account.owner_id != owner_user_id:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"mapping:{mapping.id}:invalid_account",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Invalid account reference",
                    description="Mapping references a marketplace account that is missing or not owned by the user.",
                    listing_id=mapping.listing_id,
                    marketplace_id=mapping.marketplace_id,
                    marketplace_account_id=mapping.marketplace_account_id,
                    evidence=[
                        {
                            "evidence_type": "invalid_account_reference",
                            "evidence_source": "marketplace_account",
                            "evidence_payload_json": {"mapping_id": int(mapping.id or 0)},
                            "evidence_score": 0.88,
                        }
                    ],
                    severity=0.85,
                )
            )
        marketplace = session.get(MarketplaceConnectorDefinition, mapping.marketplace_id)
        if marketplace is None or not marketplace.enabled:
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"mapping:{mapping.id}:inactive_marketplace",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Inactive marketplace reference",
                    description="Mapping references a disabled or missing marketplace definition.",
                    listing_id=mapping.listing_id,
                    marketplace_id=mapping.marketplace_id,
                    marketplace_account_id=mapping.marketplace_account_id,
                    evidence=[
                        {
                            "evidence_type": "inactive_marketplace_reference",
                            "evidence_source": "marketplace_definition",
                            "evidence_payload_json": {"marketplace_id": mapping.marketplace_id},
                            "evidence_score": 0.8,
                        }
                    ],
                    severity=0.7,
                )
            )
        if mapping.external_listing_id and mapping.sync_status.upper() == "PENDING":
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"mapping:{mapping.id}:invalid_mapping",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Invalid mapping state",
                    description="External listing id exists but mapping sync status is still pending.",
                    listing_id=mapping.listing_id,
                    marketplace_id=mapping.marketplace_id,
                    marketplace_account_id=mapping.marketplace_account_id,
                    evidence=[
                        {
                            "evidence_type": "invalid_mapping",
                            "evidence_source": "marketplace_listing_mapping",
                            "evidence_payload_json": {
                                "external_listing_id": mapping.external_listing_id,
                                "sync_status": mapping.sync_status,
                            },
                            "evidence_score": 0.76,
                        }
                    ],
                    severity=0.6,
                )
            )
    jobs = session.exec(
        select(MarketplacePublishJob).where(MarketplacePublishJob.owner_id == owner_user_id).order_by(MarketplacePublishJob.id.asc())
    ).all()
    for job in jobs:
        targets = session.exec(
            select(MarketplacePublishTarget).where(MarketplacePublishTarget.job_id == int(job.id or 0))
        ).all()
        if job.status == "COMPLETED" and any(t.target_status == "FAILED" for t in targets):
            created.append(
                create_recommendation_with_evidence(
                    session,
                    agent_execution_id=execution.execution.id,
                    recommendation_key=f"publish_job:{job.id}:lifecycle",
                    recommendation_type=RECOMMENDATION_TYPE,
                    title="Publish lifecycle inconsistency",
                    description="Completed publish job contains failed targets.",
                    listing_id=job.listing_id,
                    evidence=[
                        {
                            "evidence_type": "publish_lifecycle_inconsistency",
                            "evidence_source": "marketplace_publish_job",
                            "evidence_payload_json": {"job_id": int(job.id or 0), "job_status": job.status},
                            "evidence_score": 0.84,
                        }
                    ],
                    severity=0.75,
                )
            )
    complete_execution(
        session,
        execution_id=execution.execution.id,
        event_payload_json={"recommendations_created": len(created)},
    )
    return MarketplaceOperationsRunResponse(
        agent_execution_id=execution.execution.id,
        recommendations_created=len(created),
        dashboard=get_operations_dashboard(session, owner_user_id=owner_user_id),
        recommendations=created,
    )
