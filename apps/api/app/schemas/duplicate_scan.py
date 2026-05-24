from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

DuplicateScanClusterClassification = Literal["confirmed", "probable"]

DuplicateScanEvidenceStrength = Literal[
    "human_confirmed",
    "sha256_exact_match",
    "probable_duplicate_scan_group",
    "fingerprint_similarity",
    "mixed",
]

DuplicateScanClassificationFilter = Literal["all", "confirmed", "probable", "suppressed"]




class DuplicateScanEvidenceFlags(BaseModel):
    human_duplicate_scan_confirmed: bool = False
    sha256_exact_match: bool = False
    probable_duplicate_scan_match_group: bool = False
    fingerprint_similarity_probable: bool = False
    supporting_shared_upcs: list[str] = Field(default_factory=list)


class DuplicateScanDuplicatePeerRead(BaseModel):
    peer_cover_image_id: int
    pair_key: str
    canonical_pair_low_id: int
    canonical_pair_high_id: int
    classification: DuplicateScanClusterClassification
    evidences: DuplicateScanEvidenceFlags
    evidence_detail: dict[str, Any]
    match_candidate_ids: list[int]
    human_duplicate_scan_decision_id: int | None = None


class DuplicateScanSamplePairRead(BaseModel):
    canonical_pair_low_id: int
    canonical_pair_high_id: int
    classification: DuplicateScanClusterClassification
    evidences: DuplicateScanEvidenceFlags
    evidence_strength: DuplicateScanEvidenceStrength


class DuplicateScanClusterRead(BaseModel):
    cluster_key: str
    cover_image_ids: list[int]
    cluster_size: int
    classification: DuplicateScanClusterClassification
    evidence_strength: DuplicateScanEvidenceStrength


class DuplicateScanSuppressedPairRead(BaseModel):
    pair_key: str
    left_cover_image_id: int
    right_cover_image_id: int
    suppressed_signal_labels: list[str]
    evidence_snapshot: DuplicateScanEvidenceFlags


class DuplicateScanCandidatesResponse(BaseModel):
    focal_cover_image_id: int
    touching_clusters: list[DuplicateScanClusterRead]
    duplicate_peers: list[DuplicateScanDuplicatePeerRead]
    suppressed_pairs_touching_focal: list[DuplicateScanSuppressedPairRead]


class DuplicateScanClustersListResponse(BaseModel):
    clusters: list[DuplicateScanClusterRead]
    suppressed_pairs: list[DuplicateScanSuppressedPairRead]
    classification_filter: DuplicateScanClassificationFilter
