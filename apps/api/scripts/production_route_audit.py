"""
Production route audit: GET every visible nav page's primary APIs and emit route_audit.csv.

Usage (local TestClient):
  cd apps/api && python -m scripts.production_route_audit

Usage (live API):
  ROUTE_AUDIT_BASE_URL=https://api.example.com \\
  ROUTE_AUDIT_EMAIL=you@example.com \\
  ROUTE_AUDIT_PASSWORD=secret \\
  python -m scripts.production_route_audit
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[3]
PRIMARY_APIS_PATH = REPO_ROOT / "config" / "route-page-primary-apis.json"
NAV_TS_PATH = REPO_ROOT / "apps" / "web" / "src" / "config" / "appNavigation.ts"
DEFAULT_CSV = REPO_ROOT / "route_audit.csv"
DEFAULT_JSONL = REPO_ROOT / "route_audit_responses.jsonl"
DEFAULT_SUMMARY = REPO_ROOT / "route_audit_summary.md"

TIMEOUT_MS = int(os.environ.get("ROUTE_AUDIT_TIMEOUT_MS", "25000"))
RELATION_RE = re.compile(r'relation\s+"([^"]+)"\s+does not exist', re.I)


@dataclass
class AuditRow:
    route: str
    api_endpoint: str
    status: int
    failure_type: str
    exception: str
    missing_table: str
    load_time_ms: int
    response_body: str


def _parse_visible_nav_routes() -> list[str]:
    text = NAV_TS_PATH.read_text(encoding="utf-8")
    routes: list[str] = []
    for line in text.splitlines():
        if "hiddenFromNav: true" in line or "requiresOpsAdmin" in line:
            continue
        m = re.search(r'to:\s*"([^"]+)"', line)
        if m:
            routes.append(m.group(1))
    # stable unique order
    seen: set[str] = set()
    out: list[str] = []
    for r in routes:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _load_route_apis() -> dict[str, list[str]]:
    data = json.loads(PRIMARY_APIS_PATH.read_text(encoding="utf-8"))
    mapping: dict[str, list[str]] = {}
    for entry in data.get("routes") or []:
        mapping[str(entry["path"])] = list(entry.get("apis") or [])
    return mapping


def _extract_missing_table(body: str) -> str:
    m = RELATION_RE.search(body)
    return m.group(1) if m else ""


def _envelope_error(body: str) -> tuple[str, str] | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    inner_status = str(data.get("status") or "").upper()
    if inner_status in {"OK", "EMPTY", "SKIPPED"}:
        return None
    if inner_status not in {"ERROR", "DEGRADED"}:
        return None
    msg = str(data.get("message") or "envelope error")
    if "missing migration" in msg.lower() or "snapshot table" in msg.lower():
        return "MISSING_MIGRATION", msg
    return "BAD_RESPONSE", msg


def _classify(*, status: int, body: str, timed_out: bool, elapsed_ms: int) -> tuple[str, str]:
    if timed_out or elapsed_ms >= TIMEOUT_MS:
        return "TIMEOUT", "request exceeded timeout budget"
    lowered = body.lower()
    missing = _extract_missing_table(body)
    if missing:
        if "snapshot" in missing or "valuation" in missing:
            return "MISSING_MIGRATION", f"missing relation {missing}"
        return "MISSING_TABLE", f"missing relation {missing}"
    if status >= 500:
        return "HTTP_500", body[:240] or f"HTTP {status}"
    if status == 0:
        return "BAD_RESPONSE", body[:240] or "no response"
    env = _envelope_error(body)
    if env and status == 200:
        return env
    if status in {401, 403, 404, 422}:
        return "BAD_RESPONSE", body[:240] or f"HTTP {status}"
    if status == 200:
        if "internal server error" in lowered:
            return "BAD_RESPONSE", "200 body contains Internal server error"
        if "pg8000" in lowered or ("sqlalchemy" in lowered and "error" in lowered):
            return "BAD_RESPONSE", "200 body leaks database driver error"
        if "traceback" in lowered and "file \"" in lowered:
            return "BAD_RESPONSE", "200 body contains traceback"
        return "OK", ""
    return "BAD_RESPONSE", body[:240] or f"HTTP {status}"


def _login_live(base_url: str, email: str, password: str) -> str:
    payload = json.dumps({"email": email, "password": password}).encode("utf-8")
    req = Request(
        f"{base_url.rstrip('/')}/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data["access_token"])


def _get_live(base_url: str, path: str, token: str) -> tuple[int, str, int, str | None]:
    url = f"{base_url.rstrip('/')}{path}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    start = time.perf_counter()
    exc: str | None = None
    try:
        with urlopen(req, timeout=TIMEOUT_MS / 1000.0) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            elapsed = int((time.perf_counter() - start) * 1000)
            return resp.status, body, elapsed, None
    except HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        elapsed = int((time.perf_counter() - start) * 1000)
        return err.code, body, elapsed, None
    except URLError as err:
        elapsed = int((time.perf_counter() - start) * 1000)
        reason = str(err.reason)
        timed_out = "timed out" in reason.lower()
        status = 0 if timed_out else 0
        failure = "TIMEOUT" if timed_out else "BAD_RESPONSE"
        return status, reason, elapsed, failure


def _get_testclient(client: Any, path: str, headers: dict[str, str]) -> tuple[int, str, int, str | None]:
    start = time.perf_counter()
    try:
        resp = client.get(path, headers=headers)
        elapsed = int((time.perf_counter() - start) * 1000)
        return resp.status_code, resp.text, elapsed, None
    except Exception as exc:  # noqa: BLE001
        elapsed = int((time.perf_counter() - start) * 1000)
        return 0, str(exc), elapsed, exc.__class__.__name__


def run_audit() -> list[AuditRow]:
    visible = _parse_visible_nav_routes()
    route_apis = _load_route_apis()
    rows: list[AuditRow] = []

    base_url = os.environ.get("ROUTE_AUDIT_BASE_URL", "").strip()
    token = os.environ.get("ROUTE_AUDIT_TOKEN", "").strip()

    if base_url:
        email = os.environ.get("ROUTE_AUDIT_EMAIL", "").strip()
        password = os.environ.get("ROUTE_AUDIT_PASSWORD", "")
        if not token and email and password:
            token = _login_live(base_url, email, password)
        if not token:
            raise SystemExit("ROUTE_AUDIT_TOKEN or ROUTE_AUDIT_EMAIL/PASSWORD required for live audit")
        headers = {"Authorization": f"Bearer {token}"}
        getter = lambda p: _get_live(base_url, p, token)  # noqa: E731
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        email = "route-audit@example.com"
        client.post(
            "/auth/register",
            json={"email": email, "password": "supersecret123"},
        )
        login = client.post(
            "/auth/login",
            json={"email": email, "password": "supersecret123"},
        )
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        getter = lambda p: _get_testclient(client, p, headers)  # noqa: E731

    for route in visible:
        apis = route_apis.get(route)
        if apis is None:
            rows.append(
                AuditRow(
                    route=route,
                    api_endpoint="(unmapped)",
                    status=0,
                    failure_type="BAD_RESPONSE",
                    exception="no primary API mapping in route-page-primary-apis.json",
                    missing_table="",
                    load_time_ms=0,
                    response_body="",
                )
            )
            continue
        if not apis:
            rows.append(
                AuditRow(
                    route=route,
                    api_endpoint="(none)",
                    status=200,
                    failure_type="OK",
                    exception="",
                    missing_table="",
                    load_time_ms=0,
                    response_body="page has no GET on load",
                )
            )
            continue
        for api_path in apis:
            status, body, elapsed, raw_exc = getter(api_path)
            timed_out = elapsed >= TIMEOUT_MS or (raw_exc == "TIMEOUT")
            failure_type, exception = _classify(status=status, body=body, timed_out=timed_out, elapsed_ms=elapsed)
            if raw_exc and failure_type == "OK":
                failure_type = "BAD_RESPONSE"
                exception = raw_exc
            missing_table = _extract_missing_table(body)
            rows.append(
                AuditRow(
                    route=route,
                    api_endpoint=api_path,
                    status=status,
                    failure_type=failure_type,
                    exception=exception[:500],
                    missing_table=missing_table,
                    load_time_ms=elapsed,
                    response_body=body[:4000],
                )
            )
    return rows


def _write_csv(rows: list[AuditRow], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "route",
                "api_endpoint",
                "status",
                "failure_type",
                "exception",
                "missing_table",
                "load_time_ms",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "route": row.route,
                    "api_endpoint": row.api_endpoint,
                    "status": row.status,
                    "failure_type": row.failure_type,
                    "exception": row.exception,
                    "missing_table": row.missing_table,
                    "load_time_ms": row.load_time_ms,
                }
            )


def _write_jsonl(rows: list[AuditRow], path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                json.dumps(
                    {
                        "route": row.route,
                        "api_endpoint": row.api_endpoint,
                        "status": row.status,
                        "failure_type": row.failure_type,
                        "response_body": row.response_body,
                    }
                )
                + "\n"
            )


def _write_summary(rows: list[AuditRow], path: Path) -> None:
    failing = [r for r in rows if r.failure_type != "OK"]
    failing_routes = sorted({r.route for r in failing})
    by_type: dict[str, list[AuditRow]] = {}
    for r in failing:
        by_type.setdefault(r.failure_type, []).append(r)

    tables = sorted({r.missing_table for r in failing if r.missing_table})

    root_cause_count = _count_unique_root_causes(failing)
    lines = [
        "# Route audit summary",
        "",
        f"- **Visible nav routes:** {len(_parse_visible_nav_routes())}",
        f"- **API probes:** {len(rows)}",
        f"- **Failing probes:** {len(failing)}",
        f"- **Failing routes (any probe):** {len(failing_routes)}",
        f"- **Unique backend root causes:** {root_cause_count}",
        "",
        "## Failure types",
        "",
    ]
    for ft in sorted(by_type.keys()):
        lines.append(f"- **{ft}:** {len(by_type[ft])} probes")
    lines.extend(["", "## Missing tables / relations", ""])
    if tables:
        for t in tables:
            lines.append(f"- `{t}`")
    else:
        lines.append("- (none in raw error text; see MISSING_MIGRATION envelopes below)")
    mig_n = sum(1 for r in failing if r.failure_type == "MISSING_MIGRATION")
    if mig_n:
        lines.extend(
            [
                "",
                "## Migration gaps",
                "",
                f"- **{mig_n}** probes return safe GET envelopes with `Missing migration or snapshot table` (HTTP 200).",
                "- Repo contains Alembic revisions under `apps/api/alembic/versions/` (e.g. P77 profile/budget, P79 storage/mobile, P81 discovery); target DB likely behind `head`.",
                "- **Action:** `alembic upgrade head` on production/staging, then re-run this audit.",
            ]
        )
    lines.extend(["", "## Failing routes", ""])
    for route in failing_routes:
        probes = [r for r in failing if r.route == route]
        sample = probes[0]
        lines.append(f"- `{route}` — {sample.failure_type} @ `{sample.api_endpoint}` ({sample.exception[:120]})")
    lines.extend(["", "## Root causes (grouped)", ""])
    lines.extend(_group_root_causes(failing, tables))
    lines.extend(["", "## Recommended fix order (smallest backend set)", ""])
    lines.extend(_recommend_fix_order(failing, tables))
    lines.extend(
        [
            "",
            "## Audit method",
            "",
            "- API probes via `apps/api/scripts/production_route_audit.py` (page-load GETs from `config/route-page-primary-apis.json`).",
            "- **JS_ERROR** not measured in this run (no Playwright/browser pass). Re-run with browser tooling for full nav + console errors.",
            "- Live production: set `ROUTE_AUDIT_BASE_URL` + auth env vars and re-run the script.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _count_unique_root_causes(failing: list[AuditRow]) -> int:
    keys: set[str] = set()
    for r in failing:
        if r.failure_type == "MISSING_MIGRATION":
            keys.add("db:migrations-not-applied")
        elif r.failure_type == "MISSING_TABLE":
            keys.add(f"db:missing:{r.missing_table or 'unknown'}")
        elif r.failure_type == "BAD_RESPONSE" and r.status == 404:
            keys.add("api:empty-snapshot-404")
        elif "pg8000" in (r.exception + r.response_body).lower():
            keys.add(f"safe-get-gap:{r.api_endpoint}")
        elif r.failure_type == "TIMEOUT":
            keys.add(f"timeout:{r.api_endpoint}")
        else:
            keys.add(f"{r.failure_type}:{r.api_endpoint}")
    return len(keys)


def _group_root_causes(failing: list[AuditRow], tables: list[str]) -> list[str]:
    lines: list[str] = []
    mig_env = [r for r in failing if r.failure_type == "MISSING_MIGRATION"]
    if mig_env:
        lines.append(f"### A. Safe envelope reports missing migration ({len(mig_env)} probes)")
        for r in sorted(mig_env, key=lambda x: (x.route, x.api_endpoint)):
            lines.append(f"- `{r.route}` → `{r.api_endpoint}`")
        lines.append("")
    if tables:
        by_table: dict[str, list[str]] = {}
        for r in failing:
            if r.missing_table:
                by_table.setdefault(r.missing_table, []).append(f"{r.route} → {r.api_endpoint}")
        lines.append(f"### B. Missing DB relations in raw errors ({len(tables)} tables, {len(by_table)} unique)")
        for table in sorted(by_table.keys()):
            routes = sorted(set(by_table[table]))
            lines.append(f"- **`{table}`** — {len(routes)} probe(s): " + "; ".join(routes[:4]) + (" …" if len(routes) > 4 else ""))
        lines.append("")
    leak = [r for r in failing if r.failure_type == "BAD_RESPONSE" and "pg8000" in (r.exception + r.response_body).lower()]
    if leak:
        lines.append(f"### C. Uncaught DB errors / safe-GET gap ({len(leak)} probes)")
        for r in leak:
            lines.append(f"- `{r.api_endpoint}` ({r.route})")
        lines.append("")
    empty_snap = [
        r
        for r in failing
        if r.failure_type == "BAD_RESPONSE" and r.status == 404 and "snapshot" in r.exception.lower()
    ]
    if empty_snap:
        lines.append(f"### D. Empty analytics snapshots return 404 ({len(empty_snap)} probes)")
        for r in empty_snap:
            lines.append(f"- `{r.api_endpoint}` ({r.route})")
        lines.append("")
    unmapped = [r for r in failing if "unmapped" in r.exception]
    if unmapped:
        lines.append("### E. Config drift (unmapped routes)")
        for r in unmapped:
            lines.append(f"- `{r.route}`")
        lines.append("")
    if not lines:
        lines.append("- No failures in this run.")
    return lines


def _recommend_fix_order(failing: list[AuditRow], tables: list[str]) -> list[str]:
    steps: list[str] = []
    if any(r.failure_type == "BAD_RESPONSE" and "unmapped" in r.exception for r in failing):
        steps.append("Align `config/route-page-primary-apis.json` with actual `client.ts` page-load GETs (manifest drift).")
    mig = [r for r in failing if r.failure_type == "MISSING_MIGRATION"]
    if mig:
        steps.append(
            f"Apply pending Alembic migrations on the target DB ({len(mig)} probes return `data.status=ERROR` / missing migration)."
        )
        steps.append(
            f"Re-run audit; confirm envelope-degraded probes return real data (not `data.status=ERROR`)."
        )
    if tables:
        steps.append(
            "Ship migration batch for raw missing relations: "
            + ", ".join(f"`{t}`" for t in tables[:8])
            + (" …" if len(tables) > 8 else "")
            + "."
        )
    if any(r.failure_type in {"HTTP_500", "MISSING_TABLE"} for r in failing):
        steps.append("Extend `nav_route_safe_get` + global GET safe envelope for routes still returning raw 500/SQL.")
    leak = [r for r in failing if "pg8000" in (r.exception + r.response_body).lower()]
    if leak:
        steps.append("Wire safe GET for: " + ", ".join(sorted({r.api_endpoint for r in leak})[:6]) + ".")
    empty_404 = [r for r in failing if r.failure_type == "BAD_RESPONSE" and r.status == 404]
    if empty_404:
        steps.append("Return empty snapshot envelopes (200) for portfolio analytics `*/latest` instead of HTTP 404.")
    degraded_db = [
        r
        for r in failing
        if r.failure_type == "BAD_RESPONSE" and "database temporarily unavailable" in r.exception.lower()
    ]
    if degraded_db:
        steps.append(
            "Fix poisoned DB sessions after migration errors on: "
            + ", ".join(sorted({r.api_endpoint for r in degraded_db})[:4])
            + "."
        )
    if any(r.failure_type == "TIMEOUT" for r in failing):
        steps.append("Add cached-only fast paths for probes exceeding ROUTE_AUDIT_TIMEOUT_MS.")
    if not steps:
        steps.append("No backend failures in this run; re-run against production `ROUTE_AUDIT_BASE_URL` before deploy.")
    return [f"{i + 1}. {s}" for i, s in enumerate(steps)]


def main() -> None:
    out_csv = Path(os.environ.get("ROUTE_AUDIT_CSV", str(DEFAULT_CSV)))
    out_jsonl = Path(os.environ.get("ROUTE_AUDIT_JSONL", str(DEFAULT_JSONL)))
    out_summary = Path(os.environ.get("ROUTE_AUDIT_SUMMARY", str(DEFAULT_SUMMARY)))

    rows = run_audit()
    _write_csv(rows, out_csv)
    _write_jsonl(rows, out_jsonl)
    _write_summary(rows, out_summary)

    failing = [r for r in rows if r.failure_type != "OK"]
    print(f"Wrote {out_csv} ({len(rows)} rows, {len(failing)} failing)")
    print(f"Wrote {out_summary}")


if __name__ == "__main__":
    main()
