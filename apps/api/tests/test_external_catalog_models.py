from __future__ import annotations

import pytest
from sqlmodel import Session, select

pytestmark = pytest.mark.usefixtures("client")

from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogSource
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.external_catalog.sync_service import ensure_locg_source


def test_external_catalog_models_persist(session: Session) -> None:
    ensure_locg_source(session)
    row = ExternalCatalogIssue(
        source_name=LOCG_SOURCE_NAME,
        source_url="https://leagueofcomicgeeks.com/comic/1/test",
        title="Test #1",
        publisher="Marvel Comics",
        series_name="Test",
        issue_number="1",
        normalized_title_key="marvel comics|test|1",
    )
    session.add(row)
    session.commit()
    loaded = session.exec(select(ExternalCatalogIssue).where(ExternalCatalogIssue.title == "Test #1")).first()
    assert loaded is not None
    source = session.exec(
        select(ExternalCatalogSource).where(ExternalCatalogSource.source_name == LOCG_SOURCE_NAME)
    ).first()
    assert source is not None
