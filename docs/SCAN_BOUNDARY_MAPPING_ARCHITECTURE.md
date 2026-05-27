# P40-03 Scan Boundary Mapping Architecture

## Philosophy

P40-03 adds deterministic spatial detection on top of P40-02 normalized scan artifacts. The layer identifies the comic cover region, records geometry metadata, and emits preview overlays without interpreting titles, publishers, defects, or grades.

## Relationship to P40-02

- Input must be a completed normalization run with a `FINAL_NORMALIZED` artifact.
- Normalized artifacts remain immutable; boundary mapping only reads them and writes new boundary artifacts.
- Lineage chains original scan checksum → normalized artifact checksum → boundary manifest checksum → boundary artifact checksums.

## Deterministic spatial detection

Detection uses fixed contrast/edge heuristics (`edge_contrast_v1`) with algorithm version `P40-03-v1`. The pipeline:

1. Loads the final normalized image
2. Separates scanner-bed/background margins
3. Detects the outer comic boundary (rectangle/polygon)
4. Computes cover geometry and confidence
5. Emits deterministic issues from metadata thresholds
6. Writes append-only history and artifacts

No ML, OCR, or content classification is used.

## Geometry metadata model

Output manifests include bounding box coordinates, corner coordinates, aspect ratio, skew angle, cover area, image area, coverage ratio, and margin-to-edge distances. These values are stored in `output_manifest_json` and mirrored in the geometry manifest artifact.

## Boundary artifact lineage

Artifact types:

- `BOUNDARY_OVERLAY`
- `COVER_BOX_PREVIEW`
- `BACKGROUND_MASK`
- `GEOMETRY_MANIFEST`

Storage paths follow:

`scan-boundary/{owner_user_id}/{scan_image_id}/{boundary_run_id}/{artifact_type}.{ext}`

## Issue detection model

Issues are geometry/metadata driven with severities `INFO`, `WARNING`, and `ERROR`. Examples include low confidence, clipping, excessive background, aspect ratio anomalies, and partial cover visibility.

## Replay-safe checksum propagation

Manifest JSON is serialized with stable key ordering. `boundary_checksum` hashes algorithm version, source checksum, detection outputs, geometry, issues, and artifact checksums. Repeated runs on identical inputs return the existing run.

## Non-goals

- AI-based cover segmentation
- OCR-assisted boundary refinement
- Title/logo-aware detection
- Defect-aware boundary adjustment
- Destructive cropping or background removal
- Publisher/title matching or marketplace features
