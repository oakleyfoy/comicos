# P40-16 Authentication Assistance Architecture

## Authentication assistance philosophy

P40-16 converts existing scan intelligence into deterministic authenticity-review support signals. The layer records support, conflict, inconclusive, and review-required outputs only. It does not certify authenticity and it does not replace human review.

## Support signal vs certification

Signals describe whether current evidence supports review, conflicts with review, or needs more review. They are reliability statements over existing evidence, not certification claims and not final authenticity decisions.

## Identity consistency model

Identity consistency evaluates local evidence in deterministic priority order:

- reconciliation-selected identity
- OCR candidate agreement
- reviewer identity confirmation when available
- historical identity continuity when available

No external catalog lookup, marketplace lookup, or speculative inference is used.

## Metadata consistency model

Metadata consistency compares publisher, title, issue number, and other optional canonical fields only when they are present in upstream records. Missing metadata is preserved as missing rather than inferred.

## Lineage integrity model

The layer validates the checksum chain for the current scan context:

- original scan checksum
- normalization checksum
- boundary checksum
- OCR checksum when present
- reconciliation checksum when present
- visual evidence checksum when present
- historical comparison checksum when present
- review checksum when present

Lineage gaps produce review warnings only. They are not authenticity verdicts.

## Historical consistency model

When P40-15 output exists, P40-16 reuses its recorded match basis, comparison status, deltas, and issues. The authentication layer does not create new historical comparison logic; it only summarizes whether historical results are supportive, conflicting, or inconclusive for review.

## Review-required model

Review-required flags are emitted when identity evidence conflicts, metadata conflicts persist, lineage is incomplete, or upstream runs remain inconclusive. Every flag preserves source-system references and remains replay-safe.

## Replay-safe checksum lineage

The authentication manifest preserves:

`original scan lineage -> reconciliation/visual/historical/review lineage -> signals -> findings -> issues -> artifact refs -> authentication_checksum`

Stable ordering is required for signals, findings, issues, history events, and artifact references.

## Non-goals

P40-16 does not:

- certify authenticity
- classify counterfeit status
- detect restoration
- assign official grades
- estimate FMV
- overwrite immutable upstream evidence
- perform external database authentication checks
- run ML-based counterfeit detection
