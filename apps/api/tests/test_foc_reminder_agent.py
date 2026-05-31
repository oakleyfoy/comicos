from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.release_watchlist import ReleaseReminder
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.foc_reminder_agent import run_foc_reminders
from app.services.release_import import import_release_feed
from test_inventory import create_order, register_and_login


def test_foc_reminder_agent_generates_deadline_reminders(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "foc-reminders@example.com"
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
                            "release_uuid": "inv-foc-1",
                            "issue_number": "2",
                            "title": "Invincible #2",
                            "foc_date": str(today),
                            "release_date": str(today + timedelta(days=7)),
                            "release_status": "SCHEDULED",
                        },
                        {
                            "release_uuid": "inv-foc-2",
                            "issue_number": "3",
                            "title": "Invincible #3",
                            "foc_date": str(today - timedelta(days=1)),
                            "release_date": str(today + timedelta(days=8)),
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
        reminders, execution = run_foc_reminders(session, owner_user_id=owner_user_id)
        reminder_types = {row.reminder_type for row in reminders}
        assert execution.status == "COMPLETED"
        assert "FOC_TODAY" in reminder_types
        assert "FOC_MISSED" in reminder_types
        assert len(session.exec(select(ReleaseReminder).where(ReleaseReminder.owner_user_id == owner_user_id)).all()) >= 2
