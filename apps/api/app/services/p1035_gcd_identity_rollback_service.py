"""Rollback P103.5 identity backfill jobs (external_source_ids + job-inserted UPCs only)."""

from __future__ import annotations

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogUpc
from app.models.catalog_p97 import CatalogImportJob, utc_now


def rollback_p1035_identity_job(session: Session, job_id: int) -> dict[str, int | str]:
    job = session.get(CatalogImportJob, job_id)
    if job is None:
        raise ValueError(f"Import job {job_id} not found")
    if job.status not in ("completed", "failed"):
        raise ValueError(f"Job {job_id} is not in a rollback-eligible state ({job.status})")

    cfg = dict(job.config or {})
    rollback = dict(cfg.get("rollback") or {})
    upc_ids = [int(x) for x in rollback.get("upc_ids") or []]
    snapshots = list(rollback.get("issue_snapshots") or [])

    if not snapshots and not upc_ids:
        raise ValueError(f"Job {job_id} has no rollback payload")

    restored_issues = 0
    for snap in snapshots:
        iid = int(snap.get("catalog_issue_id") or 0)
        issue = session.get(CatalogIssue, iid)
        if issue is None:
            continue
        before = dict(snap.get("before") or {})
        if "external_source_ids" in before:
            issue.external_source_ids = dict(before["external_source_ids"])
            session.add(issue)
            restored_issues += 1

    removed_upcs = 0
    for uid in upc_ids:
        row = session.get(CatalogUpc, uid)
        if row is not None:
            session.delete(row)
            removed_upcs += 1

    job.status = "rolled_back"
    job.completed_at = utc_now()
    job.updated_at = utc_now()
    cfg["rollback_applied_at"] = job.completed_at.isoformat()
    cfg["rollback_removed"] = {
        "restored_issues": restored_issues,
        "removed_upcs": removed_upcs,
    }
    job.config = cfg
    session.add(job)
    session.commit()

    return {
        "job_id": job_id,
        "restored_issues": restored_issues,
        "removed_upcs": removed_upcs,
        "status": "rolled_back",
    }
