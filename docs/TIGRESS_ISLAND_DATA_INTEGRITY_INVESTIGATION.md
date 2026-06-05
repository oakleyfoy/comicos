# Tigress Island #1 — Data Integrity Investigation

**Date:** 2026-06-03  
**Scope:** Read-only analysis (no schema changes, no scoring changes, no production writes)  
**Environment queried:** Workspace PostgreSQL `localhost:5433/comic_os` (`APP_ENV=development`), matching the integration dataset used for owner certification.  
**Symptom owner:** `ofoy@att.net` → `owner_user_id = 1`

## Executive summary

| Field | Value |
|-------|--------|
| **Expected release date (store / 1st printing)** | **2026-03-11** |
| **Actual stored release date (`release_issue`)** | **2026-06-17** (FOC **2026-05-25**) |
| **What the UI shows** | FOC **May 24**, Release **June 16** |
| **Root cause** | Lunar **4th printing** reorder dates are imported into the **single canonical** `release_issue` row for *Tigress Island #1*, keyed only by publisher + series + issue number. That overwrites display/decision dates for the **already-released 1st printing** the store lists. A secondary UI timezone effect shifts stored dates back one calendar day. |
| **Recommended fix** | Treat reprints (`Printing` > 1 / `PTG` in Lunar title) as distinct catalog variants or child rows; do not let future reprint FOC/InStore dates replace first-print retail dates on the canonical issue; surface store/LoCG retail date when linking `external_catalog_issue`; parse date-only fields in the web UI without UTC midnight shift. |

---

## 1. Recommendation source record

`cross_system_recommendation` stores **title text only** (no `release_issue_id` or `external_catalog_issue_id` columns). IDs below are resolved via the forward release title index (`resolve_release_pair`) and latest snapshot selection (`_latest_snapshot_rows`).

### Canonical row for the reported UI issue (latest snapshot)

| Field | Value |
|-------|--------|
| **cross_system_recommendation.id** | **14259** |
| **owner_user_id** | **1** |
| **recommendation_type** | `PREORDER` |
| **recommendation_rank** | 37 |
| **title** | `Tigress Island #1` |
| **source_systems** | `P50_RELEASE`, `P57_DAILY`, `P57_UNIFIED` |
| **created_at** | `2026-06-05T18:57:07+00:00` |
| **release_issue.id** (resolved) | **1278** |
| **external_catalog_issue.id** | **None** (no `external_catalog_issue` row for this series in this database) |

Other snapshot generations for the same title exist (e.g. ids 11417, 11885, 12391, 13015, 13637) with the same resolved `release_issue_id = 1278`.

---

## 2. Stored dates and source artifacts

### `release_issue` (id **1278**)

| Field | Value |
|-------|--------|
| owner_user_id | 1 |
| release_uuid | `lunar-issue-21aa6069ba121b81a321ccf54ef727f2` |
| series | Tigress Island (`release_series.id` 1035) |
| issue_number | `1` |
| title | `Tigress Island #1` |
| publisher | Image Comics |
| foc_date | **2026-05-25** |
| release_date | **2026-06-17** |
| release_status | `SCHEDULED` |
| cover_price | 3.99 |

**`release_variant`** (issue 1278): one row — `Standard Cover`, `OPEN_ORDER`, Lunar code **`0426IM8399`**.

### `external_catalog_issue`

No rows where `series_name` or `title` matches Tigress Island in this database.  
`issue_demand_snapshot` has **no** link for `release_issue_id = 1278`.

**LoCG capture artifacts** (on disk, not live DB):

| Artifact | Identity | Release date |
|----------|----------|----------------|
| `data/locg_browser_capture/2026-03-11/4029726_detail.html` | LoCG comic **4029726** — *Tigress Island #1* (parent) | **Mar 11, 2026** |
| `data/locg_browser_capture/2026-03-11/list_page.html` | Same parent + cover variants | **Mar 11, 2026** (`data-date=1773201600`) |
| `data/locg_browser_capture/2026-06-17/list_page.html` | Variant **2634134** — *4th Printing EPHK* | **Jun 17, 2026** (`data-date=1781668800`) |
| `data/locg_browser_capture/2026-06-17/variant_persist_trace.jsonl` | 4th print persist under parent `4029726`, `parent_issue_id`: **3156** (production-style capture; **not** present as `external_catalog_issue` in local DB) |

### Lunar / distributor feed (`lunar_feed_raw_row`)

Product code **`0426IM8399`** (matches `release_variant.source_item_code`):

| Lunar field | Value |
|-------------|--------|
| Title | `TIGRESS ISLAND #1 (OF 5) 4TH PTG (MR)` |
| MainDesc | Tigress Island |
| IssueNumber | 1 |
| Publisher | Image Comics |
| **Printing** | **4** |
| UPC | **70985304589200114** |
| FOCDate | **5/25/2026** |
| InStoreDate | **6/17/2026** |
| VariantDescription | EPHK |

LoCG **4th printing** list row date (**Jun 17, 2026**) aligns with Lunar `InStoreDate`, not with the store’s **Mar 11, 2026** first-print listing.

---

## 3. Classification (symptom vs causes)

| Hypothesis | Verdict | Notes |
|------------|---------|--------|
| Wrong issue identity | **No** | Series, issue #, publisher, and UPC family match *Tigress Island #1* Image. |
| Duplicate issue record | **No** | Single `release_issue` 1278 for `#1`; Lunar identity is one canonical hash per publisher/series/issue #. |
| Second printing / reissue conflation | **Yes (primary)** | Stored Lunar row is explicitly **4th PTG**; dates are for a **future reprint**, not the March retail first print. |
| Stale release date | **Partial** | Lunar dates are current for the **4th printing** SKU; they are **wrong for store-facing “#1 release”** after first print shipped. |
| Wrong source priority | **Yes (primary)** | Recommendation decisions read **`release_issue.foc_date` / `release_date`** (Lunar-driven). No `external_catalog_issue` override in this DB. |
| Display formatting only | **Secondary** | DB has 2026-05-25 / 2026-06-17; UI shows May 24 / June 16 due to `new Date("YYYY-MM-DD")` UTC parsing in `RecommendationDecisionPanel.tsx`. |

---

## 4. Field comparison (store vs ComicOS vs sources)

| Attribute | Store / 1st print (LoCG parent 4029726) | ComicOS `release_issue` 1278 | Lunar `0426IM8399` | LoCG 4th print variant |
|-----------|----------------------------------------|------------------------------|--------------------|-------------------------|
| Title | Tigress Island #1 | Tigress Island #1 | TIGRESS ISLAND #1 (OF 5) **4TH PTG** | Tigress Island #1 **4th Printing EPHK** |
| Issue # | 1 | 1 | 1 | 1 (variant of parent) |
| Publisher | Image Comics | Image Comics | Image Comics | Image Comics |
| UPC/SKU | (store listing; 1st print) | via variant **70985304589200114** | **70985304589200114** | variant comic 2634134 |
| Variant / printing | 1st printing retail | “Standard Cover” (no print #) | **Printing: 4** | 4th Printing EPHK |
| FOC | N/A for on-shelf retail | 2026-05-25 | 5/25/2026 | (reprint order window) |
| Release | **2026-03-11** | **2026-06-17** | 6/17/2026 | **2026-06-17** |

---

## 5. Technical root cause (code path)

1. **Lunar issue identity** (`lunar_variant_identity.build_issue_release_uuid`) hashes **publisher + series_name + issue_number** only — **printing is not part of the key**.
2. **Lunar import** (`lunar_issue_resolution._apply_issue_import`) **overwrites** `foc_date` and `release_date` on the matched canonical row whenever a newer Lunar row applies.
3. The active Lunar SKU for this row is **4th printing** (`Printing: "4"`, title contains `4TH PTG`), with **June 2026** in-store date — appropriate for a **reorder**, not for the **March 2026** first-print release the store shows.
4. **Cross-system recommendations** (`P50_RELEASE` → unified/daily → cross-system) attach to title `Tigress Island #1` and resolve to `release_issue` **1278**; **decision panel dates** come from that row (`recommendation_decision_engine`).
5. **LoCG / external catalog** retail date (**2026-03-11**) is **not applied** here because **`external_catalog_issue` is missing** and demand linkage is absent — so distributor reprint scheduling wins.
6. **UI:** `formatDate` in `apps/web/src/components/RecommendationDecisionPanel.tsx` interprets API date strings as UTC instants, which displays **one day earlier** in US timezones (May 24 / June 16 vs stored May 25 / June 17).

---

## 6. Recommended fix (investigation only — not implemented)

1. **Reprint-aware release modeling:** When Lunar `Printing` > 1 or title matches `PTG` / `PRINTING`, create or update a **distinct** `release_variant` (or separate issue row) and keep the canonical **first-print** `release_issue` dates aligned with retail/LoCG once released.
2. **Date merge policy:** For issues whose first print `release_date` is in the past, do **not** replace retail release with a **future reprint** `InStoreDate` on the canonical row; use reprint dates only on the reprint SKU/variant.
3. **Catalog linkage:** Ensure LoCG parent **4029726** persists to `external_catalog_issue` and maps to `release_issue` so store/LoCG **2026-03-11** can drive customer-facing “released” state while Lunar drives **FOC for future reprints** separately.
4. **Display:** Format date-only API values as calendar dates (no UTC midnight shift) so UI matches stored `date` fields.

---

## 7. Investigation method

- SQL SELECT against local PostgreSQL (read-only).
- LoCG HTML / JSONL under `data/locg_browser_capture/`.
- Lunar payload inspection via `lunar_feed_raw_row.row_payload_json`.
- No Render/production `DATABASE_URL` mutation or write queries in this pass.

**Helper script used (local, ephemeral):** `apps/api/scripts/_tigress_investigate_readonly.py` — safe to delete; not part of the product surface.
