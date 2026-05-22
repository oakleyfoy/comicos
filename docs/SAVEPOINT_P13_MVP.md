# ComicOS Savepoint P13 MVP

## Purpose
This document records the current MVP state of `comic-os` at the P13 save point, before AI-assisted import, pricing automation, and richer ingestion workflows are introduced.

## Completed Phases P00-P13
1. **P00 - Product framing and phase roadmap**
   Defined ComicOS as a comic-investor portfolio tracker with an incremental build plan.
2. **P01 - Monorepo foundation**
   Created the monorepo, FastAPI backend, React/Vite/Tailwind frontend, base docs, env examples, and health check.
3. **P02 - Unified local dev workflow**
   Added root scripts so API and web can run together from the workspace.
4. **P03 - Database foundation**
   Added settings/config loading, SQLModel engine/session wiring, Alembic, and `GET /health/db`.
5. **P04 - Local database reset workflow**
   Added local Docker Postgres helpers and reset tooling for safe developer rebuilds.
6. **P05 - Core asset ledger models**
   Added publisher, title, issue, variant, order, order item, and inventory copy tables.
7. **P06 - Authentication and ownership**
   Added users, password hashing, JWT auth, and ownership fields for user-scoped data.
8. **P07 - Manual order creation backend**
   Added authenticated `POST /orders`, entity reuse, shipping/tax allocation, and inventory copy generation.
9. **P08 - Inventory dashboard read APIs**
   Added authenticated inventory list and inventory summary endpoints with paging/filtering/sorting.
10. **P09 - Inventory management workflows**
    Added single/bulk inventory updates and dashboard inline editing/bulk actions.
11. **P10 - Manual order entry frontend**
    Added protected `/orders/new` with multi-item order entry and success feedback.
12. **P11 - Inventory detail workflow**
    Added `/inventory/:inventoryCopyId`, dashboard links, copy detail view, and detail-page editing.
13. **P12 - FMV history and portfolio performance**
    Added FMV snapshot tracking, FMV history endpoint/UI, and portfolio performance analytics.
14. **P13 - Order history, MVP hardening, and UI polish**
    Added order list/detail flows, stricter order validation, improved success/error/loading states, shared protected-page chrome, and this savepoint.

## Current App Functionality

### Authentication
- Users can register, log in, and fetch the current authenticated user.
- All inventory, order, FMV history, and portfolio analytics are user-scoped.

### Orders
- Users can manually create purchase orders with one or more items.
- Each order item generates the correct number of `InventoryCopy` rows.
- Shipping and tax are allocated deterministically across line items.
- Users can review past orders in list and detail views.

### Inventory
- Users can browse inventory with search, filters, sorting, and pagination.
- Users can update FMV, hold status, grade status, star rating, and notes.
- Users can open a dedicated copy detail page for a deeper asset view.

### FMV and Performance
- FMV updates create immutable historical snapshots.
- Users can review FMV history per copy.
- Dashboard analytics surface top gainers, top losers, and highest-value books.

### UI State Quality
- Protected pages now share common navigation and structure.
- Dashboard, inventory detail, orders list, order detail, and order creation all include improved loading/error/empty-state handling.

## Backend Endpoints

### Health
- `GET /health`
- `GET /health/db`

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

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
- `/orders/:orderId`

## Database Tables
- `publisher`
- `comic_title`
- `comic_issue`
- `variant`
- `customer_order`
- `order_item`
- `inventory_copy`
- `inventory_fmv_snapshot`
- `user`

## Known Limitations
- No AI parsing or import workflows yet.
- No receipt uploads or image/document attachments yet.
- No automated market pricing or market scraping yet.
- No order editing, cancellation, or deletion yet.
- No inventory image uploads yet.
- No chart-based portfolio visualization yet.
- No export/reporting pipeline yet.
- No frontend automated test suite yet; confidence is currently driven by backend tests and frontend builds.

## Next Recommended Phases
1. **AI/import ingestion**
   Add assisted order ingestion from pasted text, marketplace exports, email receipts, or photos.
2. **Pricing automation**
   Add assisted FMV suggestions, valuation confidence, and optional valuation-source tracking.
3. **Portfolio analytics expansion**
   Add charts, time-series portfolio views, realized vs unrealized performance, and benchmark-style reporting.
4. **Document and media support**
   Add receipt uploads, notes attachments, and cover/media assets.
5. **Operational workflows**
   Add order editing/correction flows, audit-friendly mutations, and safer admin/debug tooling.

## MVP Summary
At P13, ComicOS is a functional authenticated MVP for:
- creating manual comic purchase orders,
- generating owned inventory copies,
- reviewing and editing inventory,
- tracking FMV history,
- reviewing portfolio performance,
- reviewing order history and order detail.

This is a strong save point for branching into AI-assisted import and pricing workflows next.
