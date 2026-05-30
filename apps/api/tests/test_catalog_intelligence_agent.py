from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from agent_security_test_utils import grant_agent_execute
import test_inventory as inv
import test_relationship_conflicts as rc
from app.models import (
    AgentDefinition,
    CanonicalIssueLinkSuggestion,
    CoverImageMatchCandidate,
    CoverImageOcrCandidate,
    CoverImageOcrQualityAnalysis,
    CoverImageOcrReconciliationWarning,
    CoverImageOcrResult,
    CoverRelationshipConflict,
    DuplicateCandidateReview,
    DuplicateCluster,
    DuplicateClusterItem,
    InventoryCopy,
    User,
)
from app.services.agent_registry import enable_agent
from app.services.agent_seed import seed_foundational_agents
from app.services.catalog_intelligence_agent import run_catalog_intelligence_agent


def _enable_catalog_intelligence_agent(session: Session) -> None:
    seed_foundational_agents(session)
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == "catalog_intelligence_agent")).first()
    assert row is not None and row.id is not None
    enable_agent(session, agent_id=int(row.id))
    grant_agent_execute(session, agent_id=int(row.id))


def _owner(session: Session, email: str) -> User:
    row = session.exec(select(User).where(User.email == email)).one()
    assert row.id is not None
    return row


def _inventory_state(session: Session, *, owner_user_id: int) -> list[tuple]:
    rows = session.exec(select(InventoryCopy).where(InventoryCopy.user_id == owner_user_id).order_by(InventoryCopy.id.asc())).all()
    return [
        (
            int(row.id or 0),
            row.metadata_identity_key,
            row.canonical_series_id,
            row.release_year,
            row.primary_cover_image_id,
        )
        for row in rows
    ]


def _seed_catalog_inventory(client: TestClient, session: Session, *, email: str) -> User:
    token = inv.register_and_login(client, email)
    source_inventory_id, source_cover_id = rc._create_cover(
        client,
        token,
        title="Invincible",
        issue_number="1",
        color=(20, 80, 200),
    )
    peer_inventory_id, peer_cover_id = rc._create_cover(
        client,
        token,
        title="Invincible",
        issue_number="1",
        color=(25, 85, 205),
    )
    user = _owner(session, email)

    source_copy = session.get(InventoryCopy, source_inventory_id)
    peer_copy = session.get(InventoryCopy, peer_inventory_id)
    assert source_copy is not None and peer_copy is not None
    source_copy.metadata_identity_key = "Image|Invincible|1|Cover A"
    source_copy.release_year = None
    source_copy.primary_cover_image_id = source_cover_id
    peer_copy.metadata_identity_key = "Image|Invincible|1|Cover A"
    peer_copy.primary_cover_image_id = peer_cover_id
    session.add(source_copy)
    session.add(peer_copy)
    session.commit()

    now = datetime.now(timezone.utc)
    ocr_result = CoverImageOcrResult(
        cover_image_id=source_cover_id,
        ocr_engine="tesseract",
        ocr_engine_version="catalog-test-v1",
        processing_status="failed",
        raw_text="INVINCIBLE 1 IMAGE",
        normalized_text=None,
        confidence_score=None,
        processing_error="seeded OCR failure",
        processed_at=now,
        created_at=now,
    )
    session.add(ocr_result)
    session.commit()
    session.refresh(ocr_result)
    session.add(
        CoverImageOcrCandidate(
            cover_image_id=source_cover_id,
            ocr_result_id=int(ocr_result.id or 0),
            candidate_type="publisher",
            raw_candidate_text="MARVEL",
            normalized_candidate_text="Marvel",
            confidence_score=0.61,
            extraction_source="ocr",
            extraction_version="catalog-test-v1",
            review_status="pending",
        )
    )
    session.add(
        CoverImageOcrQualityAnalysis(
            cover_image_id=source_cover_id,
            source_ocr_result_id=None,
            quality_type="unreadable_ocr",
            deterministic_score=0.15,
            severity="warning",
            detail_json={"seed": "catalog"},
            extraction_version="catalog-test-v1",
            created_at=now,
            updated_at=now,
        )
    )
    session.add(
        CoverImageOcrReconciliationWarning(
            cover_image_id=source_cover_id,
            inventory_copy_id=source_inventory_id,
            ocr_candidate_id=None,
            warning_type="publisher_mismatch",
            severity="critical",
            current_metadata_value="Image",
            candidate_value="Marvel",
            message="publisher mismatch",
            status="open",
            created_at=now,
        )
    )
    session.add(
        CoverImageOcrReconciliationWarning(
            cover_image_id=source_cover_id,
            inventory_copy_id=source_inventory_id,
            ocr_candidate_id=None,
            warning_type="title_mismatch",
            severity="warning",
            current_metadata_value="Invincible",
            candidate_value="Invisible",
            message="title mismatch",
            status="open",
            created_at=now,
        )
    )
    session.add(
        CoverImageMatchCandidate(
            source_cover_image_id=source_cover_id,
            candidate_cover_image_id=peer_cover_id,
            candidate_type="combined_similarity",
            confidence_bucket="high",
            deterministic_score=0.9,
            normalized_confidence_score=0.9,
            confidence_version="catalog-test-v1",
            extraction_version="catalog-test-v1",
            ranking_score=0.83,
            ranking_version="catalog-test-v1",
            matched_signals={"phash_similarity": 0.8},
            hard_match_flags_json={},
            weak_signal_flags_json={},
            ranking_reason_json={},
            grouping_type="probable_variant_family",
            grouping_key="catalog-variant-family",
        )
    )
    session.commit()
    match_candidate = session.exec(select(CoverImageMatchCandidate).where(CoverImageMatchCandidate.source_cover_image_id == source_cover_id)).one()

    session.add(
        CoverRelationshipConflict(
            conflict_type="canonical_suggestion_mismatch",
            severity="critical",
            source_cover_image_id=source_cover_id,
            related_cover_image_id=peer_cover_id,
            link_decision_id=None,
            match_candidate_id=match_candidate.id,
            canonical_issue_suggestion_id=None,
            conflict_key="catalog-conflict",
            status="open",
            evidence_json={"signals": ["catalog-test"]},
        )
    )
    session.add(
        CanonicalIssueLinkSuggestion(
            cover_image_id=source_cover_id,
            inventory_copy_id=source_inventory_id,
            canonical_issue_id=None,
            canonical_series_id=None,
            canonical_publisher_id=None,
            suggested_metadata_identity_key="Image|Invincible|1|",
            suggestion_type="normalized_title_issue_publisher",
            confidence_bucket="high",
            deterministic_score=0.81,
            confidence_version="canonical-issue-suggestion-v1",
            evidence_json={"seed": "catalog"},
            suppression_reason=None,
            review_state="pending",
            reviewed_by_user_id=None,
            reviewed_at=None,
        )
    )
    session.add(
        DuplicateCandidateReview(
            metadata_identity_key=source_copy.metadata_identity_key or "",
            review_status="pending",
            notes="seed duplicate review",
        )
    )
    session.commit()

    session.add(
        DuplicateCluster(
            owner_user_id=int(user.id),
            canonical_comic_issue_id=None,
            cluster_key="dup:catalog:invincible-1",
            cluster_type="duplicate_candidate",
            generation_batch_checksum="catalog-batch",
            replay_key="catalog-replay",
            total_item_count=2,
            graded_item_count=0,
            raw_item_count=2,
            total_fmv_amount=Decimal("20.00"),
            total_cost_basis_amount=Decimal("10.00"),
            liquidity_profile="medium",
            duplication_status="open",
            checksum="catalog-cluster-checksum",
            snapshot_date=date.today(),
        )
    )
    session.commit()
    cluster = session.exec(select(DuplicateCluster).where(DuplicateCluster.cluster_key == "dup:catalog:invincible-1")).one()
    session.add(
        DuplicateClusterItem(
            duplicate_cluster_id=int(cluster.id or 0),
            inventory_item_id=source_inventory_id,
            portfolio_id=None,
            grading_status="raw",
            estimated_strength_score=Decimal("0.50"),
            liquidity_score=Decimal("0.50"),
            current_fmv=Decimal("10.00"),
            acquisition_cost=Decimal("5.00"),
            recommendation_priority="medium",
        )
    )
    session.commit()
    return user


def test_catalog_intelligence_agent_generates_catalog_review_recommendations_without_mutation(
    client: TestClient,
    session: Session,
) -> None:
    _enable_catalog_intelligence_agent(session)
    user = _seed_catalog_inventory(client, session, email="catalog-intelligence-owner@example.com")

    before_state = _inventory_state(session, owner_user_id=int(user.id or 0))
    result = run_catalog_intelligence_agent(session, current_user=user)

    assert result.snapshot.status == "COMPLETED"
    assert result.snapshot.research_type == "catalog_intelligence"
    assert {row.recommendation_type for row in result.recommendations} >= {
        "missing_metadata",
        "possible_duplicate",
        "catalog_conflict",
        "publisher_conflict",
        "series_conflict",
        "ocr_review_needed",
        "variant_review_needed",
        "cover_review_needed",
        "identity_review_needed",
    }
    assert all(row.confidence_score > 0 for row in result.recommendations)
    assert before_state == _inventory_state(session, owner_user_id=int(user.id or 0))
