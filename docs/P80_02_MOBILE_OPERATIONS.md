# P80-02 Mobile Inventory Operations

Mobile workflows on P80-01 identification plus existing order receiving (P53/P67), P79 assignment, and P79 audit.

## Intake

- `POST /api/v1/mobile/intake/start` — `ORDER` / `PURCHASE` / `MANUAL` (+ optional `order_id`)
- `POST /api/v1/mobile/intake/scan` — identify, match order lines, mark received (or create copy in `MANUAL`)
- `POST /api/v1/mobile/intake/complete` — close session with missing count

## Storage

- `POST /api/v1/mobile/storage/suggest` — slot + path with series grouping heuristic
- `POST /api/v1/mobile/storage/assign` — P79 `assign_inventory_copy` (optional barcode resolve)

## Audit

- `POST /api/v1/mobile/audit/start`
- `POST /api/v1/mobile/audit/scan` — verify expected or record unexpected
- `POST /api/v1/mobile/audit/complete` — auto-mark unverified expected as missing
- `GET /api/v1/mobile/audit/{audit_id}`

## Dashboard

- `GET /api/v1/mobile/operations`

## UI routes

- `/mobile-intake`, `/mobile-storage`, `/mobile-audit`, `/mobile-operations`
