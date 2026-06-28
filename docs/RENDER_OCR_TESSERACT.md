# Render OCR (Tesseract) availability for ComicOS intake

## Problem

Live intake item 68 showed:

```text
ocr_engine_available=false
ocr_error="Local Tesseract OCR engine is unavailable on this host."
```

With no Tesseract binary, P106.1 cover recovery gets no `ocr_title`, no
`raw_ocr_text_excerpt`, and no facsimile cue, so it blocks with
`insufficient_series_or_title_hint`.

## Root cause

The API and worker were deployed on Render's **native Python runtime**
(`pip install -e .[dev]` build, `python scripts/render_web_start.py` start).
The native runtime runs builds without root and has **no apt-get path**, so the
`tesseract-ocr` system binary can never be installed. `tesseract --version`
fails in the shell, and `_resolve_ocr_engine_cmd()` cannot find the engine.

## Fix: Docker runtime with Tesseract baked in

Cover OCR runs on the **intake worker** (and the API exposes the health probe),
so **both** the `comic-os-api` web service and the `comic-os-worker` background
worker must switch to Docker.

Added in this repo:

- `apps/api/Dockerfile` — `python:3.12-slim` + apt installs
  `tesseract-ocr libtesseract-dev` (and `libgl1 libglib2.0-0` for opencv
  headless), pins `TESSERACT_CMD=/usr/bin/tesseract`, and runs
  `scripts/render_web_start.py` (web) — the worker overrides the command.
- `apps/api/.dockerignore` — keeps the build context small (excludes
  `data/`, caches, tests, decompiler scratch).
- `docs/render/API_WORKER_DOCKER_BLUEPRINT.yaml` — reproducible Docker
  blueprint for the API + worker.

### Option A — switch existing services in the Render dashboard

For **each** of `comic-os-api` and `comic-os-worker`:

1. Service → **Settings** → **Build & Deploy**.
2. **Runtime**: change to **Docker**.
3. **Root Directory**: `apps/api`.
4. **Dockerfile Path**: `apps/api/Dockerfile`.
5. **Docker Build Context Directory**: `apps/api`.
6. Worker only — **Docker Command**: `python -m app.workers.rq_worker`
   (the API web service keeps the Dockerfile default).
7. **Environment** → add `TESSERACT_CMD=/usr/bin/tesseract` (the Dockerfile
   already sets this as a default; setting it explicitly is belt-and-suspenders).
8. **Save**, then **Manual Deploy → Clear build cache & deploy**.

### Option B — apply the blueprint

Apply `docs/render/API_WORKER_DOCKER_BLUEPRINT.yaml` (New → Blueprint), then fill
in the `sync: false` secrets. Avoid creating duplicate services if the
dashboard ones already exist — Option A is safer for the live services.

## Verification

### 1. Shell on the deployed service

```bash
tesseract --version
# expected: "tesseract 5.x.x" ...
echo "$TESSERACT_CMD"
# expected: /usr/bin/tesseract
```

### 2. OCR health endpoint

```bash
curl -s https://api.comicosapp.com/api/ops/ocr-health
```

Expected (ops-admin authenticated):

```json
{
  "tesseract_available": true,
  "tesseract_cmd": "/usr/bin/tesseract",
  "version": "5.x.x",
  "error": null
}
```

### 3. Startup log confirmation

On boot the API logs (see `app/main.py:_log_tesseract_on_startup`):

```text
ocr.tesseract.startup TESSERACT_CMD='/usr/bin/tesseract' resolved='/usr/bin/tesseract' version=5.x.x
```

### 4. Rescan barcode 75960620629200111

After both services redeploy on Docker, rescan the barcode and confirm on the
resulting `IntakeSessionItem.barcode_read_json.barcode_gap`:

- `recovery_hints.ocr_engine_available = true`
- `recovery_hints.ocr_error = null`
- `recovery_hints.raw_ocr_text_excerpt` is non-empty
- `recovery_hints.facsimile_or_reprint = true` when the cover reads
  "Facsimile Edition"

No scoring or thresholds changed — this only restores the OCR signal that
P106.1 was already designed to consume.
