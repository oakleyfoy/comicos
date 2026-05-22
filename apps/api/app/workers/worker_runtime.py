import os
from typing import TypeAlias

from rq import SimpleWorker, Worker
from rq.timeouts import TimerDeathPenalty

from app.tasks.queue import get_redis_connection, get_worker_queues

WorkerType: TypeAlias = type[Worker]


class LoggingWorkerMixin:
    def execute_job(self, job, queue):
        self.log.info(
            "Picked up job %s job_type=%s from queue %s",
            job.id,
            job.meta.get("job_type"),
            queue.name,
        )
        return super().execute_job(job, queue)

    def perform_job(self, job, queue) -> bool:
        self.log.info(
            "Started job %s job_type=%s (%s) on queue %s",
            job.id,
            job.meta.get("job_type"),
            job.func_name,
            queue.name,
        )
        return super().perform_job(job, queue)

    def handle_job_success(self, job, queue, started_job_registry):
        self.log.info(
            "Finished job %s job_type=%s (%s) on queue %s",
            job.id,
            job.meta.get("job_type"),
            job.func_name,
            queue.name,
        )
        return super().handle_job_success(job, queue, started_job_registry)

    def handle_job_failure(self, job, queue, started_job_registry=None, exc_string=""):
        self.log.error(
            "Failed job %s job_type=%s (%s) on queue %s: %s",
            job.id,
            job.meta.get("job_type"),
            job.func_name,
            queue.name,
            exc_string or "unknown",
        )
        return super().handle_job_failure(job, queue, started_job_registry, exc_string)


class LoggedWorker(LoggingWorkerMixin, Worker):
    pass


class WindowsLocalSimpleWorker(LoggingWorkerMixin, SimpleWorker):
    death_penalty_class = TimerDeathPenalty


def build_worker(*, local_mode: bool) -> Worker:
    queues = get_worker_queues()
    connection = get_redis_connection()
    worker_class: WorkerType = (
        WindowsLocalSimpleWorker if local_mode and os.name == "nt" else LoggedWorker
    )
    worker = worker_class(
        queues=queues,
        connection=connection,
    )
    worker.log.info(
        "Worker startup mode=%s class=%s queues=%s redis=%s",
        "local" if local_mode else "standard",
        worker_class.__name__,
        [queue.name for queue in queues],
        connection.connection_pool.connection_kwargs,
    )
    return worker


def run_worker(*, local_mode: bool) -> None:
    worker = build_worker(local_mode=local_mode)
    worker.work(with_scheduler=not local_mode)
