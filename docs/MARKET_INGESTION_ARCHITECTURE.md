# Market ingestion architecture (P39-01)

## Philosophy

ComicOS treats market ingestion as a deterministic intake ledger, not an intelligence engine:

- preserve raw external acquisition records exactly as received
- materialize replay-safe ingestion batches with stable checksums and raw hashes
- keep batch processing append-only and auditable
- defer normalization, enrichment, scoring, and ranking to later P39 phases

This phase is intentionally foundational. It does not infer desirability, pricing edge, or portfolio fit.

## Raw vs. normalized separation

P39-01 introduces four ingestion-only tables:

- `MarketAcquisitionIngestionBatch`
  - one deterministic import envelope for a submitted dataset
- `MarketAcquisitionRawSource`
  - append-only preserved raw rows, one per submitted record
- `MarketAcquisitionCandidate`
  - lightweight persisted candidate scaffold created only for records that pass basic ingestion validation
- `MarketAcquisitionIngestionEvent`
  - append-only event ledger for batch creation, record parsing/rejection, and batch completion

Important boundary:

- raw payloads are always preserved on `MarketAcquisitionRawSource`
- candidate rows are still ingestion scaffolding only; `normalized_flag` remains `false`
- no normalization or intelligence fields are written in this phase

## Ingestion flow

Owner ingestion route:

1. receive an external dataset through `POST /market-ingestion/batch`
2. compute a deterministic `batch_checksum` from `batch_source_type + ordered records`
3. reuse the existing batch if the same owner replays the identical dataset
4. create a processing batch row
5. persist one raw-source row per record with a deterministic `raw_hash`
6. create a lightweight candidate row only for records that satisfy ingestion validation
7. append deterministic events:
   - `BATCH_CREATED`
   - `RECORD_PARSED`
   - `RECORD_REJECTED`
   - `BATCH_COMPLETED`
8. mark the batch `COMPLETED` when at least one record was accepted, otherwise `FAILED`

## Replay safety model

- `batch_checksum` is deterministic for the same ordered input payload
- `raw_hash` is deterministic for the same raw record payload
- owner ingestion reuses the existing batch when `(owner_user_id, batch_checksum)` already exists
- replay reuse means retries do not create duplicate batches, raw rows, candidates, or events

This keeps the ingestion lane append-only while still preventing duplicate materialization across identical retries.

## Deterministic guarantees

- canonical JSON hashing uses sorted keys and stable separators
- record order is preserved exactly as submitted when building the batch checksum
- raw rows list in ingestion order (`created_at`, `id`)
- ingestion events list in append order (`created_at`, `id`)
- ops and owner reads share the same batch/raw schemas; ops adds cross-owner visibility only

## Batch processing rules

- raw payload is never overwritten or cleaned in place
- batch rows are not mutated into a different checksum identity
- rejected records still produce raw-source rows and rejection events
- accepted records only create ingestion scaffolding (`MarketAcquisitionCandidate`) with `normalized_flag = false`
- no inventory, FMV, listing, or recommendation rows are touched

## Owner vs ops APIs

### Owner routes

- `POST /market-ingestion/batch`
- `GET /market-ingestion/batches`
- `GET /market-ingestion/batches/{id}`
- `GET /market-ingestion/batches/{id}/raw`

### Ops routes

- `GET /ops/market-ingestion/batches`
- `GET /ops/market-ingestion/batches/{id}`
- `GET /ops/market-ingestion/raw`

Ops routes are read-only mirrors and support cross-owner inspection without changing ingested data.

## Deferred normalization layer

P39-02 is expected to add deterministic normalization on top of this preserved raw ledger. P39-01 explicitly does not:

- normalize publishers, variants, issue strings, or conditions
- score or rank candidates
- enrich from external market intelligence
- predict pricing or market movement
- automatically ingest from live marketplaces

## Known limitations

- ingestion is currently synchronous and request-bound
- owner writes are supported now; global/null-owner ingestion is reserved for future system-controlled lanes
- duplicate prevention is based on exact dataset replay, not fuzzy deduplication of near-identical datasets
- validation is intentionally minimal and only enforces ingestion safety, not market correctness
