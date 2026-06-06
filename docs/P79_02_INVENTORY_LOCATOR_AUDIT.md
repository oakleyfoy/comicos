# P79-02 Inventory Locator & Audit

## Objective

On P79-01 storage foundation, answer:

- Can I find a book quickly?
- Is storage accurate?
- What is missing, misplaced, duplicated, or unassigned?

Out of scope: mobile/camera scanning, advanced analytics, eBay/listing changes, auto-destructive moves.

## Locator rules

`GET /api/v1/storage/locator?q=`

Matches (case-insensitive substring):

- Series / title, issue number, variant fields, publisher
- Inventory copy ID (numeric)
- Storage box ID (`box:{id}` or numeric box lookup)
- Barcode/UPC hints in `metadata_identity_key` or `condition_notes`
- CGC cert numbers from grading queue/history

Returns per hit:

- Full path (room, rack, shelf, box, section, slot)
- Assignment status (`ASSIGNED` / `UNASSIGNED`)
- Assignment confidence (`HIGH` / `MEDIUM` / `LOW`)
- Duplicate candidate copy IDs (same series/issue/variant assigned elsewhere)

## Box contents

`GET /api/v1/storage/boxes/{box_id}/contents`

- Rows sorted by slot, grouped into sections (25 slots per section)
- Capacity, utilization, total estimated FMV
- Flags: `UNASSIGNED`, `MISPLACED`, `DUPLICATE_CANDIDATE`, `OVER_CAPACITY`

## Audit workflow

States: `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED` (sessions start `IN_PROGRESS`).

Entry statuses: `EXPECTED`, `VERIFIED`, `MISSING`, `UNEXPECTED`, `DUPLICATE`, `MOVED`.

1. `POST /storage/audits` — scope by `scope_box_id` or `scope_location_id`; seeds `EXPECTED` entries from current assignments.
2. `POST .../verify` — mark entry verified.
3. `POST .../missing` — mark expected book missing.
4. `POST .../unexpected` — record found book; optional `move_to_box` performs explicit reassignment (non-destructive elsewhere).
5. `POST .../complete` — close session with counts.

## Missing / misplaced detection

`build_detection_summary` reports:

- Unassigned inventory copies
- Duplicate title/variant assignments
- Boxes over capacity
- Misplaced candidates (copy listed in wrong box context)

Surfaced on audit detail `detection_summary`.

## Label payload format

`GET /storage/labels/{entity_type}/{entity_id}`

`entity_type`: `location`, `rack`, `shelf`, `box`

```json
{
  "label_code": "P79-BOX-12",
  "qr_payload": "comicos://p79/storage/box/12",
  "printable_title": "Box 17",
  "storage_path": "Office / Rack A / Shelf 3 / 17",
  "capacity": 100,
  "current_count": 52
}
```

QR strings are for future mobile scan; no camera workflow in P79-02.

## UI

- `/inventory-locator` — search and path display
- `/storage-box-contents` — box ID → contents
- `/storage-audit` — start audit, verify/missing
- `/storage-label-preview` — label/QR preview

## Known limitations

- Search is substring-based, not fuzzy ranked.
- Duplicate detection is heuristic (series + issue + variant), not strict barcode identity.
- Audits do not auto-delete assignments or auto-move without `move_to_box`.
- No mobile scanner app.

## Verification

```bash
pytest apps/api/tests/test_inventory_locator.py -v
pytest apps/api/tests/test_box_contents.py -v
pytest apps/api/tests/test_storage_audit.py -v
pytest apps/api/tests/test_storage_missing_detection.py -v
pytest apps/api/tests/test_storage_labels.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
