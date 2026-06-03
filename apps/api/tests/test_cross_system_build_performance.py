from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import app.services.cross_system_recommendation_engine as engine
from app.services.cross_system_recommendation_engine import build_cross_system_candidates


def test_build_cross_system_skips_upstream_regeneration_by_default() -> None:
    session = MagicMock()
    unified_calls: list[int] = []
    daily_calls: list[int] = []

    original_build_index = engine.build_forward_release_title_index
    original_unified = engine._unified_candidates
    original_daily = engine._list_daily_collector_actions
    original_budget = engine.get_purchase_budget_row
    original_enrich = engine._enrich_estimated_values

    def _fake_index(_session, *, owner_user_id: int, pipeline_cache=None):
        return {}

    import app.services.daily_action_engine as daily_mod
    import app.services.recommendation_forward_window as forward_mod
    import app.services.unified_collector_intelligence as unified_mod

    original_key_signals = forward_mod._key_signals_by_issue

    unified_mod.generate_unified_collector_recommendations = lambda *a, **k: unified_calls.append(1) or 0  # type: ignore[method-assign]
    daily_mod.generate_daily_actions = lambda *a, **k: daily_calls.append(1) or 0  # type: ignore[method-assign]

    try:
        engine.build_forward_release_title_index = _fake_index  # type: ignore[method-assign]
        engine._unified_candidates = lambda *a, **k: []  # type: ignore[method-assign]
        engine._list_daily_collector_actions = lambda *a, **k: []  # type: ignore[method-assign]
        engine.get_purchase_budget_row = lambda *a, **k: SimpleNamespace(  # type: ignore[method-assign]
            is_active=False, monthly_budget=0.0
        )
        engine._enrich_estimated_values = lambda *a, **k: None  # type: ignore[method-assign]
        forward_mod._key_signals_by_issue = lambda *a, **k: {}  # type: ignore[method-assign]

        build_cross_system_candidates(session, owner_user_id=1, refresh_upstream=False)
        assert unified_calls == []
        assert daily_calls == []
    finally:
        engine.build_forward_release_title_index = original_build_index  # type: ignore[method-assign]
        engine._unified_candidates = original_unified  # type: ignore[method-assign]
        engine._list_daily_collector_actions = original_daily  # type: ignore[method-assign]
        engine.get_purchase_budget_row = original_budget  # type: ignore[method-assign]
        engine._enrich_estimated_values = original_enrich  # type: ignore[method-assign]
        forward_mod._key_signals_by_issue = original_key_signals  # type: ignore[method-assign]
