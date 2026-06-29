# ComicOS API image for Render (Docker runtime).
#
# Why Docker: Render's native Python runtime cannot install system packages,
# so the Tesseract OCR binary is never present. P106.1 cover OCR recovery
# requires it. This image must be a superset of the old native build
# (`pip install -e ".[browser]" && python -m playwright install chromium`):
#   - Tesseract OCR binary           -> P106.1 cover recovery hints
#   - opencv/zxing runtime libs      -> barcode decode + fingerprinting
#   - Playwright + Chromium browser  -> retailer / external-catalog scraping
#                                       (Midtown, LOCG, eBay, release lifecycle)
#
# Build context is apps/api (set Root Directory = apps/api in Render).
# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# System packages:
#   tesseract-ocr / libtesseract-dev -> cover OCR for P106.1 recovery hints
#   libgl1 / libglib2.0-0            -> runtime libs required by opencv headless
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libtesseract-dev \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Tesseract installs to /usr/bin/tesseract; pin it so OCR never depends on PATH.
ENV TESSERACT_CMD=/usr/bin/tesseract

# Install the Chromium browser binary to a stable, world-readable path. This must
# match the runtime PLAYWRIGHT_BROWSERS_PATH (set the same value in the Render
# service env, overriding any legacy value) or Playwright cannot find the browser.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Mirror the repo layout (/app = repo root, code under /app/apps/api). app/core/config.py
# resolves API_ROOT/REPO_ROOT via Path(__file__).parents[2]/[4], so the apps/api nesting
# must be preserved or config import fails with IndexError.
WORKDIR /app/apps/api

# Install Python dependencies first for better layer caching. The editable
# install needs pyproject.toml, README.md, and the app package present.
COPY pyproject.toml README.md ./
COPY app ./app
# opencv/zxing/playwright are core deps; [dev] adds nothing browser-related.
# `playwright install --with-deps chromium` apt-installs Chromium's system libs
# and downloads the browser into PLAYWRIGHT_BROWSERS_PATH.
RUN python -m pip install --upgrade pip \
    && pip install -e .[dev] \
    && python -m playwright install --with-deps chromium

# Migration + runtime assets used by scripts/render_web_start.py.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY scripts ./scripts

EXPOSE 8000

# Web service entrypoint: runs alembic upgrade head, then execs uvicorn.
# (The RQ worker stays on Render's native runtime; only the API uses this image.)
CMD ["python", "scripts/render_web_start.py"]
