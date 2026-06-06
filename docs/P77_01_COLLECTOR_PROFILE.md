# P77-01 Collector Profile, Goals & Budget Foundation

Personalization storage for collector identity, interests, goals, and budget. Does not alter recommendation scoring (P77-02).

## API (`/api/v1/collector-profile`)

| Method | Path | Purpose |
|--------|------|---------|
| GET/PUT | `` | Profile identity + buying preferences + ranked interests |
| GET/POST/PUT | `/goals`, `/goals/{id}` | Collection goals and progress |
| GET/PUT | `/budget` | Monthly budget and allocations |
| GET | `/dashboard` | Profile, budget, goals summary |

## Web routes

- `/collector-profile` — identity & buying preferences
- `/collector-goals` — goal management
- `/collector-budget` — budget settings

## Modules

- `apps/api/app/models/p77_collector_profile.py`
- `apps/api/app/services/p77_collector_profile_service.py`
- `apps/api/app/api/p77_collector_profile.py`
- `apps/api/tests/test_p77_collector_profile.py`

Engine version: `collector_profile` = `P77-01`
