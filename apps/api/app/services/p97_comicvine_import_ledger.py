"""Record ComicVine API usage against the P97 request ledger."""

from __future__ import annotations

from app.services.p97_comicvine_rate_budget import ComicVineRateBudget


def record_comicvine_import_requests(
    budget: ComicVineRateBudget,
    *,
    request_type: str,
    volume_id: int,
    queue_id: int | None,
    api_requests_used: int,
    throttled: bool,
) -> None:
    n = max(0, int(api_requests_used))
    if throttled:
        for _ in range(max(0, n - 1)):
            budget.record_request(
                request_type=request_type,
                comicvine_volume_id=volume_id,
                queue_id=queue_id,
                status_code=200,
            )
        budget.record_420(comicvine_volume_id=volume_id, queue_id=queue_id)
        return
    for _ in range(n):
        budget.record_request(
            request_type=request_type,
            comicvine_volume_id=volume_id,
            queue_id=queue_id,
            status_code=200,
        )
