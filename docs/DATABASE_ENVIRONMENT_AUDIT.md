# Database Environment Audit

**Generated:** 2026-06-03 (from `apps/api` settings + live PostgreSQL queries)  
**Purpose:** Identify which database this workspace uses and which owner holds inventory for P63 certification.

---

## 1. Connection summary

| Field | Value |
|-------|--------|
| **APP_ENV** | `development` |
| **DATABASE_URL (masked)** | `postgresql+pg8000://postgres:****@localhost:5433/comic_os` |
| **Host** | `localhost` |
| **Port** | `5433` |
| **Database name (config)** | `comic_os` |
| **Database name (live `current_database()`)** | `comic_os` |
| **Current schema** | `public` |

Password is never stored in this document; only the masked URL above is shown.

---

## 2. Table row counts (this environment)

| Table | Row count |
|-------|-----------|
| `inventory_copy` | **0** |
| `customer_order` (`orders`) | 4 |
| `buy_queue_item` | 0 |
| `issue_demand_snapshot` | 1,740 |
| `release_issue` | 2,483 |
| `user` | 22 |

---

## 3. Top 20 owners by `inventory_copy` count

**No rows** — every `inventory_copy.user_id` is unset or the table is empty. There are **zero** owners with `inventory_count > 0` in this database.

---

## 4. Owner detail (certification-relevant)

### `ofoy@att.net` (requested P63 cert email)

| Field | Value |
|-------|--------|
| **owner_id** | 41 |
| **email** | `ofoy@att.net` |
| **inventory_count** | **0** |
| **order_count** | (not in top-20; query by user_id separately) |
| **buy_queue_count** | 0 |

P63 certification correctly refuses this owner in **this** environment: portfolio/sell lanes require inventory-backed P63 snapshots.

### Note on “22”

This database has **22 `user` rows**, but **0 `inventory_copy` rows**. If you expected **22 inventory copies**, that data is **not** in `postgresql://…@localhost:5433/comic_os` as configured for this workspace. The number 22 may have been **user count**, not copy count.

---

## 5. Environment classification

| Signal | Observation | Inference |
|--------|-------------|-----------|
| Host `localhost:5433` | Not a remote production host | **Local** PostgreSQL |
| `APP_ENV=development` | Default dev settings | **Local dev** profile |
| Large `issue_demand_snapshot` / `release_issue` | P61/P62-style seed or refresh data present | **Dev / integration** data, not empty fixture |
| `inventory_copy = 0` | No ledger copies | **Not** a production clone with real collection data |
| `customer_order = 4` | Minimal orders | Test or partial seed |

**Conclusion for this workspace:**

| Label | Applies? |
|-------|----------|
| Local fixture DB (pytest SQLite) | **No** — this audit used PostgreSQL via `DATABASE_URL`, not test SQLite |
| **Local dev DB** (`localhost:5433/comic_os`) | **Yes** — primary match |
| Production clone with collection | **No** — zero inventory |
| Production DB | **No** — localhost + development env |

To certify P63 against **22 inventory copies**, point `DATABASE_URL` (repo root `.env` or `apps/api/.env`, or `COMICOS_API_ENV_ROOT`) at the PostgreSQL instance that actually contains those rows, then re-run:

```bash
cd apps/api
python scripts/p63_market_intelligence_certification.py --list-owners-only --skip-pytest
```

Use the email on the line with the expected `inventory=` count.

---

## 6. How this audit was produced

Live queries via `app.db.session.get_engine()` and `app.core.config.get_settings()` (same path as API and certification scripts). Re-run anytime:

```bash
cd apps/api
python scripts/p63_market_intelligence_certification.py --list-owners-only --skip-pytest
```

For a fuller owner/order breakdown when inventory exists, extend the audit script or SQL:

```sql
SELECT u.id, u.email, COUNT(ic.id) AS inventory_count
FROM "user" u
LEFT JOIN inventory_copy ic ON ic.user_id = u.id
GROUP BY u.id, u.email
ORDER BY inventory_count DESC
LIMIT 20;
```

---

## 7. Environment switch for P63/P64 certification (2026-06-03)

### Config sources checked

| Source | Present? | `DATABASE_URL` host | DB name | User | `APP_ENV` |
|--------|----------|---------------------|---------|------|-----------|
| `comic-os-p41-feed/.env` | **Missing** | — | — | — | — |
| `comic-os-p41-feed/apps/api/.env` | **Missing** | — | — | — | — |
| `COMICOS_API_ENV_ROOT` | **Not set** | — | — | — | — |
| **Companion** `C:\comic-os\apps\api\.env` | **Exists** | `localhost` | `comic_os` | `postgres` | `development` |
| **Process** `DATABASE_URL` | Set | `localhost` | `comic_os` | `postgres` | (inherits settings) |
| **`get_settings()` effective** | — | `localhost` | `comic_os` | `postgres` | `development` |

All reachable targets in this workspace resolve to the **same** local empty-ledger DB. `ofoy@att.net` → **user id 41**, **inventory_count 0**.

### Documented production / Render

| Reference | Detail |
|-----------|--------|
| [RENDER_DEPLOYMENT_DRY_RUN.md](RENDER_DEPLOYMENT_DRY_RUN.md) | `DATABASE_URL=<render postgres connection string>`, `APP_ENV=production` |
| [.github/workflows/migrate-production.yml](../.github/workflows/migrate-production.yml) | GitHub Actions secret **`PRODUCTION_DATABASE_URL`** (value **not** in repo) |
| `apps/api/seed.log` (historical run) | `db_host=**dpg-d88dr5egvqtc73b0nrkg-a.ohio-postgres.render.com**`, `ofoy@att.net` → **owner_user_id=1** (production id, not local 41) |

**Conclusion:** Real collection/inventory for certification lives on **Render Postgres** (`dpg-d88dr5egvqtc73b0nrkg-a.ohio-postgres.render.com`), not on `localhost:5433/comic_os`. This workspace has **no** `.env` pointing at Render; `gh` CLI is unavailable here to read `PRODUCTION_DATABASE_URL`.

### Cert commands (run only after switching `DATABASE_URL`)

Do **not** certify against localhost while `inventory_copy` is 0.

```powershell
# PowerShell: set session URL from Render dashboard External Database URL (do not commit)
$env:DATABASE_URL = "postgresql+pg8000://USER:PASSWORD@dpg-d88dr5egvqtc73b0nrkg-a.ohio-postgres.render.com:5432/DATABASE"
$env:APP_ENV = "production"

cd apps\api
python scripts/p63_market_intelligence_certification.py --list-owners-only --skip-pytest
# Continue only if ofoy@att.net appears with inventory_count > 0
python scripts/p63_market_intelligence_certification.py --skip-pytest --owner-email ofoy@att.net
python scripts/p64_collector_assistant_certification.py --skip-pytest --owner-email ofoy@att.net
```

`config.py` loads companion `C:\comic-os\apps\api\.env` with **`override=False`**, so a **process-level** `DATABASE_URL` set before Python starts overrides the companion file for certification runs.

---

## 8. Recommended next steps

1. On the machine where you see 22 copies, run `echo %DATABASE_URL%` (or inspect `.env`) and compare host/db to the table in §1.
2. If inventory lives on another host, update `.env` for local cert runs **or** run certification on that host only.
3. After `DATABASE_URL` points at the inventory-rich DB, cert with  
   `python scripts/p63_market_intelligence_certification.py --skip-pytest --owner-email <email-from-list>`.
