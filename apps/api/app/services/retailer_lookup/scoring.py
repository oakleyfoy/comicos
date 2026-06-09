"""Deterministic retailer candidate scoring."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.metadata_aliases import normalize_alias_lookup_key

from .base import RetailerProductCandidate, cover_letter_from_text

ACCEPT_SCORE = 65
POSSIBLE_SCORE = 50


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _tokens(value: str | None) -> set[str]:
    return {tok for tok in re.split(r"[^a-z0-9]+", _normalize_text(value)) if len(tok) >= 3}


def _price_decimal(value: str | None) -> Decimal | None:
    if not value:
        return None
    try:
        return Decimal(value.replace("$", "").strip())
    except (InvalidOperation, AttributeError):
        return None


def _price_distance(left: str | None, right: str | None) -> Decimal | None:
    a = _price_decimal(left)
    b = _price_decimal(right)
    if a is None or b is None:
        return None
    return abs(a - b)


def _issue_match(item: dict[str, Any], candidate: RetailerProductCandidate) -> bool | None:
    line_issue = _normalize_text(item.get("issue_number") or item.get("canonical_issue_number"))
    candidate_issue = _normalize_text(candidate.issue_number)
    if not line_issue or not candidate_issue:
        return None
    return normalize_alias_lookup_key(line_issue) == normalize_alias_lookup_key(candidate_issue)


def score_retailer_candidate(
    item: dict[str, Any],
    candidate: RetailerProductCandidate,
) -> tuple[int, list[str], str | None]:
    reasons: list[str] = []
    score = 0

    item_issue = _normalize_text(item.get("issue_number") or item.get("canonical_issue_number"))
    cand_issue = _normalize_text(candidate.issue_number)
    if item_issue and cand_issue:
        if normalize_alias_lookup_key(item_issue) == normalize_alias_lookup_key(cand_issue):
            score += 25
            reasons.append("issue_number_exact")
        else:
            return 0, ["issue_number_conflict"], "wrong_issue_number"

    item_title = _normalize_text(item.get("title") or item.get("canonical_title"))
    cand_title = _normalize_text(candidate.product_title)
    if item_title and cand_title:
        if item_title == cand_title:
            score += 30
            reasons.append("title_exact")
        else:
            item_tokens = _tokens(item_title)
            cand_tokens = _tokens(cand_title)
            overlap = len(item_tokens & cand_tokens)
            if overlap >= 2:
                score += 20
                reasons.append("title_overlap")
            elif overlap == 0:
                return 0, ["title_conflict"], "title_conflict"

    item_letter = cover_letter_from_text(
        " ".join(
            filter(
                None,
                [
                    item.get("cover_name"),
                    item.get("raw_variant_text"),
                    item.get("canonical_variant_text"),
                    item.get("variant_type"),
                ],
            )
        )
    )
    cand_letter = cover_letter_from_text(
        " ".join(filter(None, [candidate.cover_name, candidate.variant_type, candidate.product_title]))
    )
    if item_letter and cand_letter:
        if item_letter == cand_letter:
            score += 20
            reasons.append("cover_letter_exact")
        else:
            return 0, ["cover_letter_conflict"], "cover_letter_conflict"

    item_artist = _normalize_text(item.get("cover_artist"))
    cand_artist = _normalize_text(candidate.cover_artist)
    if item_artist and cand_artist:
        if item_artist == cand_artist:
            score += 10
            reasons.append("cover_artist_exact")
        else:
            item_artist_tokens = _tokens(item_artist)
            cand_artist_tokens = _tokens(cand_artist)
            if item_artist_tokens and cand_artist_tokens and item_artist_tokens & cand_artist_tokens:
                score += 8
                reasons.append("cover_artist_overlap")

    item_publisher = normalize_alias_lookup_key(item.get("publisher") or item.get("canonical_publisher"))
    cand_publisher = normalize_alias_lookup_key(candidate.publisher)
    if item_publisher and cand_publisher and item_publisher == cand_publisher:
        score += 10
        reasons.append("publisher_alias_match")

    price_delta = _price_distance(item.get("raw_item_price"), candidate.price)
    if price_delta is not None and price_delta <= Decimal("0.50"):
        score += 5
        reasons.append("price_close")

    item_release = _normalize_text(item.get("release_date") or item.get("parsed_release_date"))
    cand_release = _normalize_text(candidate.release_date)
    if item_release and cand_release and item_release == cand_release:
        score += 5
        reasons.append("release_date_exact")

    if candidate.product_url and item.get("retailer_product_url"):
        if _normalize_text(candidate.product_url) == _normalize_text(item.get("retailer_product_url")):
            score += 40
            reasons.append("product_url_exact")
    if candidate.sku and item.get("retailer_sku"):
        if _normalize_text(candidate.sku) == _normalize_text(item.get("retailer_sku")):
            score += 40
            reasons.append("sku_exact")

    return score, reasons, None


def accept_retailer_candidate(score: int) -> bool:
    return score >= ACCEPT_SCORE


def possible_retailer_candidate(score: int) -> bool:
    return POSSIBLE_SCORE <= score < ACCEPT_SCORE
