from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from app.services.recommendation_signal_bucket_fast import (
    SignalBucketDiagnosticCaches,
    fetch_stored_recommendation_by_title,
    fetch_top_stored_recommendations,
)


def test_title_path_does_not_call_list_latest_cross_system() -> None:
    with patch(
        "app.services.recommendation_signal_bucket_fast._latest_snapshot_rows",
        return_value={1: MagicMock(title="Youngblood #1", priority_score=90.0, recommendation_rank=1)},
    ) as snap:
        with patch(
            "app.services.cross_system_recommendation.list_latest_cross_system_recommendations",
        ) as list_latest:
            with patch(
                "app.services.recommendation_decision_engine.decision_for_cross_system",
            ) as decision:
                session = MagicMock(spec=Session)
                row = snap.return_value[1]
                row.recommendation_type = "ACQUIRE"
                row.confidence_score = 0.9
                row.source_systems = ["P57_UNIFIED"]
                row.rationale = "test"
                caches = SignalBucketDiagnosticCaches()
                rec, _ = fetch_stored_recommendation_by_title(
                    session,
                    owner_user_id=1,
                    title_query="Youngblood",
                    caches=caches,
                )
                list_latest.assert_not_called()
                decision.assert_not_called()
    assert rec is not None
    assert "Youngblood" in rec["title"]


def test_fetch_top_stored_without_decision() -> None:
    rows = {
        1: MagicMock(
            title="A #1",
            priority_score=99.0,
            confidence_score=0.9,
            recommendation_rank=1,
            recommendation_type="ACQUIRE",
            source_systems=[],
            rationale="",
        ),
        2: MagicMock(
            title="B #2",
            priority_score=88.0,
            confidence_score=0.8,
            recommendation_rank=2,
            recommendation_type="PREORDER",
            source_systems=[],
            rationale="",
        ),
    }
    with patch(
        "app.services.recommendation_signal_bucket_fast._latest_snapshot_rows",
        return_value=rows,
    ):
        with patch(
            "app.services.recommendation_decision_engine.decision_for_cross_system",
        ) as decision:
            session = MagicMock(spec=Session)
            caches = SignalBucketDiagnosticCaches()
            out = fetch_top_stored_recommendations(
                session, owner_user_id=1, limit=2, caches=caches
            )
            decision.assert_not_called()
    assert len(out) == 2
    assert out[0]["recommendation_rank"] == 1


def test_creator_profiles_loaded_once() -> None:
    caches = SignalBucketDiagnosticCaches()
    session = MagicMock(spec=Session)
    profile = MagicMock(creator_name="Test Creator", id=1, status="ACTIVE")
    session.exec.return_value.all.return_value = [profile]

    first = caches.get_active_creators(session)
    second = caches.get_active_creators(session)
    assert first is second
    assert caches.creator_profile_load_count == 1


def test_market_demand_cached_after_first_load() -> None:
    caches = SignalBucketDiagnosticCaches()
    session = MagicMock(spec=Session)
    mp = MagicMock(entity_name="youngblood", demand_score=50.0)
    session.exec.return_value.all.return_value = [mp]

    caches.get_market_profiles(session, search_blob="youngblood series")
    caches.get_market_profiles(session, search_blob="other")
    assert caches.market_demand_load_count == 1


def test_diagnose_title_fast_path_script_imports() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "diagnose_recommendation_signal_bucket.py"
    ).read_text(encoding="utf-8")
    assert "fetch_stored_recommendation_by_title" in source
    assert "list_latest_cross_system_recommendations" not in source
    assert '"performance"' in source or "'performance'" in source or "performance_payload" in source


def test_single_title_script_skips_title_index_build() -> None:
    """--title path should not call build_forward_release_title_index."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "diagnose_recommendation_signal_bucket.py"
    ).read_text(encoding="utf-8")
    title_block = source.split("if args.title:")[1].split("rec_limit = top_n")[0]
    assert "build_forward_release_title_index" not in title_block
    assert "use_title_index_resolve=False" in title_block
