from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app.core.config import get_settings
from app.models.demand_intelligence import DemandVelocitySnapshot, IssueDemandSnapshot
from app.services.cross_system_recommendation_engine import build_cross_system_candidates
from app.models.external_catalog import ExternalCatalogIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.services.demand_refresh_service import run_demand_refresh
from app.services.demand_velocity_service import compute_demand_velocity
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.recommendation_v3_components import score_v3_demand_components
from app.services.recommendation_v3_preview_service import (
    build_recommendation_v3_preview,
    count_persisted_cross_system_rows,
)
from app.services.recommendation_v3_scoring_context import build_recommendation_v3_scoring_context


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def _owner_id(session: Session, email: str) -> int:
    from app.models import User

    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _seed_locg(session: Session) -> ExternalCatalogIssue:
    issue = ExternalCatalogIssue(
        source_name=LOCG_SOURCE_NAME,
        title="P62 Preview Series #1",
        publisher="Pub",
        series_name="P62 Preview Series",
        issue_number="1",
        release_date=date.today() + timedelta(days=14),
        pull_count=200,
        want_count=100,
        normalized_title_key="p62 preview series #1",
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    return issue


def _add_forward_issue(session: Session, *, owner_id: int) -> ReleaseIssue:
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Marvel",
        series_name="P62 Preview Series",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    foc = date.today() + timedelta(days=10)
    issue = ReleaseIssue(
        owner_user_id=owner_id,
        release_uuid="p62-preview-1",
        series_id=int(series.id or 0),
        issue_number="1",
        title="P62 Preview Series #1",
        release_status="SCHEDULED",
        foc_date=foc,
        release_date=foc + timedelta(days=21),
        cover_price=4.99,
    )
    session.add(issue)
    session.commit()
    session.refresh(issue)
    session.add(
        ReleaseKeySignal(
            owner_user_id=owner_id,
            issue_id=int(issue.id or 0),
            signal_type="NEW_NUMBER_ONE",
            confidence_score=0.9,
            signal_payload_json={},
        )
    )
    session.commit()
    return issue


def test_v3_context_batch_loads_p61_maps(session: Session) -> None:
    ext = _seed_locg(session)
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    compute_demand_velocity(session, window_days=7)
    snap = session.exec(select(IssueDemandSnapshot).where(IssueDemandSnapshot.external_issue_id == int(ext.id))).first()
    assert snap is not None
    issue_id = int(snap.release_issue_id or 0)
    ctx = build_recommendation_v3_scoring_context(session, owner_user_id=1, issue_ids=[issue_id] if issue_id else [999])
    if issue_id:
        assert ctx.demand_for_issue(issue_id) is not None or ctx.demand_by_external_issue_id.get(int(ext.id)) is not None
    assert ctx.readiness.velocity_snapshot_count >= 1 or session.exec(select(func.count()).select_from(DemandVelocitySnapshot)).one() >= 1


def test_v3_component_scoring_matched_vs_unmatched(session: Session) -> None:
    ext = _seed_locg(session)
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    snap = session.exec(select(IssueDemandSnapshot)).first()
    assert snap is not None
    iid = int(snap.release_issue_id or 1)
    ctx = build_recommendation_v3_scoring_context(session, owner_user_id=1, issue_ids=[iid])
    matched = score_v3_demand_components(ctx, release_issue_id=iid)
    assert matched.preview_score > 0
    assert len(matched.components) == 5
    assert any(c.component_name == "COMMUNITY_DEMAND_SCORE" for c in matched.components)
    missing = score_v3_demand_components(ctx, release_issue_id=999_999)
    assert missing.demand_intel_status == "NOT_MATCHED"


def test_v3_preview_does_not_mutate_v2_rows(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("P62_V3_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("P62_V3_PERSIST_ENABLED", "false")
    get_settings.cache_clear()
    email = "p62-v3-preview@example.com"
    register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_locg(session)
    _add_forward_issue(session, owner_id=owner_id)
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    compute_demand_velocity(session, window_days=7)
    assert build_cross_system_candidates(session, owner_user_id=owner_id, refresh_upstream=True)

    before = count_persisted_cross_system_rows(session, owner_user_id=owner_id)
    preview = build_recommendation_v3_preview(session, owner_user_id=owner_id, limit=10)
    after = count_persisted_cross_system_rows(session, owner_user_id=owner_id)
    assert preview["v2_mutated"] is False
    assert before == after


def test_v3_preview_endpoint(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("P62_V3_PREVIEW_ENABLED", "true")
    get_settings.cache_clear()
    email = "p62-v3-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_locg(session)
    _add_forward_issue(session, owner_id=owner_id)
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    compute_demand_velocity(session, window_days=7)
    assert build_cross_system_candidates(session, owner_user_id=owner_id, refresh_upstream=True)

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/v1/recommendation-intelligence/v3/preview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["enabled"] is True
    assert data["v2_mutated"] is False


def test_v3_certification_endpoint(client: TestClient, session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("P62_V3_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("P62_V3_PERSIST_ENABLED", "false")
    get_settings.cache_clear()
    email = "p62-v3-cert@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    _seed_locg(session)
    _add_forward_issue(session, owner_id=owner_id)
    run_demand_refresh(session, scope="ISSUE_UPCOMING", days_forward=90, refresh_locg=False)
    compute_demand_velocity(session, window_days=7)
    assert build_cross_system_candidates(session, owner_user_id=owner_id, refresh_upstream=True)

    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/v1/recommendation-intelligence/v3/certification", headers=headers)
    assert resp.status_code == 200
    cert = resp.json()["data"]
    assert cert["flags"]["P62_V3_PERSIST_ENABLED"] is False
    assert cert["preview"]["v2_mutated"] is False


def test_not_ready_when_no_demand() -> None:
    from app.services.recommendation_v3_scoring_context import build_recommendation_v3_readiness

    diag = build_recommendation_v3_readiness(
        None,  # type: ignore[arg-type]
        owner_user_id=1,
        demand_rows=[],
        velocity_count=0,
        spec_snapshot=None,
        spec_rows=[],
    )
    assert diag.ready is False
    assert "NO_DEMAND_SNAPSHOTS" in diag.reason_codes
    assert "NO_VELOCITY_SNAPSHOTS" in diag.reason_codes


def test_read_only_get_uses_latest_list(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("P62_READ_ONLY_GET", "true")
    get_settings.cache_clear()
    email = "p62-readonly@example.com"
    token = register_and_login(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    def _boom(*args, **kwargs):
        raise AssertionError("refresh_and_list should not run when P62_READ_ONLY_GET=true")

    monkeypatch.setattr(
        "app.api.cross_system_recommendation.refresh_and_list_latest_cross_system_recommendations",
        _boom,
    )
    resp = client.get("/api/v1/cross-system-recommendations", headers=headers)
    assert resp.status_code == 200
