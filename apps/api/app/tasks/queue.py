import logging
from datetime import timedelta
from functools import lru_cache
from typing import Literal

from redis import Redis
from rq import Queue, Retry, Worker
from rq.exceptions import NoSuchJobError
from rq.job import Job
from rq.registry import DeferredJobRegistry, ScheduledJobRegistry, StartedJobRegistry

from app.core.config import get_settings

LOGGER = logging.getLogger(__name__)

AI_PARSE_IMPORT_JOB_TYPE = "ai_parse_import"
GMAIL_SYNC_JOB_TYPE = "gmail_sync"
METADATA_REENRICH_JOB_TYPE = "metadata_reenrich"
COVER_IMAGE_PROCESS_JOB_TYPE = "cover_image_process"
COVER_IMAGE_OCR_JOB_TYPE = "cover_image_ocr"


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


def build_cover_pipeline_retry_policy() -> Retry | None:
    settings = get_settings()
    if settings.rq_cover_pipeline_retry_max < 1:
        return None
    return Retry(
        max=settings.rq_cover_pipeline_retry_max,
        interval=settings.rq_cover_pipeline_retry_interval_seconds,
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


def enqueue_metadata_reenrich_job(
    *,
    entity_type: str,
    entity_id: int,
    user_id: int,
    reason: str | None = None,
) -> Job:
    from app.tasks.jobs import run_metadata_reenrich_job

    settings = get_settings()
    queue = get_ai_parse_queue()
    job_id = f"metadata-reenrich-{entity_type}-{entity_id}"
    existing = fetch_job_by_id(job_id)
    if existing is not None and existing.get_status(refresh=True) in {
        "queued",
        "started",
        "scheduled",
        "deferred",
    }:
        return existing

    job = queue.enqueue(
        run_metadata_reenrich_job,
        entity_type,
        entity_id,
        user_id,
        reason,
        job_id=job_id,
        description=f"Metadata re-enrichment for {entity_type} {entity_id}",
        meta={
            "job_type": METADATA_REENRICH_JOB_TYPE,
            "user_id": user_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "reason": reason,
        },
        retry=build_retry_policy(),
        result_ttl=settings.rq_job_result_ttl_seconds,
        failure_ttl=settings.rq_job_failure_ttl_seconds,
        job_timeout=settings.rq_job_timeout_seconds,
    )
    LOGGER.info(
        "Enqueued job %s job_type=%s queue=%s user_id=%s entity_type=%s entity_id=%s",
        job.id,
        METADATA_REENRICH_JOB_TYPE,
        queue.name,
        user_id,
        entity_type,
        entity_id,
    )
    return job


def enqueue_cover_image_process_job(*, cover_image_id: int, user_id: int) -> Job:
    from app.tasks.jobs import run_cover_image_process_job

    settings = get_settings()
    queue = get_ai_parse_queue()
    job_id = f"cover-image-process-{cover_image_id}"
    existing = fetch_job_by_id(job_id)
    active_statuses = {"queued", "started", "scheduled", "deferred"}
    if existing is not None and existing.get_status(refresh=True) in active_statuses:
        return existing

    job = queue.enqueue(
        run_cover_image_process_job,
        cover_image_id,
        user_id,
        job_id=job_id,
        description=f"Cover image processing for cover {cover_image_id}",
        meta={
            "job_type": COVER_IMAGE_PROCESS_JOB_TYPE,
            "user_id": user_id,
            "cover_image_id": cover_image_id,
            "retry_policy_max": settings.rq_cover_pipeline_retry_max,
            "retry_policy_interval_seconds": settings.rq_cover_pipeline_retry_interval_seconds,
            "pipeline_job_timeout_seconds": settings.rq_cover_pipeline_job_timeout_seconds,
        },
        retry=build_cover_pipeline_retry_policy(),
        result_ttl=settings.rq_job_result_ttl_seconds,
        failure_ttl=settings.rq_job_failure_ttl_seconds,
        job_timeout=settings.rq_cover_pipeline_job_timeout_seconds,
    )
    LOGGER.info(
        "Enqueued job %s job_type=%s queue=%s user_id=%s cover_image_id=%s",
        job.id,
        COVER_IMAGE_PROCESS_JOB_TYPE,
        queue.name,
        user_id,
        cover_image_id,
    )
    return job


COVER_IMAGE_OCR_JOB_ID_TEMPLATE = "cover-image-ocr-{cover_image_id}"


def cover_image_ocr_job_ui_status(cover_image_id: int) -> Literal["idle", "queued", "running"]:
    """RQ-backed queue state for the deterministic OCR job id."""
    job = fetch_job_by_id(COVER_IMAGE_OCR_JOB_ID_TEMPLATE.format(cover_image_id=cover_image_id))
    if job is None:
        return "idle"
    status = job.get_status(refresh=True)
    if status in {"queued", "scheduled", "deferred"}:
        return "queued"
    if status == "started":
        return "running"
    return "idle"


def enqueue_cover_image_ocr_job(*, cover_image_id: int, user_id: int, ocr_result_id: int) -> Job:
    from app.tasks.jobs import run_cover_image_ocr_job

    settings = get_settings()
    queue = get_ai_parse_queue()
    job_id = COVER_IMAGE_OCR_JOB_ID_TEMPLATE.format(cover_image_id=cover_image_id)
    existing = fetch_job_by_id(job_id)
    active_statuses = {"queued", "started", "scheduled", "deferred"}
    if existing is not None and existing.get_status(refresh=True) in active_statuses:
        return existing

    job = queue.enqueue(
        run_cover_image_ocr_job,
        cover_image_id,
        user_id,
        ocr_result_id,
        job_id=job_id,
        description=f"Cover image OCR for cover {cover_image_id}",
        meta={
            "job_type": COVER_IMAGE_OCR_JOB_TYPE,
            "user_id": user_id,
            "cover_image_id": cover_image_id,
            "ocr_result_id": ocr_result_id,
            "retry_policy_max": settings.rq_cover_pipeline_retry_max,
            "retry_policy_interval_seconds": settings.rq_cover_pipeline_retry_interval_seconds,
            "pipeline_job_timeout_seconds": settings.rq_cover_pipeline_job_timeout_seconds,
        },
        retry=build_cover_pipeline_retry_policy(),
        result_ttl=settings.rq_job_result_ttl_seconds,
        failure_ttl=settings.rq_job_failure_ttl_seconds,
        job_timeout=settings.rq_cover_pipeline_job_timeout_seconds,
    )
    LOGGER.info(
        "Enqueued job %s job_type=%s queue=%s user_id=%s cover_image_id=%s ocr_result_id=%s",
        job.id,
        COVER_IMAGE_OCR_JOB_TYPE,
        queue.name,
        user_id,
        cover_image_id,
        ocr_result_id,
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


def find_active_metadata_reenrich_job(entity_type: str, entity_id: int) -> Job | None:
    queue = get_ai_parse_queue()
    for job_id in _active_job_ids(queue):
        job = fetch_job_by_id(job_id)
        if job is None:
            continue
        if (
            job.meta.get("job_type") == METADATA_REENRICH_JOB_TYPE
            and job.meta.get("entity_type") == entity_type
            and job.meta.get("entity_id") == entity_id
        ):
            return job
    return None


def find_active_cover_image_process_job(cover_image_id: int) -> Job | None:
    queue = get_ai_parse_queue()
    for job_id in _active_job_ids(queue):
        job = fetch_job_by_id(job_id)
        if job is None:
            continue
        if (
            job.meta.get("job_type") == COVER_IMAGE_PROCESS_JOB_TYPE
            and job.meta.get("cover_image_id") == cover_image_id
        ):
            return job
    return None


def find_active_cover_image_ocr_job(cover_image_id: int) -> Job | None:
    queue = get_ai_parse_queue()
    for job_id in _active_job_ids(queue):
        job = fetch_job_by_id(job_id)
        if job is None:
            continue
        if (
            job.meta.get("job_type") == COVER_IMAGE_OCR_JOB_TYPE
            and job.meta.get("cover_image_id") == cover_image_id
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
