from __future__ import annotations

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.services.lunar_variant_repair import repair_lunar_variants_for_owner
from test_inventory import register_and_login


def test_repair_creates_variants_without_deleting_issues(client) -> None:
    register_and_login(client, "lunar-repair@example.com")
    with Session(get_engine()) as session:
        user = session.exec(select(User).where(User.email == "lunar-repair@example.com")).one()
        owner_id = int(user.id)
        series = ReleaseSeries(
            owner_user_id=owner_id,
            publisher="DC Comics",
            series_name="ZATANNA (2026)",
            series_type="ONGOING",
            status="ACTIVE",
        )
        session.add(series)
        session.commit()
        session.refresh(series)
        for idx, title in enumerate(
            [
                "ZATANNA (2026) #5 CVR A JAMAL CAMPBELL",
                "ZATANNA (2026) #5 CVR B DAVID TALASKI CARD STOCK VAR",
            ],
            start=1,
        ):
            session.add(
                ReleaseIssue(
                    owner_user_id=owner_id,
                    release_uuid=f"lunar-0626DC000{idx}",
                    series_id=int(series.id),
                    issue_number="5",
                    title=title,
                    cover_price=4.99,
                    release_status="SCHEDULED",
                )
            )
        session.commit()
        before_issues = len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).all())
        summary = repair_lunar_variants_for_owner(session, owner_user_id=owner_id)
        after_issues = len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).all())
        variants = session.exec(
            select(ReleaseVariant)
            .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_id)
        ).all()
    assert before_issues == after_issues
    assert summary.variants_created >= 1
    assert len(variants) >= 2
