from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from app.models.next_issue import NextIssue
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.lunar_variant_identity import build_issue_release_uuid
from app.services.next_issue_engine import CONFIDENCE_EXACT, CONFIDENCE_STRONG, generate_next_issues
from app.services.next_issues import persist_next_issues
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


def _import_lunar_catalog(
    session: Session,
    *,
    owner_user_id: int,
    publisher: str,
    series_name: str,
    issue_numbers: list[str],
    catalog_publisher: str | None = None,
    catalog_series: str | None = None,
) -> None:
    pub = catalog_publisher or publisher
    series = catalog_series or series_name
    today = date.today()
    issues = []
    for num in issue_numbers:
        issues.append(
            {
                "release_uuid": build_issue_release_uuid(
                    publisher=pub,
                    series_name=series,
                    issue_number=num,
                ),
                "issue_number": num,
                "title": f"{series} #{num}",
                "release_date": str(today + timedelta(days=14)),
                "release_status": "SCHEDULED",
            }
        )
    payload = ReleaseImportFeedRequest.model_validate(
        {
            "series": [
                {
                    "publisher": pub,
                    "series_name": series,
                    "series_type": "ONGOING",
                    "status": "ACTIVE",
                    "issues": issues,
                }
            ]
        }
    )
    import_release_feed(session, owner_user_id=owner_user_id, payload=payload)


def test_exact_next_issue_detection(client: TestClient, session: Session) -> None:
    email = "ni-exact@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items([str(n) for n in range(1, 16)]))
    _import_lunar_catalog(session, owner_user_id=owner_id, publisher="Image", series_name="Battle Beast", issue_numbers=["16"])

    predictions = generate_next_issues(session, owner_user_id=owner_id)
    assert len(predictions) == 1
    row = predictions[0]
    assert row.series_name == "Battle Beast"
    assert row.current_issue == "15"
    assert row.next_issue == "16"
    assert row.confidence == CONFIDENCE_EXACT


def test_confidence_strong_match(client: TestClient, session: Session) -> None:
    email = "ni-strong@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["1", "2", "3"]))
    _import_lunar_catalog(
        session,
        owner_user_id=owner_id,
        publisher="Image",
        series_name="Battle Beast",
        issue_numbers=["4"],
        catalog_publisher="IMAGE COMICS",
        catalog_series="Battle Beast",
    )

    predictions = generate_next_issues(session, owner_user_id=owner_id)
    assert len(predictions) == 1
    assert predictions[0].next_issue == "4"
    assert predictions[0].confidence == CONFIDENCE_STRONG


def test_owner_isolation(client: TestClient, session: Session) -> None:
    token_a = register_and_login(client, "ni-a@example.com")
    token_b = register_and_login(client, "ni-b@example.com")
    owner_a = _owner_id(session, "ni-a@example.com")
    create_order(client, token_a, items=_battle_beast_items(["1", "2", "3"]))
    _import_lunar_catalog(session, owner_user_id=owner_a, publisher="Image", series_name="Battle Beast", issue_numbers=["4"])
    client.get("/api/v1/next-issues/latest", headers=auth_headers(token_a))
    b_list = client.get("/api/v1/next-issues", headers=auth_headers(token_b))
    assert b_list.status_code == 200
    assert b_list.json()["data"]["items"] == []


def test_persist_and_api(client: TestClient, session: Session) -> None:
    email = "ni-api@example.com"
    token = register_and_login(client, email)
    owner_id = _owner_id(session, email)
    create_order(client, token, items=_battle_beast_items(["14", "15"]))
    _import_lunar_catalog(session, owner_user_id=owner_id, publisher="Image", series_name="Battle Beast", issue_numbers=["16"])
    assert persist_next_issues(session, owner_user_id=owner_id) == 1
    assert persist_next_issues(session, owner_user_id=owner_id) == 0

    latest = client.get("/api/v1/next-issues/latest", headers=auth_headers(token))
    assert latest.status_code == 200
    item = latest.json()["data"]["items"][0]
    assert item["next_issue"] == "16"
    assert item["confidence"] == 1.0

    rows = session.exec(select(NextIssue).where(NextIssue.owner_user_id == owner_id)).all()
    assert len(rows) == 1
