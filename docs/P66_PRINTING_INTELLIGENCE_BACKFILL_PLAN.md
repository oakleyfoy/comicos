# P66 Printing Intelligence — Backfill Plan

**Status:** Dry-run only — **no production mutation** until this plan is reviewed and an apply step is explicitly approved.

**Goal:** Repair existing `release_issue` rows where Lunar **reprint** FOC/InStore dates were stored at issue level, while preserving or restoring **first-print** `original_release_date` / `original_foc_date` and moving reprint schedules onto `release_variant.printing_*` fields.

---

## 1. Detection (who is affected)

### Primary signal (recommended)

Join `release_variant.source_item_code` to `lunar_feed_raw_row.product_code` where the Lunar payload parses as a **reprint line** via `printing_intelligence.parse_printing_from_lunar_row`:

| Lunar / title signal | `printing_kind` |
|----------------------|-----------------|
| `2ND PTG`, `3RD PTG`, `4TH PTG`, … | `REPRINT` + `printing_number` |
| `Nth printing` | `REPRINT` |
| Lunar `Printing` field ≥ 2 | `REPRINT` |
| `facsimile` | `FACSIMILE` |
| `anniversary` (+ edition / reissue) | `ANNIVERSARY_REISSUE` |

### Secondary signals (manual QA)

- `release_issue.original_release_date` is **NULL** but `release_date` equals a linked Lunar reprint `InStoreDate`.
- `release_variant.printing_release_date` is **NULL** while issue-level dates match Lunar reprint SKU.
- `current_ui_badge` empty but Lunar title contains `PTG` (pre-backfill code path).

### Out of scope for automatic backfill

- Variants with **no** `source_item_code` and **no** Lunar row (needs manual research).
- Issues where **first print** and **reprint** Lunar rows were both imported into the **same** issue group before P66-06 (backfill still moves dates using the reprint SKU; first-print dates must come from LoCG).

---

## 2. Per-issue repair algorithm (apply phase — not run yet)

For each candidate `release_issue_id`:

1. **Load** all `release_variant` rows for the issue.
2. **For each variant** with a Lunar reprint `product_code`:
   - Set `printing_number`, `printing_kind` from parser.
   - Set `printing_foc_date` / `printing_release_date` from Lunar `FOCDate` / `InStoreDate`.
   - Do **not** change cover/ratio identity fields.
3. **First-print schedule on the issue** (do not overwrite with reprint dates):
   - If `external_catalog_issue` is **MATCHED** to this issue and the external row is **not** a reprint title → set `original_release_date` (and `release_date`) from LoCG `release_date` when earlier than polluted issue date.
   - Else if `original_release_date` already set → restore `release_date` / `foc_date` from originals (`apply_reprint_issue_guard` semantics).
   - Else if issue-level dates **equal** the reprint variant’s Lunar dates → **clear** issue-level FOC/release (pollution removal) and flag `needs_locg_original_stamp = true`.
4. **Never** copy reprint `InStoreDate` onto `release_issue.release_date` after step 3.
5. **Recompute UI check** with `resolve_printing_schedule(issue, variants)` → expect non-empty `printing_badge` when a reprint variant has `printing_*` populated.

### Prerequisite on production (critical)

Many polluted rows (including **Tigress Island #1**) have **no** `external_catalog_issue` match in dev. Production may have LoCG parent `4029726` (`parent_issue_id` **3156** in capture traces). **Before or during backfill:**

1. Ensure LoCG parent **Tigress Island #1** exists in `external_catalog_issue` with `release_date = 2026-03-11`.
2. Run `rebuild_external_catalog_crosswalk` for the owner so `stamp_original_release_from_external` can set `original_release_date`.

Without LoCG, backfill can still move reprint dates to variants and clear polluted issue dates, but **first print will be null** until catalog stamp runs.

---

## 3. Tigress Island #1 — acceptance criteria

| Check | Expected after backfill + LoCG stamp |
|-------|--------------------------------------|
| `release_issue.id` (owner 1, dev) | **1278** |
| First-print `original_release_date` / `release_date` | **2026-03-11** (from LoCG/store) |
| 4th print `printing_release_date` (variant `0426IM8399`) | **2026-06-17** |
| 4th print `printing_foc_date` | **2026-05-25** |
| `printing_number` / `printing_kind` | **4** / **REPRINT** |
| UI badge (cross-system / decision panel) | **4th Printing** |
| Issue-level dates must **not** remain June 2026 | `release_date` = March 11, not June 17 |

### Dry-run snapshot (local `localhost:5433`, owner **1**, 2026-06-05)

Script: `apps/api/scripts/printing_intelligence_backfill_dry_run.py`  
Artifact: `data/printing_backfill_dry_run_owner1.json`

| Field | Dry-run value |
|-------|----------------|
| `release_issue_id` | 1278 |
| **Before** issue `release_date` / `foc_date` | 2026-06-17 / 2026-05-25 (polluted) |
| **Before** `original_*` | null |
| **Proposed variant** `0426IM8399` | 4th PTG → printing FOC 2026-05-25, release 2026-06-17 |
| `proposed_ui_badge_after_backfill` | **4th Printing** |
| `locg_first_print_release` (local DB) | **null** (no LoCG rows locally) |
| `needs_locg_original_stamp` | **true** |

**Interpretation:** Dry-run correctly splits the 4th print onto the variant and badge, but **March 11** requires LoCG crosswalk on the target environment. Production dry-run should be repeated after catalog sync.

---

## 4. Dry-run execution (safe — read-only)

```powershell
cd apps/api
python scripts/printing_intelligence_backfill_dry_run.py --owner-user-id 1 `
  --json-out ../../data/printing_backfill_dry_run_owner1.json
```

### Local dry-run summary (owner 1)

| Metric | Count |
|--------|------:|
| Candidates scanned (issue IDs with Lunar reprint SKU on a variant) | 129 |
| Proposals emitted | 129 |
| Issues where issue-level dates would change | 129 |

Review the JSON for false positives (e.g. trade paperbacks with high `printing_number`, facsimile editions).

### Production dry-run (required before apply)

1. Use read-only DB credentials or a **restored clone** if available.
2. Run the same script with `--owner-user-id <prod_owner>` (e.g. **1** for `ofoy@att.net`).
3. Confirm Tigress block matches section 3 (with LoCG present on prod).
4. Spot-check 10 highest-traffic series from cross-system recommendations.

**Do not** run an apply script on production until sign-off.

---

## 5. Planned apply phase (future — gated)

_Not implemented in this task._ Proposed shape:

| Step | Action |
|------|--------|
| A | Migration `20260612_0227` already deployed |
| B | LoCG calendar sync + crosswalk for affected owners |
| C | `printing_intelligence_backfill_apply.py --dry-run` (default) |
| D | `printing_intelligence_backfill_apply.py --apply --owner-user-id N` inside a single transaction per owner |
| E | Rebuild cross-system recommendations (read-only GET or controlled rebuild) |
| F | Verify Tigress + 5 random reprint cases in UI |

Apply rules will mirror section 2 and reuse `printing_intelligence` merge/guard helpers (same code path as Lunar import post-P66-06).

---

## 6. Validation checklist (post-apply)

- [ ] `pytest tests/test_printing_intelligence.py` green on release branch.
- [ ] Tigress Island #1: decision shows **Original release March 11**, **Printing release June 17**, badge **4th Printing**.
- [ ] No `release_issue` row where `release_date` equals a variant’s `printing_release_date` and `original_release_date` is null (except announced-first-print-only issues).
- [ ] Lunar re-import does not regress issue-level dates (`issue_import_is_reprint_only` guard).

---

## 7. References

- Implementation: `docs/P66_PHASE_6_PRINTING_INTELLIGENCE.md`
- Root-cause write-up: `docs/TIGRESS_ISLAND_DATA_INTEGRITY_INVESTIGATION.md`
- Dry-run tool: `apps/api/scripts/printing_intelligence_backfill_dry_run.py`
- Sample output: `data/printing_backfill_dry_run_owner1.json` (local; do not commit unless desired)
