# ComicOS API / worker image for Render (Docker runtime).
#
# Why Docker: Render's native Python runtime cannot install system packages,
# so the Tesseract OCR binary is never present. P106.1 cover OCR recovery
# requires it. This image apt-installs Tesseract (plus the runtime libs that
# opencv-contrib-python-headless needs) and pins TESSERACT_CMD.
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

# Mirror the repo layout (/app = repo root, code under /app/apps/api). app/core/config.py
# resolves API_ROOT/REPO_ROOT via Path(__file__).parents[2]/[4], so the apps/api nesting
# must be preserved or config import fails with IndexError.
WORKDIR /app/apps/api

# Install Python dependencies first for better layer caching. The editable
# install needs pyproject.toml, README.md, and the app package present.
COPY pyproject.toml README.md ./
COPY app ./app
RUN python -m pip install --upgrade pip \
    && pip install -e .[dev]

# Migration + runtime assets used by scripts/render_web_start.py.
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY scripts ./scripts

EXPOSE 8000

# Web service entrypoint: runs alembic upgrade head, then execs uvicorn.
# The worker service overrides this with: python -m app.workers.rq_worker
CMD ["python", "scripts/render_web_start.py"]
