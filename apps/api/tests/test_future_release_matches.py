from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.future_release_match import FutureReleaseMatch
from app.models.release_intelligence import ReleaseIssue
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.future_release_match_engine import generate_future_release_matches
from app.services.future_release_matches import persist_future_release_matches
from app.services.lunar_variant_classifier import classify_lunar_variant
from app.services.lunar_variant_identity import build_issue_release_uuid, build_variant_uuid
from app.services.release_import import import_release_feed
from test_inventory import auth_headers, create_order, register_and_login


def _owner_id(session: Session, email: str) -> int:
    return int(session.exec(select(User).where(User.email == email)).one().id or 0)


def _battle_beast_items(numbers: list[str]) -> list[dict]:
    return [
        {
            "title": "Battle Beast",
            "publisher": "Image",
            "issue_number": num,
            "cover_name": "Cover A",
            "printing": None,
            "ratio": None,
            "variant_type": None,
            "cover_artist": None,
            "quantity": 1,
            "raw_item_price": 5.00,
        }
        for num in numbers
    ]


def _import_future_lunar_issue(
    session: Session,
    *,
    owner_user_id: int,
    issue_number: str,
    foc_date: date,
    release_date: date,
    variant_count: int = 2,
) -> int:
    classification = classify_lunar_variant(title="Battle Beast", variant_desc="Cover A")
    variants = []
    for idx in range(variant_count):
        variants.append(
            {
                "variant_uuid": build_variant_uuid(
                    source_item_code=f"BB-{issue_number}-{idx}",
                    classification=classification,
                ),
                "variant_name": f"Cover {chr(65 + idx)}",
                "variant_type": "standard",
                "source_item_code": f"BB-{issue_number}-{idx}",
            }
        )
    payload = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": "Image",
                    "series_name": "Battle Beast",
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": [
                        {
                            "release_uuid": build_issue_release_uuid(
                                publisher="Image",
                                series_name="Battle Beast",
                                issue_number=issue_number,
                            ),
                            "issue_number": issue_number,
                            "title": f"Battle Beast #{issue_number}",
                            "foc_date": str(foc_date),
                            "release_date": str(release_date),
                            "release_status": "SCHEDULED",
                            "variants": variants,
                        }
                    ],
                }
            ]
        }
    )
    import_release_feed(session, owner_user_id=owner_user_id, payload=payload)
    release_uuid = build_issue_release_uuid(
        publisher="Image",
        series_name="Battle Beast",
        issue_number=issue_number,
    )
    issue = session.exec(
        select(ReleaseIssue)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_uuid == release_uuid)
    ).one()
    return int(issue.id or 0)


def test_future_release_matching(client: TestClient, session: Session) -> None:
    email = "frm-match@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items([str(n) for n in range(1, 16)]))
    today = date.today()
    _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="16",
        foc_date=today + timedelta(days=7),
        release_date=today + timedelta(days=21),
        variant_count=3,
    )

    matches = generate_future_release_matches(session, owner_user_id=owner_id)
    assert len(matches) == 1
    match = matches[0]
    assert match.series_name == "Battle Beast"
    assert match.issue_number == "16"
    assert match.variant_count == 3
    assert match.confidence == 1.0


def test_release_date_and_foc_retrieval(client: TestClient, session: Session) -> None:
    email = "frm-dates@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["14", "15"]))
    foc = date.today() + timedelta(days=5)
    ship = date.today() + timedelta(days=19)
    release_id = _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="16",
        foc_date=foc,
        release_date=ship,
    )

    persist_future_release_matches(session, owner_user_id=owner_id)
    row = session.exec(select(FutureReleaseMatch).where(FutureReleaseMatch.owner_user_id == owner_id)).one()
    assert row.foc_date == foc
    assert row.release_date == ship
    assert row.release_id == release_id

    issue = session.exec(select(ReleaseIssue).where(ReleaseIssue.id == release_id)).one()
    assert issue.foc_date == foc
    assert issue.release_date == ship

    api = client.get("/api/v1/future-release-matches/latest", headers=auth_headers(token))
    assert api.status_code == 200
    item = api.json()["data"]["items"][0]
    assert item["foc_date"] == foc.isoformat()
    assert item["release_date"] == ship.isoformat()


def test_past_releases_excluded(client: TestClient, session: Session) -> None:
    email = "frm-past@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2"]))
    today = date.today()
    _import_future_lunar_issue(
        session,
        owner_user_id=owner_id,
        issue_number="3",
        foc_date=today - timedelta(days=30),
        release_date=today - timedelta(days=7),
    )
    matches = generate_future_release_matches(session, owner_user_id=owner_id)
    assert matches == []
