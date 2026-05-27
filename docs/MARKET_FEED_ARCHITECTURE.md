# Market Intelligence Feed (P39-09)

This document describes the deterministic feed layer that records meaningful P39 activity as an append-only event stream and exposes replay-safe read models through the standardized market API.

---

## Data model

The feed is stored in a dedicated backend ledger:

- `MarketIntelligenceFeedEvent`
- `MarketIntelligenceFeedSnapshot`
- `MarketIntelligenceFeedHistory`
- `MarketIntelligenceFeedCursor`

Rules:

1. Events are append-only and immutable.
2. `event_sequence_id` is a monotonic per-owner sequence.
3. `event_checksum` is the SHA-256 of the canonical event payload.
4. `owner_user_id` is nullable so the feed can represent shared/system activity.
5. Replays must not mutate upstream P39 source rows.

---

## Event sources

The feed only records deterministic outputs from the existing P39 layers:

- P39-01 ingestion
- P39-02 normalization
- P39-03 scoring
- P39-04 signals
- P39-05 opportunities
- P39-06 portfolio-market coupling
- P39-08 snapshot generation

No new intelligence is introduced by the feed layer itself.

---

## Read models

Feed snapshots materialize the most common owner views:

- Latest events by type
- Timeline rows in sequence order
- Activity heatmap by date and event type
- Failure clustering by severity and event type

History rows preserve prior replay/materialization results for auditability, while cursors store the last seen sequence for deterministic polling.

---

## API contract

The feed is exposed through the P39 v1 envelope:

- Owner routes: `/api/v1/market/market-feed/*`
- Ops routes: `/api/v1/market/ops/market-feed/*`

Owner routes stay scoped to the authenticated user. Ops routes can inspect other owners when explicitly filtered and authorized.

---

## Replay rules

Replay is deterministic and replay-safe:

1. Read the feed events in `event_sequence_id` order.
2. Recompute event checksums from canonical payloads.
3. Validate sequence continuity.
4. Persist replay outputs only when the checksum/signature does not already exist.

The replay surface is intentionally read-only with respect to the upstream intelligence engines.

---

## UI surfaces

The web app uses the feed in three places:

- Dashboard: append-only feed summary panel
- Operations: full event timeline and snapshot drill-down
- Inventory detail: lightweight latest-event teaser

These surfaces are observational only and must not mutate feed state.

