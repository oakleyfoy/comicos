# Render memory investigation — post intelligence deploy

**Service:** `comic-os-api` (Render memory limit / restart)  
**Scope:** P61–P64 intelligence deploy (`1d7b04f`); **no app behavior changes** in this investigation.  
**Render logs:** Not available from this workspace (no Render API/dashboard access). Use the correlation guide below when reviewing the Render log stream.

---

## 1. How to read Render logs (correlation guide)

Filter the `comic-os-api` deploy/restart window and look for this **sequence**:

| Order | Log line / signal | Phase |
|-------|-------------------|--------|
| A | `Running Alembic upgrade head (pre-uvicorn)...` | Migration subprocess start |
| B | Alembic `INFO ... Running upgrade ...` lines (many if head behind) | Migration subprocess |
| C | `Alembic upgrade complete` | Migration subprocess end |
| D | Uvicorn / `Started server process` | Worker import `app.main:app` |
| E | `Application startup complete` | Ready for traffic |
| F | First HTTP access logs (`GET /health`, `GET /api/v1/...`) | Request phase |

**Memory warning / SIGKILL** timing:

- **Between A–C** → suspect **Alembic child process** (loads `app.db.base` → full `app.models` metadata, runs DDL).
- **Between D–E (no requests yet)** → suspect **`import app.main`** (monolithic router attach).
- **After E, on specific paths** → suspect **request-time pipelines** (rebuild POSTs, cross-system, or heavy GET payloads).

If the restart happens **before** any request lines for `/api/v1/market-intelligence/*` or `/comicos-intelligence` traffic, the new UI is **not** the trigger; boot/migration is.

---

## 2. `render_web_start.py` — verified behavior

```text
render_web_start.py
  → should_run_startup_migrations()  (APP_ENV=production)
  → subprocess: python -m alembic upgrade head   # separate process; exits
  → os.execvp(uvicorn app.main:app)              # replaces process; single worker default
```

| Check | Result |
|-------|--------|
| Migrations run **once** before uvicorn | **Yes** (subprocess, then `execvp`) |
| Certification scripts on startup | **No** |
| P63/P64 `run_*_build` / `run_*_pipeline` on startup | **No** |
| FastAPI `lifespan` / `@app.on_event("startup")` hooks | **None** in `app/` |

P63/P64 builds run only on explicit **POST** routes (e.g. `/platform/build`, `/briefing/build`) or certification **GET** endpoints that intentionally invoke builds (`collector_assistant` certification service), not during import.

---

## 3. Phase attribution (code + local measurements)

### Alembic `upgrade head`

- Subprocess uses `alembic/env.py` → `app.db.base` → **`import app.models`** (large model registry, not full `app.main`).
- Local (already at head): `upgrade head` ~5s, light stdout.
- **Production deploy after intelligence:** if head was behind, one deploy applied P61–P64 migrations in the same subprocess; memory is **moderate**, usually **lower peak than uvicorn import**, and **short-lived** (process exits before uvicorn).

### App import / startup (`import app.main`)

- **No** intelligence pipeline execution at import.
- **Does** eagerly import **100+** `attach_*_layer` modules and register **~1886 routes** (`main.py`).
- Intelligence deploy added routers: `attach_market_intelligence_platform_layer`, `attach_collector_assistant_layer`, `attach_recommendation_intelligence_platform_layer` (P62 routes), `attach_demand_intelligence_platform_layer` (existing P61).
- Local measurement (dev machine, cold import):
  - **~67s** wall time to `import app.main`
  - **~288 MiB** tracemalloc peak (Python heap only; **RSS on Linux is typically higher**, often **400–600+ MiB** for this codebase)
- `python -X importtime`: cumulative import cost dominated by `app.main` pulling the entire API surface (scan, marketplace, agents, grading, recommendations, etc.) — **not** a single P63 module.

**Most likely Render OOM on deploy/restart:** uvicorn worker loading **`app.main`**, especially on **512 MiB** plans, not the intelligence dashboard itself.

### First request

- `/health` and `/health/db` are light.
- New frontend **`/comicos-intelligence`** issues **13 parallel GET** `*/latest` calls (read-only). These **do not** call `run_market_intelligence_platform_build` or `run_collector_assistant_build` on GET.
- GET handlers may still load **snapshot payloads** (e.g. portfolio items list). For owner with **22** copies, this is small compared to import RSS.
- **Exception:** `GET /api/v1/collector-assistant/platform/certification` runs a full assistant build — **not** used by the dashboard page.

### Intelligence endpoint calls (ongoing)

- **POST rebuild** paths remain the main **runtime** memory risk (documented in prior production stability audit: cross-system, unified, daily actions, title index).
- P63 **market signals** build can be slow/heavy when invoked via POST `/platform/build`, not on GET `/latest`.
- P61 weekly capture pipeline can call `run_collector_intelligence_pipeline` — only via **automation POST**, not startup.

---

## 4. Heavy imports / startup work (summary)

| Source | Startup? | Notes |
|--------|----------|--------|
| `app.main` router attachment | **Yes** | ~1886 routes; largest steady-state cost |
| `app.models` package | **Alembic + ORM** | Full registry via `models/__init__.py` |
| P63/P64 service modules | **Import only** | Loaded with API routers; no snapshot build |
| `validate_production_settings()` | **Yes** | Config check only |
| Recommendation rebuild pipelines | **No** | Request/job triggered |
| `render_web_start` certification | **No** | Not present |

---

## 5. Recommended fixes (no behavior change required for investigation)

**Priority 1 — Confirm in Render logs**  
Classify restart as **boot (D–E)** vs **request (F+)** using section 1.

**Priority 2 — Reduce boot RSS (structural, same API behavior)**  
- **Lazy router registration:** defer `attach_*_layer` imports until first use or split routers into optional sub-apps (large refactor, high impact).  
- **Slim Alembic metadata:** avoid `import app.models` full barrel in `app/db/base.py` for migrations only (medium refactor).  
- **Move heavy service imports** inside route handlers (incremental; lowers import peak for unused domains).

**Priority 3 — Migration ops (boot time / dual-process clarity)**  
- Run migrations via **GitHub** `migrate-production.yml` on release; keep Render boot on `render_web_start.py` so migrations complete before uvicorn starts.
- Keep `render_web_start.py` for environments without CI migrate.

**Priority 4 — Runtime (if logs show OOM on rebuild POSTs)**  
- Continue scoped title index + pipeline diagnostics (`recommendation_pipeline_diagnostics.py`).  
- Avoid calling certification GETs in production monitors.  
- Rate-limit parallel rebuilds on small instances.

**Priority 5 — Capacity**  
- If logs show OOM **during import only** with no rebuild traffic, **upgrade Render memory** (e.g. 512 → 1 GiB) is justified even when code is optimized — monolith import may remain **>512 MiB RSS**.

---

## 6. What this deploy likely changed

- **Added** import-time weight for P63/P64 API modules (small vs existing monolith).  
- **Did not add** startup pipelines or certification runners.  
- **Added** frontend aggregate **read** traffic pattern (13 GETs); unlikely to equal **import** peak on first deploy restart.

---

## 7. Top Recommendations timeout (related)

Production Top Recommendations failures were traced to **GET summary triggering full cross-system generate** (not startup OOM). Fixed in [TOP_RECOMMENDATIONS_TIMEOUT_FIX.md](TOP_RECOMMENDATIONS_TIMEOUT_FIX.md): read-only GETs + `POST .../rebuild` for refresh.

---

## 8. Next verification steps (ops)

1. Render → `comic-os-api` → Logs: capture timestamp of memory alert vs lines A–E above.  
2. Note instance **RAM** plan and whether **rolling deploy** ran two instances briefly.  
3. If boot-bound: measure restart RSS with the current production boot path and keep migration timing separate from app import cost.  
4. If request-bound: identify path from access log; compare with rebuild POSTs vs `/comicos-intelligence` GETs.
