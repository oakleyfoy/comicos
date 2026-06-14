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
