from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.release_watchlist import CollectionContinuityAlert, CollectionRun
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.release_import import import_release_feed
from app.services.run_continuity_agent import run_continuity_detection
from test_inventory import create_order, register_and_login


def _seed_continuity_data(client, email: str) -> int:
    token = register_and_login(client, email)
    create_order(
        client,
        token,
        items=[
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            },
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "2",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            },
        ],
    )
    return token


def test_run_continuity_agent_detects_next_issue_and_missing_risk(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "continuity@example.com"
    _seed_continuity_data(client, email)
    today = date.today()
    payload = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "Image",
                    "series_name": "Invincible",
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": "invincible-3",
                            "issue_number": "3",
                            "title": "Invincible #3",
                            "release_date": str(today + timedelta(days=3)),
                            "release_status": "SCHEDULED",
                        },
                        {
                            "release_uuid": "invincible-5",
                            "issue_number": "5",
                            "title": "Invincible #5",
                            "release_date": str(today + timedelta(days=10)),
                            "release_status": "SCHEDULED",
                        },
                    ],
                }
            ]
        }
    )

    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        import_release_feed(session, owner_user_id=owner_user_id, payload=payload)
        runs, alerts, execution = run_continuity_detection(session, owner_user_id=owner_user_id)

        assert execution.status == "COMPLETED"
        assert len(runs) >= 1
        alert_types = {alert.alert_type for alert in alerts}
        assert "CONTINUE_RUN" in alert_types
        assert "NEXT_ISSUE_ANNOUNCED" in alert_types
        assert "MISSING_ISSUE_RISK" in alert_types
        assert len(session.exec(select(CollectionRun).where(CollectionRun.owner_user_id == owner_user_id)).all()) >= 1
        assert (
            len(session.exec(select(CollectionContinuityAlert).where(CollectionContinuityAlert.owner_user_id == owner_user_id)).all())
            >= 3
        )
