# P40 Storage Architecture

This document describes how P40 stores immutable scan artifacts, feed exports, and replay evidence.

## Storage roots

- Each phase owns its own storage root.
- Feed artifacts use the configured feed storage root.
- Replay artifacts use the configured replay storage root.
- Hardening and documentation artifacts live in the repository `docs/` tree, not in runtime storage.

## Artifact path conventions

- Phase artifacts should remain rooted to their owning run id and scan image id.
- Feed artifacts use deterministic storage paths under the feed root.
- Replay artifacts use deterministic storage paths under the replay root.

## Deterministic path rules

- Path generation must be stable for identical owner, scan image, run id, and artifact type inputs.
- Directory naming should remain replay-safe and append-only.
- Path traversal outside the configured root is not allowed.

## Append-only rules

- Never overwrite an upstream artifact in place.
- When a new export is needed, create a new artifact row and a new immutable file path.
- History rows remain append-only.

## Replay artifact rules

- Replay artifacts are verification evidence only.
- Replay artifacts may summarize upstream data but never replace upstream evidence.
- Replay artifacts should remain stable for identical replay inputs.

## Lineage storage rules

- Stored artifacts should keep direct references back to their source run ids and scan ids.
- Checksum metadata must be preserved alongside the artifact bytes.
- Artifact lineage should be readable from the database without reconstructing from filenames.

## Checksum ownership

- The database row owns the canonical checksum metadata.
- The file system owns the canonical bytes.
- Validation compares the two and preserves discrepancies when they differ.

## Storage isolation guidance

- Keep production storage roots separate from scratch and test roots.
- Do not mix debug output with production artifact directories.
- Prefer durable storage backed by the deployed environment, not local developer scratch space.

## Cloud-storage readiness notes

- The path convention is compatible with future object storage mapping.
- The current implementation uses deterministic filesystem-backed paths.
- Cloud migration should preserve checksum and row identity semantics first, then storage backend changes.

## Replay regeneration philosophy

- Replay may regenerate verification artifacts only as new append-only evidence.
- Replay must not mutate the upstream files it audits.
- The storage architecture favors visible evidence over silent repair.

