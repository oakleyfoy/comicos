from datetime import datetime, timezone
from decimal import Decimal

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from rq import Queue
from sqlmodel import Session, select

from app.core.config import get_settings
from app.main import app
from app.models import (
    CanonicalIssueLinkSuggestion,
    CoverImageLinkDecision,
    CoverImageMatchCandidate,
    CoverRelationshipConflict,
    DraftImport,
    GmailAccount,
    GmailImportRecord,
    RelationshipReplayItem,
    RelationshipReplayRun,
    User,
)
from app.schemas.ai import ParseOrderResponse
from app.services.cover_link_decisions import cover_link_pair_key
from app.services.ops_events import record_ops_event
from app.tasks import queue as rq_queue_module
import test_relationship_conflicts as relationship_conflicts


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_draft_payload() -> dict:
    return ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown Comics",
            "order_date": "2026-05-21",
            "source_type": "gmail_draft",
            "shipping_amount": Decimal("4.99"),
            "tax_amount": Decimal("1.50"),
            "items": [
                {
                    "publisher": "DC",
                    "title": "Batman",
                    "issue_number": "1",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                }
            ],
            "warnings": ["Imported from Gmail email"],
            "confidence_score": 0.88,
        }
    ).model_dump(mode="json")


def test_ops_dashboard_denies_non_admins(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "user@example.com")

    response = client.get("/ops/dashboard", headers=auth_headers(token))

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "HTTP_403"
    assert body["error"]["message"] == "Operations dashboard access denied"


def test_ops_dashboard_returns_recent_visibility_data(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")
    owner = session.exec(select(User).where(User.email == "ops@example.com")).one()

    account = GmailAccount(
        user_id=owner.id,
        gmail_email="ops@gmail.com",
        google_subject_id="google-subject-ops",
        access_token_encrypted="encrypted-token",
        auto_sync_enabled=True,
        last_sync_status="success",
        last_sync_started_at=datetime(2026, 5, 23, 15, 0, tzinfo=timezone.utc),
        last_sync_completed_at=datetime(2026, 5, 23, 15, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 5, 23, 14, 0, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 23, 15, 1, tzinfo=timezone.utc),
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    draft = DraftImport(
        user_id=owner.id,
        raw_text="Batman order",
        parsed_payload_json=build_draft_payload(),
        confidence_score=Decimal("0.88"),
        status="draft",
        created_at=datetime(2026, 5, 23, 15, 2, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 23, 15, 2, tzinfo=timezone.utc),
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)

    session.add(
        GmailImportRecord(
            gmail_account_id=account.id,
            external_message_id="gmail-message-123",
            draft_import_id=draft.id,
            imported_at=datetime(2026, 5, 23, 15, 3, tzinfo=timezone.utc),
        )
    )
    session.commit()

    record_ops_event(
        event_type="gmail_sync",
        status="success",
        user_id=owner.id,
        gmail_account_id=account.id,
        job_id="gmail-job-1",
        queue_name="gmail_sync",
        message="Gmail sync completed",
        details={
            "processed_messages": 2,
            "created_draft_imports": 1,
            "skipped_duplicates": 1,
        },
    )
    record_ops_event(
        event_type="duplicate_skip",
        status="skipped",
        user_id=owner.id,
        gmail_account_id=account.id,
        draft_import_id=draft.id,
        external_message_id="gmail-message-123",
        message="Skipped duplicate Gmail import",
        details={"original_imported_at": "2026-05-23T15:03:00+00:00"},
    )
    record_ops_event(
        event_type="parser_failure",
        status="failed",
        user_id=owner.id,
        gmail_account_id=account.id,
        external_message_id="gmail-message-999",
        message="OpenAI API request failed: insufficient_quota",
        details={"failure_type": "openai_quota_failure"},
    )
    record_ops_event(
        event_type="confirm_success",
        status="success",
        user_id=owner.id,
        draft_import_id=draft.id,
        order_id=7,
        message="Draft import confirmed into order",
        details={"all_in_total": "6.49"},
    )

    queue = Queue("ai_parse", connection=rq_queue_module.get_redis_connection())
    job = queue.enqueue("app.tasks.jobs.run_worker_heartbeat", result_ttl=300)
    job.meta["job_type"] = "ai_parse_import"
    job.meta["user_id"] = owner.id
    job.save_meta()

    response = client.get("/ops/dashboard", headers=auth_headers(token))

    assert response.status_code == 200
    data = response.json()
    assert len(data["queue_health"]) == 2
    assert data["gmail_sync_statuses"][0]["processed_messages"] == 2
    assert data["gmail_sync_statuses"][0]["created_draft_imports"] == 1
    assert data["gmail_sync_statuses"][0]["skipped_duplicates"] == 1
    assert data["recent_draft_imports"][0]["draft_id"] == draft.id
    assert data["recent_draft_imports"][0]["warning_count"] == 1
    assert data["duplicate_skip_events"][0]["external_message_id"] == "gmail-message-123"
    assert data["parser_failures"][0]["details"]["failure_type"] == "openai_quota_failure"
    assert data["confirm_events"][0]["order_id"] == 7
    assert any(job_row["job_id"] == job.id for job_row in data["recent_ai_parse_jobs"])

    pipeline_health = data["pipeline_health"]
    assert isinstance(pipeline_health.get("window_hours"), int)
    assert pipeline_health["failed_ocr_results"] >= 0
    assert isinstance(data["recent_cover_pipeline_jobs"], list)


def test_ops_ocr_pipeline_recover_requires_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "user@example.com")

    response = client.post("/ops/ocr-pipeline/recover", headers=auth_headers(token))

    assert response.status_code == 403


def test_ops_ocr_pipeline_recover_returns_counts_for_admin(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")

    response = client.post("/ops/ocr-pipeline/recover", headers=auth_headers(token))

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "ocr_results_recovered": 0,
        "batch_items_recovered": 0,
        "replay_items_recovered": 0,
    }


def test_main_route_registrations_remain_unique_for_reconciliation_paths() -> None:
    route_counts: dict[tuple[str, str], int] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, route.path)
            route_counts[key] = route_counts.get(key, 0) + 1

    assert route_counts[("POST", "/cover-images/{cover_image_id}/regenerate-match-confidence")] == 1
    assert route_counts[("POST", "/ops/cover-images/{cover_image_id}/regenerate-match-confidence")] == 1
    assert route_counts[("GET", "/ops/cover-images/{cover_image_id}/relationship-graph")] == 1
    assert route_counts[("GET", "/ops/cover-relationship-graph")] == 1


def test_ops_dashboard_returns_reconciliation_summary_counts(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops@example.com")
    owner = session.exec(select(User).where(User.email == "ops@example.com")).one()

    _, source_cover_id = relationship_conflicts._create_cover(
        client,
        token,
        title="Saga",
        issue_number="1",
        color=(25, 90, 180),
    )
    _, candidate_cover_id = relationship_conflicts._create_cover(
        client,
        token,
        title="Saga",
        issue_number="1",
        color=(45, 110, 200),
    )

    match_candidate = CoverImageMatchCandidate(
        source_cover_image_id=source_cover_id,
        candidate_cover_image_id=candidate_cover_id,
        candidate_type="combined_similarity",
        confidence_bucket="very_high",
        deterministic_score=0.97,
        normalized_confidence_score=0.97,
        confidence_version="ops-summary-v1",
        extraction_version="ops-summary-v1",
        ranking_score=0.91,
        ranking_version="ops-summary-v1",
        grouping_type="probable_variant_family",
        grouping_key="vf-summary-1",
        matched_signals={"phash_similarity": 0.97},
        hard_match_flags_json={},
        weak_signal_flags_json={},
        ranking_reason_json={},
    )
    session.add(match_candidate)
    session.commit()
    session.refresh(match_candidate)

    link_decision = CoverImageLinkDecision(
        source_cover_image_id=source_cover_id,
        candidate_cover_image_id=candidate_cover_id,
        pair_key=cover_link_pair_key(source_cover_id, candidate_cover_id),
        source_match_candidate_id=match_candidate.id,
        decision_type="approved_link",
        relationship_type="duplicate_scan",
        decision_state="active",
        reviewer_user_id=owner.id,
        decision_reason="ops summary fixture",
        decision_source="human",
    )
    session.add(link_decision)

    suggestion = CanonicalIssueLinkSuggestion(
        cover_image_id=source_cover_id,
        suggested_metadata_identity_key="image|saga|1|cover-a",
        suggestion_type="relationship_context",
        confidence_bucket="medium",
        deterministic_score=0.7,
        confidence_version="ops-summary-v1",
        evidence_json={"seed": "ops-summary"},
        review_state="pending",
    )
    session.add(suggestion)
    session.commit()
    session.refresh(suggestion)

    conflict = CoverRelationshipConflict(
        conflict_type="canonical_suggestion_mismatch",
        severity="warning",
        source_cover_image_id=source_cover_id,
        related_cover_image_id=candidate_cover_id,
        link_decision_id=link_decision.id,
        match_candidate_id=match_candidate.id,
        canonical_issue_suggestion_id=suggestion.id,
        conflict_key="ops-summary-conflict",
        status="open",
        evidence_json={"signals": [{"kind": "canonical_identity"}]},
    )
    session.add(conflict)

    replay_run = RelationshipReplayRun(
        replay_type="relationship_graph",
        status="completed_with_changes",
        total_items=1,
        changed_items=1,
        unchanged_items=0,
        failed_items=0,
        created_by=owner.id,
        replay_version="ops-summary-v1",
    )
    session.add(replay_run)
    session.commit()
    session.refresh(replay_run)

    replay_item = RelationshipReplayItem(
        replay_run_id=replay_run.id,
        cover_image_id=source_cover_id,
        relationship_key=f"cover:{source_cover_id}",
        status="changed",
        previous_snapshot_json={"nodes": 1},
        replay_snapshot_json={"nodes": 2},
        diff_summary_json={"status": "changed", "added": 1},
    )
    session.add(replay_item)
    session.commit()

    response = client.get("/ops/dashboard", headers=auth_headers(token))

    assert response.status_code == 200
    summary = response.json()["reconciliation_summary"]
    assert summary == {
        "open_conflicts": 1,
        "pending_canonical_suggestions": 1,
        "high_confidence_unreviewed_match_candidates": 1,
        "confirmed_duplicate_scans": 1,
        "probable_variant_families": 1,
        "recent_relationship_replay_changes": 1,
    }
