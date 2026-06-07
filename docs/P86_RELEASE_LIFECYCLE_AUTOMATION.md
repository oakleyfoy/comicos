# P86 Release Lifecycle Automation

ComicOS refreshes League of Comic Geeks (LoCG) release data at four lifecycle points instead of scraping arbitrary future dates.

## Lifecycle model

| Offset from anchor Wednesday `T` | Capture date | Stage | Purpose |
|----------------------------------|--------------|-------|---------|
| T − 8 weeks | post-release cleanup | `POST_RELEASE_CLEANUP` | Late corrections, covers, creators, variants |
| T | release day | `RELEASE_DAY_REFRESH` | Final issue list, variants, metadata |
| T + 8 weeks | pre-order window | `PREORDER_ACCURACY` | FOC / pre-order intelligence, variants |
| T + 12 weeks | early discovery | `EARLY_DISCOVERY` | New #1s, milestones, future pull list seed |

Example: `T = 2026-06-10` → captures `2026-04-15`, `2026-06-10`, `2026-08-05`, `2026-09-02`.

## Weekly schedule

Every **Wednesday at 10:00 PM America/Chicago**, compute `T` as the current release Wednesday and run the four captures **sequentially** (never in parallel):

1. `POST_RELEASE_CLEANUP`
2. `RELEASE_DAY_REFRESH`
3. `PREORDER_ACCURACY`
4. `EARLY_DISCOVERY`

Production owner: `ofoy@att.net` (verified before each batch).

## Render Cron setup (required for unattended production)

**The root `render.yaml` only deploys the static frontend.** P86 automation is **not** enabled until you create a Render Cron Job manually or from the blueprint:

- Blueprint file: [`docs/render/P86_RENDER_CRON_BLUEPRINT.yaml`](render/P86_RENDER_CRON_BLUEPRINT.yaml)

| Setting | Value |
|---------|--------|
| Name | `comic-os-release-lifecycle-weekly` |
| Root directory | `apps/api` |
| Command | `python scripts/run_release_lifecycle_weekly.py` |
| Schedule (timezone UI) | `America/Chicago`, Wednesday **22:00** |
| Schedule (UTC cron) | **CDT:** `0 3 * * 4` (Thu 03:00 UTC) · **CST:** `0 4 * * 4` |

### Required environment variables

- **`DATABASE_URL`** (required; script exits 1 if missing)

Optional (match API/worker if Playwright needs them):

- `REDIS_URL`
- `PLAYWRIGHT_BROWSERS_PATH`

Use the same Python dependencies and Playwright browser install as the API worker.

### Verify before enabling cron

```bash
cd apps/api
export DATABASE_URL='postgresql+pg8000://…/comic_os'
python scripts/run_release_lifecycle_weekly.py --dry-run
```

Dry run checks `DATABASE_URL`, DB connectivity, owner lookup for `ofoy@att.net`, and prints the four lifecycle dates. It does **not** capture or write run records.

### Manual production run

```bash
cd apps/api
export DATABASE_URL='postgresql+pg8000://…/comic_os'
python scripts/run_release_lifecycle_weekly.py
```

Exit codes:

- **0** — batch finished (including partial BLOCKED dates), dry-run OK, or skipped duplicate batch
- **1** — missing `DATABASE_URL`, owner lookup failure, DB unavailable, or fatal scheduler stop

The script prints a redacted database target (host, database, username; never password).

## Capture command (internal)

All scheduled captures use production Postgres and **always skip crosswalk**:

```bash
python scripts/capture_locg_date_details_browser.py \
  --production --email ofoy@att.net \
  --date YYYY-MM-DD --headful --save-raw --adaptive-delay --skip-crosswalk
```

## API (`/api/v1/release-lifecycle`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/plan` | Four dates for the current release week |
| POST | `/run-weekly` | Run the weekly plan sequentially (ops admin) |
| GET | `/runs` | Recent lifecycle run records |
| GET | `/dashboard` | Dashboard payload for `/release-lifecycle` |
| GET | `/latest-report` | Latest weekly report (`status: EMPTY` if none) |
| POST | `/runs/{id}/retry` | Retry a `BLOCKED` or `FAILED` date |

## Dashboard & reporting

Web route: **`/release-lifecycle`**

Shows plan, automation hint (honest if cron never ran), **latest weekly report**, recent runs, failed/blocked runs, and retry actions.

After each weekly batch:

1. **`p86_release_lifecycle_report`** row with title/body and per-date summary
2. **P84 notification** (`RELEASE_LIFECYCLE_REPORT`, priority **HIGH** if any FAILED/BLOCKED, else **NORMAL**)
3. **Briefing sections** on daily and weekly `CollectorBriefing` (`release_lifecycle` section)

If Render Cron is not configured, the dashboard states that no weekly run has completed yet.

## RQ recurring job (optional, not bootstrapped)

`schedule_release_lifecycle_weekly_scan()` exists but is **not** registered on API/worker startup in this repo. Use Render Cron unless you explicitly seed Redis once:

```python
from app.tasks.scheduled import schedule_release_lifecycle_weekly_scan
schedule_release_lifecycle_weekly_scan()
```

Job id: `scheduled-release-lifecycle-weekly`.

## Post-weekly refreshes

After captures complete, lightweight refreshes run: discovery cache, future pull list, release monitoring snapshot, FOC dashboard snapshot, cross-system recommendations (`refresh_upstream=False`).

## Stop rules

Fatal stop only on: owner lookup failure, DB unavailable, Playwright launch failure, or **two consecutive** Cloudflare blocks.

## If Cloudflare blocks one date

- Date is marked `BLOCKED`; batch continues unless two consecutive blocks
- Use **Retry** on `/release-lifecycle` or `POST /runs/{id}/retry`
- Do not hammer the same date automatically

## If the cron does not run

1. Confirm the Render Cron Job exists and is enabled (not in root `render.yaml` alone)
2. Run `--dry-run` on the cron service shell or locally with production `DATABASE_URL`
3. Check cron logs for exit code 1 (config) vs 0 with SKIPPED (duplicate RUNNING batch)
4. Use manual `POST /run-weekly` or the script for recovery

## Persistence

- `p86_release_lifecycle_run` — per-date capture runs
- `p86_release_lifecycle_report` — weekly summary reports

## Tests

```bash
cd apps/api
pytest tests/test_release_lifecycle_*.py -q
```
