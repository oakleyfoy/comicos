from __future__ import annotations

import uuid

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.models import User
from app.services.lunar_feed_import import import_lunar_csv_bytes
from app.services.lunar_issue_identity import is_canonical_lunar_issue_uuid, is_legacy_flat_lunar_issue_uuid
from app.services.lunar_release_normalizer import normalize_lunar_rows
from app.services.lunar_variant_identity import build_issue_release_uuid
from lunar_feed_test_helpers import MULTI_VARIANT_CSV


def _owner(session: Session) -> int:
    user = User(email=f"lunar-reimport-{uuid.uuid4().hex[:8]}@example.com", password_hash="x", is_active=True)
    session.add(user)
    session.commit()
    session.refresh(user)
    return int(user.id)


def test_normalizer_groups_variants_under_one_issue_uuid() -> None:
    from app.services.lunar_csv_parser import parse_lunar_product_csv

    rows = parse_lunar_product_csv(MULTI_VARIANT_CSV)
    feed, errors = normalize_lunar_rows(rows)
    assert not errors
    issue = feed.series[0].issues[0]
    assert len(issue.variants) == 3
    assert is_canonical_lunar_issue_uuid(issue.release_uuid)
    assert not issue.release_uuid.startswith("lunar-0626")


def test_reimport_does_not_create_duplicate_issues_or_variants() -> None:
    with Session(get_engine()) as session:
        owner_id = _owner(session)
        first = import_lunar_csv_bytes(
            session,
            owner_user_id=owner_id,
            file_name="zatanna.csv",
            content_bytes=MULTI_VARIANT_CSV.encode("utf-8"),
        )
        issues_after_first = session.exec(
            select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)
        ).all()
        variants_after_first = session.exec(
            select(ReleaseVariant)
            .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_id)
        ).all()
        issue_count_first = len(issues_after_first)
        variant_count_first = len(variants_after_first)

        second = import_lunar_csv_bytes(
            session,
            owner_user_id=owner_id,
            file_name="zatanna.csv",
            content_bytes=MULTI_VARIANT_CSV.encode("utf-8"),
        )
        issues_after_second = session.exec(
            select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)
        ).all()
        variants_after_second = session.exec(
            select(ReleaseVariant)
            .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_id)
        ).all()

    assert issue_count_first == 1
    assert variant_count_first == 3
    assert len(issues_after_second) == issue_count_first
    assert len(variants_after_second) == variant_count_first
    assert first.issues_created if hasattr(first, "issues_created") else first.records_created >= 1
    assert second.records_created == 0


def test_legacy_flat_rows_reused_on_reimport() -> None:
    with Session(get_engine()) as session:
        owner_id = _owner(session)
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
        for code in ("0626DC0001", "0626DC0002"):
            session.add(
                ReleaseIssue(
                    owner_user_id=owner_id,
                    release_uuid=f"lunar-{code}",
                    series_id=int(series.id),
                    issue_number="5",
                    title=f"legacy flat {code}",
                    cover_price=4.99,
                    release_status="SCHEDULED",
                )
            )
        session.commit()
        before_count = len(
            session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).all()
        )

        import_lunar_csv_bytes(
            session,
            owner_user_id=owner_id,
            file_name="zatanna.csv",
            content_bytes=MULTI_VARIANT_CSV.encode("utf-8"),
        )
        issues = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).all()
        variants = session.exec(
            select(ReleaseVariant)
            .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
            .where(ReleaseIssue.owner_user_id == owner_id)
        ).all()
        canonical_uuid = build_issue_release_uuid(
            publisher="DC Comics",
            series_name="ZATANNA (2026)",
            issue_number="5",
        )

    assert len(issues) == before_count
    assert len(variants) == 3
    assert sum(1 for row in issues if row.release_uuid == canonical_uuid) == 1
    assert sum(1 for row in issues if is_legacy_flat_lunar_issue_uuid(row.release_uuid)) >= 1
