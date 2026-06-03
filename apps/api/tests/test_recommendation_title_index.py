"""Scoped forward release title index."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.recommendation_title_index import (
    RecommendationPipelineIndexCache,
    build_scoped_forward_release_title_index,
    build_full_release_title_index,
)


def test_scoped_index_uses_forward_window_not_full_select() -> None:
    session = MagicMock()
    forward_pair = (MagicMock(id=1), MagicMock(series_name="Alpha", issue_number="1"))

    with (
        patch(
            "app.services.recommendation_title_index.iter_forward_release_rows",
            return_value=[forward_pair],
        ) as forward_iter,
        patch(
            "app.services.recommendation_title_index._collect_recommendation_title_keys",
            return_value=set(),
        ),
        patch(
            "app.services.recommendation_title_index._lookup_pairs_for_title_keys",
            return_value=([], 0),
        ),
    ):
        result = build_scoped_forward_release_title_index(session, owner_user_id=1)
        forward_iter.assert_called_once()
        assert result.title_index_rows_loaded == 1
        assert "forward_window" in result.title_index_source
        session.exec.assert_not_called()


def test_pipeline_cache_reuses_index() -> None:
    session = MagicMock()
    cache = RecommendationPipelineIndexCache(owner_user_id=7)
    built = build_scoped_forward_release_title_index

    with patch(
        "app.services.recommendation_title_index.build_scoped_forward_release_title_index",
        wraps=lambda *a, **k: type(
            "R",
            (),
            {
                "index": {"alpha #1": (MagicMock(), MagicMock())},
                "title_index_rows_loaded": 1,
                "title_index_source": "forward_window",
                "title_index_memory_mb": 0.1,
                "title_index_build_ms": 1.0,
            },
        )(),
    ) as mock_build:
        idx1 = cache.get_index(session)
        idx2 = cache.get_index(session)
        assert idx1 is idx2
        assert mock_build.call_count == 1


def test_full_catalog_builder_still_available() -> None:
    session = MagicMock()
    issue = MagicMock(id=2, issue_number="3", owner_user_id=1)
    series = MagicMock(series_name="Beta")
    session.exec.return_value.all.return_value = [(issue, series)]
    index = build_full_release_title_index(session, owner_user_id=1)
    assert len(index) == 1
