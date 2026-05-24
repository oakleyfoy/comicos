from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CanonicalCreator, MetadataAlias
from app.schemas.ai import ParseOrderResponse
from app.services.canonical_creators import compute_creator_key, get_or_create_canonical_creator
from app.services.metadata_enrichment import enrich_parse_order_metadata, normalize_creator_name


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_manual_import_payload() -> dict:
    return {
        "raw_text": "creator-rich import",
        "retailer": "Midtown",
        "order_date": "2026-05-21",
        "source_type": "manual_draft",
        "shipping_amount": "0.00",
        "tax_amount": "0.00",
        "items": [
            {
                "publisher": "Marvel",
                "title": "Amazing Spider-Man",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "writers": ["Tom King"],
                "artists": ["Daniel Sampere"],
                "cover_artists": ["J. Scott Campbell", "J Scott Campbell"],
                "quantity": 1,
                "raw_item_price": "4.99",
            }
        ],
        "warnings": [],
        "confidence_score": 1.0,
    }


def test_creator_name_normalization_is_deterministic() -> None:
    first = normalize_creator_name(" J. Scott Campbell ")
    second = normalize_creator_name("J Scott Campbell")
    apostrophe = normalize_creator_name("  dONny  cates ")

    assert first.normalized_value == second.normalized_value == "j scott campbell"
    assert first.canonical_value == "J Scott Campbell"
    assert second.canonical_value == "J Scott Campbell"
    assert apostrophe.canonical_value == "Donny Cates"


def test_creator_aliases_apply_deterministically(
    client: TestClient,
    session: Session,
) -> None:
    del client
    session.add(
        MetadataAlias(
            alias_value="Joshua Cassara",
            canonical_value="Josh Cassara",
            alias_type="creator",
            source="manual",
            is_active=True,
        )
    )
    session.commit()

    normalized = normalize_creator_name("Joshua Cassara", session=session)

    assert normalized.canonical_value == "Josh Cassara"
    assert normalized.normalized_value == "josh cassara"
    assert normalized.decision == "database_alias"


def test_same_normalized_name_resolves_same_canonical_creator(
    client: TestClient,
    session: Session,
) -> None:
    del client
    first = normalize_creator_name("J. Scott Campbell")
    second = normalize_creator_name("J Scott Campbell")

    creator_a = get_or_create_canonical_creator(
        session,
        canonical_name=first.canonical_value or "",
        normalized_name=first.normalized_value or "",
    )
    creator_b = get_or_create_canonical_creator(
        session,
        canonical_name=second.canonical_value or "",
        normalized_name=second.normalized_value or "",
    )

    assert creator_a.id == creator_b.id
    assert creator_a.creator_key == compute_creator_key("j scott campbell")


def test_malformed_creator_strings_are_preserved_and_flagged() -> None:
    parsed = ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "DC",
                    "title": "Wonder Woman",
                    "issue_number": "1",
                    "writers": "Tom King / Daniel Sampere",
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        }
    )

    enriched = enrich_parse_order_metadata(parsed, raw_text="creator malformed")
    item = enriched.items[0]

    assert item.raw_writers == ["Tom King / Daniel Sampere"]
    assert item.writers == ["Tom King / Daniel Sampere"]
    assert item.metadata_review_required is True
    assert (
        "Writer list format was malformed or unsupported. Review preserved creator values."
        in item.metadata_review_notes
    )


def test_creator_metadata_does_not_change_metadata_identity_key() -> None:
    base = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "manual_draft",
                "shipping_amount": "0.00",
                "tax_amount": "0.00",
                "items": [
                    {
                        "publisher": "Marvel",
                        "title": "Amazing Spider-Man",
                        "issue_number": "1",
                        "cover_name": "Cover A",
                        "quantity": 1,
                        "raw_item_price": "4.99",
                    }
                ],
                "warnings": [],
                "confidence_score": 1.0,
            }
        ),
        raw_text="base",
    )
    with_creators = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "manual_draft",
                "shipping_amount": "0.00",
                "tax_amount": "0.00",
                "items": [
                    {
                        "publisher": "Marvel",
                        "title": "Amazing Spider-Man",
                        "issue_number": "1",
                        "cover_name": "Cover A",
                        "writers": ["Tom King"],
                        "artists": ["Daniel Sampere"],
                        "cover_artists": ["J. Scott Campbell"],
                        "quantity": 1,
                        "raw_item_price": "4.99",
                    }
                ],
                "warnings": [],
                "confidence_score": 1.0,
            }
        ),
        raw_text="with creators",
    )

    assert base.items[0].metadata_identity_key == with_creators.items[0].metadata_identity_key


def test_confirm_import_persists_canonical_creators_and_ops_registry_filters(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-creators@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-creators@example.com")

    created = client.post(
        "/imports/manual",
        json=build_manual_import_payload(),
        headers=auth_headers(token),
    )
    assert created.status_code == 201

    confirm = client.post(
        f"/imports/{created.json()['id']}/confirm",
        headers=auth_headers(token),
    )
    assert confirm.status_code == 200

    registry = client.get(
        "/ops/canonical-creators",
        headers=auth_headers(token),
        params={"name": "campbell"},
    )
    assert registry.status_code == 200
    rows = registry.json()
    assert len(rows) == 1
    assert rows[0]["canonical_name"] == "J Scott Campbell"
    assert rows[0]["normalized_name"] == "j scott campbell"
    assert rows[0]["creator_key"] == "creator:j scott campbell"


def test_ops_canonical_creators_combine_broad_search_with_specific_fields(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-creator-filters@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-creator-filters@example.com")

    created = client.post(
        "/imports/manual",
        json=build_manual_import_payload(),
        headers=auth_headers(token),
    )
    assert created.status_code == 201
    assert (
        client.post(
            f"/imports/{created.json()['id']}/confirm",
            headers=auth_headers(token),
        ).status_code
        == 200
    )

    narrowed = client.get(
        "/ops/canonical-creators",
        headers=auth_headers(token),
        params={"name": "samp", "canonical_name": "Daniel"},
    )
    assert narrowed.status_code == 200
    names = [row["canonical_name"] for row in narrowed.json()]
    assert names == ["Daniel Sampere"]

    conflicting = client.get(
        "/ops/canonical-creators",
        headers=auth_headers(token),
        params={"name": "king", "normalized_name": "sampere"},
    )
    assert conflicting.status_code == 200
    assert conflicting.json() == []

    normalized_only = client.get(
        "/ops/canonical-creators",
        headers=auth_headers(token),
        params={"normalized_name": "j scott"},
    )
    assert normalized_only.status_code == 200
    assert [row["normalized_name"] for row in normalized_only.json()] == ["j scott campbell"]

    creator_key_partial = client.get(
        "/ops/canonical-creators",
        headers=auth_headers(token),
        params={"creator_key": "creator:j"},
    )
    assert creator_key_partial.status_code == 200
    assert len(creator_key_partial.json()) >= 1
    assert any(row["canonical_name"] == "J Scott Campbell" for row in creator_key_partial.json())


def test_manual_import_detail_exposes_creator_metadata_for_review_tools(
    client: TestClient,
) -> None:
    token = register_and_login(client, "creator-review-payload@example.com")

    created = client.post(
        "/imports/manual",
        json={
            "raw_text": "creator malformed writers",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "DC",
                    "title": "Wonder Woman",
                    "issue_number": "1",
                    "writers": "Tom King / Daniel Sampere",
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )
    assert created.status_code == 201

    detail = client.get(f"/imports/{created.json()['id']}", headers=auth_headers(token))
    assert detail.status_code == 200
    payload_item = detail.json()["parsed_payload_json"]["items"][0]
    assert payload_item["raw_writers"] == ["Tom King / Daniel Sampere"]
    assert payload_item["writers"] == ["Tom King / Daniel Sampere"]
    assert payload_item["metadata_review_required"] is True
    assert any(
        "Writer list format was malformed" in note
        for note in payload_item["metadata_review_notes"]
    )


def test_draft_enrichment_creates_unique_canonical_creators(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "draft-creators@example.com")

    response = client.post(
        "/imports/manual",
        json=build_manual_import_payload(),
        headers=auth_headers(token),
    )
    assert response.status_code == 201

    creators = session.exec(
        select(CanonicalCreator).order_by(CanonicalCreator.canonical_name.asc())
    ).all()
    assert [creator.canonical_name for creator in creators] == [
        "Daniel Sampere",
        "J Scott Campbell",
        "Tom King",
    ]
