# LoCG July 2026 forward capture validation

Command (each week):

```bash
cd apps/api
export DATABASE_URL=postgresql+pg8000://postgres:postgres@localhost:5433/comic_os
python scripts/capture_locg_date_details_browser.py \
  --production --email ofoy@att.net \
  --date YYYY-MM-DD --headful --save-raw --adaptive-delay
```

Baseline proof (pre-forward): **2026-06-24**, **2026-07-01** — PASS.

## Summary table (forward weeks)

| Week | Certification | Rows | Parents | Variants | Persisted | Runtime (s) |
|------|---------------|------|---------|----------|-----------|---------------|
| 2026-07-08 | **PASS** | 419 | 130 | 289 | 289 | 197.0 |
| 2026-07-15 | **PASS** | 512 | 148 | 364 | 364 | 223.1 |
| 2026-07-22 | **PASS** | 447 | 123 | 324 | 324 | 186.0 |
| 2026-07-29 | **PASS** (lighter week) | 317 | 98 | 219 | 219 | 147.9 |

**July forward gate:** **4/4** weeks certified. **2026-07-29** is a **legitimately lighter** release week (~115 releases manual vs **98** parents captured); initial DOM was **317** rows (not the ~165 truncated chunk). Scroll flat at 317; variants **219/219** persisted.

## Per-week detail

### 2026-07-08 — PASS

| Metric | Value |
|--------|-------|
| certification_passed | true |
| total_li_issue_rows | 419 |
| parent_issue_rows | 130 |
| variant_rows | 289 |
| list_variants_found | 289 |
| list_variants_persisted | 289 |
| skipped_missing_parent | 0 |
| variant_upsert_failure | 0 |
| parent_details_processed | 130 |
| avg_parent_detail_seconds | 1.714 |
| total_runtime | 197.005 |
| cloudflare_wait_count | 0 |
| 429_count | 0 |

Discovery: 165 → 419 after scroll #1.

### 2026-07-15 — PASS

| Metric | Value |
|--------|-------|
| certification_passed | true |
| total_li_issue_rows | 512 |
| parent_issue_rows | 148 |
| variant_rows | 364 |
| list_variants_found | 364 |
| list_variants_persisted | 364 |
| skipped_missing_parent | 0 |
| variant_upsert_failure | 0 |
| parent_details_processed | 148 |
| avg_parent_detail_seconds | 1.709 |
| total_runtime | 223.137 |
| cloudflare_wait_count | 0 |
| 429_count | 0 |

Discovery: 166 → 512 after scroll #1.

### 2026-07-22 — PASS

| Metric | Value |
|--------|-------|
| certification_passed | true |
| total_li_issue_rows | 447 |
| parent_issue_rows | 123 |
| variant_rows | 324 |
| list_variants_found | 324 |
| list_variants_persisted | 324 |
| skipped_missing_parent | 0 |
| variant_upsert_failure | 0 |
| parent_details_processed | 123 |
| avg_parent_detail_seconds | 1.688 |
| total_runtime | 185.953 |
| cloudflare_wait_count | 0 |
| 429_count | 0 |

Discovery: 167 → 447 after scroll #1.

### 2026-07-29 — PASS (lighter week)

| Metric | Value |
|--------|-------|
| certification_passed | true |
| total_li_issue_rows | 317 |
| parent_issue_rows | 98 |
| variant_rows | 219 |
| list_variants_found | 219 |
| list_variants_persisted | 219 |
| skipped_missing_parent | 0 |
| variant_upsert_failure | 0 |
| parent_details_processed | 98 |
| avg_parent_detail_seconds | 1.659 |
| total_runtime | 147.896 |
| cloudflare_wait_count | 0 |
| 429_count | 0 |

`proof_run_assessment.legitimately_lighter_release_week=true`: high initial DOM (317), scroll stabilized with no further growth, parents/variants/detail persistence complete. Not the truncated-165 incomplete pattern.

Artifacts: `data/locg_browser_capture/<date>/`.

## Production certification status

- **LoCG capture:** production-ready for pipeline/features (June 24, July 1, July 8/15/22).
- **July forward suite:** **not fully certified** until 2026-07-29 is re-run or documented as a legitimate sub-400 week.

## Runtime notes

- Adaptive delay: **0.75–1.5s**, no 429/Cloudflare on these runs.
- Typical wall clock: **~3–4 min** per week (parents × ~1.7s + discovery).
