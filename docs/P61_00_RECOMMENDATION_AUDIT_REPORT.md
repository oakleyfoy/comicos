# P61-00 — Recommendation audit report

**Generated:** 2026-06-05 (UTC)  
**Test owner:** `ofoy@att.net` (user id **41**)  
**Database:** local `DATABASE_URL` (`postgresql+pg8000://…/comic_os`)  
**Ranking source:** Cross-system Top Recommendations (`build_cross_system_candidates` → priority/confidence spread → persist snapshot)

Related: [P61_00_GET_REFRESH_INVENTORY.md](P61_00_GET_REFRESH_INVENTORY.md)

---

## 1. Executive summary

| Check | Result |
|--------|--------|
| Test owner persisted cross-system rows | **0** (no snapshot) |
| Test owner `ReleaseIssue` rows | **0** |
| Top 20 for test owner (persisted) | **Not available** — pipeline not seeded |
| Top 20 (live candidate pool, same DB) | **Not run** — empty release catalog for owner 41 |
| Reference candidate pool (owner 40, lunar reimport fixture) | **119** candidates; top priority spread **98.0 → 77.2** (~20.8) |
| Youngblood in recommendation pool | **Absent** (classification **A** — not in feed/catalog) |
| P61 GET refresh risk (cross-system) | **Open** — `GET /cross-system-recommendations` still calls `refresh_and_list_*` |

**Action for production-quality audit on test owner:** run `scripts/seed_production_recommendations.py` (or production `DATABASE_URL`), then `scripts/verify_cross_system_owner.py --email ofoy@att.net --rebuild --top 20`.

---

## 2. Test owner — persisted Top 20

Read-only verification (`verify_cross_system_owner.py`, no rebuild):

| Field | Value |
|--------|------:|
| `cross_system_recommendation_row_count` | 0 |
| `latest_snapshot_size` | 0 |
| `daily_collector_action_row_count` | 0 |
| `spread_verification.pass` | false (no rows) |
| `top_20_score_trace` | `[]` |

Until release ingest + unified/daily/cross-system rebuild runs for owner **41**, the UI and audit APIs have nothing to rank.

---

## 3. Scoring breakdown export (complete fields)

When the candidate pool is non-empty, each recommendation row exposes:

| Layer | Fields |
|--------|--------|
| **Persisted** | `priority_score`, `confidence_score`, `recommendation_rank`, `recommendation_type`, `title` |
| **Priority trace** | `raw_priority_score` → `normalized_priority_score` → `computed_priority_score` (must match persisted within tolerance) |
| **Confidence trace** | `raw_confidence_score` → `normalized_confidence_score` → `computed_confidence_score` |
| **Collector significance** | `base_score`, `franchise_score`, `publisher_score`, `creator_score`, `milestone_score`, `homage_score`, `audience_score`, `collector_ranking_boost`, `final_pre_spread_score` |

Modules: `recommendation_priority_spread`, `recommendation_priority_spread` (confidence), `recommendation_intelligence_enrichment` (collector boost), pipeline epoch **11**.

### Reference Top 20 (owner 40 candidate pool, read-only)

Illustrates full breakdown when catalog exists (not test owner 41). Sorted live candidates, not latest DB snapshot (snapshot had only **3** stale rows).

| Rank | Title | Type | Priority | Conf | Raw→Norm priority | Final pre-spread | Boost |
|------|-------|------|----------|------|-------------------|------------------|-------|
| 1 | Transformers The Movie 40th Anniversary Edition #3 | PREORDER | 98.0 | 0.882 | 91.19→98.0 | 91.19 | 6.19 |
| 2 | Batman Bad Seeds - Sunset #1 | PREORDER | 97.5 | 0.918 | 89.19→97.5 | 89.19 | 4.19 |
| 3 | Witchblade Vampirella #1 | PREORDER | 96.8 | 0.894 | 88.83→96.8 | 88.83 | 3.83 |
| 4 | Batman & Robin Year One - Dynamic Duos #1 | PREORDER | 96.3 | 0.960 | 86.19→96.3 | 86.19 | 4.19 |
| 5 | Vampirella Vs. Red Sonja: Red City #1 | PREORDER | 92.4 | 0.906 | 85.83→92.4 | 85.83 | 3.83 |
| 6 | Archie Comics 85th Anniversary Presents: Betty & Veronica Fashion Pages #1 | PREORDER | 91.7 | 0.838 | 90.15→91.7 | 90.15 | 5.15 |
| 7 | Batman #12 | PREORDER | 89.5 | 0.817 | 89.19→89.5 | 89.19 | 4.19 |
| 8 | Absolute Batman #23 | PREORDER | 89.0 | 0.805 | 89.19→89.0 | 89.19 | 4.19 |
| 9 | Batman/Superman World's Finest #54 | PREORDER | 86.3 | 0.781 | 88.34→86.3 | 88.34 | 3.34 |
| 10 | Gargoyles #1 | PREORDER | 85.7 | 0.793 | 88.73→85.7 | 88.73 | 3.73 |
| 11 | DF Marvel Comics Commissioned Cover Art… Spider-Man Sketch #1 | PREORDER | 84.2 | 0.760 | 89.14→84.2 | 89.14 | 4.14 |
| 12 | G.I. Joe #25 | PREORDER | 81.6 | 0.638 | 91.09→81.6 | 91.09 | 6.09 |
| 13 | Invincible Universe Battle Beast #12 | PREORDER | 81.0 | 0.734 | 88.59→81.0 | 88.59 | 3.59 |
| 14 | Marvel X-men Jigsaw Puzzle and Trivia #1 | PREORDER | 80.5 | 0.710 | 89.0→80.5 | 89.0 | 4.00 |
| 15 | Gunslinger Spawn #57 | PREORDER | 79.9 | 0.722 | 87.95→79.9 | 87.95 | 2.95 |
| 16 | Street Fighter Masters Juri #1 | PREORDER | 79.4 | 0.698 | 88.58→79.4 | 88.58 | 3.58 |
| 17 | Spawn The Curse Of Sherlee Johnson #7 | PREORDER | 78.8 | 0.686 | 87.95→78.8 | 87.95 | 2.95 |
| 18 | Spawn Scorched #54 | PREORDER | 78.3 | 0.662 | 87.95→78.3 | 87.95 | 2.95 |
| 19 | Invincible Universe Capes #10 | PREORDER | 77.7 | 0.674 | 87.74→77.7 | 87.74 | 2.74 |
| 20 | Transformers #35 | PREORDER | 77.2 | 0.614 | 89.0→77.2 | 89.0 | 4.00 |

**Observation:** `collector_significance_boost` dominated build time (~**118–122 s** per candidate build on this DB). Priority/confidence spread and sort are fast once candidates exist.

---

## 4. Youngblood ranking investigation

### 4.1 Release feed (`audit_release_feed_youngblood.py`, owner 41)

| Finding | Value |
|---------|--------|
| Classification | **A** — absent from source feed / not imported to catalog |
| Lunar raw rows matching Youngblood | **0** (50k row scan) |
| Owner `ReleaseIssue` rows matching Youngblood | **0** |
| Vol 6 / #100 shaped rows | **none** |

**Conclusion:** Youngblood cannot appear in Top Recommendations until it exists in the owner release catalog (Lunar ingest and/or LoCG crosswalk path). Ranking logic is not the blocker.

### 4.2 Candidate pool (owner 40, 119 forward-window candidates)

- **`youngblood_in_pool`:** 0 titles  
- No rank to explain for Youngblood #100 / Vol 6 on this database.

### 4.3 Historical test context

- Parser/fixture tests use **Youngblood #100** as a sample title (`test_locg_parser`, crosswalk tests).  
- `test_recommendation_signal_bucket_fast` expects **Youngblood** in fast signal bucket when mocked — not live DB state.  
- Volume classification audit documents **Youngblood Vol 6 #100** vs single-issue **Youngblood #100** separation.

**Remediation path for Youngblood visibility:** Lunar/LoCG ingest → `ReleaseIssue` → unified/daily → cross-system rebuild → verify title in `build_cross_system_candidates` output.

---

## 5. P61 alignment (read vs refresh)

From [P61_00_GET_REFRESH_INVENTORY.md](P61_00_GET_REFRESH_INVENTORY.md), industry/spec GET endpoints were moved to **read persisted + POST refresh**. Recommendation layer **still regenerates on some GETs**:

| Endpoint | Behavior |
|----------|----------|
| `GET /api/v1/cross-system-recommendations` | **`refresh_and_list_latest_cross_system_recommendations`** (side-effect rebuild) |
| `GET /api/v1/cross-system-recommendations/latest` | read persisted snapshot only |
| `GET /api/v1/cross-system-recommendations/summary` | **`generate_cross_system_recommendations`** |

Audit tooling uses **`refresh=False`** on ranking diagnostics to avoid implicit rebuild (matches P61 intent for inspection).

---

## 6. Recommendation V3 — requirements (derived)

No `V3` module exists yet. Proposed requirements from this audit and P61:

1. **Read path separation (P61 completion)**  
   - Default GET list = persisted snapshot only (`/latest` semantics or `refresh=false` default).  
   - Explicit `POST /cross-system-recommendations/run` (or reuse existing rebuild POSTs) for regeneration.

2. **Owner bootstrap contract**  
   - Document/enforce: test owner must have `ReleaseIssue` + at least one successful cross-system snapshot before certification.  
   - Empty owner returns structured `NOT_READY` (not silent empty list).

3. **Scoring transparency API**  
   - Stable JSON schema for full breakdown (priority trace + intelligence components + decision engine outputs).  
   - Align persisted snapshot row count with ranked candidate count (fix stale partial snapshots).

4. **Performance**  
   - Cache or batch `collector_significance_boost` (dominant cost in cross-system build).  
   - Optional skip crosswalk on ingest-only jobs (see LoCG `--skip-crosswalk` pattern).

5. **Catalog coverage diagnostics**  
   - First-class “title not in pool” report (Youngblood class A/B/C/D) linked from recommendation audit.

6. **Decision layer integration**  
   - V2 per-issue scores + **Decision Engine V1** (`compute_recommendation_decision`) should attach to cross-system rows for Top N, not only spec/PREORDER silos.

7. **Certification gates**  
   - Spread verification (`distinct_score_count`, `top_20_score_spread`, confidence diversity) as automated PASS/FAIL on owner rebuild.  
   - Block “permanently complete” ingestion/ranking sign-off when spread_verification fails or pool &lt; 20.

---

## 7. Commands

```bash
cd apps/api
export DATABASE_URL=...

# Test owner (read-only persisted audit)
python scripts/verify_cross_system_owner.py --email ofoy@att.net --top 20

# Full rebuild + top 20 (after seed / production DB)
python scripts/verify_cross_system_owner.py --email ofoy@att.net --rebuild --top 20

# Youngblood feed classification
python scripts/audit_release_feed_youngblood.py --email ofoy@att.net

# JSON export (extend for CI)
python scripts/p61_00_recommendation_audit.py --email ofoy@att.net --top 20
```

---

## 8. Artifacts

| Artifact | Purpose |
|----------|---------|
| `apps/api/scripts/p61_00_recommendation_audit.py` | JSON export for audits |
| `apps/api/scripts/verify_cross_system_owner.py` | Owner snapshot + spread verification |
| `apps/api/scripts/audit_release_feed_youngblood.py` | Youngblood feed classification |
| `app/services/recommendation_ranking_diagnostics.py` | Ranking audit + intelligence attach |
