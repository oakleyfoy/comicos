"""P37-09 deterministic grading reporting closeout tests."""

from __future__ import annotations

from sqlmodel import Session, select

from test_dealer_grading_dashboard import _seed_dashboard_fixture
from test_inventory import auth_headers, register_and_login

from app.core.config import get_settings
from app.models import (
    DealerGradingDashboardSnapshot,
    GradingCandidate,
    GradingOperationalReportItem,
    GradingOperationalReportRun,
    GradingRecommendation,
    GradingReconciliationRecord,
    GradingRiskSnapshot,
    GradingRoiSnapshot,
    GradingSpreadSnapshot,
    GradingSubmissionBatch,
)

REPORT_TYPES = [
    "grading_candidate_summary",
    "grading_roi_summary",
    "grading_submission_summary",
    "grading_reconciliation_summary",
    "grading_recommendation_summary",
    "grading_risk_summary",
    "grading_dashboard_summary",
    "grader_performance_summary",
]


def _generate_report(client, token: str, report_type: str, replay_key: str) -> dict:
    rsp = client.post(
        "/grading-reports/generate",
        headers=auth_headers(token),
        json={"report_type": report_type, "replay_key": replay_key, "generation_params": {}},
    )
    assert rsp.status_code in (200, 201), rsp.text
    return rsp.json()


def test_generate_all_grading_reports_and_download(client, session: Session) -> None:
    token = register_and_login(client, "grading-report-owner@example.com")
    _seed_dashboard_fixture(client, session, token)
    dashboard_rsp = client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(token),
        json={"snapshot_date": "2026-05-26", "replay_key": "grading-report-dashboard"},
    )
    assert dashboard_rsp.status_code in (200, 201), dashboard_rsp.text

    for idx, report_type in enumerate(REPORT_TYPES, start=1):
        payload = _generate_report(client, token, report_type, replay_key=f"grading-report-{idx}")
        assert payload["report_type"] == report_type
        assert payload["status"] == "COMPLETED"
        assert payload["checksum"]
        assert payload["csv_row_count"] >= 1
        assert payload["files"]
        assert payload["items"]
        assert all(item["row_checksum"] for item in payload["items"])
        assert payload["files"][0]["file_name"].startswith(f"comic_os_{report_type}_")
        download = client.get(f"/grading-reports/{payload['id']}/download", headers=auth_headers(token))
        assert download.status_code == 200, download.text
        lines = [line for line in download.text.strip().splitlines() if line]
        assert lines[0] == "metric_family,metric_key,metric_value_integer,metric_value_decimal,metric_value_text,notes"


def test_grading_report_replay_checksum_stability_and_append_history(client, session: Session) -> None:
    token = register_and_login(client, "grading-report-stable@example.com")
    _seed_dashboard_fixture(client, session, token)
    assert client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(token),
        json={"snapshot_date": "2026-05-26", "replay_key": "grading-report-stable-dashboard"},
    ).status_code in (200, 201)

    first = _generate_report(client, token, "grading_dashboard_summary", replay_key="grading-stable-001")
    same_replay = _generate_report(client, token, "grading_dashboard_summary", replay_key="grading-stable-001")
    assert same_replay["id"] == first["id"]
    assert same_replay["checksum"] == first["checksum"]

    second = _generate_report(client, token, "grading_dashboard_summary", replay_key="grading-stable-002")
    assert second["id"] != first["id"]
    assert second["checksum"] == first["checksum"]

    dl_first = client.get(f"/grading-reports/{first['id']}/download", headers=auth_headers(token))
    dl_second = client.get(f"/grading-reports/{second['id']}/download", headers=auth_headers(token))
    assert dl_first.status_code == 200, dl_first.text
    assert dl_second.status_code == 200, dl_second.text
    assert dl_first.text == dl_second.text

    runs = session.exec(select(GradingOperationalReportRun)).all()
    assert len(runs) == 2
    items = session.exec(select(GradingOperationalReportItem)).all()
    assert len(items) >= first["csv_row_count"]


def test_owner_scoping_ops_visibility_and_no_source_mutation(client, session: Session, monkeypatch) -> None:
    owner = register_and_login(client, "grading-report-scope-owner@example.com")
    other = register_and_login(client, "grading-report-scope-other@example.com")
    admin = register_and_login(client, "grading-report-scope-admin@example.com")
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "grading-report-scope-admin@example.com")
    get_settings.cache_clear()

    _seed_dashboard_fixture(client, session, owner)
    _seed_dashboard_fixture(client, session, other)
    assert client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(owner),
        json={"snapshot_date": "2026-05-26", "replay_key": "grading-report-owner-dashboard"},
    ).status_code in (200, 201)
    assert client.post(
        "/dealer-grading-dashboard/generate",
        headers=auth_headers(other),
        json={"snapshot_date": "2026-05-26", "replay_key": "grading-report-other-dashboard"},
    ).status_code in (200, 201)

    before_counts = {
        "candidate": len(session.exec(select(GradingCandidate)).all()),
        "spread": len(session.exec(select(GradingSpreadSnapshot)).all()),
        "roi": len(session.exec(select(GradingRoiSnapshot)).all()),
        "submission": len(session.exec(select(GradingSubmissionBatch)).all()),
        "reconciliation": len(session.exec(select(GradingReconciliationRecord)).all()),
        "recommendation": len(session.exec(select(GradingRecommendation)).all()),
        "risk": len(session.exec(select(GradingRiskSnapshot)).all()),
        "dashboard": len(session.exec(select(DealerGradingDashboardSnapshot)).all()),
    }

    owner_run = _generate_report(client, owner, "grading_risk_summary", replay_key="grading-owner-run")
    other_run = _generate_report(client, other, "grading_candidate_summary", replay_key="grading-other-run")

    miss = client.get(f"/grading-reports/{owner_run['id']}", headers=auth_headers(other))
    assert miss.status_code == 404
    bad_download = client.get(f"/grading-reports/{owner_run['id']}/download", headers=auth_headers(other))
    assert bad_download.status_code == 404

    ops_list = client.get(
        "/ops/grading-reports",
        params={"owner_user_id": owner_run["owner_user_id"], "report_type": "grading_risk_summary"},
        headers=auth_headers(admin),
    )
    assert ops_list.status_code == 200, ops_list.text
    assert ops_list.json()["total_items"] >= 1
    assert all(row["owner_user_id"] == owner_run["owner_user_id"] for row in ops_list.json()["items"])

    ops_detail = client.get(f"/ops/grading-reports/{owner_run['id']}", headers=auth_headers(admin))
    assert ops_detail.status_code == 200, ops_detail.text
    assert ops_detail.json()["id"] == owner_run["id"]

    ops_download = client.get(f"/ops/grading-reports/{owner_run['id']}/download", headers=auth_headers(admin))
    assert ops_download.status_code == 200, ops_download.text

    civilian_ops = client.get("/ops/grading-reports", headers=auth_headers(owner))
    assert civilian_ops.status_code == 403

    session.expire_all()
    after_counts = {
        "candidate": len(session.exec(select(GradingCandidate)).all()),
        "spread": len(session.exec(select(GradingSpreadSnapshot)).all()),
        "roi": len(session.exec(select(GradingRoiSnapshot)).all()),
        "submission": len(session.exec(select(GradingSubmissionBatch)).all()),
        "reconciliation": len(session.exec(select(GradingReconciliationRecord)).all()),
        "recommendation": len(session.exec(select(GradingRecommendation)).all()),
        "risk": len(session.exec(select(GradingRiskSnapshot)).all()),
        "dashboard": len(session.exec(select(DealerGradingDashboardSnapshot)).all()),
    }
    assert before_counts == after_counts
    assert owner_run["id"] != other_run["id"]
