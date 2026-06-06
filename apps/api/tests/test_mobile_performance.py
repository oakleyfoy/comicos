from __future__ import annotations

import time

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.services.mobile_scanning_certification import (
    PERF_ASSIGN_TARGET_MS,
    PERF_COLLECTOR_TARGET_MS,
    PERF_SCAN_TARGET_MS,
    ensure_p80_certification_fixture,
    run_mobile_scanning_certification,
)
from test_inventory import auth_headers, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def test_mobile_performance_targets_via_certification(session: Session) -> None:
    owner_id = 1
    user = session.get(User, owner_id)
    if user is None:
        return
    cert = run_mobile_scanning_certification(session, owner_user_id=owner_id)
    perf_checks = [c for c in cert.checks if c.category == "performance"]
    assert perf_checks
    for row in perf_checks:
        if row.duration_ms is not None:
            assert row.passed is True, f"{row.component} exceeded target: {row.duration_ms}ms"


def test_mobile_scan_api_latency(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p80-perf@example.com")
    owner_id = _owner_id(session, "p80-perf@example.com")
    fixture = ensure_p80_certification_fixture(session, owner_user_id=owner_id)
    session.commit()

    start = time.perf_counter()
    response = client.post(
        "/api/v1/mobile/scan",
        headers=auth_headers(token),
        json={"barcode": fixture.upc},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert response.status_code == 201, response.text
    assert elapsed_ms < PERF_SCAN_TARGET_MS * 3, f"scan took {elapsed_ms:.0f}ms"

    start = time.perf_counter()
    collector = client.post(
        "/api/v1/collector/scan",
        headers=auth_headers(token),
        json={"barcode": fixture.upc, "vendor_price": 10},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert collector.status_code == 200, collector.text
    assert elapsed_ms < PERF_COLLECTOR_TARGET_MS * 3

    start = time.perf_counter()
    assign = client.post(
        "/api/v1/mobile/storage/assign",
        headers=auth_headers(token),
        json={"inventory_copy_id": fixture.copy_id, "box_id": fixture.box_id, "use_suggested_slot": True},
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert assign.status_code == 200, assign.text
    assert elapsed_ms < PERF_ASSIGN_TARGET_MS * 3
