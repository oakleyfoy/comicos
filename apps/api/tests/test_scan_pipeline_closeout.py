"""P34-10 scan pipeline closeout regressions — API contracts & non-mutation guardrails."""

from __future__ import annotations

from collections import Counter
from unittest.mock import MagicMock

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.main import app
from app.models import InventoryCopy
from app.services import background_jobs as background_jobs_module
from app.tasks import queue as tasks_queue_module
from test_inventory import auth_headers, create_order, register_and_login

_ROUTING_TEST_SHA = "ab" * 32

# HTTP paths guarded for accidental duplicate registrations (subset of scan-plane surface).
_SCAN_PLANE_ROUTE_PREFIXES: tuple[str, ...] = (
    "/scan-sessions",
    "/scan-pipeline-dashboard",
    "/scan-pipeline-replays",
    "/scan-routing-recommendations",
    "/scanner-profiles",
    "/physical-intake",
    "/high-res-review-requests",
    "/ops/scanner-profiles",
    "/ops/scan-sessions",
    "/ops/scan-pipeline-dashboard",
    "/ops/scan-pipeline-replays",
    "/ops/scan-qa",
    "/ops/scan-routing-recommendations",
    "/ops/physical-intake",
)


def test_scan_plane_http_handlers_remain_unique_where_registered():
    counts: Counter[tuple[str, str]] = Counter()

    def matches_scan_plane_route(path_template: str) -> bool:
        return any(path_template.startswith(prefix) for prefix in _SCAN_PLANE_ROUTE_PREFIXES)

    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not matches_scan_plane_route(route.path):
            continue
        for method in sorted(route.methods or ()):
            if method == "HEAD":
                continue
            counts[(method, route.path)] += 1

    doubled = [(key, qty) for key, qty in counts.items() if qty != 1]
    assert doubled == [], f"duplicate registrations: {doubled}"


def test_generate_routing_snapshot_does_not_enqueue_workers(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    boom = MagicMock(side_effect=AssertionError("routing snapshot must not enqueue OCR/process jobs"))

    monkeypatch.setattr(tasks_queue_module, "enqueue_cover_image_ocr_job", boom)
    monkeypatch.setattr(tasks_queue_module, "enqueue_cover_image_process_job", boom)
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_user", boom)
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_ops", boom)

    token = register_and_login(client, "p34-route-no-queue@example.com")
    hdr = auth_headers(token)
    sid = client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr).json()["id"]
    assert (
        client.post(
            f"/scan-sessions/{sid}/items",
            json={
                "items": [
                    {
                        "source_filename": "solo.png",
                        "image_sha256": _ROUTING_TEST_SHA,
                        "image_width": 800,
                        "image_height": 1200,
                    },
                ],
            },
            headers=hdr,
        ).status_code
        == 200
    )
    rsp = client.post(f"/scan-sessions/{sid}/generate-routing", headers=hdr)
    assert rsp.status_code == 200
    boom.assert_not_called()


def test_scan_pipeline_dashboard_reads_preserve_inventory_identity(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
    session: Session,
) -> None:
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_user", MagicMock())
    monkeypatch.setattr(background_jobs_module, "enqueue_cover_image_ocr_for_ops", MagicMock())

    token = register_and_login(client, "p34-dash-no-meta@example.com")
    hdr = auth_headers(token)
    create_order(client, token)

    before = {
        row.id: (row.metadata_identity_key, row.canonical_series_id, row.order_status)
        for row in session.exec(select(InventoryCopy)).all()
        if row.id is not None
    }
    client.post("/scan-sessions", json={"session_type": "bulk_ingest"}, headers=hdr)

    dash = client.get("/scan-pipeline-dashboard", headers=hdr)
    assert dash.status_code == 200
    summ = client.get("/scan-pipeline-dashboard/summary", headers=hdr)
    assert summ.status_code == 200

    session.expire_all()
    after = {
        row.id: (row.metadata_identity_key, row.canonical_series_id, row.order_status)
        for row in session.exec(select(InventoryCopy)).all()
        if row.id is not None
    }
    assert before == after
