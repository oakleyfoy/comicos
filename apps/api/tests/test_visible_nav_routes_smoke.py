"""Smoke: primary APIs for visible nav routes return 200 (no uncaught 500 on load)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session

from test_inventory import auth_headers, register_and_login

_MANIFEST = Path(__file__).resolve().parents[3] / "config" / "nav-route-smoke.manifest.json"


def _load_manifest() -> list[dict]:
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    return list(data["routes"])


def _api_paths() -> list[str]:
    paths: list[str] = []
    for route in _load_manifest():
        for api in route.get("apis") or []:
            path = api.split("?", 1)[0]
            if path not in paths:
                paths.append(path)
    return paths


def test_visible_nav_primary_apis_return_200(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "nav-smoke@example.com")
    headers = auth_headers(token)
    failures: list[str] = []
    for path in _api_paths():
        resp = client.get(path, headers=headers)
        body_preview = resp.text[:400]
        if resp.status_code != 200:
            failures.append(f"{path} -> {resp.status_code} {body_preview}")
            continue
        lowered = body_preview.lower()
        if "internal server error" in lowered or "pg8000" in lowered or "does not exist" in lowered and "relation" in lowered:
            failures.append(f"{path} -> 200 but leaked error payload {body_preview}")
    assert not failures, "nav API smoke failures:\n" + "\n".join(failures)


def test_manifest_covers_priority_routes() -> None:
    routes = {r["path"] for r in _load_manifest()}
    priority = {
        "/collector-home",
        "/daily-actions",
        "/collector-command-center",
        "/notifications",
        "/daily-briefing",
        "/workflow-health",
        "/pull-lists",
        "/foc-dashboard",
        "/marketplace-opportunities",
        "/future-pull-list",
        "/dashboard",
        "/collection-valuation-dashboard",
        "/key-issues",
        "/sell-queue",
        "/storage-dashboard",
        "/storage-locations",
        "/grading-queue",
        "/grading-intelligence",
        "/grading-platform",
        "/listing-drafts",
        "/listings",
        "/selling-analytics",
        "/imports",
        "/imports/email",
        "/orders/import",
        "/discovery-feed",
        "/mobile-scan",
    }
    missing = priority - routes
    assert not missing, f"manifest missing priority routes: {sorted(missing)}"
