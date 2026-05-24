"""Read-only deterministic duplicate ownership API schemas."""

from typing import Literal

from pydantic import BaseModel, Field

DuplicateOwnershipClassification = Literal[
    "intentional_multi_copy",
    "probable_accidental_duplicate",
    "duplicate_scan_only",
    "preorder_plus_owned",
    "graded_plus_raw",
    "unresolved_duplicate",
]


class DuplicateOwnershipSignals(BaseModel):
    """Explainability pins for duplicate ownership classifications (computed-only)."""

    shares_metadata_identity_key: bool = False
    metadata_identity_keys: list[str | None] = Field(default_factory=list)
    preorder_and_in_hand_both_present: bool = False
    graded_and_raw_both_present: bool = False
    pending_duplicate_inventory_review: bool = False
    touches_duplicate_scan_cluster: bool = False
    duplicate_scan_evidence_exact: bool = Field(
        default=False,
        description="Deterministic dup-scan escalation (confirmed clusters or dup-scan OCR/SHA cues).",
    )
    overlaps_probable_duplicate_scan_cluster: bool = False
    human_duplicate_scan_approved_pair: bool = False
    human_same_cover_approved_pair: bool = False
    canonical_pending_duplicate_scan_context: bool = False


class DuplicateOwnershipGroupRead(BaseModel):
    group_key: str
    owner_user_id: int | None = None
    classification: DuplicateOwnershipClassification
    inventory_copy_ids: list[int] = Field(default_factory=list)
    signal_flags: DuplicateOwnershipSignals


class DuplicateOwnershipSummary(BaseModel):
    total_groups: int = Field(default=0, ge=0)
    intentional_multi_copy_groups: int = Field(default=0, ge=0)
    probable_accidental_duplicate_groups: int = Field(default=0, ge=0)
    duplicate_scan_only_groups: int = Field(default=0, ge=0)
    preorder_plus_owned_groups: int = Field(default=0, ge=0)
    graded_plus_raw_groups: int = Field(default=0, ge=0)
    unresolved_duplicate_groups: int = Field(default=0, ge=0)


class DuplicateOwnershipListRead(BaseModel):
    summary: DuplicateOwnershipSummary = Field(default_factory=DuplicateOwnershipSummary)
    groups: list[DuplicateOwnershipGroupRead] = Field(default_factory=list)


class DuplicateOwnershipCopyAttachment(BaseModel):
    group_key: str
    classification: DuplicateOwnershipClassification
    sibling_inventory_copy_ids: list[int] = Field(default_factory=list)
