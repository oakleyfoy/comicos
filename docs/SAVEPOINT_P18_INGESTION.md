# ComicOS Savepoint P18 Ingestion

## Purpose
This document records the ComicOS state at the P18 save point, after the first AI-assisted ingestion workflow, persisted import drafts, import history UI, and imports workspace filtering were added.

## Completed Phases P00-P18
1. **P00 - Product framing and roadmap**
   Defined ComicOS as a portfolio and ingestion platform for comic investors with phased delivery.
2. **P01 - Monorepo foundation**
   Created the FastAPI backend, React/Vite frontend, Tailwind UI shell, README, and env examples.
3. **P02 - Unified local dev**
   Added root scripts to run the web and API together.
4. **P03 - Database foundation**
   Added SQLModel, Alembic, settings, session wiring, and DB health checks.
5. **P04 - Local database reset**
   Added local-only Docker database reset and helper scripts.
6. **P05 - Core asset ledger models**
   Added publisher, title, issue, variant, order, order item, and inventory copy tables.
7. **P06 - Authentication and ownership**
   Added users, password hashing, JWT auth, and user-scoped data ownership.
8. **P07 - Manual order creation backend**
   Added authenticated `POST /orders`, deterministic allocations, and inventory copy generation.
9. **P08 - Inventory read APIs**
   Added inventory listing and summary endpoints with filtering, sorting, and pagination.
10. **P09 - Inventory management**
    Added single/bulk inventory updates and dashboard editing workflows.
11. **P10 - Manual order entry frontend**
    Added protected `/orders/new` and manual multi-item order entry.
12. **P11 - Inventory detail workflow**
    Added copy detail endpoint, detail page, and linked dashboard navigation.
13. **P12 - FMV history and performance**
    Added FMV snapshot history and portfolio performance analytics.
14. **P13 - Order history and MVP polish**
    Added order list/detail views, improved validation, shared protected layout, and stronger empty/loading/error states.
15. **P14 - AI draft parsing**
    Added `POST /ai/parse-order` and the first paste-to-draft AI workflow without direct DB writes.
16. **P15 - AI parser hardening**
    Added configuration-safe failures, stricter parser guardrails, warnings, confidence rules, and sample receipt testing docs.
17. **P16 - Persisted import drafts**
    Added the `draft_import` table and import lifecycle endpoints so AI drafts can be saved, edited, confirmed, or discarded.
18. **P17 - Import draft history UI**
    Added `/imports`, import history navigation, reopen/confirm/discard actions, and linked-order history behavior.
19. **P18 - Import workspace polish**
    Added imports filtering, search, sorting, pagination, and this savepoint.

## Current Ingestion Architecture

### Import Entry
- Users start a new ingestion flow at `/orders/import`.
- Raw pasted receipt or invoice text is sent to `POST /imports`.
- The backend parses the text through the isolated AI parser service.
- The parsed result is saved as a persisted `draft_import` row.

### Draft Review
- Users can reopen a saved draft from `/imports` or by visiting `/orders/import?importId={id}`.
- Draft fields remain fully editable before confirmation.
- Drafts can be updated through `PATCH /imports/{id}`.
- Drafts can be discarded through `POST /imports/{id}/discard`.

### Import Confirmation
- `POST /imports/{id}/confirm` is the only AI-import endpoint allowed to create orders or inventory.
- Confirmation validates the saved parsed payload, converts it into the standard order payload, creates the order, creates inventory copies, and marks the import as confirmed.
- Confirmed imports retain a linked `order_id` for history and navigation.

## Import Draft Lifecycle
- `draft`
  Saved AI draft, still editable, confirmable, and discardable.
- `confirmed`
  Successfully converted into a real order and inventory through the confirm endpoint.
- `discarded`
  Closed without creating inventory. Cannot be confirmed afterward.

## AI Safety Rules
- AI never directly creates inventory.
- AI never directly creates an order from the parse endpoint.
- AI only produces a draft payload plus warnings and confidence.
- The parser prefers `null` over invented data.
- Prices and ratios are not invented when uncertain.
- Warnings are required for uncertain retailer, issue, quantity, variant/cover, or price fields.
- Confirm is the only workflow boundary where AI-derived drafts can become inventory.

## Backend Endpoints

### Health
- `GET /health`
- `GET /health/db`

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### AI Draft Parsing
- `POST /ai/parse-order`

### Imports
- `GET /imports`
  - optional `status`
  - optional `search`
  - `page`
  - `page_size`
  - optional `sort_by`
  - `sort_dir`
- `GET /imports/{id}`
- `POST /imports`
- `PATCH /imports/{id}`
- `POST /imports/{id}/confirm`
- `POST /imports/{id}/discard`

### Orders
- `POST /orders`
- `GET /orders`
- `GET /orders/{order_id}`

### Inventory
- `GET /inventory`
- `GET /inventory/summary`
- `GET /inventory/{inventory_copy_id}`
- `GET /inventory/{inventory_copy_id}/fmv-history`
- `PATCH /inventory/{inventory_copy_id}`
- `PATCH /inventory/bulk`

### Portfolio Analytics
- `GET /portfolio/performance`

## Frontend Routes
- `/`
- `/login`
- `/register`
- `/dashboard`
- `/inventory/:inventoryCopyId`
- `/orders`
- `/orders/new`
- `/orders/import`
- `/orders/:orderId`
- `/imports`

## Database Tables
- `publisher`
- `comic_title`
- `comic_issue`
- `variant`
- `customer_order`
- `order_item`
- `inventory_copy`
- `inventory_fmv_snapshot`
- `draft_import`
- `user`

## Known Limitations
- No Gmail ingestion yet.
- No OCR or image upload ingestion yet.
- No background workers or async ingestion jobs yet.
- No import attachments or document storage yet.
- No order editing after an import has been confirmed.
- No automatic FMV enrichment or market pricing yet.
- No frontend automated test suite yet; confidence still comes from backend tests and frontend builds.
- Import search is limited to stored draft content and parsed payload text, not rich semantic search.

## Next Recommended Phases
1. **Gmail ingestion**
   Pull order receipts from email into the draft import pipeline.
2. **OCR and image ingestion**
   Add photo, screenshot, and invoice document parsing into the same draft lifecycle.
3. **Automated FMV**
   Add assisted valuation suggestions and valuation-source tracking after ingestion is stable.
4. **Operational ingestion tooling**
   Add audit trails, import notes, retry flows, and richer draft correction history.
5. **Analytics expansion**
   Add ingestion funnel analytics, portfolio charts, and time-series reporting.

## Savepoint Summary
At P18, ComicOS supports:
- manual order entry,
- AI-assisted paste-to-draft parsing,
- persisted import drafts,
- import history and lifecycle management,
- deterministic confirm-only inventory creation,
- inventory and order history management,
- FMV tracking and portfolio performance analytics.

This is a strong save point before adding Gmail ingestion, OCR/document ingestion, and automated FMV workflows.
