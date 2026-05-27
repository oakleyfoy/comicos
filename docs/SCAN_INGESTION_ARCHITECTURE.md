# Scan Ingestion Architecture

P40-01 establishes the deterministic visual ingestion foundation for ComicOS.

## Philosophy

This layer is ingestion only.

- Accept scan uploads.
- Register immutable originals.
- Capture stable image and scanner metadata.
- Generate deterministic checksums.
- Record append-only ingestion events.

This layer does not perform OCR, grading, defect detection, or AI analysis.

## Immutable Originals

- The original uploaded bytes are written once to deterministic storage paths.
- Originals are content-addressed by checksum.
- Variants never overwrite originals.
- Duplicate uploads reuse immutable storage while still recording registration history.

## Storage Model

- Originals live under the configured scan-ingestion storage root.
- Variants live under deterministic derivative paths scoped by parent image and checksum.
- Storage paths remain relative so the ledger can later target filesystem, Render disk, S3, or another object store adapter.

## Deterministic Registration

- Files are sorted deterministically before batch registration.
- Batch and upload-session checksums are computed from canonical payloads.
- Duplicate detection is checksum-based only.
- Replay of the same logical batch returns the existing batch rather than mutating history.

## Upload Session Flow

1. Owner stages image files or ZIP import.
2. Upload session checksum is computed from canonical file facts.
3. Scan ingestion batch checksum is computed from the deterministic registration payload.
4. Each original is registered as a `scan_image` row.
5. Derived variants are registered append-only as `scan_image_variant` rows.
6. Events are appended to `scan_ingestion_event`.

## Non-Goals

P40-01 does not include:

- OCR processing
- defect analysis
- grading logic
- AI scan interpretation
- ML classification
- image enhancement intelligence
- live scanner streaming
