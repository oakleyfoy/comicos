# P40-02 Scan Normalization Architecture

## Philosophy

P40-02 is a deterministic image-preparation layer for ComicOS. It exists to make future OCR, defect analysis, grading review, and visual evidence systems operate on stable preprocessed inputs without mutating the original scan asset.

This phase does not interpret comic content. It only performs repeatable geometric and tonal preparation:

- orientation normalization
- border-aware crop cleanup
- mild perspective correction
- color normalization
- deterministic derivative generation
- append-only issue + lineage recording

## Immutable handling

- Original scan files remain immutable in the scan-ingestion storage root.
- Normalization never overwrites a source image.
- Every derived stage is written as a new normalization artifact with its own checksum.
- Replay-safe requests return the original normalization run when the source image and deterministic stage outputs match.

## Artifact lineage

Each successful normalization run emits the following artifact chain in fixed order:

1. `ROTATED`
2. `CROPPED`
3. `PERSPECTIVE_FIXED`
4. `COLOR_NORMALIZED`
5. `FINAL_NORMALIZED`
6. `THUMBNAIL`

Each artifact records:

- owning run + scan image
- deterministic order
- parent artifact linkage
- parent checksum
- artifact checksum
- storage path
- dimensions + DPI metadata

This creates a replay-safe checksum lineage from source scan to final normalized derivative.

## Checksum propagation

- Source image checksum begins the lineage.
- Each stage computes a deterministic artifact checksum.
- History rows preserve `from_checksum` -> `to_checksum` for every stage transition.
- The run checksum is derived from source checksum, stage checksums, stage order, and issue outputs.
- If a rerun produces the same run checksum for the same owner, the existing run is reused instead of creating a duplicate ledger entry.

## Issue detection model

Issue detection is deterministic and metadata-driven only. P40-02 intentionally avoids ML classification and semantic image understanding.

Current issue examples:

- `LOW_DPI`
- `EXCESSIVE_SKEW`
- `EXTREME_SHADOW`
- `OVEREXPOSED`
- `UNDEREXPOSED`
- `PARTIAL_SCAN`
- `BORDER_CLIPPING`

These are derived from scanner metadata, crop geometry, brightness histograms, and border/canvas coverage rather than learned models.

## Storage model

- Normalization artifacts live under a dedicated normalization storage root.
- Paths are deterministic by scan image id, artifact type, source checksum prefix, and artifact checksum.
- Storage naming is filesystem-backed today but remains compatible with future object-storage abstraction.
- The API returns metadata and preview payloads without requiring destructive or in-place mutations.

## Non-goals

P40-02 explicitly does not include:

- OCR
- grading intelligence
- defect detection
- AI enhancement
- detail invention or restoration
- aggressive sharpening
- hallucinated perspective reconstruction
- destructive cleanup of source images
