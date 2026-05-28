# P40 Architecture Index

This is the canonical navigation entry for the P40 scan intelligence stack. It links the phase docs, the cross-phase replay/hardening docs, and the operational references that describe how the system behaves in production.

## P40 overview

P40 is a deterministic scan-intelligence pipeline that transforms immutable scan inputs into replay-safe ledgers, artifacts, review support, authentication support, feed chronology, replay verification, and hardening evidence.

## Phase map

- P40-01 to P40-05: `[Scan ingestion](SCAN_INGESTION_ARCHITECTURE.md)`, `[Normalization](SCAN_NORMALIZATION_ARCHITECTURE.md)`, `[Boundary](SCAN_BOUNDARY_MAPPING_ARCHITECTURE.md)`, `[OCR](SCAN_OCR_ARCHITECTURE.md)`, `[Reconciliation](SCAN_RECONCILIATION_ARCHITECTURE.md)`
- P40-06 to P40-10: `[Defect foundation](SCAN_DEFECT_FOUNDATION_ARCHITECTURE.md)`, `[Spine ticks](SCAN_SPINE_TICK_ARCHITECTURE.md)`, `[Corner / edge wear](SCAN_CORNER_EDGE_ARCHITECTURE.md)`, `[Surface defects](SCAN_SURFACE_DEFECT_ARCHITECTURE.md)`, `[Structural damage](SCAN_STRUCTURAL_DAMAGE_ARCHITECTURE.md)`
- P40-11 to P40-12: `[Defect aggregation](SCAN_DEFECT_AGGREGATION_ARCHITECTURE.md)`, `[Grading assistance](SCAN_GRADING_ASSISTANCE_ARCHITECTURE.md)`
- P40-13 to P40-14: `[Visual evidence](SCAN_VISUAL_EVIDENCE_ARCHITECTURE.md)`, `[Review workspace](SCAN_REVIEW_WORKSPACE_ARCHITECTURE.md)`
- P40-15 to P40-16: `[Historical comparison](SCAN_HISTORICAL_COMPARISON_ARCHITECTURE.md)`, `[Authentication assistance](SCAN_AUTHENTICATION_ASSISTANCE_ARCHITECTURE.md)`
- P41-17 to P40-19: `[Scan intelligence feed](SCAN_INTELLIGENCE_FEED_ARCHITECTURE.md)`, `[Determinism / replay](SCAN_REPLAY_ARCHITECTURE.md)`, `[Hardening](P40_HARDENING_REPORT.md)`

## Dependency and lineage references

- `[P40 dependency graph](P40_DEPENDENCY_GRAPH.md)`
- `[Scan lifecycle](P40_SCAN_LIFECYCLE.md)`
- `[Determinism guarantees](P40_DETERMINISM_GUARANTEES.md)`
- `[Replay / audit guide](P40_REPLAY_AUDIT_GUIDE.md)`
- `[Storage architecture](P40_STORAGE_ARCHITECTURE.md)`

## Operations and deployment

- `[Operations guide](P40_OPERATIONS_GUIDE.md)`
- `[API reference](P40_API_REFERENCE.md)`
- `[Production readiness report](P40_PRODUCTION_READINESS_REPORT.md)`
- `[Production readiness baseline](PRODUCTION_READINESS.md)`
- `[Render dry run](RENDER_DEPLOYMENT_DRY_RUN.md)`

## System surfaces

- Owner-facing scan workspace docs:
  - `[Ingestion](SCAN_INGESTION_ARCHITECTURE.md)`
  - `[Review](SCAN_REVIEW_WORKSPACE_ARCHITECTURE.md)`
  - `[Feed](SCAN_INTELLIGENCE_FEED_ARCHITECTURE.md)`
  - `[Replay](SCAN_REPLAY_ARCHITECTURE.md)`
- Ops-facing docs:
  - `[Feed operations](SCAN_INTELLIGENCE_FEED_ARCHITECTURE.md)`
  - `[Replay operations](SCAN_REPLAY_ARCHITECTURE.md)`
  - `[Hardening](P40_HARDENING_REPORT.md)`

## Deterministic guarantees

- Stable ordering across phase ledgers and replay ledgers
- Append-only history and artifact storage
- Owner-isolated API surfaces
- Stable manifest hashing and replay checksums
- Replay discrepancies preserved as audit evidence

## Storage and artifact systems

- `[Storage architecture](P40_STORAGE_ARCHITECTURE.md)`
- `[Replay / audit guide](P40_REPLAY_AUDIT_GUIDE.md)`
- `[Hardening report](P40_HARDENING_REPORT.md)`

## Reference docs outside P40

- `[Scan pipeline architecture](SCAN_PIPELINE_ARCHITECTURE.md)`
- `[Technical debt log](TECH_DEBT.md)`
- `[Local runtime](LOCAL_RUNTIME.md)` for development bootstrap

