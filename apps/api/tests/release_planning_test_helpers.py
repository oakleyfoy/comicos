from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.release_import import import_release_feed
from test_inventory import create_order


def seed_release_issue(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str,
    series_name: str,
    issue_number: str,
    title: str,
    release_uuid: str,
    days_out: int,
    signals: list[tuple[str, dict]] | None = None,
    cover_price: float = 4.99,
    release_status: str = "SCHEDULED",
) -> tuple[ReleaseIssue, ReleaseSeries]:
    today = date.today()
    payload = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": publisher,
                    "series_name": series_name,
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": release_uuid,
                            "issue_number": issue_number,
                            "title": title,
                            "release_date": str(today + timedelta(days=days_out)),
                            "cover_price": cover_price,
                            "release_status": release_status,
                        }
                    ],
                }
            ]
        }
    )
    import_release_feed(session, owner_user_id=owner_user_id, payload=payload)
    series = session.exec(
        select(ReleaseSeries)
        .where(ReleaseSeries.owner_user_id == owner_user_id)
        .where(ReleaseSeries.series_name == series_name)
    ).one()
    issue = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_uuid == release_uuid)
    ).one()
    if signals:
        for signal_type, payload_json in signals:
            session.add(
                ReleaseKeySignal(
                    owner_user_id=owner_user_id,
                    issue_id=int(issue.id or 0),
                    signal_type=signal_type,
                    confidence_score=0.9,
                    signal_payload_json=payload_json,
                )
            )
        session.commit()
        session.refresh(issue)
    return issue, series


def seed_inventory_issues(
    client,
    token: str,
    *,
    publisher: str,
    title: str,
    issue_numbers: list[str],
) -> None:
    create_order(
        client,
        token,
        items=[
            {
                "title": title,
                "publisher": publisher,
                "issue_number": issue_number,
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            }
            for issue_number in issue_numbers
        ],
    )
