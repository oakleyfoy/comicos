from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.release_import import import_release_feed
from test_inventory import register_and_login


def _sample_feed() -> ReleaseImportFeedRequest:
    return ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "Marvel",
                    "series_name": "Amazing Future",
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": "rel-amazing-future-1",
                            "issue_number": "1",
                            "title": "Amazing Future #1",
                            "foc_date": "2026-06-10",
                            "release_date": "2026-06-24",
                            "cover_price": 4.99,
                            "release_status": "SCHEDULED",
                            "variants": [
                                {
                                    "variant_name": "Open Order",
                                    "variant_type": "OPEN_ORDER",
                                },
                                {
                                    "variant_name": "1:25 Incentive",
                                    "variant_type": "INCENTIVE",
                                    "ratio_value": 25,
                                },
                            ],
                        }
                    ],
                }
            ]
        }
    )


def test_release_import_is_deterministic_and_append_safe(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "release-import@example.com"
    register_and_login(client, email)
    with Session(get_engine()) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        owner_user_id = int(owner.id or 0)

        result = import_release_feed(session, owner_user_id=owner_user_id, payload=_sample_feed())
        assert result.series_created == 1
        assert result.issues_created == 1
        assert result.variants_created == 2

        duplicate = import_release_feed(session, owner_user_id=owner_user_id, payload=_sample_feed())
        assert duplicate.series_created == 0
        assert duplicate.issues_created == 0
        assert duplicate.variants_created == 0

        assert len(session.exec(select(ReleaseSeries).where(ReleaseSeries.owner_user_id == owner_user_id)).all()) == 1
        assert len(session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()) == 1
        assert len(session.exec(select(ReleaseVariant)).all()) == 2
