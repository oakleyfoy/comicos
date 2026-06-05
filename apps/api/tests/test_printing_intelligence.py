from __future__ import annotations

from datetime import date

from app.models.release_intelligence import ReleaseIssue, ReleaseVariant
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.lunar_release_normalizer import normalize_lunar_rows
from app.services.lunar_variant_identity import build_issue_release_uuid
from app.services.printing_intelligence import (
    PRINTING_KIND_ANNIVERSARY,
    PRINTING_KIND_FACSIMILE,
    PRINTING_KIND_FIRST,
    PRINTING_KIND_REPRINT,
    merge_first_print_issue_dates,
    parse_printing_profile,
    resolve_printing_schedule,
)
from app.services.printing_backfill import build_proposal, classify_confidence, load_lunar_reprint_index, run_backfill
from app.services.release_import import import_release_feed
from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from test_inventory import register_and_login


def test_parse_fourth_printing_ptg() -> None:
    profile = parse_printing_profile(title="TIGRESS ISLAND #1 (OF 5) 4TH PTG (MR)", lunar_printing_field="4")
    assert profile.printing_kind == PRINTING_KIND_REPRINT
    assert profile.printing_number == 4
    assert profile.is_reprint_line is True
    assert profile.badge_label == "4th Printing"


def test_parse_facsimile_and_anniversary() -> None:
    fac = parse_printing_profile(title="Amazing Spider-Man #1 Facsimile Edition")
    assert fac.printing_kind == PRINTING_KIND_FACSIMILE
    ann = parse_printing_profile(title="X-Men #1 60th Anniversary Edition")
    assert ann.printing_kind == PRINTING_KIND_ANNIVERSARY


def test_merge_first_print_preserves_earlier_release() -> None:
    issue = ReleaseIssue(
        owner_user_id=1,
        release_uuid="test",
        series_id=1,
        issue_number="1",
        title="T",
        foc_date=date(2026, 3, 1),
        release_date=date(2026, 3, 11),
        original_foc_date=date(2026, 3, 1),
        original_release_date=date(2026, 3, 11),
        cover_price=3.99,
        release_status="SCHEDULED",
    )
    merge_first_print_issue_dates(issue, foc_date=date(2026, 5, 25), release_date=date(2026, 6, 17))
    assert issue.release_date == date(2026, 3, 11)
    assert issue.original_release_date == date(2026, 3, 11)


def test_lunar_normalizer_splits_reprint_dates() -> None:
    rows = [
        {
            "Publisher": "Image Comics",
            "MainDesc": "Tigress Island",
            "Title": "TIGRESS ISLAND #1 (OF 5) 4TH PTG (MR)",
            "IssueNumber": "1",
            "Code": "0426IM8399",
            "Printing": "4",
            "FOCDate": "5/25/2026",
            "InStoreDate": "6/17/2026",
            "Retail": "3.99",
            "UPC": "70985304589200114",
        }
    ]
    feed, errors = normalize_lunar_rows(rows)
    assert not errors
    issue = feed.series[0].issues[0]
    assert issue.foc_date is None
    assert issue.release_date is None
    variant = issue.variants[0]
    assert variant.printing_kind == PRINTING_KIND_REPRINT
    assert variant.printing_number == 4
    assert variant.printing_foc_date == date(2026, 5, 25)
    assert variant.printing_release_date == date(2026, 6, 17)


def test_reprint_import_does_not_overwrite_first_print_dates(client) -> None:
    email = "printing-intel@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_id = int(owner.id or 0)
        first = ReleaseImportFeedRequest.model_validate(
            {
                "series": [
                    {
                        "publisher": "Image Comics",
                        "series_name": "Tigress Island",
                        "series_type": "ONGOING",
                        "status": "ACTIVE",
                        "issues": [
                            {
                                "release_uuid": "ti-1",
                                "issue_number": "1",
                                "title": "Tigress Island #1",
                                "foc_date": "2026-02-01",
                                "release_date": "2026-03-11",
                                "cover_price": 3.99,
                                "release_status": "SCHEDULED",
                                "variants": [
                                    {
                                        "variant_name": "Standard Cover",
                                        "variant_type": "OPEN_ORDER",
                                        "printing_kind": "FIRST_PRINT",
                                        "printing_number": 1,
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        )
        import_release_feed(session, owner_user_id=owner_id, payload=first)
        issue = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_id)).one()
        assert issue.release_date == date(2026, 3, 11)

        lunar_uuid = build_issue_release_uuid(
            publisher="Image Comics",
            series_name="Tigress Island",
            issue_number="1",
        )
        reprint = ReleaseImportFeedRequest.model_validate(
            {
                "series": [
                    {
                        "publisher": "Image Comics",
                        "series_name": "Tigress Island",
                        "series_type": "ONGOING",
                        "status": "ACTIVE",
                        "issues": [
                            {
                                "release_uuid": lunar_uuid,
                                "issue_number": "1",
                                "title": "Tigress Island #1",
                                "foc_date": None,
                                "release_date": None,
                                "cover_price": 3.99,
                                "release_status": "SCHEDULED",
                                "variants": [
                                    {
                                        "variant_name": "Standard Cover",
                                        "variant_type": "OPEN_ORDER",
                                        "source_item_code": "0426IM8399",
                                        "printing_kind": "REPRINT",
                                        "printing_number": 4,
                                        "printing_foc_date": "2026-05-25",
                                        "printing_release_date": "2026-06-17",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        )
        import_release_feed(session, owner_user_id=owner_id, payload=reprint)
        session.refresh(issue)
        assert issue.release_date == date(2026, 3, 11)
        assert issue.original_release_date == date(2026, 3, 11)

        variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == issue.id)).all()
        ctx = resolve_printing_schedule(issue, list(variants))
        assert ctx.printing_badge == "4th Printing"
        assert ctx.printing_release_date == date(2026, 6, 17)
        assert ctx.original_release_date == date(2026, 3, 11)


def test_tigress_backfill_high_confidence(client) -> None:
    from app.db.session import get_engine
    from app.models import User
    from app.models.lunar_feed import LunarFeedRawRow

    email = "printing-backfill-tigress@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_id = int(owner.id or 0)
        polluted = ReleaseImportFeedRequest.model_validate(
            {
                "series": [
                    {
                        "publisher": "Image Comics",
                        "series_name": "Tigress Island",
                        "series_type": "ONGOING",
                        "status": "ACTIVE",
                        "issues": [
                            {
                                "release_uuid": "ti-polluted-1",
                                "issue_number": "1",
                                "title": "Tigress Island #1",
                                "foc_date": "2026-05-25",
                                "release_date": "2026-06-17",
                                "cover_price": 3.99,
                                "release_status": "SCHEDULED",
                                "variants": [
                                    {
                                        "variant_name": "Standard Cover",
                                        "variant_type": "OPEN_ORDER",
                                        "source_item_code": "0426IM8399",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            }
        )
        import_release_feed(session, owner_user_id=owner_id, payload=polluted)
        session.add(
            LunarFeedRawRow(
                feed_run_id=1,
                row_index=1,
                product_code="0426IM8399",
                row_payload_json={
                    "Code": "0426IM8399",
                    "Title": "TIGRESS ISLAND #1 (OF 5) 4TH PTG (MR)",
                    "Printing": "4",
                    "FOCDate": "5/25/2026",
                    "InStoreDate": "6/17/2026",
                },
            )
        )
        session.commit()

        report = run_backfill(session, owner_user_id=owner_id, apply=False)
        tigress = report.get("tigress_island_1")
        assert tigress is not None
        assert tigress["confidence"] == "HIGH"
        assert tigress["known_first_print_release"] == "2026-03-11"
        assert tigress["proposed_ui_badge_after_backfill"] == "4th Printing"
