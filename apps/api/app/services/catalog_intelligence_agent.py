from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.models import (
    AgentDefinition,
    CanonicalIssueLinkSuggestion,
    CoverImage,
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
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.schemas.intelligence import IntelligenceRunResponse
from app.services.agent_execution import complete_execution, fail_execution, start_execution
from app.services.intelligence_engine import (
    attach_evidence,
    calculate_confidence_score,
    calculate_opportunity_score,
    calculate_priority_score,
    create_recommendation,
)
from app.services.order_arrival_intelligence import compute_order_arrival_intelligence
from app.services.research_agent_base import create_snapshot, complete_snapshot, fail_snapshot

AGENT_CODE = "catalog_intelligence_agent"
RESEARCH_TYPE = "catalog_intelligence"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@dataclass(frozen=True)
class _InventoryRow:
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    metadata_identity_key: str | None
    canonical_series_id: int | None
    release_date: date | None
    release_year: int | None
    release_status: str
    order_status: str
    primary_cover_image_id: int | None


def _agent_id(session: Session) -> int:
    row = session.exec(select(AgentDefinition).where(AgentDefinition.code == AGENT_CODE)).first()
    if row is None or row.id is None:
        raise RuntimeError("Catalog intelligence agent is not registered.")
    return int(row.id)


def _inventory_rows(session: Session, *, owner_user_id: int) -> list[_InventoryRow]:
    rows = session.exec(
        apply_inventory_spine_joins(
            select(
                InventoryCopy.id.label("inventory_copy_id"),
                title_expr().label("title"),
                publisher_expr().label("publisher"),
                issue_number_expr().label("issue_number"),
                InventoryCopy.metadata_identity_key.label("metadata_identity_key"),
                InventoryCopy.canonical_series_id.label("canonical_series_id"),
                InventoryCopy.release_date.label("release_date"),
                InventoryCopy.release_year.label("release_year"),
                InventoryCopy.release_status.label("release_status"),
                InventoryCopy.order_status.label("order_status"),
                InventoryCopy.primary_cover_image_id.label("primary_cover_image_id"),
            ).select_from(InventoryCopy)
        )
        .where(InventoryCopy.user_id == owner_user_id)
        .order_by(InventoryCopy.id.asc())
    ).all()
    return [
        _InventoryRow(
            inventory_copy_id=int(row.inventory_copy_id),
            title=str(row.title),
            publisher=str(row.publisher),
            issue_number=str(row.issue_number),
            metadata_identity_key=str(row.metadata_identity_key) if row.metadata_identity_key is not None else None,
            canonical_series_id=int(row.canonical_series_id) if row.canonical_series_id is not None else None,
            release_date=row.release_date,
            release_year=int(row.release_year) if row.release_year is not None else None,
            release_status=str(row.release_status),
            order_status=str(row.order_status),
            primary_cover_image_id=int(row.primary_cover_image_id) if row.primary_cover_image_id is not None else None,
        )
        for row in rows
    ]


def _covers_by_inventory(session: Session, *, inventory_ids: list[int]) -> dict[int, list[CoverImage]]:
    if not inventory_ids:
        return {}
    rows = session.exec(
        select(CoverImage)
        .where(CoverImage.inventory_copy_id.in_(inventory_ids))
        .order_by(CoverImage.inventory_copy_id.asc(), CoverImage.id.asc())
    ).all()
    out: dict[int, list[CoverImage]] = defaultdict(list)
    for row in rows:
        if row.inventory_copy_id is not None:
            out[int(row.inventory_copy_id)].append(row)
    return dict(out)


def _latest_ocr_by_cover(session: Session, *, cover_ids: list[int]) -> dict[int, CoverImageOcrResult]:
    if not cover_ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id.in_(cover_ids))
        .order_by(CoverImageOcrResult.cover_image_id.asc(), CoverImageOcrResult.created_at.desc(), CoverImageOcrResult.id.desc())
    ).all()
    out: dict[int, CoverImageOcrResult] = {}
    for row in rows:
        out.setdefault(int(row.cover_image_id), row)
    return out


def _pending_ocr_candidates_by_cover(session: Session, *, cover_ids: list[int]) -> dict[int, list[CoverImageOcrCandidate]]:
    if not cover_ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(
            CoverImageOcrCandidate.cover_image_id.in_(cover_ids),
            CoverImageOcrCandidate.review_status == "pending",
        )
        .order_by(CoverImageOcrCandidate.cover_image_id.asc(), CoverImageOcrCandidate.id.asc())
    ).all()
    out: dict[int, list[CoverImageOcrCandidate]] = defaultdict(list)
    for row in rows:
        out[int(row.cover_image_id)].append(row)
    return dict(out)


def _quality_rows_by_cover(session: Session, *, cover_ids: list[int]) -> dict[int, list[CoverImageOcrQualityAnalysis]]:
    if not cover_ids:
        return {}
    rows = session.exec(
        select(CoverImageOcrQualityAnalysis)
        .where(CoverImageOcrQualityAnalysis.cover_image_id.in_(cover_ids))
        .order_by(CoverImageOcrQualityAnalysis.cover_image_id.asc(), CoverImageOcrQualityAnalysis.id.asc())
    ).all()
    out: dict[int, list[CoverImageOcrQualityAnalysis]] = defaultdict(list)
    for row in rows:
        out[int(row.cover_image_id)].append(row)
    return dict(out)


def _match_rows_by_cover(session: Session, *, cover_ids: list[int]) -> dict[int, list[CoverImageMatchCandidate]]:
    if not cover_ids:
        return {}
    rows = session.exec(
        select(CoverImageMatchCandidate)
        .where(
            CoverImageMatchCandidate.source_cover_image_id.in_(cover_ids),
            CoverImageMatchCandidate.dismissed_at.is_(None),
            CoverImageMatchCandidate.acknowledged_at.is_(None),
        )
        .order_by(
            CoverImageMatchCandidate.source_cover_image_id.asc(),
            CoverImageMatchCandidate.candidate_rank.asc(),
            CoverImageMatchCandidate.id.asc(),
        )
    ).all()
    out: dict[int, list[CoverImageMatchCandidate]] = defaultdict(list)
    for row in rows:
        out[int(row.source_cover_image_id)].append(row)
    return dict(out)


def _warning_rows_by_inventory(
    session: Session,
    *,
    inventory_ids: list[int],
    cover_to_inventory: dict[int, int],
) -> dict[int, list[CoverImageOcrReconciliationWarning]]:
    if not inventory_ids and not cover_to_inventory:
        return {}
    rows = session.exec(
        select(CoverImageOcrReconciliationWarning)
        .where(CoverImageOcrReconciliationWarning.status == "open")
        .order_by(CoverImageOcrReconciliationWarning.created_at.asc(), CoverImageOcrReconciliationWarning.id.asc())
    ).all()
    out: dict[int, list[CoverImageOcrReconciliationWarning]] = defaultdict(list)
    for row in rows:
        inv_id = int(row.inventory_copy_id) if row.inventory_copy_id is not None else cover_to_inventory.get(int(row.cover_image_id))
        if inv_id in inventory_ids:
            out[inv_id].append(row)
    return dict(out)


def _conflict_rows_by_inventory(
    session: Session,
    *,
    inventory_ids: list[int],
    cover_to_inventory: dict[int, int],
) -> dict[int, list[CoverRelationshipConflict]]:
    rows = session.exec(
        select(CoverRelationshipConflict)
        .where(CoverRelationshipConflict.status == "open")
        .order_by(CoverRelationshipConflict.created_at.asc(), CoverRelationshipConflict.id.asc())
    ).all()
    out: dict[int, list[CoverRelationshipConflict]] = defaultdict(list)
    for row in rows:
        touched = set()
        if row.source_cover_image_id is not None:
            touched.add(cover_to_inventory.get(int(row.source_cover_image_id)))
        if row.related_cover_image_id is not None:
            touched.add(cover_to_inventory.get(int(row.related_cover_image_id)))
        for inv_id in sorted(item for item in touched if item in inventory_ids):
            out[inv_id].append(row)
    return dict(out)


def _duplicate_clusters_by_inventory(
    session: Session,
    *,
    owner_user_id: int,
    inventory_ids: list[int],
) -> dict[int, list[tuple[DuplicateCluster, DuplicateClusterItem]]]:
    if not inventory_ids:
        return {}
    rows = session.exec(
        select(DuplicateCluster, DuplicateClusterItem)
        .join(DuplicateClusterItem, DuplicateClusterItem.duplicate_cluster_id == DuplicateCluster.id)
        .where(
            DuplicateCluster.owner_user_id == owner_user_id,
            DuplicateClusterItem.inventory_item_id.in_(inventory_ids),
        )
        .order_by(DuplicateCluster.id.asc(), DuplicateClusterItem.id.asc())
    ).all()
    out: dict[int, list[tuple[DuplicateCluster, DuplicateClusterItem]]] = defaultdict(list)
    for cluster, item in rows:
        out[int(item.inventory_item_id)].append((cluster, item))
    return dict(out)


def _canonical_suggestions_by_inventory(session: Session, *, inventory_ids: list[int]) -> dict[int, list[CanonicalIssueLinkSuggestion]]:
    if not inventory_ids:
        return {}
    rows = session.exec(
        select(CanonicalIssueLinkSuggestion)
        .where(
            CanonicalIssueLinkSuggestion.inventory_copy_id.in_(inventory_ids),
            CanonicalIssueLinkSuggestion.review_state == "pending",
        )
        .order_by(CanonicalIssueLinkSuggestion.inventory_copy_id.asc(), CanonicalIssueLinkSuggestion.id.asc())
    ).all()
    out: dict[int, list[CanonicalIssueLinkSuggestion]] = defaultdict(list)
    for row in rows:
        if row.inventory_copy_id is not None:
            out[int(row.inventory_copy_id)].append(row)
    return dict(out)


def _duplicate_candidate_reviews_by_key(
    session: Session,
    *,
    metadata_identity_keys: list[str],
) -> dict[str, DuplicateCandidateReview]:
    if not metadata_identity_keys:
        return {}
    rows = session.exec(
        select(DuplicateCandidateReview)
        .where(DuplicateCandidateReview.metadata_identity_key.in_(metadata_identity_keys))
        .order_by(DuplicateCandidateReview.created_at.asc(), DuplicateCandidateReview.id.asc())
    ).all()
    out: dict[str, DuplicateCandidateReview] = {}
    for row in rows:
        out.setdefault(row.metadata_identity_key, row)
    return out


def _persist_recommendation(
    session: Session,
    *,
    agent_execution_id: int,
    snapshot_id: int,
    recommendation_key: str,
    recommendation_type: str,
    title: str,
    description: str,
    inventory_copy_id: int,
    inventory_title: str,
    recommendation_payload_json: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    opportunity_score: float,
    urgency_score: float,
) -> tuple[str, Any]:
    confidence_score = calculate_confidence_score(
        evidence_scores=[float(row["evidence_score"]) for row in evidence_rows],
        supporting_signal_count=len(evidence_rows),
        data_freshness_score=1.0,
    )
    opportunity = calculate_opportunity_score(
        data_gap_score=opportunity_score,
        urgency_score=urgency_score,
        trend_score=0.0,
        spread_score=0.0,
        scarcity_score=0.0,
    )
    priority_score = calculate_priority_score(
        opportunity_score=opportunity,
        confidence_score=confidence_score,
        urgency_score=urgency_score,
    )
    recommendation = create_recommendation(
        session,
        agent_execution_id=agent_execution_id,
        recommendation_key=recommendation_key,
        recommendation_type=recommendation_type,
        title=title,
        description=description,
        inventory_copy_id=inventory_copy_id,
        inventory_title=inventory_title,
        confidence_score=confidence_score,
        opportunity_score=opportunity,
        priority_score=priority_score,
        recommendation_payload_json={"research_snapshot_id": snapshot_id, **recommendation_payload_json},
    )
    for evidence in evidence_rows:
        attach_evidence(
            session,
            recommendation_id=recommendation.id,
            evidence_type=str(evidence["evidence_type"]),
            evidence_source=str(evidence["evidence_source"]),
            evidence_payload_json=dict(evidence.get("evidence_payload_json") or {}),
            evidence_score=float(evidence["evidence_score"]),
        )
    return recommendation.recommendation_type, recommendation


def run_catalog_intelligence_agent(session: Session, *, current_user: User) -> IntelligenceRunResponse:
    assert current_user.id is not None
    owner_user_id = int(current_user.id)
    agent_execution = start_execution(
        session,
        agent_id=_agent_id(session),
        triggered_by=str(owner_user_id),
        trigger_source="intelligence_agent:catalog",
    )
    snapshot_id: int | None = None
    try:
        inventory_rows = _inventory_rows(session, owner_user_id=owner_user_id)
        inventory_ids = [row.inventory_copy_id for row in inventory_rows]
        covers_by_inventory = _covers_by_inventory(session, inventory_ids=inventory_ids)
        cover_to_inventory = {
            int(cover.id or 0): inv_id
            for inv_id, covers in covers_by_inventory.items()
            for cover in covers
            if cover.id is not None
        }
        cover_ids = sorted(cover_to_inventory)
        latest_ocr_by_cover = _latest_ocr_by_cover(session, cover_ids=cover_ids)
        pending_candidates_by_cover = _pending_ocr_candidates_by_cover(session, cover_ids=cover_ids)
        quality_by_cover = _quality_rows_by_cover(session, cover_ids=cover_ids)
        match_rows_by_cover = _match_rows_by_cover(session, cover_ids=cover_ids)
        warning_rows_by_inventory = _warning_rows_by_inventory(
            session,
            inventory_ids=inventory_ids,
            cover_to_inventory=cover_to_inventory,
        )
        conflict_rows_by_inventory = _conflict_rows_by_inventory(
            session,
            inventory_ids=inventory_ids,
            cover_to_inventory=cover_to_inventory,
        )
        duplicate_clusters_by_inventory = _duplicate_clusters_by_inventory(
            session,
            owner_user_id=owner_user_id,
            inventory_ids=inventory_ids,
        )
        canonical_suggestions_by_inventory = _canonical_suggestions_by_inventory(session, inventory_ids=inventory_ids)
        duplicate_reviews_by_key = _duplicate_candidate_reviews_by_key(
            session,
            metadata_identity_keys=sorted({row.metadata_identity_key for row in inventory_rows if row.metadata_identity_key}),
        )
        arrival_response, _ = compute_order_arrival_intelligence(session, current_user=current_user)
        arrival_by_inventory: dict[int, set[str]] = defaultdict(set)
        for item in arrival_response.items:
            arrival_by_inventory[item.inventory_copy_id].add(item.classification)

        snapshot = create_snapshot(
            session,
            agent_execution_id=agent_execution.execution.id,
            agent_code=AGENT_CODE,
            research_type=RESEARCH_TYPE,
            input_scope_json={
                "owner_user_id": owner_user_id,
                "inventory_copy_count": len(inventory_rows),
                "cover_count": len(cover_ids),
            },
        )
        snapshot_id = snapshot.id
        recommendations = []
        recommendation_types: list[str] = []

        for row in inventory_rows:
            covers = covers_by_inventory.get(row.inventory_copy_id, [])
            primary_cover_id = row.primary_cover_image_id or (int(covers[0].id or 0) if covers else None)
            primary_cover = next((cover for cover in covers if int(cover.id or 0) == primary_cover_id), covers[0] if covers else None)
            ocr_result = latest_ocr_by_cover.get(primary_cover_id or -1) if primary_cover_id is not None else None
            pending_candidates = pending_candidates_by_cover.get(primary_cover_id or -1, []) if primary_cover_id is not None else []
            quality_rows = quality_by_cover.get(primary_cover_id or -1, []) if primary_cover_id is not None else []
            match_rows = match_rows_by_cover.get(primary_cover_id or -1, []) if primary_cover_id is not None else []
            warning_rows = warning_rows_by_inventory.get(row.inventory_copy_id, [])
            conflict_rows = conflict_rows_by_inventory.get(row.inventory_copy_id, [])
            duplicate_rows = duplicate_clusters_by_inventory.get(row.inventory_copy_id, [])
            canonical_rows = canonical_suggestions_by_inventory.get(row.inventory_copy_id, [])
            duplicate_review = duplicate_reviews_by_key.get(row.metadata_identity_key or "")
            arrival_classifications = arrival_by_inventory.get(row.inventory_copy_id, set())

            base_evidence = [
                {
                    "evidence_type": "inventory_projection",
                    "evidence_source": "inventory_copy",
                    "evidence_payload_json": {
                        "inventory_copy_id": row.inventory_copy_id,
                        "title": row.title,
                        "publisher": row.publisher,
                        "issue_number": row.issue_number,
                        "metadata_identity_key": row.metadata_identity_key,
                        "canonical_series_id": row.canonical_series_id,
                        "release_date": row.release_date,
                        "release_year": row.release_year,
                        "release_status": row.release_status,
                        "order_status": row.order_status,
                        "primary_cover_image_id": primary_cover_id,
                    },
                    "evidence_score": 1.0,
                }
            ]
            if primary_cover is not None:
                base_evidence.append(
                    {
                        "evidence_type": "cover_image",
                        "evidence_source": "cover_image",
                        "evidence_payload_json": {
                            "cover_image_id": int(primary_cover.id or 0),
                            "processing_status": primary_cover.processing_status,
                            "sha256_hash": primary_cover.sha256_hash,
                        },
                        "evidence_score": 0.82,
                    }
                )
            if ocr_result is not None:
                base_evidence.append(
                    {
                        "evidence_type": "ocr_result",
                        "evidence_source": "cover_image_ocr_result",
                        "evidence_payload_json": {
                            "ocr_result_id": int(ocr_result.id or 0),
                            "processing_status": ocr_result.processing_status,
                            "confidence_score": ocr_result.confidence_score,
                        },
                        "evidence_score": 0.78 if ocr_result.processing_status == "processed" else 0.68,
                    }
                )

            inventory_title = f"{row.title} #{row.issue_number}"

            if (
                row.metadata_identity_key in {None, ""}
                or row.canonical_series_id is None
                or row.release_year is None
                or ("missing_release_date" in arrival_classifications)
            ):
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"missing_metadata|{row.inventory_copy_id}",
                    recommendation_type="missing_metadata",
                    title=f"{inventory_title} is missing catalog metadata",
                    description="Key catalog fields are incomplete, so this copy should be reviewed before downstream catalog use.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_missing_metadata"},
                    evidence_rows=base_evidence,
                    opportunity_score=0.92,
                    urgency_score=0.8 if "missing_release_date" in arrival_classifications else 0.55,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if duplicate_rows or (duplicate_review is not None and duplicate_review.review_status == "pending"):
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "duplicate_cluster",
                            "evidence_source": "duplicate_cluster",
                            "evidence_payload_json": {
                                "cluster_id": int(cluster.id or 0),
                                "cluster_type": cluster.cluster_type,
                                "total_item_count": cluster.total_item_count,
                                "duplication_status": cluster.duplication_status,
                            },
                            "evidence_score": 0.86,
                        }
                        for cluster, _item in duplicate_rows
                    ],
                ]
                if duplicate_review is not None:
                    evidence_rows.append(
                        {
                            "evidence_type": "duplicate_candidate_review",
                            "evidence_source": "duplicate_candidate_review",
                            "evidence_payload_json": {
                                "review_status": duplicate_review.review_status,
                                "metadata_identity_key": duplicate_review.metadata_identity_key,
                            },
                            "evidence_score": 0.78,
                        }
                    )
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"possible_duplicate|{row.inventory_copy_id}",
                    recommendation_type="possible_duplicate",
                    title=f"{inventory_title} may be a duplicate candidate",
                    description="Duplicate signals already exist for this copy and should be reviewed before any catalog-facing action.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_possible_duplicate"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.7,
                    urgency_score=0.62,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if conflict_rows or any(warning.warning_type not in {"publisher_mismatch"} for warning in warning_rows):
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "catalog_conflict",
                            "evidence_source": "cover_relationship_conflict",
                            "evidence_payload_json": {
                                "conflict_id": int(conflict.id or 0),
                                "conflict_type": conflict.conflict_type,
                                "severity": conflict.severity,
                            },
                            "evidence_score": 0.9 if conflict.severity == "critical" else 0.8,
                        }
                        for conflict in conflict_rows
                    ],
                    *[
                        {
                            "evidence_type": "ocr_warning",
                            "evidence_source": "cover_image_ocr_reconciliation_warning",
                            "evidence_payload_json": {
                                "warning_id": int(warning.id or 0),
                                "warning_type": warning.warning_type,
                                "severity": warning.severity,
                            },
                            "evidence_score": 0.82,
                        }
                        for warning in warning_rows
                        if warning.warning_type not in {"publisher_mismatch"}
                    ],
                ]
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"catalog_conflict|{row.inventory_copy_id}",
                    recommendation_type="catalog_conflict",
                    title=f"{inventory_title} has catalog conflicts to resolve",
                    description="Existing cover or OCR reconciliation conflicts indicate catalog disagreement that needs a human decision.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_catalog_conflict"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.76,
                    urgency_score=0.78,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            publisher_warnings = [warning for warning in warning_rows if warning.warning_type == "publisher_mismatch"]
            publisher_candidates = [candidate for candidate in pending_candidates if candidate.candidate_type == "publisher"]
            if publisher_warnings or publisher_candidates:
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "publisher_warning",
                            "evidence_source": "cover_image_ocr_reconciliation_warning",
                            "evidence_payload_json": {
                                "warning_id": int(warning.id or 0),
                                "warning_type": warning.warning_type,
                                "current_metadata_value": warning.current_metadata_value,
                                "candidate_value": warning.candidate_value,
                            },
                            "evidence_score": 0.88,
                        }
                        for warning in publisher_warnings
                    ],
                    *[
                        {
                            "evidence_type": "publisher_candidate",
                            "evidence_source": "cover_image_ocr_candidate",
                            "evidence_payload_json": {
                                "candidate_id": int(candidate.id or 0),
                                "raw_candidate_text": candidate.raw_candidate_text,
                                "normalized_candidate_text": candidate.normalized_candidate_text,
                                "confidence_score": candidate.confidence_score,
                            },
                            "evidence_score": 0.76,
                        }
                        for candidate in publisher_candidates
                    ],
                ]
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"publisher_conflict|{row.inventory_copy_id}",
                    recommendation_type="publisher_conflict",
                    title=f"{inventory_title} has a publisher conflict",
                    description="OCR-derived publisher signals disagree with the current catalog publisher and need manual review.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_publisher_conflict"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.74,
                    urgency_score=0.72,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if canonical_rows and any(row.suggestion_type in {"variant_family_context", "normalized_title_issue", "normalized_title_issue_publisher"} for row in canonical_rows):
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "canonical_issue_suggestion",
                            "evidence_source": "canonical_issue_link_suggestion",
                            "evidence_payload_json": {
                                "suggestion_id": int(suggestion.id or 0),
                                "suggestion_type": suggestion.suggestion_type,
                                "suggested_metadata_identity_key": suggestion.suggested_metadata_identity_key,
                            },
                            "evidence_score": 0.84,
                        }
                        for suggestion in canonical_rows
                    ],
                ]
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"series_conflict|{row.inventory_copy_id}",
                    recommendation_type="series_conflict",
                    title=f"{inventory_title} has unresolved series identity signals",
                    description="Canonical issue suggestion data indicates this copy needs a human review of its series identity.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_series_identity"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.71,
                    urgency_score=0.66,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if (ocr_result is not None and ocr_result.processing_status != "processed") or pending_candidates:
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "ocr_candidate",
                            "evidence_source": "cover_image_ocr_candidate",
                            "evidence_payload_json": {
                                "candidate_id": int(candidate.id or 0),
                                "candidate_type": candidate.candidate_type,
                                "confidence_score": candidate.confidence_score,
                            },
                            "evidence_score": 0.74,
                        }
                        for candidate in pending_candidates
                    ],
                ]
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"ocr_review_needed|{row.inventory_copy_id}",
                    recommendation_type="ocr_review_needed",
                    title=f"{inventory_title} needs OCR review",
                    description="OCR processing or OCR candidates remain unresolved, so the catalog record needs a human OCR review pass.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_ocr_output"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.69,
                    urgency_score=0.68,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            variant_matches = [match for match in match_rows if match.grouping_type == "probable_variant_family"]
            if variant_matches:
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "cover_match_candidate",
                            "evidence_source": "cover_image_match_candidate",
                            "evidence_payload_json": {
                                "match_candidate_id": int(match.id or 0),
                                "grouping_type": match.grouping_type,
                                "confidence_bucket": match.confidence_bucket,
                            },
                            "evidence_score": 0.81,
                        }
                        for match in variant_matches
                    ],
                ]
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"variant_review_needed|{row.inventory_copy_id}",
                    recommendation_type="variant_review_needed",
                    title=f"{inventory_title} may need variant review",
                    description="Cover match intelligence grouped this copy into a probable variant family that should be reviewed by a human.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_variant_family"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.64,
                    urgency_score=0.58,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            severe_quality_rows = [quality for quality in quality_rows if quality.severity in {"warning", "critical"}]
            if primary_cover is None or severe_quality_rows or (primary_cover is not None and primary_cover.processing_status == "failed"):
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "cover_quality",
                            "evidence_source": "cover_image_ocr_quality_analysis",
                            "evidence_payload_json": {
                                "quality_analysis_id": int(quality.id or 0),
                                "quality_type": quality.quality_type,
                                "severity": quality.severity,
                                "deterministic_score": quality.deterministic_score,
                            },
                            "evidence_score": 0.79 if quality.severity == "critical" else 0.72,
                        }
                        for quality in severe_quality_rows
                    ],
                ]
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"cover_review_needed|{row.inventory_copy_id}",
                    recommendation_type="cover_review_needed",
                    title=f"{inventory_title} needs cover review",
                    description="Cover image availability or quality is not strong enough to trust the current catalog state without human review.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_cover_assets"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.73,
                    urgency_score=0.74 if primary_cover is None else 0.63,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

            if canonical_rows or row.metadata_identity_key in {None, ""}:
                evidence_rows = [
                    *base_evidence,
                    *[
                        {
                            "evidence_type": "canonical_issue_suggestion",
                            "evidence_source": "canonical_issue_link_suggestion",
                            "evidence_payload_json": {
                                "suggestion_id": int(suggestion.id or 0),
                                "suggestion_type": suggestion.suggestion_type,
                                "confidence_bucket": suggestion.confidence_bucket,
                            },
                            "evidence_score": 0.84,
                        }
                        for suggestion in canonical_rows
                    ],
                ]
                rec_type, rec = _persist_recommendation(
                    session,
                    agent_execution_id=agent_execution.execution.id,
                    snapshot_id=snapshot_id,
                    recommendation_key=f"identity_review_needed|{row.inventory_copy_id}",
                    recommendation_type="identity_review_needed",
                    title=f"{inventory_title} needs identity review",
                    description="Canonical issue or metadata identity signals are still unresolved for this copy.",
                    inventory_copy_id=row.inventory_copy_id,
                    inventory_title=inventory_title,
                    recommendation_payload_json={"candidate_action": "review_identity_mapping"},
                    evidence_rows=evidence_rows,
                    opportunity_score=0.78,
                    urgency_score=0.7,
                )
                recommendation_types.append(rec_type)
                recommendations.append(rec)

        summary = {
            "owner_user_id": owner_user_id,
            "inventory_copy_count": len(inventory_rows),
            "recommendation_count": len(recommendations),
            "recommendations_by_type": dict(sorted(Counter(recommendation_types).items())),
        }
        completed_snapshot = complete_snapshot(session, snapshot_id=snapshot_id, summary_json=summary)
        complete_execution(
            session,
            execution_id=agent_execution.execution.id,
            event_payload_json={
                "snapshot_id": snapshot_id,
                "recommendation_count": len(recommendations),
                "research_type": RESEARCH_TYPE,
            },
        )
        return IntelligenceRunResponse(snapshot=completed_snapshot, recommendations=recommendations)
    except Exception as exc:
        if snapshot_id is not None:
            fail_snapshot(
                session,
                snapshot_id=snapshot_id,
                summary_json={"error": str(exc), "research_type": RESEARCH_TYPE},
            )
        fail_execution(
            session,
            execution_id=agent_execution.execution.id,
            event_payload_json={
                "snapshot_id": snapshot_id,
                "research_type": RESEARCH_TYPE,
                "error": str(exc),
            },
        )
        raise
