# LoCG 2026 backfill — cumulative certification report

**Window:** Wednesday release weeks **2026-01-07** through **2026-08-26** (34 weeks).  
**Source of truth:** `data/locg_browser_capture/<date>/locg_capture_certification.json` (gitignored on disk; paths referenced for local reproduction).  
**Certification model:** LoCG-Certified-v1 queue coverage (`detail_pages_succeeded == final_parent_issue_queue_count`, variants persisted to `final_variant_queue_count`). Older artifacts without queue fields are labeled **legacy** below.

## Executive summary

| Metric | Value |
|--------|------:|
| Weeks with certification artifact | 34 |
| Weeks `passed: true` | 34 |
| Weeks `passed: false` | 0 |
| Weeks with queue-based cert fields | 19 |
| Total parent issues (queue or persisted succeeded) | 7831 |
| Total variants (queue or persisted) | 12640 |
| `skipped_missing_parent` (sum) | 0 |
| `variant_upsert_failure` (sum) | 0 |
| Cloudflare wait events (sum) | 0 |
| HTTP 429 count in cert artifacts | *not stored* (operational logs: 0 across backfill) |
| Total certified runtime (sum of `total_runtime_seconds`) | 12189.3 s (~3.39 h) |
| Average runtime per week | 358.5 s (~6.0 min) |

## Data quality notes

### Duplicate DOM `<li>` rows (queue coverage still passed)

- **2026-04-15:** duplicate parent `35`, variant `130` (queue parents `212`, variants `386`).
- **2026-05-13:** duplicate parent `33`, variant `132` (queue parents `239`, variants `415`).

### Lighter release weeks (assessment flag)

- **2026-07-29:** `317` list rows, `98` parents, `219` variants.

### Non-clean terminal exit but artifact PASS

Shell exit `4294967295` (force-stop) or missing JSON footer after certification; artifacts on disk remain authoritative.

- 2026-01-14
- 2026-01-28
- 2026-04-08
- 2026-04-22
- 2026-04-29
- 2026-05-06

### Legacy / incomplete captures (artifact `passed` but parent gap)

- **2026-06-10:** DOM parents `75`, detail succeeded `45` — **recapture recommended** under queue v1.
- **2026-06-17:** DOM parents `85`, detail succeeded `47` — **recapture recommended** under queue v1.

## Per-week detail

| Week | Cert | Schema | List `<li>` | Parents (queue) | Variants (queue) | Runtime (s) | CF | Notes |
|------|------|--------|-------------|-----------------|------------------|-------------|----|-------|
| 2026-01-07 | PASS | queue v1 | 696 | 303 | 393 | 446.9 | 0 | — |
| 2026-01-14 | PASS | queue v1 | 609 | 286 | 323 | 425.5 | 0 | non-clean shell exit |
| 2026-01-21 | PASS | queue v1 | 711 | 316 | 395 | 466.1 | 0 | — |
| 2026-01-28 | PASS | queue v1 | 671 | 316 | 355 | 467.1 | 0 | non-clean shell exit |
| 2026-02-04 | PASS | queue v1 | 725 | 311 | 414 | 462.0 | 0 | — |
| 2026-02-11 | PASS | queue v1 | 708 | 321 | 387 | 476.8 | 0 | — |
| 2026-02-18 | PASS | queue v1 | 787 | 310 | 477 | 458.0 | 0 | — |
| 2026-02-25 | PASS | queue v1 | 705 | 310 | 395 | 465.4 | 0 | — |
| 2026-03-04 | PASS | queue v1 | 795 | 297 | 498 | 446.6 | 0 | — |
| 2026-03-11 | PASS | queue v1 | 730 | 324 | 406 | 480.1 | 0 | — |
| 2026-03-18 | PASS | queue v1 | 853 | 288 | 565 | 430.1 | 0 | — |
| 2026-03-25 | PASS | queue v1 | 724 | 313 | 411 | 465.1 | 0 | — |
| 2026-04-01 | PASS | queue v1 | 628 | 301 | 327 | 443.5 | 0 | — |
| 2026-04-08 | PASS | queue v1 | 679 | 290 | 389 | 426.9 | 0 | non-clean shell exit |
| 2026-04-15 | PASS | queue v1 | 763 | 212 | 386 | 320.2 | 0 | dup DOM +35/+130; warning |
| 2026-04-22 | PASS | queue v1 | 820 | 281 | 539 | 447.4 | 0 | non-clean shell exit |
| 2026-04-29 | PASS | queue v1 | 677 | 331 | 346 | 635.0 | 0 | non-clean shell exit |
| 2026-05-06 | PASS | queue v1 | 672 | 278 | 394 | 470.9 | 0 | non-clean shell exit |
| 2026-05-13 | PASS | queue v1 | 819 | 239 | 415 | 347.2 | 0 | dup DOM +33/+132 |
| 2026-05-20 | PASS | legacy | 666 | 268 | 398 | 403.7 | 0 | legacy cert JSON |
| 2026-05-27 | PASS | legacy | 634 | 267 | 367 | 401.2 | 0 | legacy cert JSON |
| 2026-06-03 | PASS | legacy | 522 | 256 | 266 | 375.9 | 0 | legacy cert JSON |
| 2026-06-10 | PASS | legacy | 504 | 45 | 291 | 64.6 | 0 | legacy cert JSON; INCOMPLETE dom_parents=75 ok=45 |
| 2026-06-17 | PASS | legacy | 505 | 47 | 285 | 395.1 | 0 | legacy cert JSON; INCOMPLETE dom_parents=85 ok=47 |
| 2026-06-24 | PASS | legacy | 589 | 185 | 404 | 275.3 | 0 | legacy cert JSON |
| 2026-07-01 | PASS | legacy | 495 | 159 | 336 | 230.6 | 0 | legacy cert JSON |
| 2026-07-08 | PASS | legacy | 419 | 130 | 289 | 197.0 | 0 | legacy cert JSON |
| 2026-07-15 | PASS | legacy | 512 | 148 | 364 | 223.1 | 0 | legacy cert JSON |
| 2026-07-22 | PASS | legacy | 447 | 123 | 324 | 186.0 | 0 | legacy cert JSON |
| 2026-07-29 | PASS | legacy | 317 | 98 | 219 | 147.9 | 0 | lighter week; legacy cert JSON; warning |
| 2026-08-05 | PASS | legacy | 472 | 134 | 338 | 194.8 | 0 | legacy cert JSON |
| 2026-08-12 | PASS | legacy | 449 | 124 | 325 | 183.5 | 0 | legacy cert JSON |
| 2026-08-19 | PASS | legacy | 405 | 109 | 296 | 160.0 | 0 | legacy cert JSON |
| 2026-08-26 | PASS | legacy | 434 | 111 | 323 | 170.2 | 0 | legacy cert JSON |

## Operational follow-ups

1. **Remediation (open):** [LOCG_REMEDIATION_TASK_2026-06-10_17.md](LOCG_REMEDIATION_TASK_2026-06-10_17.md) — recapture **2026-06-10** and **2026-06-17** under queue-v1 before permanent platform sign-off.
2. Post-cert crosswalk: capture script skips `rebuild_external_catalog_crosswalk` by default; use `--run-crosswalk` only when needed (`--skip-crosswalk` in backfill docs).
3. Post-cert CLI hang mitigated: default path omits `per_issue_timings` from stdout JSON; use `--timing-table` for full dumps.
4. Regenerate this file after remediation (or any cert change): `python scripts/generate_locg_2026_backfill_certification_report.py` from `apps/api`.
