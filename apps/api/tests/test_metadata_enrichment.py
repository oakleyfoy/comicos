from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import InventoryCopy, Publisher
from app.schemas.ai import ParseOrderResponse
from app.services.metadata_enrichment import (
    build_metadata_identity_components,
    build_metadata_identity_key,
    enrich_parse_order_metadata,
    normalize_issue_number,
    normalize_publisher_name,
    normalize_series_title,
    normalize_variant_text,
    parse_release_date,
)


def register_and_login(client: TestClient, email: str = "metadata@example.com") -> str:
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


def test_normalization_helpers_are_deterministic() -> None:
    first_pass = (
        normalize_publisher_name("Marvel Comics"),
        normalize_series_title("   ultimate spider-man   "),
        normalize_issue_number(" #001a "),
        normalize_variant_text("  foil  edition / cover a "),
    )
    second_pass = (
        normalize_publisher_name("Marvel Comics"),
        normalize_series_title("   ultimate spider-man   "),
        normalize_issue_number(" #001a "),
        normalize_variant_text("  foil  edition / cover a "),
    )

    assert first_pass == second_pass
    assert first_pass[0].canonical_value == "Marvel"
    assert first_pass[1].canonical_value == "Ultimate Spider-Man"
    assert first_pass[2].canonical_value == "1A"
    assert first_pass[3].canonical_value == "Foil Edition / Cover A"


def test_metadata_identity_key_is_deterministic_for_same_components() -> None:
    first = build_metadata_identity_key(
        build_metadata_identity_components(
            publisher="Marvel",
            series_title="Amazing Spider-Man",
            issue_number="1",
            variant="Cover A",
        )
    )
    second = build_metadata_identity_key(
        build_metadata_identity_components(
            publisher="Marvel",
            series_title="Amazing Spider-Man",
            issue_number="1",
            variant="Cover A",
        )
    )

    assert first == second == "Marvel|Amazing Spider-Man|1|Cover A"


def test_metadata_identity_key_preserves_empty_variant_component() -> None:
    key = build_metadata_identity_key(
        build_metadata_identity_components(
            publisher="Marvel",
            series_title="Amazing Spider-Man",
            issue_number="1",
            variant=None,
        )
    )

    assert key == "Marvel|Amazing Spider-Man|1|"


def test_issue_number_normalization_handles_common_formats_deterministically() -> None:
    examples = {
        "#1": "1",
        "001": "1",
        "No. 1": "1",
        "Issue 1": "1",
        "1A": "1A",
        "1 B": "1B",
        "001.CVRA": "1CVRA",
    }

    for raw_value, expected in examples.items():
        first = normalize_issue_number(raw_value)
        second = normalize_issue_number(raw_value)
        assert first == second
        assert first.canonical_value == expected
        assert first.review_required is False


def test_issue_number_preserves_special_identifiers() -> None:
    examples = {
        "Annual 1": "Annual 1",
        "Annual 001": "Annual 1",
        "Omega": "Omega",
        "Alpha": "Alpha",
        "TPB": "TPB",
        "HC": "HC",
    }

    for raw_value, expected in examples.items():
        normalized = normalize_issue_number(raw_value)
        assert normalized.canonical_value == expected
        assert normalized.review_required is False


def test_issue_number_low_confidence_formats_are_flagged() -> None:
    normalized = normalize_issue_number("Issue #1")
    assert normalized.canonical_value == "1"
    assert normalized.review_required is True
    assert (
        normalized.note
        == "Issue number included multiple formatting markers. Review canonical issue value."
    )

    preserved = normalize_issue_number("1/2")
    assert preserved.canonical_value == "1/2"
    assert preserved.review_required is True
    assert preserved.note == "Issue number format was low confidence and preserved conservatively."


def test_variant_normalization_handles_common_patterns_deterministically() -> None:
    examples = {
        "Cover A": "Cover A",
        "CVR A": "Cover A",
        "A Cover": "Cover A",
        " virgin variant ": "Virgin Variant",
        "foil  edition / cvr a": "Foil Edition / Cover A",
    }

    for raw_value, expected in examples.items():
        first = normalize_variant_text(raw_value)
        second = normalize_variant_text(raw_value)
        assert first == second
        assert first.canonical_value == expected
        assert first.review_required is False


def test_release_date_parsing_is_deterministic_without_guessing() -> None:
    assert parse_release_date("2024") == parse_release_date("2024")
    assert parse_release_date("2024").parsed_date is None
    assert parse_release_date("2024").parsed_year == 2024
    assert parse_release_date("2024-05").parsed_date is None
    assert parse_release_date("2024-05").parsed_year == 2024
    assert parse_release_date("2024-05-17").parsed_date == date(2024, 5, 17)
    assert parse_release_date("2024-05-17").parsed_year == 2024
    assert parse_release_date("May 2024").parsed_date is None
    assert parse_release_date("May 2024").parsed_year == 2024
    assert parse_release_date("May 17 2024").parsed_date == date(2024, 5, 17)


def test_release_date_malformed_values_are_flagged_for_review() -> None:
    malformed = parse_release_date("05/2024")
    assert malformed.raw_value == "05/2024"
    assert malformed.parsed_date is None
    assert malformed.parsed_year is None
    assert malformed.review_required is True
    assert (
        malformed.note
        == "Release date format was malformed or unsupported. Review preserved release chronology."
    )

    impossible = parse_release_date("2024-02-31")
    assert impossible.parsed_date is None
    assert impossible.parsed_year is None
    assert impossible.review_required is True


def test_malformed_variant_text_is_flagged_for_review() -> None:
    normalized = normalize_variant_text("Cover // ???")
    assert normalized.canonical_value == "Cover / ???"
    assert normalized.review_required is True
    assert (
        normalized.note
        == "Variant description appears malformed or ambiguous. Review canonical variant value."
    )


def test_variant_normalization_preserves_wonder_man_cover_phrase() -> None:
    raw = (
        "Cover B / Variant / Stefano Caselli First Appearance A Wonder Man Cover"
    )
    normalized = normalize_variant_text(raw)
    assert "Wonder Man Cover" in normalized.canonical_value
    assert "Wonder Cover Man" not in normalized.canonical_value
    assert normalized.review_required is False


def test_variant_slash_variant_segment_is_structural_not_malformed() -> None:
    normalized = normalize_variant_text("Cover B / Variant / Artist Name")
    assert normalized.canonical_value == "Cover B / Variant / Artist Name"
    assert normalized.review_required is False


def test_enrichment_normalizes_known_aliases_and_preserves_raw_values() -> None:
    parsed = ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "gmail_draft",
            "shipping_amount": Decimal("0.00"),
            "tax_amount": Decimal("0.00"),
            "items": [
                {
                    "publisher": "IDW Publishing",
                    "title": "  teenage mutant ninja turtles  ",
                    "issue_number": "#001",
                    "cover_name": "  cover a  ",
                    "printing": "  first print ",
                    "ratio": None,
                    "variant_type": "  foil edition ",
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                }
            ],
            "warnings": [],
            "confidence_score": 0.92,
        }
    )

    enriched = enrich_parse_order_metadata(parsed, raw_text="IDW Publishing TMNT #001")
    item = enriched.items[0]

    assert item.raw_publisher == "IDW Publishing"
    assert item.publisher == "IDW"
    assert item.canonical_publisher == "IDW"
    assert item.raw_title == "teenage mutant ninja turtles"
    assert item.title == "Teenage Mutant Ninja Turtles"
    assert item.canonical_issue_number == "1"
    assert item.raw_issue_number == "#001"
    assert item.raw_variant_text == "cover a / first print / foil edition"
    assert item.canonical_variant_text == "Cover A / First Print / Foil Edition"
    assert item.metadata_identity_components is not None
    assert item.metadata_identity_components.publisher == "IDW"
    assert item.metadata_identity_components.series_title == "Teenage Mutant Ninja Turtles"
    assert item.metadata_identity_components.issue_number == "1"
    assert item.metadata_identity_components.variant == "Cover A / First Print / Foil Edition"
    assert (
        item.metadata_identity_key
        == "IDW|Teenage Mutant Ninja Turtles|1|Cover A / First Print / Foil Edition"
    )
    assert item.metadata_review_required is False

    enriched_again = enrich_parse_order_metadata(enriched, raw_text="IDW Publishing TMNT #001")
    assert enriched_again.model_dump(mode="json") == enriched.model_dump(mode="json")


def test_enrichment_preserves_unknown_publishers_and_flags_review() -> None:
    parsed = ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "gmail_draft",
            "shipping_amount": Decimal("0.00"),
            "tax_amount": Decimal("0.00"),
            "items": [
                {
                    "publisher": "Indie House",
                    "title": "Babylon Cove",
                    "issue_number": "01",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                }
            ],
            "warnings": [],
            "confidence_score": 0.88,
        }
    )

    enriched = enrich_parse_order_metadata(parsed, raw_text="Indie House Babylon Cove #01")
    item = enriched.items[0]

    assert item.raw_publisher == "Indie House"
    assert item.publisher == "Indie House"
    assert item.metadata_identity_key == "Indie House|Babylon Cove|1|"
    assert item.metadata_review_required is True
    assert item.metadata_review_notes == [
        "Publisher preserved from raw parse. Review canonical publisher if needed."
    ]
    assert enriched.warnings == [
        "Publisher metadata needs review for items: 1 (Babylon Cove #1)."
    ]


def test_enrichment_flags_low_confidence_issue_and_variant_notes() -> None:
    parsed = ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "gmail_draft",
            "shipping_amount": Decimal("0.00"),
            "tax_amount": Decimal("0.00"),
            "items": [
                {
                    "publisher": "Image Comics",
                    "title": "Spawn",
                    "issue_number": "Issue #1",
                    "cover_name": "Cover // ???",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                }
            ],
            "warnings": [],
            "confidence_score": 0.8,
        }
    )

    enriched = enrich_parse_order_metadata(
        parsed,
        raw_text="Image Comics Spawn Issue #1 Cover // ???",
    )
    item = enriched.items[0]

    assert item.canonical_issue_number == "1"
    assert item.canonical_variant_text == "Cover / ???"
    assert item.metadata_review_required is True
    assert item.metadata_review_notes == [
        "Issue number included multiple formatting markers. Review canonical issue value.",
        "Variant description appears malformed or ambiguous. Review canonical variant value.",
    ]


def test_enrichment_preserves_release_date_fields_and_flags_malformed_dates() -> None:
    parsed = ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "gmail_draft",
            "shipping_amount": Decimal("0.00"),
            "tax_amount": Decimal("0.00"),
            "items": [
                {
                    "publisher": "Image Comics",
                    "title": "Saga",
                    "release_date": "2024-05",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                },
                {
                    "publisher": "Image Comics",
                    "title": "Saga",
                    "release_date": "05/2024",
                    "issue_number": "2",
                    "cover_name": "Cover B",
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": Decimal("4.99"),
                },
            ],
            "warnings": [],
            "confidence_score": 0.88,
        }
    )

    enriched = enrich_parse_order_metadata(parsed, raw_text="Saga chronology")
    first = enriched.items[0]
    second = enriched.items[1]

    assert first.raw_release_date == "2024-05"
    assert first.release_date == "2024-05"
    assert first.parsed_release_date is None
    assert first.parsed_release_year == 2024
    assert first.metadata_review_required is False

    assert second.raw_release_date == "05/2024"
    assert second.release_date == "05/2024"
    assert second.parsed_release_date is None
    assert second.parsed_release_year is None
    assert second.metadata_review_required is True
    assert second.metadata_review_notes == [
        "Release date format was malformed or unsupported. Review preserved release chronology."
    ]


def test_release_date_does_not_change_metadata_identity_key() -> None:
    with_date = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "gmail_draft",
                "shipping_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
                "items": [
                    {
                        "publisher": "Marvel",
                        "title": "Amazing Spider-Man",
                        "release_date": "2024-05-17",
                        "issue_number": "1",
                        "cover_name": "Cover A",
                        "printing": None,
                        "ratio": None,
                        "variant_type": None,
                        "cover_artist": None,
                        "quantity": 1,
                        "raw_item_price": Decimal("4.99"),
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            }
        ),
        raw_text="Marvel Amazing Spider-Man 1 Cover A",
    )
    without_date = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "gmail_draft",
                "shipping_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
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
                        "quantity": 1,
                        "raw_item_price": Decimal("4.99"),
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            }
        ),
        raw_text="Marvel Amazing Spider-Man 1 Cover A",
    )

    assert with_date.items[0].metadata_identity_key == without_date.items[0].metadata_identity_key


def test_enrichment_normalizes_spacing_and_case_into_same_identity_key() -> None:
    first = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "gmail_draft",
                "shipping_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
                "items": [
                    {
                        "publisher": "marvel comics",
                        "title": " amazing spider-man ",
                        "issue_number": "No. 001",
                        "cover_name": "cvr a",
                        "printing": None,
                        "ratio": None,
                        "variant_type": None,
                        "cover_artist": None,
                        "quantity": 1,
                        "raw_item_price": Decimal("4.99"),
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            }
        ),
        raw_text="marvel comics amazing spider-man No. 001 cvr a",
    )
    second = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "gmail_draft",
                "shipping_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
                "items": [
                    {
                        "publisher": "Marvel",
                        "title": "Amazing Spider-Man",
                        "issue_number": "#1",
                        "cover_name": "Cover A",
                        "printing": None,
                        "ratio": None,
                        "variant_type": None,
                        "cover_artist": None,
                        "quantity": 1,
                        "raw_item_price": Decimal("4.99"),
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            }
        ),
        raw_text="Marvel Amazing Spider-Man #1 Cover A",
    )

    assert first.items[0].metadata_identity_key == "Marvel|Amazing Spider-Man|1|Cover A"
    assert second.items[0].metadata_identity_key == "Marvel|Amazing Spider-Man|1|Cover A"


def test_variant_differences_produce_different_identity_keys() -> None:
    cover_a = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "gmail_draft",
                "shipping_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
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
                        "quantity": 1,
                        "raw_item_price": Decimal("4.99"),
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            }
        ),
        raw_text="Marvel Amazing Spider-Man 1 Cover A",
    )
    cover_b = enrich_parse_order_metadata(
        ParseOrderResponse.model_validate(
            {
                "retailer": "Midtown",
                "order_date": "2026-05-21",
                "source_type": "gmail_draft",
                "shipping_amount": Decimal("0.00"),
                "tax_amount": Decimal("0.00"),
                "items": [
                    {
                        "publisher": "Marvel",
                        "title": "Amazing Spider-Man",
                        "issue_number": "1",
                        "cover_name": "Cover B",
                        "printing": None,
                        "ratio": None,
                        "variant_type": None,
                        "cover_artist": None,
                        "quantity": 1,
                        "raw_item_price": Decimal("4.99"),
                    }
                ],
                "warnings": [],
                "confidence_score": 0.9,
            }
        ),
        raw_text="Marvel Amazing Spider-Man 1 Cover B",
    )

    assert cover_a.items[0].metadata_identity_key != cover_b.items[0].metadata_identity_key


def test_confirm_import_uses_canonical_metadata_values(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, email="canonical-confirm@example.com")

    create_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Marvel Comics Ultimate Spider-Man #001A",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Marvel Comics",
                    "title": " ultimate spider-man ",
                    "issue_number": "#001A",
                    "cover_name": " cover a ",
                    "printing": None,
                    "ratio": None,
                    "variant_type": " foil edition ",
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "5.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )

    assert create_response.status_code == 201
    import_payload = create_response.json()["parsed_payload_json"]["items"][0]
    assert import_payload["raw_publisher"] == "Marvel Comics"
    assert import_payload["publisher"] == "Marvel"
    assert import_payload["title"] == "Ultimate Spider-Man"
    assert import_payload["issue_number"] == "1A"

    import_id = create_response.json()["id"]
    confirm_response = client.post(f"/imports/{import_id}/confirm", headers=auth_headers(token))

    assert confirm_response.status_code == 200
    publisher_names = [publisher.name for publisher in session.exec(select(Publisher)).all()]
    assert publisher_names == ["Marvel"]

    order_detail = client.get(
        f"/orders/{confirm_response.json()['order_id']}",
        headers=auth_headers(token),
    )
    assert order_detail.status_code == 200
    item = order_detail.json()["items"][0]
    assert item["publisher"] == "Marvel"
    assert item["title"] == "Ultimate Spider-Man"
    assert item["issue_number"] == "1A"
    assert item["cover_name"] == "Cover A"
    assert item["variant_type"] == "Foil Edition"
    inventory_copy = session.exec(select(InventoryCopy)).one()
    assert (
        inventory_copy.metadata_identity_key
        == "Marvel|Ultimate Spider-Man|1A|Cover A / Foil Edition"
    )


def test_confirm_import_allows_unknown_but_present_publisher(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, email="unknown-present@example.com")

    create_response = client.post(
        "/imports/manual",
        json={
            "raw_text": "Indie House Babylon Cove #01",
            "retailer": "Midtown",
            "order_date": "2026-05-21",
            "source_type": "manual_draft",
            "shipping_amount": "0.00",
            "tax_amount": "0.00",
            "items": [
                {
                    "publisher": "Indie House",
                    "title": "Babylon Cove",
                    "issue_number": "01",
                    "cover_name": None,
                    "printing": None,
                    "ratio": None,
                    "variant_type": None,
                    "cover_artist": None,
                    "quantity": 1,
                    "raw_item_price": "4.99",
                }
            ],
            "warnings": [],
            "confidence_score": 1.0,
        },
        headers=auth_headers(token),
    )

    assert create_response.status_code == 201
    assert create_response.json()["needs_metadata_review"] is True
    assert create_response.json()["parsed_payload_json"]["items"][0]["publisher"] == "Indie House"

    confirm_response = client.post(
        f"/imports/{create_response.json()['id']}/confirm",
        headers=auth_headers(token),
    )

    assert confirm_response.status_code == 200
    publisher_names = [publisher.name for publisher in session.exec(select(Publisher)).all()]
    assert publisher_names == ["Indie House"]
