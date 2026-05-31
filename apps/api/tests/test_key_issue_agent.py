from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseKeySignal
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.key_issue_agent import detect_key_issues
from app.services.release_import import import_release_feed
from test_inventory import register_and_login


def test_key_issue_agent_detects_keyword_and_milestone_signals(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "release-key@example.com"
    register_and_login(client, email)
    feed = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "Image",
                    "series_name": "Legacy Saga",
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": "legacy-origin-1",
                            "issue_number": "1",
                            "title": "The Origin of Legacy Hero",
                            "release_status": "SCHEDULED",
                        },
                        {
                            "release_uuid": "legacy-25",
                            "issue_number": "25",
                            "title": "Legacy Saga Anniversary Special",
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
        import_release_feed(session, owner_user_id=owner_user_id, payload=feed)

        signals, execution = detect_key_issues(session, owner_user_id=owner_user_id)
        signal_types = {signal.signal_type for signal in signals}
        assert execution.status == "COMPLETED"
        assert "ORIGIN_ISSUE" in signal_types
        assert "ANNIVERSARY_ISSUE" in signal_types
        assert "MILESTONE_NUMBERING" in signal_types
        assert len(session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)).all()) >= 3
