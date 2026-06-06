# P80-01 Mobile Scanning Platform Foundation

Collector-scoped mobile scan APIs consolidate identification plus P51/P68/P70/P72/P73/P79 intelligence into one payload.

## API

- `POST /api/v1/mobile/scan` — barcode, manual entry, or image reference; returns identification and intelligence.
- `GET /api/v1/mobile/scan/{scan_id}` — persisted scan result.
- `GET /api/v1/mobile/book/{inventory_id}` — intelligence for an owned `inventory_copy` id.
- `GET /api/v1/mobile/scans` — recent scan history (pagination).

## UI

- `/mobile-scan` — camera placeholder, manual barcode entry, scan history.
- `/mobile-scan/:scanId` — full scan result with action card.

## Identification sources

UPC/ISBN normalization, external catalog UPC (`importance_signals_json`), known UPC registry, cover barcode candidates, inventory copy id, and P79 storage QR (`comicos://p79/storage/...`).

OCR image ingestion is reserved via `image` on the scan request (architecture hook only in P80-01).
