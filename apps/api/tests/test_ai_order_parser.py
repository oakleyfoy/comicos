import json
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import Settings
from app.models import InventoryCopy, Order
from app.schemas.ai import ParseOrderResponse
from app.services.ai_order_parser import parse_order_draft_from_text


def register_and_login(client: TestClient, email: str = "ai@example.com") -> str:
    client.post(
        "/auth/register",
        json={"email": email, "password": "supersecret123"},
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "supersecret123"},
    )
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_mock_draft() -> ParseOrderResponse:
    return ParseOrderResponse.model_validate(
        {
            "retailer": "Whatnot",
            "order_date": "2026-05-21",
            "source_type": "ai_draft",
            "shipping_amount": Decimal("4.99"),
            "tax_amount": Decimal("1.50"),
            "items": [
                {
                    "publisher": "Image",
                    "title": "Invincible",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": "1:25",
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("7.65"),
                }
            ],
            "warnings": [],
            "confidence_score": 0.92,
        }
    )


class FakeUrlOpenResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_parse_order_unauthorized_request_fails(client: TestClient) -> None:
    response = client.post("/ai/parse-order", json={"raw_text": "Whatnot order receipt"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


def test_parse_order_empty_raw_text_rejected(client: TestClient) -> None:
    token = register_and_login(client)

    response = client.post(
        "/ai/parse-order",
        json={"raw_text": "   "},
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_parse_order_missing_api_key_returns_503(client: TestClient) -> None:
    token = register_and_login(client)

    response = client.post(
        "/ai/parse-order",
        json={"raw_text": "Whatnot order receipt"},
        headers=auth_headers(token),
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "AI parser is not configured."}


def test_parse_order_returns_structured_response(
    client: TestClient,
    monkeypatch,
) -> None:
    token = register_and_login(client)

    monkeypatch.setattr("app.main.parse_order_draft_from_text", lambda raw_text: build_mock_draft())

    response = client.post(
        "/ai/parse-order",
        json={"raw_text": "Whatnot receipt text"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["retailer"] == "Whatnot"
    assert data["source_type"] == "ai_draft"
    assert data["shipping_amount"] == "4.99"
    assert data["tax_amount"] == "1.50"
    assert data["items"][0]["publisher"] == "Image"
    assert data["warnings"] == []
    assert data["confidence_score"] == 0.92


def test_parser_warnings_included_for_uncertain_fields(monkeypatch) -> None:
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "retailer": None,
                            "order_date": "2026-05-21",
                            "source_type": "ai_draft",
                            "shipping_amount": 0,
                            "tax_amount": 0,
                            "items": [
                                {
                                    "publisher": "Marvel",
                                    "title": "Ultimate Spider-Man",
                                    "issue_number": None,
                                    "cover_name": None,
                                    "printing": None,
                                    "ratio": None,
                                    "variant_type": None,
                                    "cover_artist": None,
                                    "quantity": None,
                                    "raw_item_price": None,
                                }
                            ],
                            "warnings": [],
                            "confidence_score": 0.99,
                        }
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(
        "app.services.ai_order_parser.request.urlopen",
        lambda _request, timeout=60: FakeUrlOpenResponse(response_payload),
    )

    draft = parse_order_draft_from_text(
        "uncertain whatnot paste",
        settings=Settings(openai_api_key="test-key", openai_order_parser_model="gpt-4o-mini"),
    )

    assert draft.retailer is None
    assert draft.items[0].raw_item_price is None
    assert draft.items[0].quantity is None
    assert draft.confidence_score == 0.28
    assert "Retailer uncertain or missing. Review before confirming the draft." in draft.warnings
    assert (
        "Item 1 price is missing or uncertain. Review the raw item price before confirming."
        in draft.warnings
    )
    assert "Item 1 quantity is uncertain. Review the quantity before confirming." in draft.warnings
    assert (
        "Item 1 issue number is uncertain or missing. Review before confirming."
        in draft.warnings
    )
    assert (
        "Item 1 variant or cover details are uncertain. Review cover, printing, and variant fields."
        in draft.warnings
    )


def test_parser_response_always_validates_against_schema(monkeypatch) -> None:
    response_payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "retailer": "Whatnot",
                            "order_date": "2026-05-21",
                            "source_type": "ai_draft",
                            "shipping_amount": 4.99,
                            "tax_amount": 1.5,
                            "items": [
                                {
                                    "publisher": "Image",
                                    "title": "Invincible",
                                    "issue_number": "1",
                                    "cover_name": "Cover A",
                                    "printing": None,
                                    "ratio": "1:25",
                                    "variant_type": None,
                                    "cover_artist": None,
                                    "quantity": 1,
                                    "raw_item_price": 7.65,
                                }
                            ],
                            "warnings": [],
                            "confidence_score": 0.1,
                        }
                    )
                }
            }
        ]
    }
    monkeypatch.setattr(
        "app.services.ai_order_parser.request.urlopen",
        lambda _request, timeout=60: FakeUrlOpenResponse(response_payload),
    )

    draft = parse_order_draft_from_text(
        "whatnot receipt",
        settings=Settings(openai_api_key="test-key", openai_order_parser_model="gpt-4o-mini"),
    )

    validated = ParseOrderResponse.model_validate(draft.model_dump())
    assert validated.source_type == "ai_draft"
    assert validated.confidence_score == 0.92


def test_parse_order_does_not_write_to_database(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client)

    monkeypatch.setattr("app.main.parse_order_draft_from_text", lambda raw_text: build_mock_draft())

    response = client.post(
        "/ai/parse-order",
        json={"raw_text": "eBay invoice text"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert len(session.exec(select(Order)).all()) == 0
    assert len(session.exec(select(InventoryCopy)).all()) == 0
