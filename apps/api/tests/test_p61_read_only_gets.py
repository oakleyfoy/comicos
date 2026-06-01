from __future__ import annotations

import tracemalloc

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.industry_scanner_dashboard import build_industry_scanner_dashboard
from test_industry_scanner_automation import _import_lunar_issue, _owner_id
from test_inventory import auth_headers, register_and_login


def test_industry_dashboard_read_default_skips_refresh(client: TestClient, session: Session) -> None:
    email = "p61-read-only@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _import_lunar_issue(session, owner_user_id=owner_id)

    cold = client.get("/api/v1/industry-scanner-dashboard", headers=auth_headers(token))
    assert cold.status_code == 200
    assert cold.json()["data"]["summary"]["releases_scanned"] == 0

    tracemalloc.start()
    read_only = build_industry_scanner_dashboard(session, owner_user_id=owner_id, refresh=False)
    read_mb, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    refreshed = build_industry_scanner_dashboard(session, owner_user_id=owner_id, refresh=True)
    refresh_mb, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert refreshed.summary.releases_scanned >= read_only.summary.releases_scanned
    assert refresh_mb >= read_mb

    hot = client.post("/api/v1/industry-opportunities/refresh", headers=auth_headers(token))
    assert hot.status_code == 200
    assert hot.json()["data"]["scores_computed"] >= 0
