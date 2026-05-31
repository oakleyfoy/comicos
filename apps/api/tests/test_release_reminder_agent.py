from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.release_watchlist import ReleaseReminder
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.release_import import import_release_feed
from app.services.release_reminder_agent import run_release_reminders
from test_inventory import create_order, register_and_login


def test_release_reminder_agent_generates_upcoming_release_reminders(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "release-reminders@example.com"
    token = register_and_login(client, email)
    create_order(client, token)
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
                            "release_uuid": "inv-release-1",
                            "issue_number": "2",
                            "title": "Invincible #2",
                            "release_date": str(today),
                            "release_status": "SCHEDULED",
                        },
                        {
                            "release_uuid": "inv-release-2",
                            "issue_number": "3",
                            "title": "Invincible #3",
                            "release_date": str(today + timedelta(days=1)),
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
        reminders, execution = run_release_reminders(session, owner_user_id=owner_user_id)
        reminder_types = {row.reminder_type for row in reminders}
        assert execution.status == "COMPLETED"
        assert "RELEASE_TODAY" in reminder_types
        assert "RELEASE_TOMORROW" in reminder_types
        assert len(session.exec(select(ReleaseReminder).where(ReleaseReminder.owner_user_id == owner_user_id)).all()) >= 2
