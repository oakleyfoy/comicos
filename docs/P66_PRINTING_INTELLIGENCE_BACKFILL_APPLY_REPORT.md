# P66 Printing Intelligence — Backfill Review & Apply Report

**Commit baseline:** `404510a` (P66 Printing Intelligence)  
**Plan:** [`P66_PRINTING_INTELLIGENCE_BACKFILL_PLAN.md`](P66_PRINTING_INTELLIGENCE_BACKFILL_PLAN.md)  
**Apply script:** `apps/api/scripts/p66_apply_printing_backfill.py`  
**Engine:** `apps/api/app/services/printing_backfill.py`

**Production (Render Postgres):** Owner **1** backfill **complete** — **129** HIGH-confidence issues applied (Tigress pilot + 10-issue sample + bulk **118**). Low-confidence rows **not** applied. Scoring / cross-system rebuild **not** run.

---

## 1. Production dry-run (owner `1`, Render — read-only)

**When:** 2026-06-05  
**Command:** `python scripts/p66_apply_printing_backfill.py --owner-user-id 1` (default dry-run, `apply: false`)  
**Artifact:** `data/p66_backfill_prod_dry_run.json`

| Metric | Count |
|--------|------:|
| Candidate issues scanned | 129 |
| Proposals | 129 |
| Variant rows to update | 235 |
| High-confidence | 129 |
| Low-confidence | 0 |
| **Writes** | **0** (`applied_count: 0`, `dry_run: true`) |

### Tigress Island #1 in production dry-run

| Check | Result |
|-------|--------|
| `release_issue_id` | **1278** (present in proposals + `tigress_island_1`) |
| `confidence` | **HIGH** |
| `proposed_ui_badge_after_backfill` | **4th Printing** |
| `known_first_print_release` | **2026-03-11** |
| `locg_first_print_release` | null (no matched LoCG row on prod at dry-run time) |

**Pre-pilot state on prod:** Issue already had `original_release_date` / `release_date` **2026-03-11**, but issue-level `foc_date` was still **2026-05-25** (reprint pollution). Variant **0426IM8399** already had printing fields and UI badge **4th Printing** in dry-run read path.

---

## 2. Production Tigress pilot apply (`--issue-id 1278`)

**Command:**
```powershell
python scripts/p66_apply_printing_backfill.py --owner-user-id 1 --issue-id 1278 --apply
```
**Artifact:** `data/p66_backfill_prod_tigress1278_apply.json`  
**Transaction:** 1 issue applied (`applied_count: 1`); no errors.

### Post-apply verification (live DB + decision engine, no cross-system rebuild)

| Check | Value |
|-------|--------|
| `release_issue` 1278 `release_date` | **2026-03-11** |
| `release_issue` 1278 `foc_date` | **null** (reprint FOC removed from issue row) |
| `release_issue` 1278 `original_release_date` | **2026-03-11** |
| Variant **2455** / code **0426IM8399** `printing_number` | **4** |
| `printing_kind` | **REPRINT** |
| `printing_release_date` | **2026-06-17** |
| `printing_foc_date` | **2026-05-25** |
| `resolve_printing_schedule` badge | **4th Printing** |
| `decision_for_cross_system` (existing snapshot row) | release **2026-03-11**, printing release **2026-06-17**, printing FOC **2026-05-25**, badge **4th Printing** |

LoCG stamp: still **null** on match table; first print anchored via **`KNOWN_FIRST_PRINT_RELEASE`** until LoCG parent **4029726** is synced and crosswalked.

---

## 3. Production sample apply (10 HIGH-confidence issues)

**When:** 2026-06-05  
**Script:** `apps/api/scripts/p66_production_sample_apply.py`  
**Command:**
```powershell
cd apps/api
python scripts/p66_production_sample_apply.py --apply --json-out ../../data/p66_prod_sample10_apply.json
```
**Artifact:** `data/p66_prod_sample10_apply.json`  
**Selection:** Fixed list across publishers/series (excludes Tigress `1278`, already piloted). All **HIGH** confidence via pollution fingerprint (issue `release_date` / `foc_date` matched Lunar reprint SKU dates). No LoCG / known-first-print anchor on these rows — apply **cleared** polluted issue-level FOC/release to **null** and stamped **printing_*** on the reprint Lunar variant only.

| issue_id | title | variant SKU | badge | current issue release / FOC | proposed issue release / FOC | variant printing release / FOC | confidence reason |
|---------:|-------|-------------|-------|------------------------------|------------------------------|--------------------------------|-------------------|
| 7 | Absolute Batman #23 | 0626DC0016 | Anniversary Reissue | 2026-08-12 / 2026-07-20 | null / null | 2026-08-12 / 2026-07-20 | release + FOC match Lunar reprint |
| 40 | Art of Goosebumps HC #1 | 0626DE0653 | 2nd Printing | 2026-08-12 / 2026-07-27 | null / null | 2026-08-12 / 2026-07-27 | release + FOC match Lunar reprint |
| 38 | Archie 85th Anniversary … Betty & Veronica #1 | 0626AC0531 | Anniversary Reissue | 2026-08-26 / 2026-08-03 | null / null | 2026-08-26 / 2026-08-03 | release + FOC match Lunar reprint |
| 79 | Blitz TP #1 | 0626AZ0477 | 2nd Printing | 2026-08-05 / 2026-06-29 | null / null | 2026-08-05 / 2026-06-29 | release + FOC match Lunar reprint |
| 132 | Cul-De-Sac Anniversary Edition #1 | 0626BD0552 | Anniversary Reissue | 2026-08-12 / 2026-07-13 | null / null | 2026-08-12 / 2026-07-13 | release + FOC match Lunar reprint |
| 161 | Devil's Due Presents: Hack/Slash-Mercy Sparx #1 | 0626MP0937 | Anniversary Reissue | 2026-08-05 / 2026-06-29 | null / null | 2026-08-05 / 2026-06-29 | release + FOC match Lunar reprint |
| 391 | Mask #3 | 0626IM0377 | 2nd Printing | 2026-08-05 / 2026-07-13 | null / null | 2026-08-05 / 2026-07-13 | release + FOC match Lunar reprint |
| 459 | Prince Valiant HC #31 | 0626FB0857 | Anniversary Reissue | 2026-08-26 / 2026-07-20 | null / null | 2026-08-26 / 2026-07-20 | release + FOC match Lunar reprint |
| 462 | PS Artbooks Chamber of Chills HC … #5 | 0626PS1069 | Facsimile | 2026-08-19 / 2026-06-29 | null / null | 2026-08-19 / 2026-06-29 | release + FOC match Lunar reprint |
| 681 | Adventure Time Pride Special 2026 #1 | 0426ON0943 | Anniversary Reissue | 2026-06-03 / 2026-05-11 | null / null | 2026-06-03 / 2026-05-11 | release + FOC match Lunar reprint |

**Transaction:** `applied` length **10**; `dry_run: false`; no `fatal_error`.

### Post-apply verification (live DB)

| Check | Result |
|-------|--------|
| Printing fields on variants | Reprint SKUs received `printing_kind`, `printing_number` (where applicable), `printing_foc_date`, `printing_release_date`; non-reprint variants on multi-variant issues unchanged (`FIRST_PRINT`, null printing dates). |
| Issue-level FOC/release vs reprints | All 10 issues: `release_date` and `foc_date` **null** after apply (reprint schedule no longer on issue row). |
| `resolve_printing_schedule` badge | Matches detected badge for all 10 (`schedule_badge` in artifact). |
| Decision `printing_badge` | **7/10** with existing `cross_system_recommendation` row by title: badge matches (e.g. 7, 40, 79, 132, 391, 459, 462). **3/10** `decision_badge: null` (38, 161, 681) — no matching cross-system snapshot row; schedule path still shows badge. |
| First-print metadata lost | **No** — all `first_print_preserved: true`; none had `original_release_date` set before apply. Tigress (`1278`) originals unchanged from prior pilot. |

**Note:** Until LoCG sync stamps first-print dates, cleared issue-level dates are intentional for these pollution-only HIGH rows; UI/decision should use variant printing dates + badge for reprint scheduling.

---

## 4. Dry-run findings (owner `1`, local PostgreSQL — reference)

Source: `python scripts/p66_apply_printing_backfill.py --owner-user-id 1`  
Artifact: `data/p66_backfill_apply_dry_run_owner1.json`

| Metric | Count |
|--------|------:|
| Candidate issues scanned | 129 |
| Proposals (reprint Lunar SKU on variant) | 129 |
| Variant rows to update | 235 |
| **High-confidence** (auto-apply eligible) | **129** |
| **Low-confidence** (manual review) | **0** |

### High-confidence criteria (automatic apply)

All of the following must hold:

1. At least one `release_variant.source_item_code` maps to a Lunar row parsed as **reprint / facsimile / anniversary**.
2. **Pollution fingerprint:** `release_issue.release_date` or `foc_date` equals the Lunar reprint `InStoreDate` / `FOCDate` on that SKU, **or** a trusted first-print date exists (`external_catalog` match or `KNOWN_FIRST_PRINT_RELEASE`).
3. At most one distinct reprint `printing_release_date` across variants on the issue.
4. Facsimile / anniversary lines without a pollution fingerprint are **LOW** (skipped unless `--include-low-confidence`).

### Low-confidence / manual review (none in current owner-1 scan)

Would be flagged when:

- Reprint Lunar row exists but issue dates do **not** match reprint dates and there is no LoCG / known first-print anchor.
- Multiple reprint variants disagree on `InStoreDate`.
- Facsimile or anniversary SKU with no clear issue-level pollution.

Re-run dry-run on **production** after LoCG sync; low-confidence count may be &gt; 0 where catalog is incomplete.

---

## 5. Tigress Island #1 status (local + prod)

| Field | Value |
|-------|--------|
| `release_issue_id` (local owner 1) | **1278** |
| Lunar SKU | `0426IM8399` — `4TH PTG` |
| **Before** issue dates | release `2026-06-17`, FOC `2026-05-25` (polluted) |
| **After (proposed / applied locally)** | `original_release_date` / `release_date` **2026-03-11** (known retail) |
| Variant printing release | **2026-06-17** |
| Variant printing FOC | **2026-05-25** |
| `printing_number` / `printing_kind` | **4** / **REPRINT** |
| UI badge after apply | **4th Printing** |
| Confidence | **HIGH** (`known_first_print_release` + pollution fingerprint) |

Known first-print anchor: `KNOWN_FIRST_PRINT_RELEASE[("Image Comics", "Tigress Island", "1")] = 2026-03-11` (from store/LoCG investigation). LoCG row still absent locally; production should prefer matched `external_catalog_issue` when present.

Local apply proof: `data/p66_backfill_apply_tigress1278.json` (`--apply --issue-id 1278`).

---

## 6. Apply script safeguards

```text
apps/api/scripts/p66_apply_printing_backfill.py
```

| Flag | Behavior |
|------|----------|
| *(default)* | **Dry-run** — proposals only, **no writes** |
| `--apply` | Required to persist changes |
| `--owner-user-id` | Limit to one owner |
| `--issue-id` | Single-issue targeted run (e.g. Tigress `1278`) |
| `--limit` | Cap number of issues processed |
| `--force` | Allow overwriting existing `original_release_date` / `original_foc_date` |
| `--include-low-confidence` | Apply LOW rows (default: **skip**) |
| `--json-out` | Write full before/after report |

**Transaction:** `--apply` runs inside `session.begin()`; any exception rolls back the whole batch.

**Original date protection:** If `original_release_date` or `original_foc_date` is already set, apply restores issue schedule via `apply_reprint_issue_guard` and does **not** change originals unless `--force`.

**Scoring / ranking:** No recommendation or scoring code paths are modified.

---

## 7. Production bulk apply (remaining HIGH-confidence)

**When:** 2026-06-05  
**Script:** `apps/api/scripts/p66_production_bulk_apply.py`  
**Command:**
```powershell
cd apps/api
python scripts/p66_production_bulk_apply.py --apply --json-out ../../data/p66_prod_bulk_apply.json
```
**Scope:** Owner `1`, **HIGH** only (`high_confidence_only=True`), excludes prior **11** applied ids (`1278` + sample ten). **No** `--include-low-confidence`. **No** recommendation rebuild.

### Run totals

| Metric | Count |
|--------|------:|
| **Applied** (this run) | **118** |
| **Skipped** (low-confidence / no proposal) | **0** |
| **Failed** (apply errors) | **0** |
| **Prior applied** (pilot + sample) | **11** |
| **Owner-1 HIGH backfill total** | **129** |

### Publisher breakdown (issues applied this run)

| Publisher | Issues |
|-----------|-------:|
| Image Comics | 31 |
| DC Comics | 29 |
| DYNAMITE Entertainment | 14 |
| Archie Comics Publications | 5 |
| Massive Publishing | 5 |
| BAD IDEA | 4 |
| Fantagraphics | 4 |
| Oni Press | 3 |
| PS Artbooks | 3 |
| Titan Comics | 3 |
| ABLAZE | 2 |
| Avery Hill Publishing | 2 |
| Hermes Press | 2 |
| Papercutz | 2 |
| Prana Publishers | 2 |
| Clover Press | 1 |
| Drawn & Quarterly | 1 |
| Stranger Comics | 1 |
| Tripwire | 1 |
| TwoMorrows Publishing | 1 |
| Vault Comics | 1 |
| Wake Entertainment | 1 |

### Printing-type breakdown (reprint **variant** rows updated this run)

| `printing_kind` | Variant rows |
|-----------------|-------------:|
| ANNIVERSARY_REISSUE | 82 |
| FACSIMILE | 70 |
| REPRINT | 56 |
| **Total variant updates** | **208** |

### Post-bulk verification

| Check | Result |
|-------|--------|
| Issue-level reprint pollution | **129/129** pass after residual fixup (see below) |
| Variant `printing_*` populated | **129/129** pass |
| `resolve_printing_schedule` badges | Present on all scanned reprint issues |
| First-print metadata | No `original_release_date` / `original_foc_date` overwrites (`--force` not used) |

**Residual multi-SKU edge case:** Issues **568** and **1488** retained issue `foc_date` matching one of several anniversary variant SKUs after the bulk transaction. Cleared via `p66_fixup_residual_issue_pollution.py --apply` (issue rows only; not low-confidence backfill). Issue **955** retains `release_date` = `original_release_date` **2026-06-17** (stamped first-print anchor — not reprint pollution).

**Engine follow-up (code):** `apply_proposal` now clears issue dates that match **any** reprint variant in the proposal (future applies).

---

## 8. Tests

```powershell
cd apps/api
python -m pytest tests/test_printing_intelligence.py -q
```

**Result:** 6 passed (post-bulk re-run).

---

## 9. Artifacts (optional commit)

| File | Purpose |
|------|---------|
| `data/p66_backfill_apply_dry_run_owner1.json` | Local owner-1 dry-run |
| `data/p66_backfill_apply_tigress1278.json` | Local `--apply` for issue 1278 |
| `data/p66_backfill_prod_dry_run.json` | **Production** owner-1 dry-run |
| `data/p66_backfill_prod_tigress1278_apply.json` | **Production** Tigress pilot apply |
| `data/p66_prod_sample10_apply.json` | **Production** 10-issue sample apply + verify |
| `data/p66_prod_bulk_apply.json` | **Production** bulk apply (118) + verification block |
| `data/p66_prod_bulk_dry.json` | Pre-bulk dry-run for excluded-11 scope |

Do not commit `data/` unless your release process requires it.

---

## 10. Certification

### P66 Printing Intelligence Backfill: **COMPLETE**

| Criterion | Status |
|-----------|--------|
| Production dry-run (129 HIGH, 0 LOW) | Done |
| Tigress pilot `1278` | Done |
| 10-issue diverse sample | Done |
| Remaining HIGH-confidence bulk (118) | Done |
| Low-confidence / manual-review rows | **Not applied** |
| Scoring / ranking | **Unchanged** |
| Cross-system recommendation rebuild | **Not run** |
| Owner `1` reprint-candidate verification (129 issues) | **0 failures** |

**Signed-off scope:** Printing backfill for owner **1** on Render production Postgres. Further owners or LoCG-first-print stamping remain operational follow-ups, not blockers for this certification.
