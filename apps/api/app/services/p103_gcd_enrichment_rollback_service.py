"""Rollback a P103 GCD enrichment write job (restore fields; delete job-inserted UPCs only)."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session

from app.models.catalog_master import CatalogIssue, CatalogUpc, CatalogVariant
from app.models.catalog_p97 import CatalogImportJob, utc_now


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(str(value))


def rollback_p103_enrichment_job(session: Session, job_id: int) -> dict[str, int | str]:
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
    restored_variants = 0
    for snap in snapshots:
        iid = int(snap.get("catalog_issue_id") or 0)
        issue = session.get(CatalogIssue, iid)
        if issue is None:
            continue
        before = dict(snap.get("before") or {})
        issue.external_source_ids = dict(before.get("external_source_ids") or {})
        issue.cover_date = _parse_date(before.get("cover_date"))
        issue.release_date = _parse_date(before.get("release_date"))
        issue.store_date = _parse_date(before.get("store_date"))
        issue.title = before.get("title")
        issue.description = before.get("description")
        session.add(issue)
        restored_issues += 1

        vid = snap.get("catalog_variant_id")
        variant_before = snap.get("variant_before")
        if vid and isinstance(variant_before, dict):
            variant = session.get(CatalogVariant, int(vid))
            if variant is not None:
                variant.printing = variant_before.get("printing")
                variant.variant_name = variant_before.get("variant_name")
                session.add(variant)
                restored_variants += 1

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
        "restored_variants": restored_variants,
        "removed_upcs": removed_upcs,
    }
    job.config = cfg
    session.add(job)
    session.commit()

    return {
        "job_id": job_id,
        "status": "rolled_back",
        "restored_issues": restored_issues,
        "restored_variants": restored_variants,
        "removed_upcs": removed_upcs,
    }
