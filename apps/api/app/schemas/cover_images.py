from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cover_link_decisions import CoverImageLinkDecisionRead


CoverSourceType = Literal["upload", "gmail_attachment", "import_image"]
CoverProcessingStatus = Literal["pending", "processing", "processed", "failed"]
CoverDerivativeType = Literal["thumb", "medium"]
CoverOcrRegionType = Literal[
    "full_cover",
    "title_region",
    "issue_region",
    "publisher_region",
    "barcode_region",
    "lower_text_region",
]
CoverOcrCandidateType = Literal["title", "issue_number", "publisher", "creator", "barcode"]
CoverOcrCandidateReviewStatus = Literal["pending", "approved", "rejected"]
CoverBarcodeType = Literal["upc_a", "upc_e", "unknown"]
CoverBarcodeReviewState = Literal["pending", "approved", "rejected"]
CoverFingerprintType = Literal["phash", "ahash", "dhash"]
CoverFingerprintDerivativeType = Literal["original", "thumb", "medium"]
CoverOcrQualityType = Literal[
    "blur_detection",
    "low_resolution",
    "low_contrast",
    "unreadable_ocr",
    "crop_quality",
    "overall_quality",
]
CoverOcrQualitySeverity = Literal["info", "warning", "critical"]
CoverMatchCandidateType = Literal[
    "fingerprint_similarity",
    "barcode_similarity",
    "ocr_similarity",
    "combined_similarity",
]
CoverMatchConfidenceBucket = Literal["very_high", "high", "medium", "low", "very_low"]
CoverMatchGroupingType = Literal[
    "probable_same_issue",
    "probable_same_cover",
    "probable_duplicate_scan",
    "probable_variant_family",
]
CoverOcrReconciliationWarningType = Literal[
    "title_mismatch",
    "issue_number_mismatch",
    "publisher_mismatch",
    "barcode_present",
    "missing_metadata",
    "low_confidence_candidate",
]
CoverOcrReconciliationWarningSeverity = Literal["info", "warning", "critical"]
CoverOcrReconciliationWarningStatus = Literal["open", "acknowledged", "dismissed"]
CoverMatchingStatus = Literal["not_ready", "ready", "needs_review", "failed"]
CoverOcrProcessingStatus = Literal["pending", "processing", "processed", "failed"]


class CoverImageDerivativeRead(BaseModel):
    id: int
    derivative_type: CoverDerivativeType
    mime_type: str
    image_width: int | None = None
    image_height: int | None = None
    file_size: int | None = None
    sha256_hash: str
    generated_at: datetime
    created_at: datetime
    fetch_path: str = Field(description="Example: `/files/cover-images/{id}/derivatives/{type}`")


class StructuredProcessingErrorRead(BaseModel):
    error_code: str
    error_type: str
    safe_message: str
    retryable: bool
    occurred_at: str


class CoverImageOcrResultRead(BaseModel):
    id: int
    cover_image_id: int
    ocr_engine: str
    ocr_engine_version: str | None = None
    processing_status: CoverOcrProcessingStatus = "pending"
    raw_text: str
    normalized_text: str | None = None
    confidence_score: float | None = None
    processing_error: str | None = None
    structured_processing_error: StructuredProcessingErrorRead | None = None
    processed_at: datetime | None = None
    created_at: datetime
    source_cover_image_sha256: str | None = None
    source_thumb_derivative_sha256: str | None = None
    source_medium_derivative_sha256: str | None = None
    source_processing_version: str | None = None
    normalization_version: str | None = None
    replay_of_ocr_result_id: int | None = None
    replay_reason: str | None = None
    snapshot: "CoverImageOcrSnapshotRead"


class CoverImageOcrSnapshotRead(BaseModel):
    """Immutable OCR snapshot fields needed for replay/audit visibility."""

    ocr_engine: str
    ocr_engine_version: str | None = None
    raw_text: str
    normalized_text: str | None = None
    confidence_score: float | None = None
    source_cover_image_sha256: str | None = None
    source_thumb_derivative_sha256: str | None = None
    source_medium_derivative_sha256: str | None = None
    source_processing_version: str | None = None
    normalization_version: str | None = None
    created_at: datetime


CoverImageOcrResultRead.model_rebuild()


class CoverImageOcrRegionRead(BaseModel):
    id: int
    cover_image_id: int
    derivative_id: int | None = None
    region_type: CoverOcrRegionType
    storage_path: str
    mime_type: str
    image_width: int | None = None
    image_height: int | None = None
    file_size: int | None = None
    sha256_hash: str
    extraction_version: str
    created_at: datetime
    fetch_path: str = Field(description="Example: `/files/cover-images/{id}/ocr-regions/{region_type}`")


class CoverImageOcrCandidateRead(BaseModel):
    id: int
    cover_image_id: int
    ocr_result_id: int
    candidate_type: CoverOcrCandidateType
    raw_candidate_text: str
    normalized_candidate_text: str | None = None
    confidence_score: float | None = None
    extraction_source: CoverOcrRegionType
    extraction_version: str
    created_at: datetime
    review_status: CoverOcrCandidateReviewStatus = "pending"
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    review_notes: str | None = None


class CoverImageOcrCandidateReviewNotesPayload(BaseModel):
    """Update free-form review notes (does not implicitly approve/reject)."""

    review_notes: str | None = Field(default=None, max_length=4000)


class CoverImageBarcodeCandidateRead(BaseModel):
    id: int
    cover_image_id: int
    source_ocr_result_id: int | None = None
    source_ocr_candidate_id: int | None = None
    raw_barcode_value: str
    normalized_upc_value: str
    barcode_type: CoverBarcodeType = "unknown"
    confidence: float | None = None
    extraction_version: str
    review_state: CoverBarcodeReviewState = "pending"
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class CoverImageBarcodeCandidateExtractResponse(BaseModel):
    cover_image_id: int
    candidate_count: int
    candidates: list[CoverImageBarcodeCandidateRead] = Field(default_factory=list)


class CoverImageBarcodeCandidateReviewCounts(BaseModel):
    pending: int = Field(ge=0, default=0)
    approved: int = Field(ge=0, default=0)
    rejected: int = Field(ge=0, default=0)


class CoverImageFingerprintRead(BaseModel):
    id: int
    cover_image_id: int
    fingerprint_type: CoverFingerprintType
    fingerprint_value: str
    derivative_type: CoverFingerprintDerivativeType
    image_width: int | None = None
    image_height: int | None = None
    image_sha256: str | None = None
    extraction_version: str
    created_at: datetime
    updated_at: datetime


class CoverImageFingerprintGenerateResponse(BaseModel):
    cover_image_id: int
    fingerprint_count: int = Field(ge=0, default=0)
    fingerprints: list[CoverImageFingerprintRead] = Field(default_factory=list)


class CoverImageOcrQualityAnalysisRead(BaseModel):
    id: int
    cover_image_id: int
    source_ocr_result_id: int | None = None
    quality_type: CoverOcrQualityType
    deterministic_score: float
    severity: CoverOcrQualitySeverity
    detail_json: dict = Field(default_factory=dict)
    extraction_version: str
    created_at: datetime
    updated_at: datetime


class CoverImageOcrQualityAnalysisResponse(BaseModel):
    cover_image_id: int
    analysis_count: int = Field(ge=0, default=0)
    analyses: list[CoverImageOcrQualityAnalysisRead] = Field(default_factory=list)


class CoverImageMatchConfidenceBreakdownRead(BaseModel):
    contributing_signals: list[dict] = Field(default_factory=list)
    penalties: list[dict] = Field(default_factory=list)
    matched_fields: list[str] = Field(default_factory=list)
    failed_fields: list[str] = Field(default_factory=list)
    confidence_explanation_summary: str | None = None
    positive_score_total: float = 0.0
    penalty_total: float = 0.0


class CoverImageMatchCandidateRead(BaseModel):
    id: int
    source_cover_image_id: int
    candidate_cover_image_id: int
    candidate_type: CoverMatchCandidateType
    confidence_bucket: CoverMatchConfidenceBucket
    deterministic_score: float
    normalized_confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_version: str
    scoring_breakdown_json: dict = Field(default_factory=dict)
    matched_signal_count: int = Field(ge=0, default=0)
    hard_match_flags_json: dict = Field(default_factory=dict)
    weak_signal_flags_json: dict = Field(default_factory=dict)
    ranking_score: float = 0.0
    ranking_version: str
    ranking_reason_json: dict = Field(default_factory=dict)
    candidate_rank: int = Field(ge=0, default=0)
    grouping_key: str | None = None
    grouping_type: CoverMatchGroupingType | None = None
    grouping_confidence_bucket: CoverMatchConfidenceBucket | None = None
    grouping_reason_summary: str | None = None
    matched_signals: dict = Field(default_factory=dict)
    contributing_signals: list[dict] = Field(default_factory=list)
    penalties: list[dict] = Field(default_factory=list)
    matched_fields: list[str] = Field(default_factory=list)
    failed_fields: list[str] = Field(default_factory=list)
    confidence_explanation_summary: str | None = None
    extraction_version: str
    created_at: datetime
    updated_at: datetime
    dismissed_at: datetime | None = None
    acknowledged_at: datetime | None = None
    active_link_decision: CoverImageLinkDecisionRead | None = None


class CoverImageMatchCandidateGenerateResponse(BaseModel):
    cover_image_id: int
    candidate_count: int = Field(ge=0, default=0)
    candidates: list[CoverImageMatchCandidateRead] = Field(default_factory=list)


class CoverImageMatchGroupRead(BaseModel):
    grouping_key: str
    grouping_type: CoverMatchGroupingType
    grouping_confidence_bucket: CoverMatchConfidenceBucket
    grouping_reason_summary: str | None = None
    candidate_count: int = Field(ge=0, default=0)
    candidates: list[CoverImageMatchCandidateRead] = Field(default_factory=list)


class CoverImageOcrReconciliationWarningRead(BaseModel):
    id: int
    cover_image_id: int
    inventory_copy_id: int | None = None
    ocr_candidate_id: int | None = None
    warning_type: CoverOcrReconciliationWarningType
    severity: CoverOcrReconciliationWarningSeverity
    current_metadata_value: str | None = None
    candidate_value: str | None = None
    message: str
    status: CoverOcrReconciliationWarningStatus = "open"
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by_user_id: int | None = None


class CoverImageOcrReconciliationResponse(BaseModel):
    cover_image_id: int
    warning_count: int = Field(ge=0, default=0)
    warnings: list[CoverImageOcrReconciliationWarningRead] = Field(default_factory=list)


class CoverImageOcrReconciliationWarningCounts(BaseModel):
    open: int = Field(ge=0, default=0)
    acknowledged: int = Field(ge=0, default=0)
    dismissed: int = Field(ge=0, default=0)


CoverImageOcrQueueStatus = Literal["idle", "queued", "running"]


class CoverImageOcrVisibility(BaseModel):
    """Queue/workflow state for OCR (no interpretation of OCR text)."""

    job_status: CoverImageOcrQueueStatus = "idle"
    retry_available: bool = Field(
        default=False,
        description="True when the cover can accept a new OCR run (not blocked by readiness or an active worker job).",
    )
    ocr_run_count: int = Field(
        ge=0,
        description="Total persisted CoverImageOcrResult rows for this cover (including pending/processing rows).",
    )
    prior_run_created_ats: list[datetime] = Field(
        default_factory=list,
        description="Most recent OCR run timestamps before the latest result (newest-first), capped.",
    )


class CoverImageRead(BaseModel):
    id: int
    inventory_copy_id: int | None
    canonical_series_id: int | None
    draft_import_id: int | None
    source_type: str
    original_filename: str | None
    mime_type: str
    image_width: int | None
    image_height: int | None
    file_size: int | None
    sha256_hash: str
    processing_status: CoverProcessingStatus = "pending"
    processing_error: str | None = None
    file_structured_processing_error: StructuredProcessingErrorRead | None = None
    processed_at: datetime | None = None

    metadata_refreshed_at: datetime | None = None
    matching_status: CoverMatchingStatus = "not_ready"
    matching_notes: str | None = None
    ready_for_matching_at: datetime | None = None
    latest_ocr_result: CoverImageOcrResultRead | None = None
    ocr_visibility: CoverImageOcrVisibility = Field(
        default_factory=CoverImageOcrVisibility,
        description="OCR workflow visibility (RQ job state, history counts, retry gating).",
    )
    ocr_regions: list[CoverImageOcrRegionRead] = Field(default_factory=list)
    ocr_candidates: list[CoverImageOcrCandidateRead] = Field(default_factory=list)
    barcode_candidates: list[CoverImageBarcodeCandidateRead] = Field(default_factory=list)
    fingerprints: list[CoverImageFingerprintRead] = Field(default_factory=list)
    ocr_quality_analyses: list[CoverImageOcrQualityAnalysisRead] = Field(default_factory=list)
    match_candidates: list[CoverImageMatchCandidateRead] = Field(default_factory=list)
    ocr_reconciliation_warnings: list[CoverImageOcrReconciliationWarningRead] = Field(
        default_factory=list
    )
    thumbnail_fetch_path: str | None = None
    medium_fetch_path: str | None = None
    derivatives: list[CoverImageDerivativeRead] = Field(default_factory=list)
    created_at: datetime
    is_primary: bool = Field(
        default=False,
        description="Whether this image is the parent's designated primary display cover.",
    )
    fetch_path: str = Field(description="Example: `/files/cover-images/{id}` — use Bearer token with GET.")


class CoverImageAssignExistingPayload(BaseModel):
    cover_image_id: int = Field(ge=1)
    set_primary: bool = False


class CoverImageReturnToDraftPayload(BaseModel):
    draft_import_id: int = Field(ge=1)
    set_primary: bool = False


class CoverImageProcessingEnqueueResponse(BaseModel):
    job_id: str
    status: Literal["queued", "already_queued"]
    cover_image_id: int


class CoverImageMatchingEvaluationResponse(BaseModel):
    cover_image_id: int
    matching_status: CoverMatchingStatus
    matching_notes: str | None = None
    ready_for_matching_at: datetime | None = None


class CoverImageOcrEnqueueResponse(BaseModel):
    job_id: str
    status: Literal["queued", "already_queued"]
    cover_image_id: int
    ocr_result_id: int | None = None


class CoverImageOcrReplayPayload(BaseModel):
    replay_reason: str | None = Field(default=None, max_length=500)


class CoverImageOcrRegionExtractResponse(BaseModel):
    cover_image_id: int
    region_count: int
    regions: list[CoverImageOcrRegionRead] = Field(default_factory=list)


class CoverImageOcrCandidateExtractResponse(BaseModel):
    cover_image_id: int
    candidate_count: int
    candidates: list[CoverImageOcrCandidateRead] = Field(default_factory=list)


class CoverImageOcrCandidateReviewCounts(BaseModel):
    """Lightweight aggregate for operations monitoring (no interpretation)."""

    pending: int = Field(ge=0, default=0)
    approved: int = Field(ge=0, default=0)
    rejected: int = Field(ge=0, default=0)


class OpsCoverDuplicateMember(BaseModel):
    """One cover row inside a SHA-256 duplicate group (read-only visibility)."""

    id: int = Field(description="cover_image id")
    source_type: str
    original_filename: str | None = None
    inventory_copy_id: int | None = None
    draft_import_id: int | None = None
    canonical_series_id: int | None = None
    is_primary: bool = False
    created_at: datetime
    file_size: int | None = None
    image_width: int | None = None
    image_height: int | None = None
    owner_email: str | None = Field(
        default=None,
        description="Owner via inventory copy or draft import when linkage exists.",
    )
    matching_status: CoverMatchingStatus = "not_ready"
    matching_notes: str | None = None
    ready_for_matching_at: datetime | None = None
    thumbnail_fetch_path: str | None = None
    medium_fetch_path: str | None = None
    derivatives: list[CoverImageDerivativeRead] = Field(default_factory=list)
    fetch_path: str = Field(description="`/files/cover-images/{id}`")
    latest_ocr_result: CoverImageOcrResultRead | None = None
    ocr_visibility: CoverImageOcrVisibility = Field(
        default_factory=CoverImageOcrVisibility,
        description="Lightweight OCR queue/history for duplicate triage.",
    )


class OpsCoverDuplicateGroup(BaseModel):
    sha256_hash: str
    count: int
    covers: list[OpsCoverDuplicateMember]


class OpsCoverImageRecentRow(BaseModel):
    id: int
    original_filename: str | None = None
    source_type: str
    mime_type: str
    image_width: int | None
    image_height: int | None
    file_size: int | None
    sha256_hash: str
    processing_status: CoverProcessingStatus = "pending"
    processing_error: str | None = None
    processed_at: datetime | None = None
    metadata_refreshed_at: datetime | None = None
    matching_status: CoverMatchingStatus = "not_ready"
    matching_notes: str | None = None
    ready_for_matching_at: datetime | None = None
    latest_ocr_result: CoverImageOcrResultRead | None = None
    ocr_visibility: CoverImageOcrVisibility = Field(
        default_factory=CoverImageOcrVisibility,
        description="OCR queue/history hints for Operations monitoring.",
    )
    ocr_region_count: int = 0
    ocr_candidate_count: int = 0
    ocr_candidate_review_counts: CoverImageOcrCandidateReviewCounts = Field(
        default_factory=CoverImageOcrCandidateReviewCounts,
        description="Counts of OCR candidates by human review status for this cover.",
    )
    has_pending_ocr_candidate_review: bool = Field(
        default=False,
        description="True when at least one OCR candidate row is pending review.",
    )
    barcode_candidate_count: int = 0
    barcode_candidate_review_counts: CoverImageBarcodeCandidateReviewCounts = Field(
        default_factory=CoverImageBarcodeCandidateReviewCounts,
        description="Counts of persisted barcode candidates by review state for this cover.",
    )
    fingerprint_count: int = 0
    ocr_quality_analysis_count: int = 0
    ocr_quality_analyses: list[CoverImageOcrQualityAnalysisRead] = Field(default_factory=list)
    match_candidate_count: int = 0
    open_match_candidate_count: int = 0
    match_candidates: list[CoverImageMatchCandidateRead] = Field(default_factory=list)
    ocr_reconciliation_warning_counts: CoverImageOcrReconciliationWarningCounts = Field(
        default_factory=CoverImageOcrReconciliationWarningCounts,
        description="Counts of OCR reconciliation warnings by state for this cover.",
    )
    open_ocr_reconciliation_warning_count: int = Field(
        default=0,
        ge=0,
        description="Open OCR reconciliation warning rows for this cover.",
    )
    thumbnail_fetch_path: str | None = None
    medium_fetch_path: str | None = None
    derivatives: list[CoverImageDerivativeRead] = Field(default_factory=list)
    created_at: datetime
    inventory_copy_id: int | None
    draft_import_id: int | None
    canonical_series_id: int | None = None
    owner_email: str | None
    is_primary: bool = False
    fetch_path: str = Field(description="`/files/cover-images/{id}`")
