"""P100 photo import API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PhotoImportSessionCreatePayload(BaseModel):
    source_device: str | None = None
    capture_mode: str | None = Field(
        default=None,
        description="single_comic (default) or group (experimental)",
    )


class PhotoImportSessionRead(BaseModel):
    id: int
    session_token: str
    status: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None
    source_device: str | None
    confirmed_count: int
    uploaded_photo_count: int
    detected_book_count: int
    capture_mode: str
    mobile_url: str
    desktop_review_url: str
    vision_sandbox: bool = False


class PhotoImportVisionReadPayload(BaseModel):
    id: int
    session_id: int
    image_id: int
    publisher: str | None
    series: str | None
    issue_number: str | None
    issue_title: str | None
    variant_description: str | None
    year: str | None
    cover_date: str | None
    barcode: str | None
    confidence: float | None
    reasoning: str | None
    raw_response: dict | None
    is_correct: bool | None = None
    feedback_notes: str | None = None
    created_at: datetime


class PhotoImportVisionReadFeedbackPayload(BaseModel):
    is_correct: bool
    feedback_notes: str | None = None


class PhotoImportVisionSandboxMetricsRead(BaseModel):
    total_reads: int
    correct_reads: int
    incorrect_reads: int
    pending_feedback: int
    accuracy_percent: float
    publisher_accuracy: float
    series_accuracy: float
    issue_accuracy: float
    top_failures: list[dict[str, object]]
    most_misidentified_series: list[dict[str, object]]
    most_misidentified_publishers: list[dict[str, object]]


class PhotoImportHeartbeatPayload(BaseModel):
    source_device: str | None = None
    capture_mode: str | None = Field(
        default=None,
        description="single_comic or group (experimental)",
    )


class PhotoImportImageRead(BaseModel):
    id: int
    session_id: int
    original_filename: str
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    status: str
    created_at: datetime


class PhotoImportDetectedBookRead(BaseModel):
    id: int
    session_id: int
    image_id: int
    crop_path: str | None
    crop_image_url: str | None = None
    display_image_url: str | None = None
    bbox_x: float
    bbox_y: float
    bbox_width: float
    bbox_height: float
    status: str
    recognition_status: str
    candidate_count: int
    selected_catalog_issue_id: int | None
    selected_variant_id: int | None
    confidence: float
    ai_series: str | None
    ai_issue_number: str | None
    ai_publisher: str | None
    ai_subtitle_guess: str | None = None
    ai_variant_hint: str | None
    ai_variant_guess: str | None = None
    ai_cover_year: str | None
    ai_visible_title_text: str | None = None
    ai_visible_issue_text: str | None = None
    ai_visible_publisher_text: str | None = None
    ai_visible_character_text: str | None = None
    ai_uncertainty_reason: str | None = None
    ai_alternate_titles: list[str] | None = None
    ai_confidence: float | None
    ai_reason: str | None
    can_confirm: bool = False
    needs_match: bool = False
    review_status: str = "needs_match"
    best_candidate: "PhotoImportCandidateRead | None" = None
    source_image_url: str | None = None
    recognition_source: str | None = None
    display_crop: bool = False
    recognition_mode: str | None = None
    ai_barcode: str | None = None
    verification_reason: str | None = None
    vision_identification_label: str | None = None
    catalog_verification_status: str | None = None
    catalog_verification_label: str | None = None
    catalog_disagreement_reason: str | None = None


class PhotoImportCandidateRead(BaseModel):
    id: int
    detected_book_id: int
    catalog_issue_id: int
    variant_id: int | None
    publisher: str | None
    series: str | None
    issue_number: str | None
    variant_name: str | None
    cover_url: str | None
    thumbnail_url: str | None = None
    release_date: str | None
    match_score: float
    match_reason: str | None
    matched_on: str | None = None
    rank: int
    base_text_score: float | None = None
    cover_similarity_score: float | None = None
    fingerprint_score: float | None = None
    barcode_score: float | None = None
    final_score: float | None = None
    visual_score_status: str | None = None
    visual_match_label: str | None = None


class PhotoImportCandidateDebugInfo(BaseModel):
    search_terms_used: list[str]
    candidate_count: int
    best_match_score: float
    match_input: dict[str, object]


class PhotoImportDetectionCandidatesResponse(BaseModel):
    detection: PhotoImportDetectedBookRead
    candidates: list[PhotoImportCandidateRead]
    selected_candidate: PhotoImportCandidateRead | None
    debug: PhotoImportCandidateDebugInfo


class PhotoImportSelectCandidatePayload(BaseModel):
    candidate_id: int


class PhotoImportConfirmItemPayload(BaseModel):
    detected_book_id: int
    catalog_issue_id: int
    variant_id: int | None = None
    quantity: int = Field(default=1, ge=1, le=99)


class PhotoImportConfirmPayload(BaseModel):
    items: list[PhotoImportConfirmItemPayload]
    notes: str | None = None
    cost: str | None = None
    condition: str | None = None


class PhotoImportConfirmResponse(BaseModel):
    acquisition_id: int
    inventory_copy_ids: list[int]
    confirmed_count: int


class PhotoImportBulkIdsPayload(BaseModel):
    detected_book_ids: list[int]


PhotoImportDetectedBookRead.model_rebuild()
PhotoImportDetectionCandidatesResponse.model_rebuild()
