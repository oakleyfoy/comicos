# P40-04 Scan OCR Architecture

## Philosophy

P40-04 adds deterministic OCR extraction on top of P40-02 normalized artifacts and P40-03 boundary geometry. The layer reads immutable upstream artifacts, extracts provisional text regions and candidate metadata, and records replay-safe manifests without reconciling comics or inferring canonical identities.

## Relationship to P40-02 and P40-03

- Input must be a completed normalization run with a `FINAL_NORMALIZED` artifact.
- Input must also include a completed boundary run so OCR zones are derived from stable cover geometry rather than content-aware segmentation.
- Lineage chains original scan checksum → normalization checksum → boundary checksum → OCR manifest checksum → OCR artifact checksums.

## Deterministic OCR handling

The pipeline uses fixed OCR zones, stable region ordering, deterministic text normalization, and a single OCR engine version string. The stages are:

1. Load the immutable normalized artifact
2. Read boundary geometry from P40-03
3. Derive stable OCR zones (`TITLE`, `ISSUE_NUMBER`, `PUBLISHER`, `DATE`, `PRICE_BOX`, `LOGO`, `GENERIC_TEXT`)
4. Execute OCR per zone
5. Preserve raw OCR text and normalized OCR text separately
6. Generate provisional candidates with deterministic confidence scoring
7. Emit overlays, text exports, manifest artifacts, and append-only history rows

No AI completion, reconciliation, grading logic, or defect interpretation is used.

## OCR candidate lifecycle

- `ScanOcrTextRegion` stores the raw OCR result, normalized OCR text, geometry, confidence, and region metadata.
- `ScanOcrCandidate` stores provisional title / issue / publisher / date / price candidates linked back to their source region.
- Candidates are not canonical comic identities. They exist only as replay-safe OCR outputs for future downstream reconciliation layers.

## OCR confidence model

Confidence remains deterministic and metadata-driven. Region confidence is derived from contrast spread plus text density, then candidate confidence applies small fixed bonuses for region-specific matches. This keeps repeated identical inputs stable without relying on external scoring systems.

## Replay-safe checksum propagation

Manifest JSON is serialized with stable key ordering and deterministic list ordering for regions, candidates, issues, and artifacts. `ocr_checksum` hashes:

- source checksums
- OCR engine version
- OCR region payloads
- candidate payloads
- issue payloads
- confidence summary
- artifact checksums

Repeated runs on identical inputs return the existing run instead of generating a divergent lineage branch.

## Artifact lineage

Artifact types:

- `OCR_OVERLAY`
- `OCR_REGION_MAP`
- `OCR_TEXT_EXPORT`
- `OCR_MANIFEST`
- `OCR_DEBUG_PREVIEW`

Storage paths follow:

`scan-ocr/{owner_user_id}/{scan_image_id}/{ocr_run_id}/{artifact_type}.{ext}`

## Non-goals

- Canonical comic matching
- External marketplace reconciliation
- AI semantic OCR correction
- Multilingual / ML OCR enhancement
- Grading or defect analysis
- Mutation of normalized or boundary artifacts
