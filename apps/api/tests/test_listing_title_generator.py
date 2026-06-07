from __future__ import annotations

from app.services.listing_title_generator import TitleInputs, generate_listing_title


def test_ebay_title_includes_series_issue() -> None:
    title = generate_listing_title(
        TitleInputs(
            series="Amazing Spider-Man",
            issue_number="300",
            publisher="Marvel",
            year="1988",
            variant="",
            grade_label="VF/NM",
            key_note="1st Full Venom",
            marketplace="EBAY",
        )
    )
    assert "Amazing Spider-Man" in title
    assert "300" in title
    assert len(title) <= 81


def test_title_no_hype_injection() -> None:
    title = generate_listing_title(
        TitleInputs(
            series="X-Men",
            issue_number="1",
            publisher="Marvel",
            year="",
            variant="",
            grade_label="Raw",
            key_note="",
            marketplace="EBAY",
        )
    )
    assert "!!!" not in title
