from __future__ import annotations

from sqlmodel import Session, select

from app.models import ReleaseIssue, ReleaseImportRun, User
from app.services.release_json_import import import_json_feed, validate_json_feed
from test_release_import import _sample_feed


def test_validate_json_feed_accepts_release_feed_request() -> None:
    payload, errors = validate_json_feed(_sample_feed().model_dump())
    assert payload is not None
    assert not errors


def test_validate_json_feed_rejects_invalid_payload() -> None:
    payload, errors = validate_json_feed({"series": [{"publisher": "Marvel"}]})
    assert payload is None
    assert errors


def test_import_json_feed_creates_history(client) -> None:
    from app.db.session import get_engine
    from test_inventory import register_and_login

    email = "json-import@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        run, result = import_json_feed(
            session,
            owner_user_id=owner_user_id,
            file_name="sample.json",
            raw_feed={"feed": _sample_feed().model_dump()},
        )
        assert result is not None
        assert run.status == "COMPLETED"
        assert run.records_created > 0
        assert len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()) == 1
        assert len(session.exec(select(ReleaseImportRun).where(ReleaseImportRun.owner_user_id == owner_user_id)).all()) == 1

        second, _ = import_json_feed(
            session,
            owner_user_id=owner_user_id,
            file_name="sample.json",
            raw_feed={"feed": _sample_feed().model_dump()},
        )
        assert second.records_updated > 0
        assert len(session.exec(select(ReleaseImportRun).where(ReleaseImportRun.owner_user_id == owner_user_id)).all()) == 2
