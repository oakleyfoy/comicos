from __future__ import annotations

from app.services.retailer_lookup.midtown import lookup_midtown_product


PRODUCT_HTML = """
<html>
  <head>
    <title>Shaolin Cowboy Staying A.I. Live #1 Cover A - Midtown Comics</title>
    <meta property="og:title" content="Shaolin Cowboy Staying A.I. Live #1 Cover A" />
    <meta property="og:image" content="https://cdn.example.com/shaolin-a.jpg" />
    <meta property="product:brand" content="Dark Horse" />
    <meta property="product:release_date" content="2026-01-01" />
    <meta property="product:price" content="4.99" />
    <meta property="product:sku" content="SKU-A" />
  </head>
  <body>
    <a href="https://www.midtowncomics.com/product/1">
      <img src="https://cdn.example.com/shaolin-a.jpg" alt="Shaolin Cowboy Staying A.I. Live #1 Cover A" />
    </a>
  </body>
</html>
"""


def test_midtown_lookup_parses_exact_product_page(monkeypatch) -> None:
    monkeypatch.setattr("app.services.retailer_lookup.midtown._RATE_LIMIT_SECONDS", 0)
    monkeypatch.setattr("app.services.retailer_lookup.midtown._fetch_html", lambda url: PRODUCT_HTML)
    result = lookup_midtown_product(
        {
            "retailer": "Midtown Comics",
            "title": "Shaolin Cowboy Staying A.I. Live",
            "issue_number": "1",
            "cover_name": "Cover A",
            "cover_artist": "Geof Darrow",
            "publisher": "Dark Horse",
            "raw_item_price": "4.99",
            "retailer_product_url": "https://www.midtowncomics.com/product/1",
        }
    )
    assert result.matched is True
    assert result.selected_candidate is not None
    assert result.selected_candidate.image_url == "https://cdn.example.com/shaolin-a.jpg"
    assert result.selected_candidate.product_url == "https://www.midtowncomics.com/product/1"


def test_midtown_lookup_reuses_recent_success_cache(monkeypatch) -> None:
    monkeypatch.setattr("app.services.retailer_lookup.midtown._fetch_html", lambda url: (_ for _ in ()).throw(AssertionError("should not fetch")))
    result = lookup_midtown_product(
        {
            "retailer": "Midtown Comics",
            "title": "Shaolin Cowboy Staying A.I. Live",
            "issue_number": "1",
            "retailer_lookup_enrichment": {
                "matched": True,
                "possible_match": False,
                "retailer": "Midtown Comics",
                "checked_at": "2026-06-09T11:00:00+00:00",
                "selected_candidate": {
                    "retailer": "Midtown Comics",
                    "product_title": "Shaolin Cowboy Staying A.I. Live #1 Cover A",
                    "product_url": "https://www.midtowncomics.com/product/1",
                    "image_url": "https://cdn.example.com/shaolin-a.jpg",
                    "thumbnail_url": "https://cdn.example.com/shaolin-a.jpg",
                    "publisher": "Dark Horse",
                    "series_title": "Shaolin Cowboy Staying A.I. Live",
                    "issue_number": "1",
                    "cover_name": "Cover A",
                    "variant_type": "Cover A",
                    "cover_artist": "Geof Darrow",
                    "release_date": "2026-01-01",
                    "price": "4.99",
                    "sku": "SKU-A",
                    "source_confidence": 0.91,
                    "raw_score_reasons": ["title_exact"],
                },
            },
        }
    )
    assert result.matched is True
    assert result.selected_candidate is not None
    assert result.selected_candidate.product_url == "https://www.midtowncomics.com/product/1"


def test_midtown_lookup_reuses_recent_failure_cache(monkeypatch) -> None:
    monkeypatch.setattr("app.services.retailer_lookup.midtown._fetch_html", lambda url: (_ for _ in ()).throw(AssertionError("should not fetch")))
    result = lookup_midtown_product(
        {
            "retailer": "Midtown Comics",
            "title": "Unknown Book",
            "issue_number": "99",
            "retailer_lookup_enrichment": {
                "matched": False,
                "possible_match": False,
                "retailer": "Midtown Comics",
                "checked_at": "2026-06-09T11:00:00+00:00",
                "rejected_reason": "no_candidates",
                "diagnostics": {"candidate_count": 0},
            },
        }
    )
    assert result.matched is False
    assert result.rejected_reason == "no_candidates"
