# P70-02 eBay Sold Listings Search

This phase adds a read-only preview route for eBay sold/completed listing searches and keeps the results normalized for downstream use without writing inventory or FMV records.

## Endpoint

- `GET /api/v1/market-pricing/ebay/sold-search`

## Query Parameters

- `q`
- `title`
- `series`
- `issue_number`
- `variant`
- `publisher`
- `upc`
- `condition`
- `limit` default `25`, max `100`

## Behavior

- Uses the existing eBay OAuth client credentials foundation.
- Returns preview rows only.
- Does not mutate the database.
- Surfaces provider health metadata for `sold_search_available` and `last_error`.

## Example

```bash
curl -H "Authorization: Bearer <token>" \
  "https://api.comicosapp.com/api/v1/market-pricing/ebay/sold-search?title=Absolute%20Batman&issue_number=1&variant=Cover%20A&publisher=DC%20Comics&limit=25"
```
