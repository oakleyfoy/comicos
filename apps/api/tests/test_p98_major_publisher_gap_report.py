"""P98 — gap report JSON/CSV export + action queue generation tests."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.services.p98_skeleton_gap_service import (
    build_action_queue,
    get_priority_gap_volumes,
    get_publisher_gap_summary,
)
from test_p98_skeleton_gap_service import seed_gap

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_action_queue_generation(client: TestClient, session: Session) -> None:
    seed_gap(session)
    rows = build_action_queue(session, publisher="Marvel")
    assert len(rows) == 4
    scores = [r["priority_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)
    required = {
        "publisher",
        "volume",
        "comicvine_volume_id",
        "status",
        "missing_issue_count",
        "recommended_action",
        "priority_score",
    }
    for row in rows:
        assert required.issubset(row.keys())
    # JSON serializable end-to-end.
    assert json.loads(json.dumps(rows)) == rows


def test_json_export(client: TestClient, session: Session) -> None:
    seed_gap(session)
    summary = get_publisher_gap_summary(session, publisher="Marvel")
    rows = get_priority_gap_volumes(session, publisher="Marvel", top=10)
    payload = {"summary": summary.as_dict(), "top_missing_volumes": [r.as_dict() for r in rows]}
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    assert decoded["summary"]["publisher"] == "Marvel"
    assert decoded["summary"]["catalog_complete"] == 1
    assert "coverage_percent" in decoded["summary"]


def test_csv_export(client: TestClient, session: Session, tmp_path) -> None:
    seed_gap(session)
    from p98_major_publisher_gap_report import _write_csv

    rows = get_priority_gap_volumes(session, publisher="Marvel", top=100)
    out = tmp_path / "marvel_gap_report.csv"
    _write_csv(str(out), rows)

    with open(out, newline="", encoding="utf-8") as fh:
        reader = list(csv.DictReader(fh))
    assert len(reader) == len(rows)
    assert "comicvine_volume_id" in reader[0]
    assert "recommended_action" in reader[0]
    assert "priority_score" in reader[0]


def test_promotion_smoke_from_generated_queue(client: TestClient, session: Session) -> None:
    seed_gap(session)
    from app.services.p98_p97_promotion_service import promote_import_rows

    rows = build_action_queue(session, publisher=None)  # all major publishers
    dry = promote_import_rows(session, rows, apply=False)
    assert dry.applied is False
    assert dry.promotable >= 2
