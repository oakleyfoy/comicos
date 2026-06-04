from app.services.recommendation_title_normalize import (
    normalize_issue_number_for_match,
    normalize_recommendation_title_key,
    title_key_aliases,
)


def test_normalize_hash_and_whitespace() -> None:
    assert normalize_recommendation_title_key("  Spider-Man   #   12  ") == "spider-man #12"


def test_strip_variant_suffix() -> None:
    assert normalize_recommendation_title_key("Batman #1 (Variants)") == "batman #1"


def test_issue_number_match() -> None:
    assert normalize_issue_number_for_match("#12") == "12"
    assert normalize_issue_number_for_match("012") == "12" or normalize_issue_number_for_match("012") == "012"


def test_aliases_include_volume_stripped() -> None:
    primary = normalize_recommendation_title_key("Saga Vol. 2 #10")
    aliases = title_key_aliases("Saga Vol. 2 #10")
    assert primary.startswith("saga vol") and primary.endswith("#10")
    assert any(a.startswith("saga #") and a.endswith("10") for a in aliases)
