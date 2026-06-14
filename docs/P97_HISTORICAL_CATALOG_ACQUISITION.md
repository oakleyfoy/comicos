# P97 Historical Catalog Acquisition

ComicVine bulk import is **offline** (feeder only). Scan-time recognition uses the local catalog, not live ComicVine calls.

## ComicVine CLI: volume-only vs issue + cover

Run from `apps/api` so `CATALOG_STORAGE_ROOT` paths resolve.

### Volume-only import (series metadata)

Imports **publishers and series** (ComicVine volumes). Does **not** create `catalog_issue` or `catalog_image` rows.

```powershell
python scripts/p97_import_comicvine_catalog.py --publisher Marvel --strict-publisher --limit 25 --sleep-seconds 1
```

- Job type: `COMICVINE` / `volumes`
- `config.import_issues` is `false`
- Use when you only need series/volume metadata or will import issues in a later pass

### Issue + cover import (full catalog rows)

Adds **`--import-issues`**. After the volume phase completes, a **separate** job runs:

- Job type: `COMICVINE` / `volume_issues` (child of the volume job via `parent_volume_job_id`)
- Creates/updates **`catalog_issue`** and **`catalog_variant`**
- Creates **`catalog_image`** rows with `download_status=pending` when a cover URL exists (ready for `p97_harvest_catalog_covers.py`)

```powershell
python scripts/p97_import_comicvine_catalog.py --series-name Spawn --limit 1 --import-issues --sleep-seconds 1
```

The script prints `run_config` at start (including `import_issues`) and issue/cover counters when `--import-issues` is set.

If `--import-issues` is set but no issue import phase runs (or zero issue work), the script exits non-zero with:

`ERROR: --import-issues requested but no issue import phase ran.`

### Resume and scope

Resume cursors are scoped by **publisher**, **series_name**, **strict_publisher**, and **import_issues**. Changing publisher or toggling `--import-issues` starts a new scope (does not reuse another run’s cursor).

### Typical pipeline

```powershell
python scripts/p97_import_comicvine_catalog.py --limit 100 --import-issues --sleep-seconds 1
python scripts/p97_harvest_catalog_covers.py --limit 100
python scripts/p97_generate_catalog_fingerprints.py --limit 100
python scripts/p97_generate_catalog_ocr.py --limit 100
```

### English / US-first quality gate (P97-11)

By default, ComicVine volume import applies an **English-first, US-primary publisher gate**. International license publishers (Panini, Delcourt, Egmont, etc.) are **skipped** unless you pass:

```powershell
python scripts/p97_import_comicvine_catalog.py --allow-international-editions ...
```

`run_config` includes `international_editions_allowed: false` by default. Completion output includes `publisher_quality_summary` with counts for `PRIMARY`, `ACCEPTABLE`, `LOW_PRIORITY`, and `REJECTED` (skipped volumes).

Audit existing catalog (no deletes):

```powershell
python scripts/p97_audit_catalog_publishers.py
```

Writes `data/p97/catalog_international_audit.csv` under `CATALOG_STORAGE_ROOT`.

## Overnight catalog population (one command)

From `apps/api`, set execution policy for the session if needed and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\p97_overnight_catalog_run.ps1
```

### Continuous overnight mode (P97-16)

The overnight runner uses **continuous acquisition** (default **12 hour** target runtime, **9 hour** minimum intent). The first **3 hours** target high-value **series** imports; the **remaining time** runs **publisher-wide** acquisition to maximize catalog growth.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\p97_overnight_catalog_run.ps1
```

What it does:

- Runs continuously up to the target runtime (default 12h)
- **Series phase (up to 3h):** 150+ high-value US collector series (`--limit 1000 --import-issues` per attempt)
- **Publisher phase (remainder of run):** `--publisher` + `--strict-publisher` rotation across major US publishers
- Ends series phase early if a full pass returns zero candidates, or when **SeriesPhaseMaxHours** (3) elapses—whichever comes first
- Resumes each series using `data/p97/overnight_series_progress.json` (`last_offset` + `--resume` for scoped DB cursors)
- Handles ComicVine **HTTP 420** with 15-minute cooldown (up to 6 retries per series)
- Runs harvest / fingerprint / OCR post-processing every **3 hours** and once at shutdown
- Writes `data/p97/overnight_catalog_run.log` and `data/p97/overnight_catalog_run_summary.json`
- Does **not** pass `--allow-international-editions` (English/US-first gate remains on)

Dry-run (config + safety checks only):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\p97_overnight_catalog_run.ps1 -WhatIf
```

**Series-name imports:** ComicVine search pagination uses `--offset` stored in progress JSON; `--resume` keeps scoped volume jobs aligned in Postgres after restarts.

### Publisher acquisition mode (after series phase)

After the **series phase** ends, the runner switches to **publisher acquisition mode** for the rest of the target runtime. The series phase stops when either:

- elapsed runtime reaches **SeriesPhaseMaxHours** (default **3**), or
- a full priority-series pass returns **zero** new volume candidates

Publisher mode then runs until **TargetRuntimeHours** (default **12**).

- Uses `--publisher "<NAME>" --strict-publisher` (volumes API filter, not series search)
- Does **not** pass `--allow-international-editions`
- Resumes per-publisher `last_offset` in `data/p97/overnight_series_progress.json` (`publishers` section)
- Rotates continuously through: Marvel, DC Comics, Image, Dark Horse, Boom, IDW, Dynamite, Valiant, Skybound, Titan, Oni, Aftershock, AWA, Mad Cave, DSTLRY

Progress file fields: `acquisition_phase` (`series` | `publisher`), `series_exhausted`, `series`, `publishers`.

### Legacy one-shot behavior

The script previously ran a single pass over ~19 series then post-processed once. Continuous mode replaces that with a long-running loop and periodic checkpoints.
