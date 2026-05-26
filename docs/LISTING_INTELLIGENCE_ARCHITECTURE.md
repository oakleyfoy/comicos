# Listing Intelligence Architecture

## Purpose

`P36-06` adds deterministic listing analytics for ComicOS.

The goal is to explain listing quality, export readiness, channel performance, stale behavior, and sale outcomes without recommendations, predictive AI, auto-pricing, or sell/hold logic.

## Models

- `ListingIntelligenceSnapshot` stores the per-listing intelligence rollup.
- `ListingIntelligenceEvidence` stores the evidence rows used to explain the snapshot.
- `ListingCompletenessCheck` stores field-level completeness checks.
- `ListingChannelPerformanceSnapshot` stores descriptive channel-level aggregates.

The ledger is append-only and snapshot-based. Generation never mutates listing status or inventory state.

## Scoring Rules

Completeness scoring is deterministic and additive:

- title: 20 points if present and at least 8 characters, otherwise 10 if present but short
- description: 20 points if present and at least 40 characters, otherwise 10 if present but short
- condition: 15 points if `condition_summary` is present
- price: 15 points if amount and currency are present
- images: 20 points if a primary image exists, 10 if any image exists
- inventory link: 10 points if the listing is linked to inventory

The total is capped at 100.

Classification:

- `STRONG`: 85-100
- `ADEQUATE`: 65-84
- `WEAK`: 40-64
- `INCOMPLETE`: 0-39
- `INSUFFICIENT_DATA`: no usable evidence

## Export Readiness

Export readiness is derived from the completeness checks and requires:

- title present
- condition present
- price present
- currency present
- inventory link present
- listing status of `READY` or `ACTIVE`

This layer only reports readiness. It does not mutate listing status or generate exports.

## Channel Performance Aggregation

Channel performance snapshots combine:

- listing registry status counts
- export-run counts
- recorded sales
- velocity snapshots
- stale listing events

The metrics remain descriptive only. They are not ranked or converted into recommendations.

## Evidence Model

Evidence rows explain how the snapshot was assembled.

Supported evidence types:

- `LISTING_FIELD`
- `IMAGE`
- `PRICE`
- `EXPORT_RUN`
- `SALE`
- `LIQUIDITY`
- `CONVENTION`

Evidence rows preserve the source identifiers and a JSON payload for deterministic inspection.

## Replay Behavior

Generation is replay-safe and append-safe.

- Re-running the generator with the same snapshot date and same listing state yields the same checksum.
- Existing snapshot rows are reused instead of being destructively rewritten.
- Checksums are derived from a stable JSON payload with sorted keys.

## Owner vs Ops APIs

Owner routes are scoped to the authenticated owner.

- `GET /listing-intelligence`
- `GET /listing-intelligence/{id}`
- `GET /listing-intelligence/evidence`
- `GET /listing-completeness-checks`
- `GET /listing-channel-performance`
- `POST /listing-intelligence/generate`

Ops routes are read-only mirrors and support cross-owner filtering.

- `GET /ops/listing-intelligence`
- `GET /ops/listing-intelligence/{id}`
- `GET /ops/listing-intelligence-evidence`
- `GET /ops/listing-completeness-checks`
- `GET /ops/listing-channel-performance`

## Non-Goals

- Recommendations
- Predictive AI
- Auto-pricing
- Sell/hold logic
- AI-generated title or description suggestions
- Listing or inventory mutation
- Channel ranking as advice
- Marketplace posting or marketplace API integration
