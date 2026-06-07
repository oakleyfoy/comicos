"""CI guard: production route audit must have zero failing probes on TestClient."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.production_route_audit import run_audit

_REPO = Path(__file__).resolve().parents[3]


def test_route_audit_produces_rows() -> None:
    rows = run_audit()
    assert len(rows) >= 50
    routes = {r.route for r in rows}
    assert "/collector-home" in routes


def test_route_audit_csv_schema() -> None:
    """Regenerate CSV at repo root when pytest runs (optional artifact)."""
    rows = run_audit()
    csv_path = _REPO / "route_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["route", "api_endpoint", "status", "failure_type", "exception", "missing_table", "load_time_ms"],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "route": r.route,
                    "api_endpoint": r.api_endpoint,
                    "status": r.status,
                    "failure_type": r.failure_type,
                    "exception": r.exception,
                    "missing_table": r.missing_table,
                    "load_time_ms": r.load_time_ms,
                }
            )
