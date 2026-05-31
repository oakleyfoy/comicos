from __future__ import annotations

from sqlmodel import Session, select

from app.models import User
from app.services.release_import_dashboard import build_release_import_dashboard
from app.services.release_json_import import import_json_feed
from test_release_import import _sample_feed


def test_release_import_dashboard_aggregates_runs(client) -> None:
    from app.db.session import get_engine
    from test_inventory import register_and_login

    email = "import-dashboard@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        import_json_feed(
            session,
            owner_user_id=owner_user_id,
            file_name="sample.json",
            raw_feed={"feed": _sample_feed().model_dump()},
        )
        dashboard = build_release_import_dashboard(session, owner_user_id=owner_user_id)
        assert dashboard.recent_imports
        assert dashboard.import_success_rate >= 0
        assert dashboard.latest_uploads
        assert isinstance(dashboard.error_summary, list)
