import logging
from datetime import timedelta
from functools import lru_cache

from redis import Redis
from rq import Queue, Retry, Worker
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

from app.core.config import get_settings

LOGGER = logging.getLogger(__name__)

AI_PARSE_IMPORT_JOB_TYPE = "ai_parse_import"
GMAIL_SYNC_JOB_TYPE = "gmail_sync"


@lru_cache
def get_redis_connection() -> Redis:
    settings = get_settings()
    return Redis.from_url(settings.redis_url)


def get_queue(queue_name: str) -> Queue:
    settings = get_settings()
    return Queue(
        name=queue_name,
        connection=get_redis_connection(),
        default_timeout=settings.rq_job_timeout_seconds,
    )


def get_ai_parse_queue() -> Queue:
    settings = get_settings()
    return get_queue(settings.rq_ai_parse_queue_name)


def get_gmail_sync_queue() -> Queue:
    settings = get_settings()
    return get_queue(settings.rq_gmail_sync_queue_name)


def get_worker_queue_names() -> list[str]:
    settings = get_settings()
    return list(
        dict.fromkeys(
            [
                settings.rq_ai_parse_queue_name,
                settings.rq_gmail_sync_queue_name,
            ]
        )
    )


def get_worker_queues() -> list[Queue]:
    return [get_queue(queue_name) for queue_name in get_worker_queue_names()]


def build_retry_policy() -> Retry | None:
    settings = get_settings()
    if settings.rq_job_retry_max < 1:
        return None
    return Retry(
        max=settings.rq_job_retry_max,
        interval=settings.rq_job_retry_interval_seconds,
    )


def enqueue_ai_parse_import_job(*, user_id: int, raw_text: str) -> Job:
    from app.tasks.jobs import run_ai_parse_import_job

    settings = get_settings()
    queue = get_ai_parse_queue()
    job = queue.enqueue(
        run_ai_parse_import_job,
        user_id,
        raw_text,
        description=f"AI parse import for user {user_id}",
        meta={
            "job_type": AI_PARSE_IMPORT_JOB_TYPE,
            "user_id": user_id,
        },
        retry=build_retry_policy(),
        result_ttl=settings.rq_job_result_ttl_seconds,
        failure_ttl=settings.rq_job_failure_ttl_seconds,
        job_timeout=settings.rq_job_timeout_seconds,
    )
    LOGGER.info(
        "Enqueued job %s job_type=%s queue=%s user_id=%s",
        job.id,
        AI_PARSE_IMPORT_JOB_TYPE,
        queue.name,
        user_id,
    )
    return job


def enqueue_gmail_sync_job(*, user_id: int, gmail_account_id: int) -> Job:
    from app.tasks.jobs import run_gmail_sync_job

    settings = get_settings()
    queue = get_gmail_sync_queue()
    job = queue.enqueue(
        run_gmail_sync_job,
        user_id,
        gmail_account_id,
        description=f"Gmail sync for user {user_id}",
        meta={
            "job_type": GMAIL_SYNC_JOB_TYPE,
            "user_id": user_id,
            "gmail_account_id": gmail_account_id,
        },
        result_ttl=settings.rq_job_result_ttl_seconds,
        failure_ttl=settings.rq_job_failure_ttl_seconds,
        job_timeout=settings.rq_job_timeout_seconds,
    )
    LOGGER.info(
        "Enqueued job %s job_type=%s queue=%s user_id=%s gmail_account_id=%s",
        job.id,
        GMAIL_SYNC_JOB_TYPE,
        queue.name,
        user_id,
        gmail_account_id,
    )
    return job


def schedule_job_in(
    queue_name: str,
    delay_seconds: int,
    func: str,
    *args,
    meta: dict | None = None,
    job_id: str | None = None,
) -> Job:
    settings = get_settings()
    queue = get_queue(queue_name)
    job = queue.enqueue_in(
        timedelta(seconds=delay_seconds),
        func,
        *args,
        meta=meta,
        job_id=job_id,
        result_ttl=settings.rq_job_result_ttl_seconds,
        failure_ttl=settings.rq_job_failure_ttl_seconds,
        job_timeout=settings.rq_job_timeout_seconds,
    )
    LOGGER.info(
        "Enqueued scheduled job %s queue=%s delay_seconds=%s func=%s",
        job.id,
        queue.name,
        delay_seconds,
        func,
    )
    return job


def fetch_job_by_id(job_id: str) -> Job | None:
    try:
        return Job.fetch(job_id, connection=get_redis_connection())
    except NoSuchJobError:
        return None


def _active_job_ids(queue: Queue) -> set[str]:
    registry_job_ids = set(queue.job_ids)
    registry_job_ids.update(StartedJobRegistry(queue=queue).get_job_ids())
    registry_job_ids.update(DeferredJobRegistry(queue=queue).get_job_ids())
    registry_job_ids.update(ScheduledJobRegistry(queue=queue).get_job_ids())
    return registry_job_ids


def find_active_gmail_sync_job_for_account(gmail_account_id: int) -> Job | None:
    queue = get_gmail_sync_queue()
    for job_id in _active_job_ids(queue):
        job = fetch_job_by_id(job_id)
        if job is None:
            continue
        if (
            job.meta.get("job_type") == GMAIL_SYNC_JOB_TYPE
            and job.meta.get("gmail_account_id") == gmail_account_id
        ):
            return job

    return None


def cleanup_stale_started_jobs(queue_names: list[str] | None = None) -> dict[str, object]:
    connection = get_redis_connection()
    active_worker_names = {worker.name for worker in Worker.all(connection=connection)}
    names = queue_names or get_worker_queue_names()
    removed_job_ids: list[str] = []

    for queue_name in names:
        queue = get_queue(queue_name)
        registry = StartedJobRegistry(queue=queue)
        for job_id in registry.get_job_ids():
            job = fetch_job_by_id(job_id)
            if job is None:
                continue

            worker_name = getattr(job, "worker_name", None)
            if worker_name in active_worker_names:
                continue

            registry.remove(job, delete_job=False)
            job.delete()
            removed_job_ids.append(job.id)
            LOGGER.warning(
                "Removed stale started job %s queue=%s dead_worker=%s",
                job.id,
                queue.name,
                worker_name,
            )

    return {
        "queues": names,
        "removed_count": len(removed_job_ids),
        "removed_job_ids": removed_job_ids,
    }
