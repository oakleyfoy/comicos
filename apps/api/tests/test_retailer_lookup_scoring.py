from __future__ import annotations

from app.services.retailer_lookup.base import RetailerProductCandidate
from app.services.retailer_lookup.scoring import score_retailer_candidate


def _item(**overrides: object) -> dict[str, object]:
    base = {
        "title": "Shaolin Cowboy Staying A.I. Live",
        "issue_number": "1",
        "cover_name": "Cover A",
        "cover_artist": "Geof Darrow",
        "publisher": "Dark Horse",
        "raw_item_price": "4.99",
    }
    base.update(overrides)
    return base


def _candidate(**overrides: object) -> RetailerProductCandidate:
    base = RetailerProductCandidate(
        retailer="Midtown Comics",
        product_title="Shaolin Cowboy Staying A.I. Live",
        product_url="https://www.midtowncomics.com/product/1",
        image_url="https://cdn.example.com/a.jpg",
        thumbnail_url="https://cdn.example.com/a-thumb.jpg",
        publisher="Dark Horse",
        issue_number="1",
        cover_name="Cover A",
        variant_type="Cover A",
        cover_artist="Geof Darrow",
        release_date="2026-01-01",
        price="4.99",
        sku="SKU-A",
        source_confidence=0.0,
        raw_score_reasons=(),
    )
    return RetailerProductCandidate(**{**base.__dict__, **overrides})


def test_cover_a_rejects_cover_b_candidate() -> None:
    score, reasons, rejected_reason = score_retailer_candidate(
        _item(cover_name="Cover A"),
        _candidate(cover_name="Cover B", variant_type="Cover B", product_title="Shaolin Cowboy Staying A.I. Live #1 Cover B"),
    )
    assert score == 0
    assert rejected_reason == "cover_letter_conflict"
    assert "cover_letter_conflict" in reasons


def test_cover_a_accepts_matching_candidate() -> None:
    score, reasons, rejected_reason = score_retailer_candidate(_item(), _candidate())
    assert score >= 75
    assert rejected_reason is None
    assert "title_exact" in reasons
    assert "issue_number_exact" in reasons
    assert "cover_letter_exact" in reasons


def test_artist_match_boosts_score() -> None:
    base_score, _, _ = score_retailer_candidate(_item(cover_artist=""), _candidate(cover_artist=""))
    boosted_score, reasons, _ = score_retailer_candidate(_item(), _candidate())
    assert boosted_score >= base_score
    assert "cover_artist_exact" in reasons


def test_wrong_issue_number_hard_rejects() -> None:
    score, reasons, rejected_reason = score_retailer_candidate(_item(issue_number="2"), _candidate(issue_number="1"))
    assert score == 0
    assert rejected_reason == "wrong_issue_number"
    assert "issue_number_conflict" in reasons
