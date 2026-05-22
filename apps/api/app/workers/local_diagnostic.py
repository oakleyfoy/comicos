import json
import time
import uuid

from rq.job import Job

from app.tasks.jobs import run_local_ai_parse_diagnostic_job
from app.tasks.queue import get_ai_parse_queue, get_redis_connection


def main() -> int:
    marker = f"diag-{uuid.uuid4().hex[:8]}"
    queue = get_ai_parse_queue()
    job = queue.enqueue(
        run_local_ai_parse_diagnostic_job,
        marker,
        description="Local worker diagnostic job",
        meta={"job_type": "local_worker_diagnostic"},
        result_ttl=300,
        failure_ttl=300,
        job_timeout=30,
    )
    print(f"Enqueued diagnostic job {job.id} on queue {queue.name} with marker {marker}")

    connection = get_redis_connection()
    deadline = time.time() + 30
    while time.time() < deadline:
        time.sleep(1)
        current_job = Job.fetch(job.id, connection=connection)
        status = current_job.get_status(refresh=True)
        print(f"Diagnostic job status: {status}")
        if status == "finished":
            print(json.dumps(current_job.result))
            return 0
        if status == "failed":
            print(current_job.exc_info or "Diagnostic job failed")
            return 1

    print("Diagnostic job timed out before reaching a terminal state")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
