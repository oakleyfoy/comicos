"""Tests for Master Universe catalog coverage dashboard."""

from app.services.universe.master_universe_catalog_dashboard_service import get_master_universe_catalog_dashboard


def test_catalog_dashboard_empty_db(session) -> None:
    result = get_master_universe_catalog_dashboard(session, owner_user_id=1)
    assert result.summary.catalog_issue_count == 0
    assert result.summary.inventory_copy_count == 0
    assert result.rows == []
    assert result.total_count == 0
