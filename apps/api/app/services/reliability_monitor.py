from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from rq.job import Job
from rq.registry import FailedJobRegistry, StartedJobRegistry
from sqlmodel import Session, select

from app.models.operations_reliability import JobHealthMetric, QueueHealthMetric, ReliabilityIssue
from app.schemas.operations_reliability import JobHealthMetricRead, QueueHealthMetricRead, ReliabilityIssueRead
from app.tasks.queue import fetch_job_by_id, get_queue, get_worker_queue_names


def _owner_from_payload(payload: dict) -> int | None:
    raw = payload.get("owner_user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _collect_jobs_for_owner(owner_user_id: int) -> list[Job]:
    jobs_by_id: dict[str, Job] = {}
    for queue_name in get_worker_queue_names():
        queue = get_queue(queue_name)
        candidate_ids = list(queue.job_ids)
        candidate_ids.extend(StartedJobRegistry(queue=queue).get_job_ids())
        candidate_ids.extend(FailedJobRegistry(queue=queue).get_job_ids())
        for job_id in candidate_ids:
            if job_id in jobs_by_id:
                continue
            job = fetch_job_by_id(job_id)
            if job is None:
                continue
            meta_user = job.meta.get("user_id")
            if meta_user is not None and int(meta_user) != owner_user_id:
                continue
            jobs_by_id[job.id] = job
    return list(jobs_by_id.values())


def _issue(
    *,
    owner_user_id: int,
    subsystem: str,
    issue_type: str,
    severity: str,
    issue_payload_json: dict,
) -> ReliabilityIssue:
    return ReliabilityIssue(
        subsystem=subsystem,
        issue_type=issue_type,
        severity=severity,
        issue_status="OPEN",
        issue_payload_json={**issue_payload_json, "owner_user_id": owner_user_id},
    )


def detect_failed_jobs(session: Session, *, owner_user_id: int) -> list[ReliabilityIssueRead]:
    issues: list[ReliabilityIssue] = []
    for job in _collect_jobs_for_owner(owner_user_id):
        if job.get_status(refresh=False) != "failed":
            continue
        issues.append(
            _issue(
                owner_user_id=owner_user_id,
                subsystem="jobs",
                issue_type="failed_job",
                severity="HIGH",
                issue_payload_json={"job_id": job.id, "job_type": job.meta.get("job_type"), "queue": job.origin},
            )
        )
    for row in issues:
        session.add(row)
    if issues:
        session.commit()
        for row in issues:
            session.refresh(row)
    return [ReliabilityIssueRead.model_validate(row) for row in issues]


def detect_stuck_jobs(session: Session, *, owner_user_id: int) -> list[ReliabilityIssueRead]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    issues: list[ReliabilityIssue] = []
    for job in _collect_jobs_for_owner(owner_user_id):
        if job.get_status(refresh=False) != "started":
            continue
        started = job.started_at
        if started is not None and started.replace(tzinfo=timezone.utc) < cutoff:
            issues.append(
                _issue(
                    owner_user_id=owner_user_id,
                    subsystem="jobs",
                    issue_type="stuck_job",
                    severity="MEDIUM",
                    issue_payload_json={"job_id": job.id, "started_at": started.isoformat()},
                )
            )
    for row in issues:
        session.add(row)
    if issues:
        session.commit()
        for row in issues:
            session.refresh(row)
    return [ReliabilityIssueRead.model_validate(row) for row in issues]


def detect_queue_backlogs(session: Session, *, owner_user_id: int, backlog_threshold: int = 25) -> list[ReliabilityIssueRead]:
    issues: list[ReliabilityIssue] = []
    for queue_name in get_worker_queue_names():
        queue = get_queue(queue_name)
        queued = len(queue.job_ids)
        if queued < backlog_threshold:
            continue
        issues.append(
            _issue(
                owner_user_id=owner_user_id,
                subsystem="queues",
                issue_type="queue_backlog",
                severity="MEDIUM",
                issue_payload_json={"queue_name": queue_name, "queued_count": queued, "threshold": backlog_threshold},
            )
        )
    for row in issues:
        session.add(row)
    if issues:
        session.commit()
        for row in issues:
            session.refresh(row)
    return [ReliabilityIssueRead.model_validate(row) for row in issues]


def detect_repeated_failures(session: Session, *, owner_user_id: int) -> list[ReliabilityIssueRead]:
    counter: Counter[str] = Counter()
    for job in _collect_jobs_for_owner(owner_user_id):
        if job.get_status(refresh=False) != "failed":
            continue
        job_type = str(job.meta.get("job_type") or "unknown")
        counter[job_type] += 1
    issues: list[ReliabilityIssue] = []
    for job_type, count in counter.items():
        if count < 2:
            continue
        issues.append(
            _issue(
                owner_user_id=owner_user_id,
                subsystem="jobs",
                issue_type="repeated_failure",
                severity="HIGH",
                issue_payload_json={"job_type": job_type, "failure_count": count},
            )
        )
    for row in issues:
        session.add(row)
    if issues:
        session.commit()
        for row in issues:
            session.refresh(row)
    return [ReliabilityIssueRead.model_validate(row) for row in issues]


def detect_platform_degradation(session: Session, *, owner_user_id: int) -> list[ReliabilityIssueRead]:
    from app.models.operations_reliability import PlatformHealthCheck

    rows = session.exec(select(PlatformHealthCheck).order_by(PlatformHealthCheck.checked_at.desc(), PlatformHealthCheck.id.desc())).all()
    latest_by_subsystem: dict[str, PlatformHealthCheck] = {}
    for row in rows:
        if _owner_from_payload(row.check_payload_json) != owner_user_id:
            continue
        if row.subsystem not in latest_by_subsystem:
            latest_by_subsystem[row.subsystem] = row
    issues: list[ReliabilityIssue] = []
    for subsystem, check in latest_by_subsystem.items():
        if check.health_status not in {"FAILED", "WARNING"}:
            continue
        issues.append(
            _issue(
                owner_user_id=owner_user_id,
                subsystem=subsystem,
                issue_type="platform_degradation",
                severity="HIGH" if check.health_status == "FAILED" else "MEDIUM",
                issue_payload_json={"health_status": check.health_status, "health_score": check.health_score},
            )
        )
    for row in issues:
        session.add(row)
    if issues:
        session.commit()
        for row in issues:
            session.refresh(row)
    return [ReliabilityIssueRead.model_validate(row) for row in issues]


def capture_job_health_metrics(session: Session, *, owner_user_id: int) -> list[JobHealthMetricRead]:
    buckets: dict[str, list[Job]] = defaultdict(list)
    for job in _collect_jobs_for_owner(owner_user_id):
        job_type = str(job.meta.get("job_type") or "unknown")
        buckets[job_type].append(job)

    metrics: list[JobHealthMetric] = []
    for job_type, jobs in sorted(buckets.items()):
        failed = sum(1 for job in jobs if job.get_status(refresh=False) == "failed")
        successful = sum(1 for job in jobs if job.get_status(refresh=False) == "finished")
        durations: list[int] = []
        for job in jobs:
            if job.started_at and job.ended_at:
                delta = job.ended_at - job.started_at
                durations.append(int(delta.total_seconds() * 1000))
        avg_duration = int(sum(durations) / len(durations)) if durations else 0
        row = JobHealthMetric(
            job_type=job_type,
            total_jobs=len(jobs),
            successful_jobs=successful,
            failed_jobs=failed,
            average_duration_ms=avg_duration,
        )
        session.add(row)
        metrics.append(row)
    if not metrics:
        row = JobHealthMetric(job_type="none", total_jobs=0, successful_jobs=0, failed_jobs=0, average_duration_ms=0)
        session.add(row)
        metrics.append(row)
    session.commit()
    for row in metrics:
        session.refresh(row)
    return [JobHealthMetricRead.model_validate(row) for row in metrics]


def capture_queue_health_metrics(session: Session, *, owner_user_id: int) -> list[QueueHealthMetricRead]:
    del owner_user_id  # queue metrics are platform-wide snapshots
    metrics: list[QueueHealthMetric] = []
    for queue_name in get_worker_queue_names():
        queue = get_queue(queue_name)
        failed_registry = FailedJobRegistry(queue=queue)
        started_registry = StartedJobRegistry(queue=queue)
        row = QueueHealthMetric(
            queue_name=queue_name,
            queued_count=len(queue.job_ids),
            running_count=len(started_registry.get_job_ids()),
            failed_count=len(failed_registry.get_job_ids()),
        )
        session.add(row)
        metrics.append(row)
    if not metrics:
        row = QueueHealthMetric(queue_name="default", queued_count=0, running_count=0, failed_count=0)
        session.add(row)
        metrics.append(row)
    session.commit()
    for row in metrics:
        session.refresh(row)
    return [QueueHealthMetricRead.model_validate(row) for row in metrics]


def run_reliability_monitor(session: Session, *, owner_user_id: int) -> dict[str, object]:
    issues: list[ReliabilityIssueRead] = []
    issues.extend(detect_failed_jobs(session, owner_user_id=owner_user_id))
    issues.extend(detect_stuck_jobs(session, owner_user_id=owner_user_id))
    issues.extend(detect_queue_backlogs(session, owner_user_id=owner_user_id))
    issues.extend(detect_repeated_failures(session, owner_user_id=owner_user_id))
    issues.extend(detect_platform_degradation(session, owner_user_id=owner_user_id))
    job_metrics = capture_job_health_metrics(session, owner_user_id=owner_user_id)
    queue_metrics = capture_queue_health_metrics(session, owner_user_id=owner_user_id)
    return {"issues": issues, "job_metrics": job_metrics, "queue_metrics": queue_metrics}


def list_reliability_issues_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ReliabilityIssueRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(select(ReliabilityIssue).order_by(ReliabilityIssue.detected_at.desc(), ReliabilityIssue.id.desc())).all()
    filtered = [ReliabilityIssueRead.model_validate(row) for row in rows if _owner_from_payload(row.issue_payload_json) == owner_user_id]
    return filtered[offset : offset + limit], len(filtered)


def list_job_metrics(session: Session, *, limit: int = 50, offset: int = 0) -> tuple[list[JobHealthMetricRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(select(JobHealthMetric).order_by(JobHealthMetric.measured_at.desc(), JobHealthMetric.id.desc())).all()
    items = [JobHealthMetricRead.model_validate(row) for row in rows[offset : offset + limit]]
    return items, len(rows)


def list_queue_metrics(session: Session, *, limit: int = 50, offset: int = 0) -> tuple[list[QueueHealthMetricRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(select(QueueHealthMetric).order_by(QueueHealthMetric.measured_at.desc(), QueueHealthMetric.id.desc())).all()
    items = [QueueHealthMetricRead.model_validate(row) for row in rows[offset : offset + limit]]
    return items, len(rows)
