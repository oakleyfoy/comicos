from __future__ import annotations

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseKeySignal
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.release_import import import_release_feed
from app.services.variant_intelligence_agent import detect_variant_signals
from test_inventory import register_and_login


def test_variant_intelligence_agent_detects_ratio_and_incentive_signals(client) -> None:
    from app.db.session import get_engine
    from app.models import User

    email = "release-variant@example.com"
    register_and_login(client, email)
    feed = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "Boom!",
                    "series_name": "Variant Storm",
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": "variant-storm-1",
                            "issue_number": "1",
                            "title": "Variant Storm #1",
                            "release_status": "SCHEDULED",
                            "variants": [
                                {"variant_name": "Open Order A", "variant_type": "OPEN_ORDER"},
                                {"variant_name": "1:50 Incentive", "variant_type": "INCENTIVE", "ratio_value": 50},
                            ],
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

        signals, execution = detect_variant_signals(session, owner_user_id=owner_user_id)
        signal_types = {signal.signal_type for signal in signals}
        assert execution.status == "COMPLETED"
        assert "OPEN_ORDER_VARIANT" in signal_types
        assert "VARIANT_RATIO" in signal_types
        assert "INCENTIVE_VARIANT" in signal_types
        assert "HIGH_RATIO_VARIANT" in signal_types
        assert len(session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.owner_user_id == owner_user_id)).all()) >= 4
