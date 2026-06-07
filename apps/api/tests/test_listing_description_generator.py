from __future__ import annotations

from app.services.listing_description_generator import DescriptionInputs, generate_listing_description


def test_description_structure() -> None:
    text = generate_listing_description(
        DescriptionInputs(
            display_title="Amazing Spider-Man #300",
            publisher="Marvel",
            issue_number="300",
            variant="Cover A",
            grade_condition="Raw",
            key_notes=["First full appearance of Venom"],
            condition_paragraph="Raw comic. Please review photos carefully.",
            shipping_paragraph="Ships bagged and boarded in protective comic mailer.",
        )
    )
    assert "Details:" in text
    assert "Publisher: Marvel" in text
    assert "Condition:" in text
    assert "Shipping:" in text
