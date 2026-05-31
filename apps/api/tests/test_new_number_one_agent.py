from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.new_number_one_agent import detect_new_number_ones
from app.services.release_import import import_release_feed
from test_inventory import register_and_login


def test_new_number_one_agent_detects_issue_one_without_mutating_issues(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "release-one@example.com"
    register_and_login(client, email)
    feed = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "DC",
                    "series_name": "Future Relauch",
                    "series_type": "MINI",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": "future-relaunch-1",
                            "issue_number": "1",
                            "title": "Future Relaunch #1",
                            "release_status": "SCHEDULED",
                        }
                    ],
                }
            ]
        }
    )
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        import_release_feed(session, owner_user_id=owner_user_id, payload=feed)
        issue_count = len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all())

        signals, execution = detect_new_number_ones(session, owner_user_id=owner_user_id)
        assert execution.status == "COMPLETED"
        assert len(signals) == 1
        assert signals[0].signal_type == "NEW_NUMBER_ONE"
        assert len(session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)).all()) == 1
        assert len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()) == issue_count
