from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import LunarFeedRun, LunarFocAlert, User
from app.services.lunar_csv_parser import parse_lunar_product_csv
from app.services.lunar_foc_intelligence import generate_foc_alerts
from lunar_feed_test_helpers import SAMPLE_CSV


def test_generate_foc_alerts(client) -> None:
    foc = (date.today() + timedelta(days=7)).strftime("%m/%d/%Y")
    csv_text = SAMPLE_CSV.replace("2026-06-01", foc)
    rows = parse_lunar_product_csv(csv_text)
    with Session(get_engine()) as session:
        owner = User(email="lunar-foc@example.com", password_hash="x", is_active=True)
        session.add(owner)
        session.commit()
        session.refresh(owner)
        owner_user_id = int(owner.id or 0)
        run = LunarFeedRun(
            owner_user_id=owner_user_id,
            source_type="UPLOAD",
            file_name="test.csv",
            file_period="2026-06",
            status="RUNNING",
            source_url="",
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        alerts = generate_foc_alerts(
            session,
            owner_user_id=owner_user_id,
            feed_run_id=int(run.id or 0),
            rows=rows,
        )
        assert len(alerts) == 1
        stored = session.exec(select(LunarFocAlert).where(LunarFocAlert.owner_user_id == owner.id)).all()
        assert len(stored) == 1
