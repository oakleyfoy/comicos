"""Rollback a GCD write-batch job (delete rows created in that job only)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.asset_ledger import InventoryCopy
from app.models.catalog_master import CatalogIssue, CatalogUpc, CatalogVariant
from app.models.catalog_p97 import CatalogImportJob, utc_now


def rollback_gcd_import_job(session: Session, job_id: int) -> dict[str, int | str]:
    job = session.get(CatalogImportJob, job_id)
    if job is None:
        raise ValueError(f"Import job {job_id} not found")
    if job.status not in ("completed", "failed"):
        raise ValueError(f"Job {job_id} is not in a rollback-eligible state ({job.status})")

    cfg = dict(job.config or {})
    rollback = dict(cfg.get("rollback") or {})
    issue_ids = [int(x) for x in rollback.get("issue_ids") or []]
    upc_ids = [int(x) for x in rollback.get("upc_ids") or []]
    variant_ids = [int(x) for x in rollback.get("variant_ids") or []]

    if not issue_ids and not upc_ids:
        raise ValueError(f"Job {job_id} has no rollback payload")

    blocked_issues: list[int] = []
    for iid in issue_ids:
        linked = session.exec(select(InventoryCopy).where(InventoryCopy.catalog_issue_id == iid).limit(1)).first()
        if linked is not None:
            blocked_issues.append(iid)

    if blocked_issues:
        raise ValueError(
            f"Cannot rollback job {job_id}: inventory copies reference issues {blocked_issues[:5]}"
        )

    removed_upcs = 0
    for uid in upc_ids:
        row = session.get(CatalogUpc, uid)
        if row is not None:
            session.delete(row)
            removed_upcs += 1

    removed_variants = 0
    for vid in variant_ids:
        row = session.get(CatalogVariant, vid)
        if row is not None:
            session.delete(row)
            removed_variants += 1

    removed_issues = 0
    for iid in issue_ids:
        row = session.get(CatalogIssue, iid)
        if row is not None:
            session.delete(row)
            removed_issues += 1

    job.status = "rolled_back"
    job.completed_at = utc_now()
    job.updated_at = utc_now()
    cfg["rollback_applied_at"] = job.completed_at.isoformat()
    cfg["rollback_removed"] = {
        "issues": removed_issues,
        "upcs": removed_upcs,
        "variants": removed_variants,
    }
    job.config = cfg
    session.add(job)
    session.commit()

    return {
        "job_id": job_id,
        "status": "rolled_back",
        "removed_issues": removed_issues,
        "removed_upcs": removed_upcs,
        "removed_variants": removed_variants,
    }
