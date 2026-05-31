from __future__ import annotations

from app.services.lunar_release_normalizer import normalize_lunar_rows


def test_zatanna_issue_groups_into_one_issue_with_variants() -> None:
    rows = [
        {
            "Publisher": "DC Comics",
            "MainDesc": "ZATANNA (2026)",
            "IssueNumber": "5",
            "Title": "ZATANNA (2026) #5 CVR A JAMAL CAMPBELL",
            "Code": "0626DC0001",
            "Retail": "4.99",
        },
        {
            "Publisher": "DC Comics",
            "MainDesc": "ZATANNA (2026)",
            "IssueNumber": "5",
            "Title": "ZATANNA (2026) #5 CVR B DAVID TALASKI CARD STOCK VAR",
            "Code": "0626DC0002",
            "Retail": "4.99",
        },
        {
            "Publisher": "DC Comics",
            "MainDesc": "ZATANNA (2026)",
            "IssueNumber": "5",
            "Title": "ZATANNA (2026) #5 CVR C BRUNO REDONDO CARD STOCK VAR",
            "Code": "0626DC0003",
            "Retail": "4.99",
        },
    ]
    feed, errors = normalize_lunar_rows(rows)
    assert not errors
    assert len(feed.series) == 1
    assert len(feed.series[0].issues) == 1
    issue = feed.series[0].issues[0]
    assert issue.issue_number == "5"
    assert len(issue.variants) == 3
    assert {variant.variant_name.split()[1] for variant in issue.variants if variant.variant_name.startswith("Cover")} == {"A", "B", "C"}


def test_reimport_idempotent_variant_uuid() -> None:
    rows = [
        {
            "Publisher": "Image",
            "MainDesc": "Battle Beast",
            "IssueNumber": "9",
            "Title": "BATTLE BEAST #9 CVR A",
            "Code": "A1",
            "Retail": "3.99",
        }
    ]
    feed1, _ = normalize_lunar_rows(rows)
    feed2, _ = normalize_lunar_rows(rows)
    assert feed1.series[0].issues[0].variants[0].variant_uuid == feed2.series[0].issues[0].variants[0].variant_uuid
