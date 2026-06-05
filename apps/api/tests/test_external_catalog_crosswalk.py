from __future__ import annotations

import pytest
from datetime import date, timedelta

pytestmark = pytest.mark.usefixtures("client")

from sqlmodel import Session

from app.models import User
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.external_catalog.crosswalk import (
    MATCH_MATCHED,
    MATCH_MISSING,
    build_coverage_report,
    rebuild_external_catalog_crosswalk,
)
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.external_catalog.normalization import build_normalized_title_key


def _owner(session: Session) -> int:
    user = User(email="extcat@test.com", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return int(user.id or 0)


def test_crosswalk_matched_and_missing(session: Session) -> None:
    owner_id = _owner(session)
    series = ReleaseSeries(
        owner_user_id=owner_id,
        publisher="Image Comics",
        series_name="Youngblood",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.commit()
    session.refresh(series)
    release = ReleaseIssue(
        owner_user_id=owner_id,
        series_id=int(series.id or 0),
        issue_number="100",
        title="Youngblood #100",
        release_date=date.today() + timedelta(days=14),
        release_status="SCHEDULED",
    )
    session.add(release)
    session.commit()
    session.refresh(release)

    key = build_normalized_title_key(
        publisher="Image Comics",
        series_name="Youngblood",
        issue_number="100",
    )
    matched_ext = ExternalCatalogIssue(
        source_name=LOCG_SOURCE_NAME,
        source_url="https://leagueofcomicgeeks.com/comic/900001/youngblood-100",
        title="Youngblood #100",
        publisher="Image Comics",
        series_name="Youngblood",
        issue_number="100",
        release_date=release.release_date,
        normalized_title_key=key,
        pull_count=500,
    )
    missing_ext = ExternalCatalogIssue(
        source_name=LOCG_SOURCE_NAME,
        source_url="https://leagueofcomicgeeks.com/comic/900010/spawn-skybound",
        title="Spawn Universe #1",
        publisher="Image Comics",
        series_name="Spawn Universe",
        issue_number="1",
        release_date=date.today() + timedelta(days=30),
        normalized_title_key=build_normalized_title_key(
            publisher="Image Comics",
            series_name="Spawn Universe",
            issue_number="1",
        ),
        pull_count=400,
    )
    session.add(matched_ext)
    session.add(missing_ext)
    session.commit()
    session.refresh(matched_ext)
    session.refresh(missing_ext)

    summary = rebuild_external_catalog_crosswalk(session, owner_user_id=owner_id)
    assert summary["matched"] >= 1
    assert summary["missing_from_lunar"] >= 1

    from sqlmodel import select

    row_match = session.exec(
        select(ExternalCatalogMatch).where(
            ExternalCatalogMatch.external_issue_id == int(matched_ext.id or 0),
            ExternalCatalogMatch.owner_user_id == owner_id,
        )
    ).first()
    row_missing = session.exec(
        select(ExternalCatalogMatch).where(
            ExternalCatalogMatch.external_issue_id == int(missing_ext.id or 0),
            ExternalCatalogMatch.owner_user_id == owner_id,
        )
    ).first()
    assert row_match is not None
    assert row_match.match_status == MATCH_MATCHED
    assert row_missing is not None
    assert row_missing.match_status == MATCH_MISSING

    report = build_coverage_report(session, owner_user_id=owner_id)
    assert report["total_external_issues"] == 2
    assert report["total_missing_from_lunar"] >= 1
    assert report["number_one_issues_missing"] >= 1
