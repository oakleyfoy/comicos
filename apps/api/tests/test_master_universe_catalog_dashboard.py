"""Tests for Master Universe catalog coverage dashboard."""

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.services.universe.master_universe_catalog_dashboard_service import get_master_universe_catalog_dashboard


def test_catalog_dashboard_empty_db(session) -> None:
    result = get_master_universe_catalog_dashboard(session, owner_user_id=1)
    assert result.summary.catalog_issue_count == 0
    assert result.summary.inventory_copy_count == 0
    assert result.rows == []
    assert result.total_count == 0


def test_catalog_dashboard_with_series_and_issues(session) -> None:
    publisher = CatalogPublisher(name="DC Comics", normalized_name="dc comics")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        publisher_id=int(publisher.id),
        name="Test Series",
        normalized_name="test series",
    )
    session.add(series)
    session.flush()
    session.add(
        CatalogIssue(
            publisher_id=int(publisher.id),
            series_id=int(series.id),
            issue_number="1",
            normalized_issue_number="1",
            title="Test #1",
            external_source_ids={"GCD": "123"},
        )
    )
    session.commit()

    result = get_master_universe_catalog_dashboard(session, owner_user_id=1)
    assert result.summary.catalog_issue_count >= 1
    assert result.total_count >= 1
    dc_row = next((row for row in result.rows if "DC" in row.publisher.upper()), None)
    assert dc_row is not None
    assert dc_row.catalog_issue_count >= 1
