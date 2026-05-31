from __future__ import annotations

from sqlmodel import Session, select

from app.models import ReleaseIssue, User
from app.services.release_csv_import import import_csv_feed, validate_csv_feed


def test_validate_csv_feed_maps_rows() -> None:
    csv_text = (
        "publisher,series_name,issue_number,title,release_date,foc_date,cover_price,variant_name,ratio\n"
        "Image,Battle Beast,8,Battle Beast #8,2026-08-01,2026-07-01,4.99,1:25,25\n"
    )
    payload, errors, processed = validate_csv_feed(csv_text)
    assert payload is not None
    assert processed == 1
    assert not errors
    assert payload.series[0].issues[0].issue_number == "8"
    assert payload.series[0].issues[0].variants[0].ratio_value == 25


def test_import_csv_feed_creates_release_rows(client) -> None:
    from app.db.session import get_engine
    from test_inventory import register_and_login

    email = "csv-import@example.com"
    register_and_login(client, email)
    csv_text = (
        "publisher,series_name,issue_number,title,release_date,cover_price\n"
        "Marvel,CSV Series,1,CSV Series #1,2026-09-01,5.99\n"
    )
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)
        run, result = import_csv_feed(
            session,
            owner_user_id=owner_user_id,
            file_name="releases.csv",
            csv_text=csv_text,
        )
        assert result is not None
        assert run.status == "COMPLETED"
        issues = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        assert len(issues) == 1
        assert issues[0].title == "CSV Series #1"


def test_validate_csv_feed_reports_missing_columns() -> None:
    payload, errors, _ = validate_csv_feed("issue_number,title\n1,Test\n")
    assert payload is None
    assert any(error[1] == "MISSING_COLUMNS" for error in errors)
