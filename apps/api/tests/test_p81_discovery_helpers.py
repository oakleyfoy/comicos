from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session

from app.models.external_catalog import ExternalCatalogIssue
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries


def seed_release_number_one(session: Session, *, owner_user_id: int) -> int:
    pub = "DC"
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher=pub,
        series_name="Absolute Superman",
        series_type="NEW",
        status="ACTIVE",
    )
    session.add(series)
    session.flush()
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        series_id=int(series.id or 0),
        issue_number="1",
        title="Absolute Superman #1 — launch",
        release_date=date.today() + timedelta(days=45),
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    return int(issue.id or 0)


def seed_milestone_issue(session: Session, *, owner_user_id: int) -> int:
    series = ReleaseSeries(
        owner_user_id=owner_user_id,
        publisher="IDW",
        series_name="Teenage Mutant Ninja Turtles",
        series_type="ONGOING",
        status="ACTIVE",
    )
    session.add(series)
    session.flush()
    issue = ReleaseIssue(
        owner_user_id=owner_user_id,
        series_id=int(series.id or 0),
        issue_number="300",
        title="TMNT #300",
        release_date=date.today() + timedelta(days=60),
        release_status="SCHEDULED",
    )
    session.add(issue)
    session.commit()
    return int(issue.id or 0)


def seed_external_first_issue(session: Session) -> int:
    row = ExternalCatalogIssue(
        source_name="TEST",
        title="Battle Beast Universe #1",
        publisher="Image",
        series_name="Battle Beast Universe",
        issue_number="1",
        release_date=date.today() + timedelta(days=30),
        is_first_issue=True,
        description="New Daniel Warren Johnson project",
    )
    session.add(row)
    session.commit()
    return int(row.id or 0)
