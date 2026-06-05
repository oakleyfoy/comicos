# P65 Phase 2 — AI Collector Assistant Phase B

## Purpose

Deterministic narratives citing upstream signals; optional LLM enhancement when `P65_LLM_NARRATION_ENABLED` is true (default off).

## Outputs

Weekly briefing, buy/sell/grade/acquire/watch narrative items stored in `CollectorNarrativeSnapshot` / `CollectorNarrativeItem`.

## Service

`app/services/collector_narrative_service.py`

## Endpoints

- `GET /api/v1/collector-narratives/latest`
- `POST /api/v1/collector-narratives/build`

Rules: intelligence-first text, no invented facts, `signal_citations_json` on each item.
