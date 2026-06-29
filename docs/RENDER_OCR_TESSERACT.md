# Render OCR (Tesseract) — production API Docker cutover

## Problem

Live intake showed `ocr_engine_available=false` and
`ocr_error="Local Tesseract OCR engine is unavailable on this host."` because
Render's **native Python** API cannot `apt-get install tesseract-ocr`.

## Where OCR runs

Photo intake identification (including P106.1 cover OCR) runs in the **API**
process via `run_intake_item_async` (background thread inside `comic-os-api`).
It does **not** run on the RQ worker. The worker can stay on native Python for
now; only the **API** needs Docker for Tesseract in production.

**Local development** stays native Python — no Docker required on your laptop.

## Fix (production only)

Deploy a second web service (`comic-os-api-docker`) using `apps/api/Dockerfile`,
validate OCR, then move `api.comicosapp.com` to it and suspend the old native
`comic-os-api`.

Repo assets:

| File | Purpose |
|------|---------|
| `apps/api/Dockerfile` | Tesseract + OpenCV libs + Playwright/Chromium; `WORKDIR /app/apps/api` |
| `apps/api/scripts/ocr_runtime_selfcheck.py` | Shell self-check → `SELFCHECK OK` |
| `GET /api/ops/ocr-health` | Ops JSON probe (auth required) |

---

## A. Create new Render Web Service

Dashboard → **New** → **Web Service** → repo `oakleyfoy/comicos`, branch `main`.

| Setting | Value |
|---------|--------|
| **Name** | `comic-os-api-docker` |
| **Project / environment** | ComicOS / Production |
| **Runtime** | **Docker** |
| **Root Directory** | `apps/api` |
| **Dockerfile Path** | `./Dockerfile` (relative to root directory — **not** `apps/api/Dockerfile`) |
| **Docker Build Context Directory** | `.` (default) |
| **Region / plan** | Match `comic-os-api` (Ohio, **Standard**) |
| **Health Check Path** | Same as old API (Settings → Health Checks; often `/health`) |

Default container command is the Dockerfile `CMD`:

```text
python scripts/render_web_start.py
```

Do **not** override unless you intentionally change the production entrypoint.

---

## B. Environment variables

1. Open old service env:  
   `comic-os-api` → **Environment** → **Export** → **Copy .env**
2. On `comic-os-api-docker` → **Add from .env** → paste → **Add variables**
3. Copy **every** key from the old API (database, Redis, secrets, eBay, R2, GCD, etc.)
4. Confirm or set explicitly:

```text
TESSERACT_CMD=/usr/bin/tesseract
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

The Dockerfile sets both as image defaults; copying from the old API may still
have a legacy `PLAYWRIGHT_BROWSERS_PATH` — **override** it to `/ms-playwright`
so Playwright finds the browser baked into the image.

Remove any empty “template” env row before deploy (Render treats it as required).

---

## C. Deploy

1. **Manual Deploy** → **Clear build cache & deploy**
2. Wait for build (Playwright + pip can take several minutes)
3. Confirm deploy log ends with service live (uvicorn / health check passing)

---

## D. Verify in Render shell

Service → **Shell** (instance running):

```bash
cd /app/apps/api
python scripts/ocr_runtime_selfcheck.py
```

**Expected:**

```text
intake.runtime.startup python=3.12.x tesseract_available=True ... TESSERACT_CMD='/usr/bin/tesseract' resolved='/usr/bin/tesseract' ...
SELFCHECK OK
```

Exit code must be `0`.

Optional:

```bash
tesseract --version
echo "$TESSERACT_CMD"
echo "$PLAYWRIGHT_BROWSERS_PATH"
```

---

## E. Verify API endpoint

`GET /api/ops/ocr-health` requires a logged-in **ops admin** user
(`OPS_ADMIN_EMAILS` in settings). Anonymous calls return `401`.

**From browser (easiest):** log into ComicOS as an ops admin, open DevTools →
Network, or visit the API with your session cookie:

```text
https://api.comicosapp.com/api/ops/ocr-health
```

(Use the **temporary** `*.onrender.com` URL for the docker service **before**
domain cutover.)

**Expected JSON:**

```json
{
  "tesseract_available": true,
  "tesseract_cmd": "/usr/bin/tesseract",
  "version": "tesseract 5.x.x",
  "error": null
}
```

**From Render shell** (no browser auth): rely on `ocr_runtime_selfcheck.py` above;
the health route still enforces `get_current_user` + ops admin.

---

## F. Cutover (production traffic)

Only after D and E pass on the **docker** service temp URL:

1. **Settings → Custom Domains** on `comic-os-api-docker` → add `api.comicosapp.com`
2. **Remove** `api.comicosapp.com` from old `comic-os-api` (or move domain per Render UI)
3. Wait until certificate shows **Verified** / active
4. Confirm frontend still uses `https://api.comicosapp.com` (unchanged URL for users)
5. Smoke-test: `curl -s https://api.comicosapp.com/health`
6. **Suspend** (do not delete) old `comic-os-api` only after the docker service serves the domain

Keep `comic-os-worker` on native Python unless you have another reason to migrate it.

---

## G. Rollback

1. Reattach `api.comicosapp.com` to **comic-os-api** (native)
2. **Resume** `comic-os-api` if suspended
3. **Suspend** `comic-os-api-docker`

OCR will be unavailable again on intake until the Docker API is back on the domain.

---

## Post-deploy checklist

Use this after cutover (or on the docker service before cutover):

- [ ] API boots without crash; `GET /health` returns OK
- [ ] Startup logs include `ocr.tesseract.startup` and `intake.runtime.startup` with  
      `TESSERACT_CMD='/usr/bin/tesseract'`, `resolved='/usr/bin/tesseract'`,  
      `tesseract_version='tesseract 5.x.x'`
- [ ] Render shell: `python scripts/ocr_runtime_selfcheck.py` → **SELFCHECK OK**
- [ ] Ops-authenticated `/api/ops/ocr-health` → `tesseract_available: true`
- [ ] Normal barcode scans still resolve (no scoring/threshold changes in this work)
- [ ] **Manual (you):** rescan `75960620629200111` and confirm  
      `barcode_gap.recovery_hints.ocr_engine_available=true`,  
      non-empty `raw_ocr_text_excerpt`, facsimile cue if cover text matches

---

## Local development (no Docker)

On your laptop:

- Install Tesseract for your OS, or accept `ocr_engine_available=false` in local intake tests
- Run API with existing venv: `pip install -e ".[dev]"` (and Playwright chromium if you need retailer browser jobs)
- Optional image check (not required for local dev):

```bash
docker buildx build --platform linux/amd64 -f apps/api/Dockerfile apps/api
```

---

## What this change does **not** do

- Does not change P106.1 scoring or thresholds
- Does not require Docker for local ComicOS development
- Does not migrate the worker for intake OCR (API-only for Tesseract)
