# Test market/FMV deterministic reporting endpoints (P35-10).

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.main import app
from app.models import MetadataAudit

from test_inventory import auth_headers, register_and_login


MARKET_FORENSIC_REPORT_PATHS = frozenset(
    {
        "/reports/market-sales.csv",
        "/reports/market-eligible-comps.csv",
        "/reports/market-fmv-snapshots.csv",
        "/reports/market-trends.csv",
        "/reports/market-normalization-issues-summary.csv",
        "/reports/market-deterministic-summary.json",
        "/reports/portfolio-value-summary.csv",
        "/reports/inventory-no-market-data.csv",
        "/reports/inventory-no-market-data.json",
        "/reports/inventory-fmv-low-confidence.csv",
        "/reports/inventory-fmv-stale.csv",
        "/ops/reports/market-sales.csv",
        "/ops/reports/market-eligible-comps.csv",
        "/ops/reports/market-fmv-snapshots.csv",
        "/ops/reports/market-trends.csv",
        "/ops/reports/market-normalization-issues-summary.csv",
        "/ops/reports/market-deterministic-summary.json",
        "/ops/reports/portfolio-value-summary.csv",
        "/ops/reports/inventory-no-market-data.csv",
        "/ops/reports/inventory-no-market-data.json",
        "/ops/reports/inventory-fmv-low-confidence.csv",
        "/ops/reports/inventory-fmv-stale.csv",
    }
)


def test_market_report_paths_are_unique_registers() -> None:
    by_path: dict[str, list[tuple[str, ...]]] = {}
    for route in app.routes:
        path = getattr(route, "path", None)
        if path in MARKET_FORENSIC_REPORT_PATHS:
            methods = tuple(sorted(m for m in (route.methods or []) if m))
            by_path.setdefault(path, []).append(methods)
    for path, combos in by_path.items():
        assert len(combos) == 1, f"duplicate registration for {path}: {combos}"
    registered_paths = {getattr(route, "path", None) for route in app.routes}
    missing = sorted(MARKET_FORENSIC_REPORT_PATHS - registered_paths)
    assert not missing, f"missing handlers: {missing}"


def test_market_deterministic_summary_json_stable_between_reads(client: TestClient) -> None:
    owner_headers = auth_headers(register_and_login(client, "market-report-owner@example.com"))
    first = client.get("/reports/market-deterministic-summary.json", headers=owner_headers)
    second = client.get("/reports/market-deterministic-summary.json", headers=owner_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == second.content


def test_market_deterministic_summary_includes_boundary_copy(client: TestClient) -> None:
    owner_headers = auth_headers(register_and_login(client, "market-report-boundaries@example.com"))
    rsp = client.get("/reports/market-deterministic-summary.json", headers=owner_headers)
    assert rsp.status_code == 200
    decoded = json.loads(rsp.content.decode("utf-8"))
    disclaimers = decoded["boundary_disclaimers"]
    assert "no_buy_or_sell" in disclaimers


def test_market_report_reads_do_not_increment_metadata_audits(client: TestClient, session: Session, monkeypatch) -> None:
    monkeypatch.delenv("OPS_ADMIN_EMAILS", raising=False)

    ops_headers = auth_headers(register_and_login(client, "market-report-nonops@example.com"))
    audits_before = len(session.exec(select(MetadataAudit)).all())

    rsp = client.get("/reports/market-sales.csv", headers=ops_headers)
    json_rsp = client.get("/reports/market-deterministic-summary.json", headers=ops_headers)

    audits_after_first = len(session.exec(select(MetadataAudit)).all())
    assert audits_after_first == audits_before
    assert rsp.status_code == 200
    assert json_rsp.status_code == 200

    audits_after_reload = len(session.exec(select(MetadataAudit)).all())
    assert audits_after_reload == audits_before


def test_ops_only_market_exports_reject_regular_users(client: TestClient, monkeypatch) -> None:
    monkeypatch.delenv("OPS_ADMIN_EMAILS", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()

    ops_headers = auth_headers(register_and_login(client, "market-report-regular@example.com"))
    guarded = client.get("/ops/reports/market-deterministic-summary.json", headers=ops_headers)
    assert guarded.status_code == 403


def test_inventory_no_market_data_json_contains_schema_field(client: TestClient) -> None:
    owner_headers = auth_headers(register_and_login(client, "market-report-nmd@example.com"))
    rsp = client.get("/reports/inventory-no-market-data.json", headers=owner_headers)
    assert rsp.status_code == 200
    doc = json.loads(rsp.content.decode("utf-8"))
    assert doc["report_schema"] == "comic-os.reports.inventory_no_market_data.v1"
