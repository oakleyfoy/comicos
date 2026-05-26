# Grading Candidate Registry (P37-01)

## Purpose

Operational, owner-scoped **grading candidate ledger** — not grading AI, not grade prediction, and not marketplace submission automation.

Candidates describe *intent* for a physical inventory copy: preferred grader, priority, owner-entered economics assumptions, replay/idempotent inserts, deterministic checksum snapshots, and append-only lineage evidence.

## Tables

| Model | Role |
| --- | --- |
| `grading_candidate` | Primary row keyed by `(owner_user_id, inventory_item_id→inventory_copy)` with lifecycle `status`. |
| `grading_candidate_evidence` | Append-only evidence linked to deterministic domains/keys (`lineage_domain`, `lineage_key`, `reference_json`). |
| `grading_candidate_lifecycle_event` | Append-only lifecycle narration (`CREATED`, `SUBMITTED`, …). |
| `grading_candidate_snapshot` | Append-only deterministic snapshot of assumptions + observed evidence count + `checksum`. |

## Invariants

- **No inventory mutation**: creating or transitioning candidates never edits `inventory_copy`, FMV engines, liquidity, listings, etc.
- **Single active pipeline row per `(owner_user_id, inventory_item_id)`**: statuses `CANDIDATE`, `REVIEWING`, `READY_FOR_SUBMISSION`, `SUBMITTED` are mutually exclusive across concurrent rows — historical graded/rejected/archived rows may coexist once the pipeline frees.
- **Replay**: optional `(owner_user_id, replay_key)` uniqueness replays duplicate POST payloads to the identical persisted graph (no duplicated lifecycle rows or snapshots on replay).
- **Deterministic snapshots**: checksum is `sha256(sorted_json(assumptions_payload))`, where numeric decimals are quantized to stable string forms before hashing.
- **Append-only histories**: PATCH updates emit `UPDATED` lifecycle rows; evidence inserts append rows and regenerate snapshots rather than overwriting prior snapshots.

## Owner HTTP surface (`/grading-candidates*`)

Read/list/generate summaries: `dashboard-summary`, `GET /`, `GET /{id}`.

Writes: `POST /` creation, optional `replay_key`; `PATCH /{id}` for editable economics while statuses remain `CANDIDATE`, `REVIEWING`, or `READY_FOR_SUBMISSION`; `POST /{id}/evidence` append (non-archived candidates).

Deterministic transitions (each validates prior status, logs lifecycle rows, emits new snapshot):

- `/review`
- `/ready`
- `/submit`
- `/grade`
- `/reject`
- `/archive`

## Ops HTTP surface (`/ops/*`), read-only

- `/ops/grading-candidates` — optional `owner_user_id`, `status`, `inventory_item_id`
- `/ops/grading-candidates/{id}`
- `/ops/grading-candidate-events` — optional filters
- `/ops/grading-candidate-evidence` — optional filters

Routes require `ensure_ops_admin_access` mirroring every other ComicOS ops telescope.

## Inventory detail badge

`/inventory/{inventory_copy_id}` responses include optional `grading_candidate` summary: prioritize active pipeline rows, otherwise most recent historical non-archived row.

## Deferred (explicitly NOT P37-01)

- Grade estimation / third-party grading APIs
- Defect OCR or automated scan scoring
- AI recommendations for “should grade” decisions
- Grader SLA tracking or webhook integrations
- Cost actuals ingestion from invoices (manual economics only today)
