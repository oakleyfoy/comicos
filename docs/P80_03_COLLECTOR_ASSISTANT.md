# P80-03 Collector Assistant

Shopping and convention workflow layer on P80-01 mobile scan intelligence, P52 run/gap detection, P55 acquisition opportunities, and P51 unified recommendations.

## API (`/api/v1/collector`)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/scan` | Identify comic, ownership, FMV, grading, gaps, spec signals, shopping action card; optional `vendor_price` |
| POST | `/evaluate-price` | Compare asking price to FMV (`GREAT_BUY`, `FAIR_BUY`, `OVERPRICED`) |
| GET | `/gaps` | Refresh and list collection gaps |
| GET | `/opportunities` | Acquisition + unified recommendation opportunities |
| GET | `/dashboard` | Gaps summary, acquisitions, spec/watch lists |

## Web routes

- `/collector-assistant` — full shopping scan with optional vendor price
- `/convention-mode` — large BUY/PASS quick decision UI (collector; distinct from org convention mode)
- `/collector-dashboard` — gaps and opportunity overview

## Key modules

- `apps/api/app/schemas/p80_collector_assistant.py`
- `apps/api/app/services/p80_collector_assistant_service.py`
- `apps/api/app/api/p80_collector_assistant.py`
- `apps/api/tests/test_p80_collector_assistant.py`

## Engine version

`scan_api_v1.engine_versions.collector_assistant` = `P80-03`
