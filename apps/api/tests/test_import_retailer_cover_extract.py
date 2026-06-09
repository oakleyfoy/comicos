from app.schemas.ai import AiDraftOrderItem, ParseOrderResponse
from app.services.import_retailer_cover_extract import (
    enrich_parse_order_retailer_covers,
    extract_retailer_cover_rows,
)


def test_extract_retailer_cover_rows_from_table_html() -> None:
    html = """
    <table>
      <tr>
        <td><a href="https://shop.example.com/comic/spider-man-1"><img src="https://cdn.example.com/covers/spider-man-1.jpg" alt="Spider-Man 1 Cover A"></a></td>
        <td>Spider-Man #1</td>
      </tr>
      <tr>
        <td><a href="https://shop.example.com/comic/x-men-2"><img src="https://cdn.example.com/covers/x-men-2.png" alt="X-Men 2"></a></td>
      </tr>
    </table>
    """
    rows = extract_retailer_cover_rows(html)
    assert len(rows) == 2
    assert rows[0].image_url.endswith("spider-man-1.jpg")
    assert rows[0].product_url == "https://shop.example.com/comic/spider-man-1"
    assert rows[0].alt_text == "Spider-Man 1 Cover A"


def test_enrich_parse_order_retailer_covers_zips_by_index() -> None:
    html = """
    <tr><td><img src="https://cdn.example.com/cover-a.jpg" alt="Terminal 1"></td></tr>
    <tr><td><img src="https://cdn.example.com/cover-b.jpg" alt="Terminal 2"></td></tr>
    """
    parsed = ParseOrderResponse.model_validate(
        {
            "retailer": "Midtown Comics",
            "order_date": "2026-06-01",
            "source_type": "ai_draft",
            "items": [
                {"title": "Terminal", "issue_number": "1", "quantity": 1, "raw_item_price": "3.99"},
                {"title": "Terminal", "issue_number": "2", "quantity": 1, "raw_item_price": "3.99"},
            ],
            "warnings": [],
            "confidence_score": 0.9,
        }
    )
    enriched = enrich_parse_order_retailer_covers(parsed, html=html, retailer="Midtown Comics")
    assert enriched.items[0].retailer_cover_url == "https://cdn.example.com/cover-a.jpg"
    assert enriched.items[1].retailer_cover_url == "https://cdn.example.com/cover-b.jpg"


def test_enrich_skips_items_with_existing_retailer_cover() -> None:
    item = AiDraftOrderItem(
        title="Existing",
        issue_number="1",
        quantity=1,
        raw_item_price="1.00",
        retailer_cover_url="https://cdn.example.com/keep.jpg",
    )
    parsed = ParseOrderResponse.model_validate(
        {
            "order_date": "2026-06-01",
            "source_type": "ai_draft",
            "items": [item.model_dump()],
            "warnings": [],
            "confidence_score": 0.9,
        }
    )
    html = '<tr><td><img src="https://cdn.example.com/new.jpg"></td></tr>'
    enriched = enrich_parse_order_retailer_covers(parsed, html=html)
    assert enriched.items[0].retailer_cover_url == "https://cdn.example.com/keep.jpg"
