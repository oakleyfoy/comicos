from __future__ import annotations

from app.services.cross_system_recommendation import list_latest_cross_system_recommendations
from app.services.cross_system_recommendation_engine import (
    _Candidate,
    _confidence_for_persist,
    _priority_for_persist,
    _snapshot_confidence_saturated,
    generate_cross_system_recommendations,
)
from app.services.recommendation_ranking_diagnostics import build_recommendation_ranking_audit


def test_priority_for_persist_uses_normalized_not_saturated_raw() -> None:
    cand = _Candidate(
        recommendation_type="PREORDER",
        title="Battle Beast #12",
        priority_score=100.0,
        confidence_score=0.86,
        estimated_value=None,
        raw_priority_score=99.9,
        normalized_priority_score=96.9,
    )
    assert _priority_for_persist(cand) == 96.9


def test_confidence_for_persist_uses_normalized_not_one() -> None:
    cand = _Candidate(
        recommendation_type="PREORDER",
        title="G.I. Joe #25",
        priority_score=88.0,
        confidence_score=1.0,
        estimated_value=None,
        raw_confidence_score=0.91,
        normalized_confidence_score=0.96,
    )
    assert _confidence_for_persist(cand) == 0.96


def test_snapshot_confidence_saturated_detects_flat_one() -> None:
    from app.models.cross_system_recommendation import CrossSystemRecommendation

    snap = {
        i: CrossSystemRecommendation(
            owner_user_id=1,
            recommendation_type="PREORDER",
            priority_score=90.0,
            confidence_score=1.0,
            title=f"Title {i}",
            recommendation_rank=i,
            source_systems=[],
            rationale="x",
        )
        for i in range(1, 11)
    }
    assert _snapshot_confidence_saturated(snap) is True

def test_generate_persists_spread_priority_scores(
    client,
    session,
) -> None:
    from test_cross_system_recommendation import _seed_stack

    owner_id = _seed_stack(client, session, "persist-spread@example.com")
    inserted = generate_cross_system_recommendations(session, owner_user_id=owner_id, refresh_upstream=True)
    assert inserted >= 1
    items, _ = list_latest_cross_system_recommendations(session, owner_user_id=owner_id, limit=50)
    assert items
    assert not all(abs(float(i.priority_score) - 100.0) < 1e-9 for i in items[:20])

    audit = build_recommendation_ranking_audit(session, owner_user_id=owner_id, limit=50, refresh=False)
    top = audit.items[: min(20, len(audit.items))]
    assert all(row.computed_priority_score is not None for row in top)
    assert all(abs(float(row.priority_score) - float(row.computed_priority_score)) < 0.05 for row in top)
    assert all(abs(float(row.computed_priority_score) - float(row.normalized_priority_score)) < 0.05 for row in top)
    assert all(row.computed_confidence_score is not None for row in top)
    assert all(abs(float(row.confidence_score) - float(row.computed_confidence_score)) < 0.01 for row in top)
    assert all(abs(float(row.computed_confidence_score) - float(row.normalized_confidence_score)) < 0.01 for row in top)
    assert len({round(float(r.confidence_score), 4) for r in top}) >= min(3, len(top))
    assert not all(float(r.confidence_score) >= 0.999 for r in top)
