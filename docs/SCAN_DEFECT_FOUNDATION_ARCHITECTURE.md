# P40-06 Scan Defect Foundation Architecture

## Philosophy

P40-06 is the first condition-oriented scan layer, but it is still a foundation only. It does not assign grades, estimate market value, or name specialized defects. Instead, it creates deterministic condition regions, scan-quality gates, provisional evidence anchors, append-only artifacts, and replay-safe checksum lineage for future condition systems.

## Relationship to P40-02 through P40-05

- Required inputs originate from P40-02 normalization and P40-03 boundary mapping.
- P40-04 OCR and P40-05 reconciliation context may be attached when available, but defect foundation remains valid without them.
- The layer never mutates original uploads, normalized artifacts, boundary artifacts, OCR artifacts, or reconciliation artifacts.
- Lineage chains original scan checksum → normalization checksum → boundary checksum → optional OCR checksum → optional reconciliation checksum → defect checksum → defect artifact checksums.

## Condition region model

The service derives a stable ordered region set from boundary geometry only:

1. `FULL_COVER`
2. `SPINE_REGION`
3. `TOP_EDGE`
4. `BOTTOM_EDGE`
5. `LEFT_EDGE`
6. `RIGHT_EDGE`
7. `TOP_LEFT_CORNER`
8. `TOP_RIGHT_CORNER`
9. `BOTTOM_LEFT_CORNER`
10. `BOTTOM_RIGHT_CORNER`
11. `CENTER_SURFACE`
12. `TITLE_AREA`
13. `PRICE_BOX_AREA`

Each region stores:

- absolute image coordinates
- width / height
- deterministic `region_checksum`
- metadata describing its relative position inside the detected cover

Region ordering is fixed so replay runs produce the same manifest ordering and evidence association.

## Quality gate model

Scan-quality gates describe scan reliability, not comic condition. They are driven only by deterministic metadata and pixel statistics:

- `LOW_RESOLUTION`
- `LOW_DPI`
- `EXCESSIVE_BLUR`
- `EXCESSIVE_GLARE`
- `OVEREXPOSED_IMAGE`
- `UNDEREXPOSED_IMAGE`
- `INSUFFICIENT_CONTRAST`
- `PARTIAL_COVER`
- `BAD_BOUNDARY_GEOMETRY`
- `COLOR_SHIFT_DETECTED`

These gates feed reliability issues such as `QUALITY_GATE_FAILED` and `INSUFFICIENT_IMAGE_QUALITY` without implying grade impact.

## Baseline evidence model

The defect foundation does not classify final defects. It records provisional anomaly anchors tied to deterministic regions and categories:

- `EDGE_ANOMALY`
- `CORNER_ANOMALY`
- `SPINE_ANOMALY`
- `SURFACE_ANOMALY`
- `COLOR_ANOMALY`
- `CONTRAST_ANOMALY`
- `GEOMETRY_ANOMALY`

Each evidence row persists:

- linked region id
- evidence type
- category
- severity hint
- confidence score
- bounding box
- measurement payload

Low-confidence evidence is preserved intentionally so later specialized detectors can reason from the same append-only baseline.

## Evidence measurement model

Every evidence item records deterministic measurements with stable rounding and ordered JSON:

- pixel area
- bounding box
- relative cover position
- distance from nearest edge
- region overlap metadata
- brightness delta
- contrast delta
- edge sharpness delta
- color shift delta
- anomaly area ratio
- normalized severity hint

These are evidence primitives only. They are not grades and they are not market judgments.

## Artifact and manifest model

Every successful defect foundation run creates append-only artifacts:

- `DEFECT_REGION_MAP`
- `QUALITY_GATE_REPORT`
- `BASELINE_EVIDENCE_OVERLAY`
- `DEFECT_MANIFEST`
- `DEFECT_DEBUG_PREVIEW`

Artifacts live under deterministic storage paths:

`scan-defects/{owner_user_id}/{scan_image_id}/{defect_run_id}/{artifact_type}.{ext}`

The manifest is stable ordered JSON containing:

- upstream lineage checksums
- condition regions
- scan-quality gates
- evidence list
- issue list
- artifact checksums
- detection engine version
- evidence summary rollups

Its hash becomes `defect_checksum`. Re-running the same inputs returns the existing run.

## Replay-safe checksum lineage

`defect_checksum` is derived from stable ordered payloads only:

- original scan checksum
- normalization checksum
- boundary checksum
- optional OCR checksum
- optional reconciliation checksum
- region definitions
- evidence rows
- issue rows
- artifact checksums

This keeps defect manifests replay-safe and explainable.

## Non-goals

- assigning grades
- estimating grade impact
- estimating market value
- final defect naming
- specialized spine tick detection
- specialized corner / edge wear detection
- surface defect classification
- structural damage classification
- AI restoration or enhancement
- defect removal or image repair
