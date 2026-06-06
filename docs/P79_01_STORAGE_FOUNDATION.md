# P79-01 Storage Foundation

## Objective

Answer **“Where is this book?”** with a physical storage hierarchy, box/slot tracking, and inventory assignments.

Out of scope for P79-01: QR labels, audits, missing-book detection, storage analytics, scanning workflows (P79-02 / P79-03).

## Hierarchy model

Flexible tree (`P79StorageLocation`) with optional levels:

```
LOCATION (Office, Garage, Storage Unit)
  └── ROOM (optional)
        └── RACK (A, B, …)
              └── SHELF (1, 2, 3, …)
                    └── BOX (P79StorageBox)
                          └── SLOT (P79StorageSlot)
```

- **Boxes** attach only to `SHELF` nodes.
- **Slots** are numbered `1..capacity` within a box (created on first assignment).
- **Assignments** (`P79InventoryLocationAssignment`) bind one inventory copy to one slot.

## Assignment rules

- One active assignment per `inventory_copy_id`.
- Re-assigning updates the same row and moves the copy to a new slot.
- Manual `slot_number` or `use_suggested_slot` (next free number in box).
- `assigned_by_user_id` and timestamps recorded on create/update.

## Capacity rules

- Box `capacity` defaults to 100 (max 500 on create).
- **Occupancy** = count of assignments in the box.
- **Utilization %** = occupancy / capacity (box, shelf aggregate, location aggregate).
- **Suggested slot** = lowest free slot number in `1..capacity`.

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/storage/locations` | List locations with utilization |
| POST | `/api/v1/storage/locations` | Create location or `seed_office_template` |
| GET | `/api/v1/storage/boxes` | List boxes with capacity metrics |
| POST | `/api/v1/storage/boxes` | Create box on a shelf |
| POST | `/api/v1/storage/assign` | Assign copy to box/slot |
| GET | `/api/v1/storage/search` | Search assigned copies |
| GET | `/api/v1/storage/dashboard` | Foundation dashboard |

## Example assignment

**Absolute Batman #1** → Office / Main / Rack A / Shelf 3 / **Box 17** / **Slot 53**

## Office template seed

POST location with `seed_office_template: true` creates Office → Rack A → Shelves 1–3 → Boxes 1–3 (capacity 100 each). Custom locations can be added alongside.

## UI

- `/storage-locations` — create locations, seed template, list boxes
- `/storage-assignment` — assign by copy ID, search
- `/storage-dashboard` — capacity and assignment summary

## Known limitations

- No barcode/QR, audits, or “missing book” workflows.
- Search only returns **assigned** copies.
- Utilization at shelf/location uses summed box capacity (optional shelf `capacity` when no boxes).
- No multi-copy single-slot bundling (one copy per slot).

## Verification

```bash
pytest apps/api/tests/test_storage_locations.py -v
pytest apps/api/tests/test_storage_assignment.py -v
pytest apps/api/tests/test_storage_capacity.py -v
pytest apps/api/tests/test_storage_search.py -v
pytest apps/api/tests/test_storage_dashboard.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
