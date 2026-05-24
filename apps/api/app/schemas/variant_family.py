from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

VariantFamilyClusterClassification = Literal["confirmed", "probable"]

VariantFamilyEvidenceStrength = Literal[
    "human_confirmed_variant_family",
    "probable_variant_family_group",
    "same_issue_divergent_fingerprint",
    "metadata_identity_divergent_fingerprint",
    "mixed",
]

VariantFamilyClassificationFilter = Literal["all", "confirmed", "probable", "suppressed"]


class VariantFamilyEvidenceFlags(BaseModel):
    """Deterministic pairwise evidence surfaced to the UI."""

    human_variant_family: bool = False
    probable_variant_family_group: bool = False
    same_issue_divergent_fingerprint: bool = False
    metadata_identity_normalized: bool = False
    ocr_title_issue_exact_pairwise: bool = False
    publisher_exact_pairwise: bool = False
    fingerprint_divergent_signal: bool = False
    supporting_shared_upcs: list[str] = Field(default_factory=list)


class VariantFamilyPeerRead(BaseModel):
    peer_cover_image_id: int
    pair_key: str
    canonical_pair_low_id: int
    canonical_pair_high_id: int
    classification: VariantFamilyClusterClassification
    evidences: VariantFamilyEvidenceFlags
    evidence_detail: dict[str, Any]
    match_candidate_ids: list[int]
    human_variant_family_decision_id: int | None = None


class VariantFamilyClusterRead(BaseModel):
    cluster_key: str
    cover_image_ids: list[int]
    cluster_size: int
    classification: VariantFamilyClusterClassification
    evidence_strength: VariantFamilyEvidenceStrength


class VariantFamilySuppressedPairRead(BaseModel):
    pair_key: str
    left_cover_image_id: int
    right_cover_image_id: int
    suppressed_signal_labels: list[str]
    evidence_snapshot: VariantFamilyEvidenceFlags


class VariantFamilyCandidatesResponse(BaseModel):
    focal_cover_image_id: int
    touching_clusters: list[VariantFamilyClusterRead]
    variant_peers: list[VariantFamilyPeerRead]
    suppressed_pairs_touching_focal: list[VariantFamilySuppressedPairRead]


class VariantFamilyClustersListResponse(BaseModel):
    clusters: list[VariantFamilyClusterRead]
    suppressed_pairs: list[VariantFamilySuppressedPairRead]
    classification_filter: VariantFamilyClassificationFilter
