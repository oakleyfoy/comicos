# P79 Storage & Location Intelligence — Production Review

## Status

| Phase | Scope | Status |
|-------|--------|--------|
| P79-01 | Storage foundation | **COMPLETE** |
| P79-02 | Locator & audit | **COMPLETE** |
| P79-03 | Analytics & certification | **COMPLETE** |

**Platform status:** `APPROVED_FOR_PRODUCTION`

Out of scope: mobile/camera scanning, destructive auto-moves, eBay automation, buying recommendation changes.

## Architecture

```
P79-01 Hierarchy + assignment + capacity
        ↓
P79-02 Locator + box contents + audits + labels (QR payload)
        ↓
P79-03 Analytics snapshots + health score + certification
```

## Storage hierarchy

`LOCATION → ROOM → RACK → SHELF → BOX → SLOT` (optional levels).

## Assignment rules

- One assignment per inventory copy; explicit reassignment only.
- Suggested next free slot in box capacity.

## Audit workflow

Sessions scope a box or location subtree. Entries: `EXPECTED`, `VERIFIED`, `MISSING`, `UNEXPECTED`, `MOVED`. Moves require explicit `move_to_box`.

## Analytics formulas

**Core:** total capacity = sum(box.capacity); used = assigned slots; utilization % = used / capacity.

**Forecast:** average monthly additions ≈ copies created in last 90 days / 3. Months until full = available / monthly rate. Risk: `LOW_RISK`, `WATCH`, `AT_CAPACITY`, `OVER_CAPACITY`.

**Audit analytics:** verification rate = verified / (verified + missing); accuracy = verified / expected entries.

## Health scoring (0–100)

Weighted penalties from:

- Assignment coverage (35%)
- Audit accuracy (20%)
- Over-capacity boxes (−8 each, cap 30)
- High-value unassigned FMV ≥ $75 (−5 each, cap 25)
- Duplicate candidates (−4 each, cap 20)
- Missing audit entries (−3 each, cap 15)

Status: `HEALTHY` ≥85, `WATCH` ≥65, else `AT_RISK`.

## Snapshots

`P79StorageAnalyticsSnapshot`, `P79StorageUtilizationSnapshot`, `P79StorageAuditPerformanceSnapshot`, `P79StorageHealthSnapshot` persisted on analytics runs.

## APIs

| Endpoint | Purpose |
|----------|---------|
| `/storage/analytics` | Core metrics + forecast |
| `/storage/utilization` | By room/rack/shelf/box/type |
| `/storage/audit-analytics` | Audit performance |
| `/storage/unassigned` | Unassigned inventory dashboard |
| `/storage/health` | Health score |
| `/storage/certification` | Production checklist |
| `/storage/analytics-dashboard` | Combined UI payload |

## Known limitations

- Utilization by box type inferred from name prefix (SPEC/SALE).
- Forecast uses simple 90-day copy creation rate.
- Duplicate detection is heuristic (series/issue/variant).
- QR payloads are not scanned in-app yet.

## Future mobile scanning plan

P80+ can consume `comicos://p79/storage/{type}/{id}` QR payloads with camera workflows; no mobile scanner in P79.

## Verification

```bash
pytest apps/api/tests/test_storage_analytics.py -v
pytest apps/api/tests/test_storage_utilization.py -v
pytest apps/api/tests/test_storage_audit_analytics.py -v
pytest apps/api/tests/test_storage_health.py -v
pytest apps/api/tests/test_storage_certification.py -v
python -c "from app.main import app; print('app import ok')"
cd apps/web && npm run build
```
