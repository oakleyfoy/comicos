const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const TOKEN_STORAGE_KEY = "comic-os-access-token";

/** Matches backend `metadata_enrichment.RELEASE_DATE_PAYLOAD_SEARCH_FRAGMENT`. */
export const RELEASE_DATE_METADATA_WARNING_FRAGMENT = "Release date format was malformed";
/** Matches notes produced from creator list malformed template (Writer/Artist/… list format…). */
export const CREATOR_METADATA_WARNING_FRAGMENT =
  "list format was malformed or unsupported. Review preserved creator values";

export type SortBy =
  | "title"
  | "publisher"
  | "purchase_date"
  | "acquisition_cost"
  | "current_fmv"
  | "gain_loss"
  | "star_rating";

export type OrderSortBy = "order_date" | "retailer" | "total_amount" | "created_at";
export type ImportSortBy = "created_at" | "updated_at" | "confidence_score" | "status";

export interface RegisterPayload {
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface User {
  id: number;
  email: string;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AiParseOrderPayload {
  raw_text: string;
}

export interface AiDraftOrderItem {
  publisher: string | null;
  title: string | null;
  raw_publisher?: string | null;
  canonical_publisher?: string | null;
  raw_title?: string | null;
  canonical_title?: string | null;
  release_date?: string | null;
  raw_release_date?: string | null;
  parsed_release_date?: string | null;
  parsed_release_year?: number | null;
  release_status?: "released" | "not_released_yet" | "unknown" | null;
  order_status?: "ordered" | "preordered" | "shipped" | "received" | "cancelled" | null;
  purchase_date?: string | null;
  expected_ship_date?: string | null;
  received_at?: string | null;
  issue_number: string | null;
  raw_issue_number?: string | null;
  canonical_issue_number?: string | null;
  cover_name: string | null;
  printing: string | null;
  ratio: string | null;
  variant_type: string | null;
  cover_artist: string | null;
  writers?: string[] | null;
  raw_writers?: string[] | null;
  canonical_writers?: string[] | null;
  artists?: string[] | null;
  raw_artists?: string[] | null;
  canonical_artists?: string[] | null;
  cover_artists?: string[] | null;
  raw_cover_artists?: string[] | null;
  canonical_cover_artists?: string[] | null;
  raw_variant_text?: string | null;
  canonical_variant_text?: string | null;
  metadata_identity_key?: string | null;
  metadata_identity_components?: {
    publisher?: string;
    series_title?: string;
    issue_number?: string;
    variant?: string;
  } | null;
  metadata_review_required?: boolean;
  metadata_review_notes?: string[];
  quantity: number | null;
  raw_item_price: string | null;
}

export type DraftSourceType = "ai_draft" | "manual_draft" | "gmail_draft";

export interface AiParseOrderResponse {
  retailer: string | null;
  order_date: string | null;
  source_type: DraftSourceType;
  shipping_amount: string;
  tax_amount: string;
  items: AiDraftOrderItem[];
  warnings: string[];
  confidence_score: number;
}

export type DraftImportStatus = "draft" | "confirmed" | "discarded";

/* ——— Cover images / OCR ——— */

export type CoverImageSourceType = "upload" | "gmail_attachment" | "import_image";
export type CoverProcessingStatus = "pending" | "processing" | "processed" | "failed";
export type CoverDerivativeType = "thumb" | "medium";
export type CoverOcrRegionType =
  | "full_cover"
  | "title_region"
  | "issue_region"
  | "publisher_region"
  | "barcode_region"
  | "lower_text_region";
export type CoverOcrCandidateType = "title" | "issue_number" | "publisher" | "creator" | "barcode";
export type CoverOcrCandidateReviewStatus = "pending" | "approved" | "rejected";
export type CoverBarcodeType = "upc_a" | "upc_e" | "unknown";
export type CoverBarcodeReviewState = "pending" | "approved" | "rejected";
export type CoverFingerprintType = "phash" | "ahash" | "dhash";
export type CoverFingerprintDerivativeType = "original" | "thumb" | "medium";
export type CoverOcrQualityType =
  | "blur_detection"
  | "low_resolution"
  | "low_contrast"
  | "unreadable_ocr"
  | "crop_quality"
  | "overall_quality";
export type CoverOcrQualitySeverity = "info" | "warning" | "critical";
export type CoverMatchCandidateType =
  | "fingerprint_similarity"
  | "barcode_similarity"
  | "ocr_similarity"
  | "combined_similarity";
export type CoverMatchConfidenceBucket = "very_high" | "high" | "medium" | "low" | "very_low";
export type CoverMatchGroupingType =
  | "probable_same_issue"
  | "probable_same_cover"
  | "probable_duplicate_scan"
  | "probable_variant_family";
export type CoverLinkDecisionType = "approved_link" | "rejected_link" | "needs_review";
export type CoverLinkRelationshipType =
  | "same_cover"
  | "same_issue"
  | "duplicate_scan"
  | "variant_family"
  | "unrelated";
export type CoverLinkDecisionState = "active" | "superseded" | "reverted";
export type CoverLinkDecisionSource = "human" | "system_seeded";
export type CoverOcrReconciliationWarningType =
  | "title_mismatch"
  | "issue_number_mismatch"
  | "publisher_mismatch"
  | "barcode_present"
  | "missing_metadata"
  | "low_confidence_candidate";
export type CoverOcrReconciliationWarningSeverity = "info" | "warning" | "critical";
export type CoverOcrReconciliationWarningStatus = "open" | "acknowledged" | "dismissed";
export type CoverMatchingStatus = "not_ready" | "ready" | "needs_review" | "failed";
export type CoverOcrProcessingStatus = "pending" | "processing" | "processed" | "failed";
export type CoverImageOcrQueueStatus = "idle" | "queued" | "running";

export interface CoverImageDerivativeRead {
  id: number;
  derivative_type: CoverDerivativeType;
  mime_type: string;
  image_width: number | null;
  image_height: number | null;
  file_size: number | null;
  sha256_hash: string;
  generated_at: string;
  created_at: string;
  fetch_path: string;
}

export interface CoverImageOcrSnapshotRead {
  ocr_engine: string;
  ocr_engine_version: string | null;
  raw_text: string;
  normalized_text: string | null;
  confidence_score: number | null;
  source_cover_image_sha256: string | null;
  source_thumb_derivative_sha256: string | null;
  source_medium_derivative_sha256: string | null;
  source_processing_version: string | null;
  normalization_version: string | null;
  created_at: string;
}

export interface StructuredProcessingErrorRead {
  error_code: string;
  error_type: string;
  safe_message: string;
  retryable: boolean;
  occurred_at: string;
}

export interface CoverImageOcrResultRead {
  id: number;
  cover_image_id: number;
  ocr_engine: string;
  ocr_engine_version: string | null;
  processing_status: CoverOcrProcessingStatus;
  raw_text: string;
  normalized_text: string | null;
  confidence_score: number | null;
  processing_error: string | null;
  structured_processing_error?: StructuredProcessingErrorRead | null;
  processed_at: string | null;
  created_at: string;
  source_cover_image_sha256: string | null;
  source_thumb_derivative_sha256: string | null;
  source_medium_derivative_sha256: string | null;
  source_processing_version: string | null;
  normalization_version: string | null;
  replay_of_ocr_result_id: number | null;
  replay_reason: string | null;
  snapshot: CoverImageOcrSnapshotRead;
}

export interface CoverImageOcrRegionRead {
  id: number;
  cover_image_id: number;
  derivative_id: number | null;
  region_type: CoverOcrRegionType;
  storage_path: string;
  mime_type: string;
  image_width: number | null;
  image_height: number | null;
  file_size: number | null;
  sha256_hash: string;
  extraction_version: string;
  created_at: string;
  fetch_path: string;
}

export interface CoverImageOcrCandidateRead {
  id: number;
  cover_image_id: number;
  ocr_result_id: number;
  candidate_type: CoverOcrCandidateType;
  raw_candidate_text: string;
  normalized_candidate_text: string | null;
  confidence_score: number | null;
  extraction_source: CoverOcrRegionType;
  extraction_version: string;
  created_at: string;
  review_status: CoverOcrCandidateReviewStatus;
  reviewed_at: string | null;
  reviewed_by_user_id: number | null;
  review_notes: string | null;
}

export interface CoverImageBarcodeCandidateRead {
  id: number;
  cover_image_id: number;
  source_ocr_result_id: number | null;
  source_ocr_candidate_id: number | null;
  raw_barcode_value: string;
  normalized_upc_value: string;
  barcode_type: CoverBarcodeType;
  confidence: number | null;
  extraction_version: string;
  review_state: CoverBarcodeReviewState;
  reviewed_at: string | null;
  reviewed_by_user_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface CoverImageFingerprintRead {
  id: number;
  cover_image_id: number;
  fingerprint_type: CoverFingerprintType;
  fingerprint_value: string;
  derivative_type: CoverFingerprintDerivativeType;
  image_width: number | null;
  image_height: number | null;
  image_sha256: string | null;
  extraction_version: string;
  created_at: string;
  updated_at: string;
}

export interface CoverImageOcrQualityAnalysisRead {
  id: number;
  cover_image_id: number;
  source_ocr_result_id: number | null;
  quality_type: CoverOcrQualityType;
  deterministic_score: number;
  severity: CoverOcrQualitySeverity;
  detail_json: Record<string, unknown>;
  extraction_version: string;
  created_at: string;
  updated_at: string;
}

export interface CoverImageLinkDecisionCreatePayload {
  source_cover_image_id: number;
  candidate_cover_image_id: number;
  source_match_candidate_id?: number | null;
  decision_type: CoverLinkDecisionType;
  relationship_type: CoverLinkRelationshipType;
  decision_reason?: string | null;
}

export interface CoverImageLinkDecisionRead {
  id: number;
  source_cover_image_id: number;
  candidate_cover_image_id: number;
  pair_key: string;
  source_match_candidate_id: number | null;
  decision_type: CoverLinkDecisionType;
  relationship_type: CoverLinkRelationshipType;
  decision_state: CoverLinkDecisionState;
  reviewer_user_id: number | null;
  reviewer_user_email: string | null;
  decision_reason: string | null;
  decision_source: CoverLinkDecisionSource;
  created_at: string;
  updated_at: string;
  reverted_at: string | null;
  superseded_by_decision_id: number | null;
}

export type CoverRelationshipGraphEdgeLane = "strong" | "related" | "blocked" | "needs_review";

export interface CoverRelationshipGraphInventoryMetadata {
  inventory_copy_id: number;
  title: string;
  publisher: string;
  issue_number: string;
  cover_name: string | null;
}

export interface CoverRelationshipGraphNodeDecisionSummary {
  incident_strong_edges: number;
  incident_related_edges: number;
  incident_blocked_edges: number;
  incident_needs_review_edges: number;
}

export interface CoverRelationshipGraphNode {
  cover_image_id: number;
  inventory: CoverRelationshipGraphInventoryMetadata | null;
  primary_fetch_path: string;
  thumbnail_fetch_path: string | null;
  medium_fetch_path: string | null;
  decision_summary: CoverRelationshipGraphNodeDecisionSummary;
}

export interface CoverRelationshipGraphEdge {
  source_cover_image_id: number;
  candidate_cover_image_id: number;
  relationship_type: CoverLinkRelationshipType;
  decision_type: CoverLinkDecisionType;
  decision_id: number;
  created_at: string;
  reviewer_user_id: number | null;
  decision_reason: string | null;
  display_lane: CoverRelationshipGraphEdgeLane;
}

export interface CoverRelationshipGraphRead {
  center_cover_image_id: number;
  nodes: CoverRelationshipGraphNode[];
  edges: CoverRelationshipGraphEdge[];
}

export type DuplicateScanClassificationFilter = "all" | "confirmed" | "probable" | "suppressed";

export type DuplicateOwnershipClassification =
  | "intentional_multi_copy"
  | "probable_accidental_duplicate"
  | "duplicate_scan_only"
  | "preorder_plus_owned"
  | "graded_plus_raw"
  | "unresolved_duplicate";

export interface DuplicateOwnershipSignals {
  shares_metadata_identity_key: boolean;
  metadata_identity_keys: Array<string | null>;
  preorder_and_in_hand_both_present: boolean;
  graded_and_raw_both_present: boolean;
  pending_duplicate_inventory_review: boolean;
  touches_duplicate_scan_cluster: boolean;
  duplicate_scan_evidence_exact: boolean;
  overlaps_probable_duplicate_scan_cluster: boolean;
  human_duplicate_scan_approved_pair: boolean;
  human_same_cover_approved_pair: boolean;
  canonical_pending_duplicate_scan_context: boolean;
}

export interface DuplicateOwnershipGroup {
  group_key: string;
  owner_user_id: number | null;
  classification: DuplicateOwnershipClassification;
  inventory_copy_ids: number[];
  signal_flags: DuplicateOwnershipSignals;
}

export interface DuplicateOwnershipSummary {
  total_groups: number;
  intentional_multi_copy_groups: number;
  probable_accidental_duplicate_groups: number;
  duplicate_scan_only_groups: number;
  preorder_plus_owned_groups: number;
  graded_plus_raw_groups: number;
  unresolved_duplicate_groups: number;
}

export interface DuplicateOwnershipListResponse {
  summary: DuplicateOwnershipSummary;
  groups: DuplicateOwnershipGroup[];
}

export interface DuplicateOwnershipAttachment {
  group_key: string;
  classification: DuplicateOwnershipClassification;
  sibling_inventory_copy_ids: number[];
}

export type MissingIssueClassification =
  | "confirmed_missing"
  | "likely_missing"
  | "unreleased_future_issue"
  | "preorder_pending"
  | "unresolved_identity_gap";

export type RunDetectionSeriesStatus =
  | "partial_run"
  | "complete_limited_series"
  | "incomplete_limited_series"
  | "probable_ongoing_series"
  | "isolated_special_annual";

export interface RunDetectionSignals {
  has_confirmed_gaps: boolean;
  has_likely_gaps: boolean;
  has_unreleased_future_issues: boolean;
  has_preorder_pending_issues: boolean;
  has_unresolved_identity_gaps: boolean;
  has_isolated_special_or_annual_issues: boolean;
  variant_aware_issue_ownership: boolean;
  uses_canonical_series_identity: boolean;
}

export interface MissingIssue {
  series_key: string;
  owner_user_id: number | null;
  publisher: string;
  title: string;
  issue_number: string | null;
  classification: MissingIssueClassification;
  issue_release_date: string | null;
  related_inventory_copy_ids: number[];
  related_owned_issue_numbers: string[];
  reason: string | null;
}

export interface RunDetectionSeries {
  series_key: string;
  owner_user_id: number | null;
  publisher: string;
  title: string;
  canonical_series_id: number | null;
  series_status: RunDetectionSeriesStatus;
  owned_issue_numbers: string[];
  isolated_issue_numbers: string[];
  inventory_copy_ids: number[];
  distinct_issue_count: number;
  known_issue_count: number;
  missing_issues: MissingIssue[];
  signal_flags: RunDetectionSignals;
}

export interface RunDetectionSummary {
  total_series_groups: number;
  partial_run_groups: number;
  complete_limited_series_groups: number;
  incomplete_limited_series_groups: number;
  probable_ongoing_series_groups: number;
  isolated_special_annual_groups: number;
  total_missing_issue_rows: number;
  confirmed_missing_rows: number;
  likely_missing_rows: number;
  unreleased_future_issue_rows: number;
  preorder_pending_rows: number;
  unresolved_identity_gap_rows: number;
}

export interface RunDetectionListResponse {
  summary: RunDetectionSummary;
  series_groups: RunDetectionSeries[];
}

export interface MissingIssueListResponse {
  summary: RunDetectionSummary;
  items: MissingIssue[];
}

export interface RunDetectionSeriesDetail {
  series_key: string;
  publisher: string;
  title: string;
  owner_groups: RunDetectionSeries[];
  missing_issues: MissingIssue[];
}

export interface RunDetectionAttachment {
  series_key: string;
  series_status: RunDetectionSeriesStatus;
  missing_issue_numbers: string[];
  pending_issue_numbers: string[];
  owned_issue_numbers: string[];
}

export type DuplicateScanEvidenceStrength =
  | "human_confirmed"
  | "sha256_exact_match"
  | "probable_duplicate_scan_group"
  | "fingerprint_similarity"
  | "mixed";

export interface DuplicateScanEvidenceFlags {
  human_duplicate_scan_confirmed: boolean;
  sha256_exact_match: boolean;
  probable_duplicate_scan_match_group: boolean;
  fingerprint_similarity_probable: boolean;
  supporting_shared_upcs: string[];
}

export interface DuplicateScanDuplicatePeerRead {
  peer_cover_image_id: number;
  pair_key: string;
  canonical_pair_low_id: number;
  canonical_pair_high_id: number;
  classification: "confirmed" | "probable";
  evidences: DuplicateScanEvidenceFlags;
  evidence_detail: Record<string, unknown>;
  match_candidate_ids: number[];
  human_duplicate_scan_decision_id: number | null;
}

export interface DuplicateScanClusterRead {
  cluster_key: string;
  cover_image_ids: number[];
  cluster_size: number;
  classification: "confirmed" | "probable";
  evidence_strength: DuplicateScanEvidenceStrength;
}

export interface DuplicateScanSuppressedPairRead {
  pair_key: string;
  left_cover_image_id: number;
  right_cover_image_id: number;
  suppressed_signal_labels: string[];
  evidence_snapshot: DuplicateScanEvidenceFlags;
}

export interface DuplicateScanCandidatesResponse {
  focal_cover_image_id: number;
  touching_clusters: DuplicateScanClusterRead[];
  duplicate_peers: DuplicateScanDuplicatePeerRead[];
  suppressed_pairs_touching_focal: DuplicateScanSuppressedPairRead[];
}

export interface DuplicateScanClustersListResponse {
  clusters: DuplicateScanClusterRead[];
  suppressed_pairs: DuplicateScanSuppressedPairRead[];
  classification_filter: DuplicateScanClassificationFilter;
}

export type VariantFamilyClassificationFilter = "all" | "confirmed" | "probable" | "suppressed";

export type VariantFamilyEvidenceStrength =
  | "human_confirmed_variant_family"
  | "probable_variant_family_group"
  | "same_issue_divergent_fingerprint"
  | "metadata_identity_divergent_fingerprint"
  | "mixed";

export interface VariantFamilyEvidenceFlags {
  human_variant_family: boolean;
  probable_variant_family_group: boolean;
  same_issue_divergent_fingerprint: boolean;
  metadata_identity_normalized: boolean;
  ocr_title_issue_exact_pairwise: boolean;
  publisher_exact_pairwise: boolean;
  fingerprint_divergent_signal: boolean;
  supporting_shared_upcs: string[];
}

export interface VariantFamilyPeerRead {
  peer_cover_image_id: number;
  pair_key: string;
  canonical_pair_low_id: number;
  canonical_pair_high_id: number;
  classification: "confirmed" | "probable";
  evidences: VariantFamilyEvidenceFlags;
  evidence_detail: Record<string, unknown>;
  match_candidate_ids: number[];
  human_variant_family_decision_id: number | null;
}

export interface VariantFamilyClusterRead {
  cluster_key: string;
  cover_image_ids: number[];
  cluster_size: number;
  classification: "confirmed" | "probable";
  evidence_strength: VariantFamilyEvidenceStrength;
}

export interface VariantFamilySuppressedPairRead {
  pair_key: string;
  left_cover_image_id: number;
  right_cover_image_id: number;
  suppressed_signal_labels: string[];
  evidence_snapshot: VariantFamilyEvidenceFlags;
}

export interface VariantFamilyCandidatesResponse {
  focal_cover_image_id: number;
  touching_clusters: VariantFamilyClusterRead[];
  variant_peers: VariantFamilyPeerRead[];
  suppressed_pairs_touching_focal: VariantFamilySuppressedPairRead[];
}

export interface VariantFamilyClustersListResponse {
  clusters: VariantFamilyClusterRead[];
  suppressed_pairs: VariantFamilySuppressedPairRead[];
  classification_filter: VariantFamilyClassificationFilter;
}

export type CanonicalIssueSuggestionType =
  | "exact_identity_key"
  | "normalized_title_issue_publisher"
  | "normalized_title_issue"
  | "relationship_context"
  | "variant_family_context"
  | "duplicate_scan_context";

export type CanonicalIssueSuggestionConfidenceBucket =
  | "very_high"
  | "high"
  | "medium"
  | "low"
  | "very_low";

export type CanonicalIssueSuggestionReviewState = "pending" | "approved" | "rejected" | "ignored";

export interface CanonicalIssueLinkSuggestionRead {
  id: number;
  cover_image_id: number;
  inventory_copy_id: number | null;
  canonical_issue_id: number | null;
  canonical_series_id: number | null;
  canonical_publisher_id: number | null;
  suggested_metadata_identity_key: string | null;
  suggestion_type: CanonicalIssueSuggestionType;
  confidence_bucket: CanonicalIssueSuggestionConfidenceBucket;
  deterministic_score: number;
  confidence_version: string;
  evidence_json: Record<string, unknown>;
  suppression_reason: string | null;
  review_state: CanonicalIssueSuggestionReviewState;
  reviewed_by_user_id: number | null;
  reviewed_by_email: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CanonicalIssueSuggestionGenerateResponse {
  cover_image_id: number;
  suggestion_count: number;
  suggestions: CanonicalIssueLinkSuggestionRead[];
}

export interface CanonicalIssueSuggestionReviewActionResponse {
  suggestion: CanonicalIssueLinkSuggestionRead;
}

export interface CanonicalIssueSuggestionOpsListResponse {
  suggestions: CanonicalIssueLinkSuggestionRead[];
  review_state: CanonicalIssueSuggestionReviewState | "all";
  confidence_bucket: CanonicalIssueSuggestionConfidenceBucket | "all";
  suggestion_type: CanonicalIssueSuggestionType | "all";
}

export interface CanonicalIssueSuggestionReviewPayload {
  reason?: string | null;
}

export type RelationshipConflictType =
  | "duplicate_scan_vs_variant_family"
  | "same_cover_vs_variant_family"
  | "same_issue_vs_unrelated"
  | "approved_link_vs_rejected_link"
  | "canonical_suggestion_mismatch"
  | "duplicate_scan_different_canonical_issue"
  | "variant_family_same_fingerprint"
  | "relationship_cycle_warning"
  | "stale_confidence_after_decision"
  | "preorder_not_in_hand_reconciliation_warning";

export type RelationshipConflictSeverity = "info" | "warning" | "critical";
export type RelationshipConflictStatus = "open" | "acknowledged" | "dismissed" | "resolved";

export interface RelationshipConflictRead {
  id: number;
  conflict_type: RelationshipConflictType;
  severity: RelationshipConflictSeverity;
  source_cover_image_id: number | null;
  related_cover_image_id: number | null;
  link_decision_id: number | null;
  match_candidate_id: number | null;
  canonical_issue_suggestion_id: number | null;
  conflict_key: string;
  status: RelationshipConflictStatus;
  evidence_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  acknowledged_at: string | null;
  dismissed_at: string | null;
  resolved_at: string | null;
}

export interface RelationshipConflictListResponse {
  conflicts: RelationshipConflictRead[];
  severity: RelationshipConflictSeverity | "all";
  status: RelationshipConflictStatus | "all";
  conflict_type: RelationshipConflictType | "all";
  total_count: number;
  open_count: number;
  acknowledged_count: number;
  dismissed_count: number;
  resolved_count: number;
}

export interface RelationshipConflictDetectResponse {
  detected_count: number;
  open_count: number;
  acknowledged_count: number;
  dismissed_count: number;
  resolved_count: number;
  conflicts: RelationshipConflictRead[];
}

export interface RelationshipConflictStatusPayload {
  reason?: string | null;
}

export interface CoverImageMatchCandidateRead {
  id: number;
  source_cover_image_id: number;
  candidate_cover_image_id: number;
  candidate_type: CoverMatchCandidateType;
  confidence_bucket: CoverMatchConfidenceBucket;
  deterministic_score: number;
  normalized_confidence_score: number;
  confidence_version: string;
  scoring_breakdown_json: Record<string, unknown>;
  matched_signal_count: number;
  hard_match_flags_json: Record<string, unknown>;
  weak_signal_flags_json: Record<string, unknown>;
  ranking_score: number;
  ranking_version: string;
  ranking_reason_json: Record<string, unknown>;
  candidate_rank: number;
  grouping_key: string | null;
  grouping_type: CoverMatchGroupingType | null;
  grouping_confidence_bucket: CoverMatchConfidenceBucket | null;
  grouping_reason_summary: string | null;
  matched_signals: Record<string, unknown>;
  contributing_signals: Array<Record<string, unknown>>;
  penalties: Array<Record<string, unknown>>;
  matched_fields: string[];
  failed_fields: string[];
  confidence_explanation_summary: string | null;
  extraction_version: string;
  created_at: string;
  updated_at: string;
  dismissed_at: string | null;
  acknowledged_at: string | null;
  active_link_decision: CoverImageLinkDecisionRead | null;
}

export interface CoverImageMatchGroupRead {
  grouping_key: string;
  grouping_type: CoverMatchGroupingType;
  grouping_confidence_bucket: CoverMatchConfidenceBucket;
  grouping_reason_summary: string | null;
  candidate_count: number;
  candidates: CoverImageMatchCandidateRead[];
}

export interface CoverImageOcrReconciliationWarningRead {
  id: number;
  cover_image_id: number;
  inventory_copy_id: number | null;
  ocr_candidate_id: number | null;
  warning_type: CoverOcrReconciliationWarningType;
  severity: CoverOcrReconciliationWarningSeverity;
  current_metadata_value: string | null;
  candidate_value: string | null;
  message: string;
  status: CoverOcrReconciliationWarningStatus;
  created_at: string;
  resolved_at: string | null;
  resolved_by_user_id: number | null;
}

export interface CoverImageOcrVisibility {
  job_status?: CoverImageOcrQueueStatus;
  retry_available?: boolean;
  ocr_run_count?: number;
  prior_run_created_ats?: string[];
}

export interface CoverImageRead {
  id: number;
  inventory_copy_id: number | null;
  canonical_series_id: number | null;
  draft_import_id: number | null;
  source_type: string;
  original_filename: string | null;
  mime_type: string;
  image_width: number | null;
  image_height: number | null;
  file_size: number | null;
  sha256_hash: string;
  processing_status: CoverProcessingStatus;
  processing_error: string | null;
  file_structured_processing_error?: StructuredProcessingErrorRead | null;
  processed_at: string | null;
  metadata_refreshed_at: string | null;
  matching_status: CoverMatchingStatus;
  matching_notes: string | null;
  ready_for_matching_at: string | null;
  latest_ocr_result: CoverImageOcrResultRead | null;
  ocr_visibility: CoverImageOcrVisibility;
  ocr_regions: CoverImageOcrRegionRead[];
  ocr_candidates: CoverImageOcrCandidateRead[];
  barcode_candidates: CoverImageBarcodeCandidateRead[];
  fingerprints: CoverImageFingerprintRead[];
  ocr_quality_analyses: CoverImageOcrQualityAnalysisRead[];
  match_candidates: CoverImageMatchCandidateRead[];
  ocr_reconciliation_warnings: CoverImageOcrReconciliationWarningRead[];
  thumbnail_fetch_path: string | null;
  medium_fetch_path: string | null;
  derivatives: CoverImageDerivativeRead[];
  created_at: string;
  is_primary: boolean;
  fetch_path: string;
}

/** Alias aligned with inventory/import cover payloads. */
export type InventoryCoverImage = CoverImageRead;

export interface CoverImageAssignExistingPayload {
  cover_image_id: number;
  set_primary?: boolean;
}

export interface CoverImageProcessingEnqueueResponse {
  job_id: string;
  status: "queued" | "already_queued";
  cover_image_id: number;
}

export interface CoverImageMatchingEvaluationResponse {
  cover_image_id: number;
  matching_status: CoverMatchingStatus;
  matching_notes: string | null;
  ready_for_matching_at: string | null;
}

export interface CoverImageOcrEnqueueResponse {
  job_id: string;
  status: "queued" | "already_queued";
  cover_image_id: number;
  ocr_result_id: number | null;
}

export interface CoverImageOcrReplayPayload {
  replay_reason?: string | null;
}

export interface CoverImageBarcodeCandidateExtractResponse {
  cover_image_id: number;
  candidate_count: number;
  candidates: CoverImageBarcodeCandidateRead[];
}

export interface CoverImageOcrQualityAnalysisResponse {
  cover_image_id: number;
  analysis_count: number;
  analyses: CoverImageOcrQualityAnalysisRead[];
}

export interface CoverImageFingerprintGenerateResponse {
  cover_image_id: number;
  fingerprint_count: number;
  fingerprints: CoverImageFingerprintRead[];
}

export interface CoverImageMatchCandidateGenerateResponse {
  cover_image_id: number;
  candidate_count: number;
  candidates: CoverImageMatchCandidateRead[];
}

export interface CoverImageOcrReconciliationResponse {
  cover_image_id: number;
  warning_count: number;
  warnings: CoverImageOcrReconciliationWarningRead[];
}

export interface CoverImageOcrCandidateReviewCounts {
  pending?: number;
  approved?: number;
  rejected?: number;
}

export interface CoverImageBarcodeCandidateReviewCounts {
  pending?: number;
  approved?: number;
  rejected?: number;
}

export interface CoverImageOcrReconciliationWarningCounts {
  open?: number;
  acknowledged?: number;
  dismissed?: number;
}

export interface OpsCoverDuplicateMember {
  id: number;
  source_type: string;
  original_filename: string | null;
  inventory_copy_id: number | null;
  draft_import_id: number | null;
  canonical_series_id: number | null;
  is_primary: boolean;
  created_at: string;
  file_size: number | null;
  image_width: number | null;
  image_height: number | null;
  owner_email: string | null;
  matching_status: CoverMatchingStatus;
  matching_notes: string | null;
  ready_for_matching_at: string | null;
  thumbnail_fetch_path: string | null;
  medium_fetch_path: string | null;
  derivatives: CoverImageDerivativeRead[];
  fetch_path: string;
  latest_ocr_result: CoverImageOcrResultRead | null;
  ocr_visibility: CoverImageOcrVisibility;
}

export interface OpsCoverDuplicateGroup {
  sha256_hash: string;
  count: number;
  covers: OpsCoverDuplicateMember[];
}

export interface OpsRecentCoverImageRow {
  id: number;
  original_filename: string | null;
  source_type: string;
  mime_type: string;
  image_width: number | null;
  image_height: number | null;
  file_size: number | null;
  sha256_hash: string;
  processing_status: CoverProcessingStatus;
  processing_error: string | null;
  processed_at: string | null;
  metadata_refreshed_at: string | null;
  matching_status: CoverMatchingStatus;
  matching_notes: string | null;
  ready_for_matching_at: string | null;
  latest_ocr_result: CoverImageOcrResultRead | null;
  ocr_visibility: CoverImageOcrVisibility;
  ocr_region_count: number;
  ocr_candidate_count: number;
  ocr_candidate_review_counts: CoverImageOcrCandidateReviewCounts;
  has_pending_ocr_candidate_review: boolean;
  barcode_candidate_count: number;
  barcode_candidate_review_counts: CoverImageBarcodeCandidateReviewCounts;
  fingerprint_count: number;
  ocr_quality_analysis_count: number;
  ocr_quality_analyses: CoverImageOcrQualityAnalysisRead[];
  match_candidate_count: number;
  open_match_candidate_count: number;
  match_candidates: CoverImageMatchCandidateRead[];
  ocr_reconciliation_warning_counts: CoverImageOcrReconciliationWarningCounts;
  open_ocr_reconciliation_warning_count: number;
  thumbnail_fetch_path: string | null;
  medium_fetch_path: string | null;
  derivatives: CoverImageDerivativeRead[];
  created_at: string;
  inventory_copy_id: number | null;
  draft_import_id: number | null;
  canonical_series_id: number | null;
  owner_email: string | null;
  is_primary: boolean;
  fetch_path: string;
}

export type MetadataAliasType = "publisher" | "series" | "creator";

export interface MetadataIdentityComponentsPayload {
  publisher?: string;
  series_title?: string;
  issue_number?: string;
  variant?: string;
}

export interface MetadataAliasCreatePayload {
  alias_value: string;
  canonical_value: string;
  alias_type?: MetadataAliasType;
}

export interface MetadataAlias {
  id: number;
  alias_value: string;
  canonical_value: string;
  alias_type: MetadataAliasType;
  source: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export type InventoryDuplicatesReviewFilter =
  | "all"
  | "pending"
  | "confirmed_duplicate"
  | "not_duplicate";

export interface InventoryDuplicatesQueryParams {
  publisher?: string;
  series_title?: string;
  min_count?: number;
  review_status?: "pending" | "confirmed_duplicate" | "not_duplicate";
}

export interface DuplicateCandidateReviewDecisionPayload {
  metadata_identity_key: string;
  review_status: "confirmed_duplicate" | "not_duplicate";
  notes?: string | null;
}

export interface DuplicateCandidateNotesPayload {
  metadata_identity_key: string;
  notes: string | null;
}

export type OcrBatchStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "cancelled";

export type OcrBatchItemStatus =
  | "pending"
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "skipped"
  | "cancelled";

export interface OcrBatchItemRead {
  id: number;
  batch_id: number;
  cover_image_id: number;
  status: OcrBatchItemStatus;
  job_id: string | null;
  attempt_count: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface OcrBatch {
  id: number;
  batch_key: string;
  status: OcrBatchStatus;
  total_items: number;
  pending_count: number;
  running_count: number;
  completed_count: number;
  failed_count: number;
  skipped_count: number;
  created_by: number | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  extraction_version: string;
  batch_options_json: Record<string, unknown>;
  items: OcrBatchItemRead[];
}

export interface OcrBatchCreatePayload {
  cover_image_ids: number[];
  batch_options_json?: Record<string, unknown>;
}

export type OcrReplayType =
  | "ocr_result"
  | "candidate_extraction"
  | "barcode_extraction"
  | "fingerprint_generation"
  | "reconciliation_warning"
  | "quality_analysis"
  | "full_pipeline";

export type OcrReplayRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_changes"
  | "failed"
  | "cancelled";

export type OcrReplayItemStatus = "pending" | "running" | "unchanged" | "changed" | "failed" | "cancelled";

export interface OcrReplayItemRead {
  id: number;
  replay_run_id: number;
  cover_image_id: number;
  status: OcrReplayItemStatus;
  previous_snapshot_json: Record<string, unknown>;
  replay_snapshot_json: Record<string, unknown>;
  diff_summary_json: Record<string, unknown>;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface OcrReplayRun {
  id: number;
  replay_type: OcrReplayType;
  extraction_version_from: string;
  extraction_version_to: string;
  status: OcrReplayRunStatus;
  total_items: number;
  changed_items: number;
  unchanged_items: number;
  failed_items: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_by: number | null;
  items: OcrReplayItemRead[];
}

export interface OcrReplayCreatePayload {
  replay_type: OcrReplayType;
  cover_image_ids: number[];
}

export type RelationshipReplayType =
  | "link_decisions"
  | "relationship_graph"
  | "duplicate_scan"
  | "variant_family"
  | "canonical_issue_suggestions"
  | "relationship_conflicts"
  | "full_relationship_pipeline";

export type RelationshipReplayRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_changes"
  | "failed"
  | "cancelled";

export type RelationshipReplayItemStatus =
  | "pending"
  | "running"
  | "unchanged"
  | "changed"
  | "failed"
  | "cancelled";

export interface RelationshipReplayItemRead {
  id: number;
  replay_run_id: number;
  cover_image_id: number | null;
  relationship_key: string | null;
  status: RelationshipReplayItemStatus;
  previous_snapshot_json: Record<string, unknown>;
  replay_snapshot_json: Record<string, unknown>;
  diff_summary_json: Record<string, unknown>;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface RelationshipReplayRun {
  id: number;
  replay_type: RelationshipReplayType;
  status: RelationshipReplayRunStatus;
  total_items: number;
  changed_items: number;
  unchanged_items: number;
  failed_items: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  created_by: number | null;
  replay_version: string;
  items: RelationshipReplayItemRead[];
}

export interface RelationshipReplayCreatePayload {
  replay_type: RelationshipReplayType;
  cover_image_ids: number[];
}

export type OcrReviewItemKindLiteral =
  | "ocr_candidate"
  | "reconciliation_warning"
  | "barcode_candidate"
  | "match_candidate"
  | "ocr_quality_analysis";

export interface OcrReviewQueueItem {
  item_kind: OcrReviewItemKindLiteral;
  entity_id: number;
  cover_image_id: number;
  created_at: string;
  sort_tier?: number;
  norm_score?: number | null;
  extraction_version?: string | null;
  severity?: string | null;
  warning_type?: string | null;
  quality_type?: string | null;
  candidate_type?: string | null;
  confidence_bucket?: string | null;
  reconciliation_status?: string | null;
  barcode_review_state?: string | null;
  ocr_candidate_review_status?: string | null;
  acknowledged_at?: string | null;
  dismissed_at?: string | null;
  ocr_candidate?: CoverImageOcrCandidateRead | null;
  reconciliation_warning?: CoverImageOcrReconciliationWarningRead | null;
  barcode_candidate?: CoverImageBarcodeCandidateRead | null;
  match_candidate?: CoverImageMatchCandidateRead | null;
  ocr_quality_analysis?: CoverImageOcrQualityAnalysisRead | null;
}

export interface OcrReviewQueueResponse {
  items: OcrReviewQueueItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface OcrReviewSummaryResponse {
  pending_ocr_candidates: number;
  open_reconciliation_warnings: number;
  critical_ocr_quality_analyses: number;
  pending_high_bucket_match_candidates: number;
  batches_with_failed_items: number;
  replay_changed_items_completed_runs_total: number;
}

export interface BulkIdsPayload {
  ids: number[];
}

export interface BulkMutationResult {
  succeeded: number[];
  skipped: Record<string, string>;
}

export interface OcrReviewQueueQueryParams {
  queue_scope?: "attention" | "all";
  item_kind?: string[];
  publisher_id?: number;
  extraction_version?: string;
  created_after?: string;
  created_before?: string;
  confidence_bucket?: "high" | "medium" | "low" | "unknown";
  severity?: "critical" | "warning" | "info";
  candidate_type?: string;
  warning_type?: string;
  quality_type?: string;
  ocr_candidate_review_status?: "pending" | "approved" | "rejected";
  reconciliation_warning_status?: "open" | "acknowledged" | "dismissed";
  barcode_review_state?: "pending" | "approved" | "rejected";
  match_review?: "pending" | "acknowledged" | "dismissed";
  page?: number;
  page_size?: number;
}

export type CoverImageOcrHeadlineStatus =
  | "idle"
  | "pending"
  | "queued"
  | "processing"
  | "processed"
  | "failed";

export function resolveCoverImageOcrHeadline(input: {
  ocr_visibility: CoverImageOcrVisibility | null | undefined;
  latest_ocr_result: CoverImageOcrResultRead | null | undefined;
}): CoverImageOcrHeadlineStatus {
  const queue = input.ocr_visibility?.job_status ?? "idle";
  if (queue === "queued") {
    return "queued";
  }
  if (queue === "running") {
    return "processing";
  }
  const processing = input.latest_ocr_result?.processing_status;
  switch (processing) {
    case "failed":
      return "failed";
    case "processing":
      return "processing";
    case "pending":
      return "pending";
    case "processed":
      return "processed";
    default:
      return "idle";
  }
}

export interface DraftImport {
  id: number;
  raw_text: string;
  parsed_payload_json: AiParseOrderResponse;
  confidence_score: string;
  status: DraftImportStatus;
  needs_metadata_review?: boolean;
  metadata_review_item_count?: number;
  needs_release_date_review?: boolean;
  release_date_review_item_count?: number;
  order_id: number | null;
  created_at: string;
  updated_at: string;
  cover_images?: InventoryCoverImage[];
  cover_image_count: number;
}

export interface DraftImportListResponse {
  page: number;
  page_size: number;
  total: number;
  items: DraftImport[];
}

export interface ImportQueryParams {
  page: number;
  page_size: number;
  status?: DraftImportStatus;
  search?: string;
  sort_by?: ImportSortBy;
  sort_dir?: "asc" | "desc";
}

export interface DraftImportCreatePayload {
  raw_text: string;
}

export interface ManualDraftImportCreatePayload extends AiParseOrderResponse {
  raw_text?: string | null;
  source_type: "manual_draft";
}

export interface DraftImportUpdatePayload {
  raw_text?: string;
  parsed_payload_json?: AiParseOrderResponse;
  confidence_score?: number;
}

export interface DraftImportConfirmResponse {
  import_id: number;
  status: DraftImportStatus;
  order_id: number;
  total_items: number;
  total_copies_created: number;
  all_in_total: string;
  notices?: string[];
}

export type ImportParseJobStatus =
  | "queued"
  | "started"
  | "finished"
  | "failed"
  | "scheduled"
  | "deferred";

export interface ImportParseJobEnqueueResponse {
  job_id: string;
  status: ImportParseJobStatus;
}

export interface ImportParseJobStatusResponse {
  job_id: string;
  job_type: string;
  status: ImportParseJobStatus;
  import_id: number | null;
  import_record: DraftImport | null;
  error: string | null;
  enqueued_at: string | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface GmailStatusResponse {
  configured: boolean;
  connected: boolean;
  gmail_email: string | null;
  token_expires_at: string | null;
}

export interface GmailConnectStartResponse {
  authorization_url: string;
}

export interface GmailDisconnectResponse {
  disconnected: boolean;
}

export interface GmailSyncEnqueueResponse {
  job_id: string;
  status: string;
}

export interface GmailSyncStatusResponse {
  auto_sync_enabled: boolean;
  last_sync_started_at: string | null;
  last_sync_completed_at: string | null;
  last_sync_status: string | null;
  last_sync_error: string | null;
}

export interface GmailSyncSettingsUpdatePayload {
  auto_sync_enabled: boolean;
}

export interface GmailImportedDraft {
  external_message_id: string;
  imported_at: string;
  draft_import: DraftImport;
}

export interface OpsQueueSnapshot {
  queue_name: string;
  queued_jobs: number;
  started_jobs: number;
  failed_jobs: number;
  most_recent_job_result: string | null;
}

export interface OpsPipelineStaleRow {
  category: string;
  entity_kind: string;
  entity_id: number;
  cover_image_id: number | null;
  detail: string;
  stale_since: string | null;
}

export interface OpsReplayFailureSummary {
  failed_items_total_recent: number;
  failed_recent_run_ids: number[];
}

export interface OpsBatchFailureSummary {
  batches_with_failed_items: number;
  failed_items_total_recent: number;
}

export interface OpsPipelineHealth {
  window_hours: number;
  cutoff_utc: string;
  failed_ocr_results: number;
  ocr_tesseract_timeouts: number;
  corrupt_image_failures: number;
  retry_exhausted_batch_items: number;
  replay_failed_items_total: number;
  stale_cover_ocr_processing: number;
  stale_batch_items: number;
  stale_replay_running_items: number;
  stale_batch_rows: OpsPipelineStaleRow[];
  stale_cover_ocr_rows: OpsPipelineStaleRow[];
  stale_replay_rows: OpsPipelineStaleRow[];
  replay_failures_recent: OpsReplayFailureSummary;
  batch_failures: OpsBatchFailureSummary;
}

export interface OpsJobRow {
  job_id: string;
  job_type: string;
  queue_name: string;
  status: string;
  user_id: number | null;
  user_email: string | null;
  started_at: string | null;
  ended_at: string | null;
  result_summary: string | null;
  error: string | null;
}

export interface OpsDraftImportRow {
  draft_id: number;
  user_id: number;
  user_email: string;
  retailer: string | null;
  status: string;
  confidence: string;
  warning_count: number;
  created_at: string;
  linked_order_id: number | null;
}

export interface OpsGmailSyncRow {
  gmail_account_id: number;
  user_id: number;
  user_email: string;
  gmail_email: string;
  auto_sync_enabled: boolean;
  last_sync_status: string | null;
  last_sync_started_at: string | null;
  last_sync_completed_at: string | null;
  processed_messages: number | null;
  created_draft_imports: number | null;
  skipped_duplicates: number | null;
  last_error_message: string | null;
}

export interface OpsEventRow {
  id: number;
  event_type: string;
  status: string;
  created_at: string;
  user_id: number | null;
  user_email: string | null;
  draft_import_id: number | null;
  order_id: number | null;
  external_message_id: string | null;
  message: string | null;
  details: Record<string, unknown>;
}

export interface OpsDashboardResponse {
  recent_gmail_sync_jobs: OpsJobRow[];
  recent_ai_parse_jobs: OpsJobRow[];
  gmail_sync_statuses: OpsGmailSyncRow[];
  recent_draft_imports: OpsDraftImportRow[];
  parser_failures: OpsEventRow[];
  duplicate_skip_events: OpsEventRow[];
  confirm_events: OpsEventRow[];
  queue_health: OpsQueueSnapshot[];
  pipeline_health: OpsPipelineHealth;
  recent_cover_pipeline_jobs: OpsJobRow[];
  reconciliation_summary: {
    open_conflicts: number;
    pending_canonical_suggestions: number;
    high_confidence_unreviewed_match_candidates: number;
    confirmed_duplicate_scans: number;
    probable_variant_families: number;
    recent_relationship_replay_changes: number;
  };
}

export interface OpsOcrPipelineRecoverResponse {
  ocr_results_recovered: number;
  batch_items_recovered: number;
  replay_items_recovered: number;
}

export interface OpsInventoryDuplicateCopyRow {
  inventory_copy_id: number;
  user_id: number | null;
  user_email: string | null;
  order_id: number | null;
  retailer: string | null;
  order_date: string | null;
  acquisition_cost: string;
  created_at: string;
}

export interface OpsInventoryDuplicateCandidateGroup {
  metadata_identity_key: string;
  count: number;
  publisher: string;
  series_title: string;
  issue_number: string;
  variant: string;
  review_status: string;
  notes: string | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
  copies: OpsInventoryDuplicateCopyRow[];
}

export interface OpsCanonicalSeriesRow {
  id: number;
  canonical_title: string;
  canonical_publisher: string;
  series_key: string;
  first_seen_at: string;
  last_seen_at: string;
  earliest_known_release_date: string | null;
  latest_known_release_date: string | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  inventory_count: number;
}

export interface OpsCanonicalCreatorRow {
  id: number;
  canonical_name: string;
  normalized_name: string;
  creator_key: string;
  first_seen_at: string;
  last_seen_at: string;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface OpsMetadataAuditRow {
  id: number;
  entity_type: string;
  entity_id: number;
  action: string;
  before_snapshot: Record<string, unknown> | null;
  after_snapshot: Record<string, unknown> | null;
  reason: string | null;
  actor_user_id: number | null;
  actor_email: string | null;
  created_at: string;
}

export interface OpsMetadataReenrichmentEnqueueResponse {
  job_id: string;
  status: string;
  entity_type: string;
  entity_id: number;
}

export type InventoryRiskPriority = "critical" | "high" | "medium" | "low" | "info";
export type InventoryRiskType =
  | "needs_canonical_review"
  | "needs_conflict_review"
  | "needs_scan"
  | "needs_ocr_retry"
  | "needs_cover_processing_review"
  | "preorder_missing_release_date"
  | "released_not_received"
  | "duplicate_uncertainty"
  | "run_gap_detected"
  | "low_quality_scan"
  | "high_confidence_match_unreviewed";

export interface InventoryRiskRead {
  risk_key: string;
  inventory_copy_id: number;
  cover_image_id: number | null;
  risk_type: InventoryRiskType;
  priority: InventoryRiskPriority;
  status: "open";
  ownership_state: InventoryOwnershipNormalized;
  publisher: string;
  title: string;
  issue_number: string;
  evidence_json: Record<string, unknown>;
}

export interface InventoryRiskSummaryItem {
  inventory_copy_id: number;
  publisher: string;
  title: string;
  issue_number: string;
  ownership_state: InventoryOwnershipNormalized;
  highest_priority: InventoryRiskPriority;
  risk_count: number;
  risk_types: InventoryRiskType[];
  evidence_preview: string[];
}

export interface InventoryRiskSummary {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  total_inventory_copies: number;
  total_risk_items: number;
  copies_with_risk: number;
  critical_copies: number;
  high_copies: number;
  medium_copies: number;
  low_copies: number;
  info_copies: number;
  by_priority: KeyedInventoryCountRow[];
  by_risk_type: KeyedInventoryCountRow[];
  top_action_items: InventoryRiskSummaryItem[];
}

export interface InventoryRiskListResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  total_count: number;
  priority: InventoryRiskPriority | "all";
  risk_type: InventoryRiskType | "all";
  ownership_state: InventoryOwnershipNormalized | "all";
  publisher: string | null;
  in_hand_only: boolean;
  open_only: boolean;
  summary: InventoryRiskSummary;
  risks: InventoryRiskRead[];
}

export type OrderArrivalClassification =
  | "upcoming_preorder"
  | "releases_this_week"
  | "released_not_received"
  | "expected_to_ship_soon"
  | "overdue_expected_ship"
  | "received_recently"
  | "cancelled_order"
  | "missing_release_date"
  | "missing_expected_ship_date";

export interface OrderArrivalIntelRead {
  intel_key: string;
  inventory_copy_id: number;
  classification: OrderArrivalClassification;
  retailer: string;
  source_type: string | null;
  publisher: string;
  title: string;
  issue_number: string;
  order_item_quantity: number;
  order_status: string;
  release_status: string;
  asset_state: string;
  purchase_date?: string | null;
  release_date?: string | null;
  expected_ship_date?: string | null;
  received_at?: string | null;
  evidence_json: Record<string, unknown>;
}

export interface OrderArrivalIntelSummaryItem {
  inventory_copy_id: number;
  publisher: string;
  title: string;
  issue_number: string;
  retailer: string;
  classification_count: number;
  classifications: OrderArrivalClassification[];
  evidence_preview: string[];
}

export interface OrderArrivalIntelSummary {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  total_inventory_copies: number;
  total_intel_items: number;
  copies_tagged: number;
  by_classification: KeyedInventoryCountRow[];
  top_action_items: OrderArrivalIntelSummaryItem[];
}

export interface OrderArrivalIntelListResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  total_count: number;
  classification: OrderArrivalClassification | "all";
  retailer: string | null;
  publisher: string | null;
  release_date_from: string | null;
  release_date_to: string | null;
  expected_ship_date_from: string | null;
  expected_ship_date_to: string | null;
  order_status: string;
  in_hand_only: boolean;
  summary: OrderArrivalIntelSummary;
  items: OrderArrivalIntelRead[];
}

export interface OrderArrivalCalendarCell {
  inventory_copy_id: number;
  title: string;
  issue_number: string;
  publisher: string;
  retailer: string;
  order_status: string;
  release_status: string;
  classifications: OrderArrivalClassification[];
}

export interface OrderArrivalCalendarRow {
  calendar_date: string;
  on_release_date: OrderArrivalCalendarCell[];
  on_expected_ship_date: OrderArrivalCalendarCell[];
}

export interface OrderArrivalIntelCalendarResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  calendar_start: string;
  calendar_end: string;
  rows: OrderArrivalCalendarRow[];
}

export type OrderArrivalIntelQueryParams = {
  classification?: OrderArrivalClassification;
  retailer?: string;
  publisher?: string;
  release_date_from?: string;
  release_date_to?: string;
  expected_ship_date_from?: string;
  expected_ship_date_to?: string;
  order_status?: "ordered" | "preordered" | "shipped" | "received" | "cancelled";
  in_hand_only?: boolean;
  calendar_start?: string;
  calendar_end?: string;
};

export interface InventoryItem {
  inventory_copy_id: number;
  title: string;
  publisher: string;
  issue_number: string;
  cover_name: string | null;
  printing: string | null;
  ratio: string | null;
  variant_type: string | null;
  cover_artist: string | null;
  retailer: string;
  order_date: string;
  acquisition_cost: string;
  current_fmv: string | null;
  gain_loss: string | null;
  grade_status: "raw" | "submitted" | "graded";
  hold_status: "hold" | "sell" | "sold";
  star_rating: number | null;
  condition_notes: string | null;
  purchase_date?: string | null;
  release_date?: string | null;
  release_year?: number | null;
  release_status: "released" | "not_released_yet" | "unknown";
  order_status: "ordered" | "preordered" | "shipped" | "received" | "cancelled";
  expected_ship_date?: string | null;
  received_at?: string | null;
  asset_state: "in_hand" | "ordered_not_received" | "preorder_not_released_yet" | "cancelled";
  is_in_hand: boolean;
  inventory_intelligence?: InventoryCopyIntelligenceSignalsSummary | null;
  duplicate_ownership?: DuplicateOwnershipAttachment | null;
  run_detection?: RunDetectionAttachment | null;
  inventory_risks?: InventoryRiskRead[] | null;
  order_arrival_classifications?: OrderArrivalClassification[] | null;
}

export interface InventoryDetail extends InventoryItem {
  copy_number: number;
  source_type: string | null;
  order_id: number;
  order_item_id: number;
  variant_id: number;
  created_at: string;
  cover_images: InventoryCoverImage[];
}

export interface InventoryFmvSnapshot {
  id: number;
  previous_fmv: string | null;
  new_fmv: string;
  changed_at: string;
  source: string;
}

export interface InventoryResponse {
  page: number;
  page_size: number;
  total: number;
  items: InventoryItem[];
}

export interface InventorySummary {
  total_copies: number;
  in_hand_copies: number;
  ordered_not_received_copies: number;
  preordered_copies: number;
  cancelled_copies: number;
  total_cost_basis: string;
  total_current_fmv: string;
  total_unrealized_gain_loss: string;
  raw_count: number;
  graded_count: number;
  hold_count: number;
  sell_count: number;
}

export interface KeyedInventoryCountRow {
  key: string | null;
  count: number;
}

export type InventoryOwnershipNormalized =
  | "in_hand"
  | "preorder"
  | "ordered_not_received"
  | "cancelled"
  | "unknown_state";

export type InventoryIntelligenceHealthLevel = "healthy" | "needs_review" | "incomplete" | "blocked";

export interface InventoryCopyIntelligenceSignalsSummary {
  ownership_state: InventoryOwnershipNormalized;
  inventory_health: InventoryIntelligenceHealthLevel;
  has_cover_scan: boolean;
  preorder_missing_release_calendar: boolean;
  has_open_relationship_conflict: boolean;
  has_pending_canonical_suggestion: boolean;
  in_pending_duplicate_inventory_group: boolean;
  touches_probable_duplicate_scan_cluster: boolean;
  touches_probable_variant_family_cluster: boolean;
}

export interface InventoryIntelligenceRollupSummary {
  total_inventory_copies: number;
  ownership_in_hand: number;
  ownership_preorder: number;
  ownership_ordered_not_received: number;
  ownership_cancelled: number;
  ownership_unknown_state: number;
  graded_copies: number;
  raw_copies: number;
  scanned_copies: number;
  unscanned_copies: number;
  ocr_complete_copies: number;
  ocr_pending_copies: number;
  cover_processing_failed_copies: number;
  ocr_failed_copies: number;
  unresolved_relationship_conflicts: number;
  unresolved_canonical_suggestions: number;
  unresolved_duplicate_inventory_groups: number;
  unresolved_duplicate_scan_clusters: number;
  unresolved_variant_family_clusters: number;
}

export interface InventoryIntelligenceHealthRollup {
  healthy: number;
  needs_review: number;
  incomplete: number;
  blocked: number;
}

export interface InventoryIntelligenceBreakdownResponse {
  by_publisher: KeyedInventoryCountRow[];
  by_year: KeyedInventoryCountRow[];
  by_release_status: KeyedInventoryCountRow[];
  by_order_status: KeyedInventoryCountRow[];
  by_grade_status: KeyedInventoryCountRow[];
  by_ownership_state: KeyedInventoryCountRow[];
  unhealthy_sample_inventory_copy_ids: number[];
}

export interface PortfolioPerformanceItem {
  inventory_copy_id: number;
  title: string;
  publisher: string;
  issue_number: string;
  cover_name: string | null;
  current_fmv: string | null;
  gain_loss: string | null;
}

export interface PortfolioPerformance {
  total_cost_basis: string;
  total_current_fmv: string;
  total_unrealized_gain_loss: string;
  top_gainers: PortfolioPerformanceItem[];
  top_losers: PortfolioPerformanceItem[];
  highest_value_books: PortfolioPerformanceItem[];
}

/** Deterministic portfolio analytics (non-pricing); mirrors backend snake_case payloads. */

export interface CollectionAnalyticsPercentRollup {
  numerator: number;
  denominator: number;
  percent: number;
}

export interface CollectionPublisherAnalyticsRow {
  publisher_name: string;
  total_copies: number;
  in_hand_copies: number;
  preorder_copies: number;
  unresolved_review_copies: number;
  canonical_linked_copies: number;
}

export interface CollectionAnalyticsSummary {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  total_copies: number;
  preorder_copies: number;
  in_hand_copies: number;
  preorder_missing_calendar_copies: number;
  unscanned_primary_copies: number;
  unresolved_review_copies: number;
  graded_copies: number;
  raw_copies: number;
  released_status_breakdown: KeyedInventoryCountRow[];
  order_status_breakdown: KeyedInventoryCountRow[];
  ownership_breakdown: KeyedInventoryCountRow[];
  canonical_linked_copies: number;
}

export interface CollectionPublisherAnalyticsResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  publishers: CollectionPublisherAnalyticsRow[];
}

export interface CollectionTimelineYearBucket {
  year_key: string;
  copies: number;
}

export interface CollectionPreorderPipelineBucket {
  release_bucket_key: string;
  preorder_copies: number;
}

export interface CollectionUpcomingPreorderBucket {
  preorder_copies: number;
  first_release_bucket: string;
}

export interface CollectionTimelineAnalytics {
  generated_as_of_date: string;
  by_purchase_year: CollectionTimelineYearBucket[];
  by_release_year: CollectionTimelineYearBucket[];
  by_received_year: CollectionTimelineYearBucket[];
  preorder_pipeline: CollectionPreorderPipelineBucket[];
  upcoming_preorder_calendar: CollectionUpcomingPreorderBucket[];
}

export interface CollectionTimelineResponse {
  scope_user_id: number | null;
  scope: string;
  timeline: CollectionTimelineAnalytics;
}

export interface CollectionInventoryQuality {
  scope_active_copies_ex_cancelled: number;
  ocr_complete: CollectionAnalyticsPercentRollup;
  canonical_linked: CollectionAnalyticsPercentRollup;
  unresolved_open_conflict_copies: CollectionAnalyticsPercentRollup;
  duplicate_ownership_exposure_copies: CollectionAnalyticsPercentRollup;
  missing_primary_scan: CollectionAnalyticsPercentRollup;
  primary_cover_failed_processing: CollectionAnalyticsPercentRollup;
  primary_cover_failed_ocr: CollectionAnalyticsPercentRollup;
}

export interface CollectionQualityAnalyticsResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  inventory_quality: CollectionInventoryQuality;
}

export interface CollectionCompositionSeriesSignals {
  mini_series_limited_denominator_groups: number;
  mini_series_completed_groups: number;
  mini_series_completion_percent: number;
  probable_ongoing_series_groups: number;
  probable_ongoing_series_copy_touch_count: number;
  ongoing_series_participation_percent: number;
}

export interface PublisherConcentration {
  top_publisher_share: CollectionAnalyticsPercentRollup;
  publishers_represented: number;
}

export interface CollectionComposition {
  graded_copies: number;
  raw_copies: number;
  preorder_active_copies: number;
  in_hand_active_copies: number;
  cancelled_copies: number;
  owned_active_copies: number;
  preorder_vs_in_hand: CollectionAnalyticsPercentRollup;
  graded_vs_raw: CollectionAnalyticsPercentRollup;
  cancelled_vs_owned: CollectionAnalyticsPercentRollup;
  publisher_concentration: PublisherConcentration;
  series_signals: CollectionCompositionSeriesSignals;
}

export interface CollectionCompositionResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  composition: CollectionComposition;
}

export interface InventoryUpdatePayload {
  current_fmv?: string | null;
  hold_status?: "hold" | "sell" | "sold";
  star_rating?: number | null;
  grade_status?: "raw" | "submitted" | "graded";
  condition_notes?: string | null;
}

export interface BulkInventoryUpdatePayload {
  inventory_copy_ids: number[];
  updates: InventoryUpdatePayload;
}

export interface BulkInventoryUpdateResponse {
  updated_count: number;
}

export interface OrderItemPayload {
  publisher: string;
  title: string;
  purchase_date?: string | null;
  issue_number: string;
  release_date?: string | null;
  release_year?: number | null;
  release_status?: "released" | "not_released_yet" | "unknown" | null;
  order_status?: "ordered" | "preordered" | "shipped" | "received" | "cancelled" | null;
  expected_ship_date?: string | null;
  received_at?: string | null;
  cover_name?: string | null;
  printing?: string | null;
  ratio?: string | null;
  variant_type?: string | null;
  cover_artist?: string | null;
  quantity: number;
  raw_item_price: number;
}

export interface OrderCreatePayload {
  retailer: string;
  order_date: string;
  source_type?: string | null;
  shipping_amount: number;
  tax_amount: number;
  items: OrderItemPayload[];
}

export interface OrderCreateResponse {
  order_id: number;
  total_items: number;
  total_copies_created: number;
  all_in_total: string;
}

export interface OrderListItem {
  order_id: number;
  retailer: string;
  order_date: string;
  source_type: string | null;
  shipping_amount: string;
  tax_amount: string;
  total_amount: string;
  total_items: number;
  total_copies: number;
  created_at: string;
}

export interface OrderListResponse {
  page: number;
  page_size: number;
  total: number;
  items: OrderListItem[];
}

export interface OrderDetailItem {
  order_item_id: number;
  publisher: string;
  title: string;
  release_date?: string | null;
  release_status: "released" | "not_released_yet" | "unknown";
  order_status: "ordered" | "preordered" | "shipped" | "received" | "cancelled";
  purchase_date?: string | null;
  expected_ship_date?: string | null;
  received_at?: string | null;
  asset_state: "in_hand" | "ordered_not_received" | "preorder_not_released_yet" | "cancelled";
  issue_number: string;
  cover_name: string | null;
  printing: string | null;
  ratio: string | null;
  variant_type: string | null;
  cover_artist: string | null;
  quantity: number;
  raw_item_price: string;
  allocated_shipping: string;
  allocated_tax: string;
  all_in_unit_cost: string;
  inventory_copy_ids: number[];
}

export interface OrderDetail {
  order_id: number;
  retailer: string;
  order_date: string;
  source_type: string | null;
  shipping_amount: string;
  tax_amount: string;
  total_amount: string;
  created_at: string;
  items: OrderDetailItem[];
}

export type InventoryReleaseCalendar = "present" | "missing";

export interface InventoryQueryParams {
  page: number;
  page_size: number;
  search?: string;
  publisher?: string;
  hold_status?: string;
  grade_status?: string;
  release_year?: number;
  release_calendar?: InventoryReleaseCalendar;
  asset_state?: "in_hand" | "ordered_not_received" | "preorder_not_released_yet" | "cancelled";
  intelligence_health?: InventoryIntelligenceHealthLevel | "not_healthy";
  ownership_intel?: InventoryOwnershipNormalized;
  risk_priority?: InventoryRiskPriority;
  risk_type?: InventoryRiskType;
  needs_attention?: boolean;
  arrival_classification?: OrderArrivalClassification;
  sort_by?: SortBy;
  sort_dir?: "asc" | "desc";
}

export interface OrderQueryParams {
  page: number;
  page_size: number;
  retailer?: string;
  search?: string;
  sort_by?: OrderSortBy;
  sort_dir?: "asc" | "desc";
}

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init?.headers);

  if (!headers.has("Content-Type") && init?.body) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

  if (response.status === 401) {
    clearStoredToken();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError("Authentication required", 401);
  }

  if (!response.ok) {
    let message = "Request failed";

    try {
      const data = (await response.json()) as { detail?: string };
      if (typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      // Ignore invalid error payloads.
    }

    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

async function fetchBinary(path: string): Promise<Blob> {
  const token = getStoredToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { headers });

  if (response.status === 401) {
    clearStoredToken();
    if (window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
    throw new ApiError("Authentication required", 401);
  }

  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = (await response.json()) as { detail?: string };
      if (typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      // ignore
    }
    throw new ApiError(message, response.status);
  }

  return response.blob();
}

function buildOcrReviewQueueQueryString(params: OcrReviewQueueQueryParams): string {
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === "") {
      return;
    }
    if (key === "item_kind" && Array.isArray(value)) {
      value.forEach((v) => searchParams.append("item_kind", String(v)));
      return;
    }
    searchParams.set(key, String(value));
  });
  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function encodeOptionalReasonQuery(reason?: string): string {
  const trimmed = reason?.trim();
  return trimmed ? `?reason=${encodeURIComponent(trimmed)}` : "";
}

function buildQueryString(
  params:
    | Record<string, string | number | boolean | undefined>
    | InventoryQueryParams
    | OrderQueryParams
    | ImportQueryParams,
): string {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") {
      searchParams.set(key, String(value));
    }
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

export const apiClient = {
  register(payload: RegisterPayload): Promise<User> {
    return request<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  login(payload: LoginPayload): Promise<TokenResponse> {
    return request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getCurrentUser(): Promise<User> {
    return request<User>("/auth/me");
  },

  getGmailConnectStart(): Promise<GmailConnectStartResponse> {
    return request<GmailConnectStartResponse>("/gmail/connect/start");
  },

  getGmailStatus(): Promise<GmailStatusResponse> {
    return request<GmailStatusResponse>("/gmail/status");
  },

  getGmailSyncSummary(): Promise<GmailSyncStatusResponse> {
    return request<GmailSyncStatusResponse>("/gmail/sync/status");
  },

  updateGmailSyncSettings(
    payload: GmailSyncSettingsUpdatePayload,
  ): Promise<GmailSyncStatusResponse> {
    return request<GmailSyncStatusResponse>("/gmail/sync/settings", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  disconnectGmail(): Promise<GmailDisconnectResponse> {
    return request<GmailDisconnectResponse>("/gmail/disconnect", {
      method: "POST",
    });
  },

  syncGmail(): Promise<GmailSyncEnqueueResponse> {
    return request<GmailSyncEnqueueResponse>("/gmail/sync", {
      method: "POST",
    });
  },

  getGmailSyncStatus(jobId: string): Promise<ImportParseJobStatusResponse> {
    return request<ImportParseJobStatusResponse>(`/gmail/sync/${jobId}`);
  },

  getGmailImports(): Promise<GmailImportedDraft[]> {
    return request<GmailImportedDraft[]>("/gmail/imports");
  },

  getOpsDashboard(): Promise<OpsDashboardResponse> {
    return request<OpsDashboardResponse>("/ops/dashboard");
  },

  postOpsOcrPipelineRecover(): Promise<OpsOcrPipelineRecoverResponse> {
    return request<OpsOcrPipelineRecoverResponse>("/ops/ocr-pipeline/recover", {
      method: "POST",
    });
  },

  getInventory(params: InventoryQueryParams): Promise<InventoryResponse> {
    const query = buildQueryString(params);
    return request<InventoryResponse>(`/inventory${query}`);
  },

  getInventorySummary(): Promise<InventorySummary> {
    return request<InventorySummary>("/inventory/summary");
  },

  getInventoryIntelligenceSummary(): Promise<InventoryIntelligenceRollupSummary> {
    return request<InventoryIntelligenceRollupSummary>("/inventory-intelligence/summary");
  },

  getInventoryIntelligenceHealth(): Promise<InventoryIntelligenceHealthRollup> {
    return request<InventoryIntelligenceHealthRollup>("/inventory-intelligence/health");
  },

  getInventoryIntelligenceBreakdown(): Promise<InventoryIntelligenceBreakdownResponse> {
    return request<InventoryIntelligenceBreakdownResponse>("/inventory-intelligence/breakdown");
  },

  getOpsInventoryIntelligenceSummary(): Promise<InventoryIntelligenceRollupSummary> {
    return request<InventoryIntelligenceRollupSummary>("/ops/inventory-intelligence/summary");
  },

  getOpsInventoryIntelligenceHealth(): Promise<InventoryIntelligenceHealthRollup> {
    return request<InventoryIntelligenceHealthRollup>("/ops/inventory-intelligence/health");
  },

  getOpsInventoryIntelligenceBreakdown(): Promise<InventoryIntelligenceBreakdownResponse> {
    return request<InventoryIntelligenceBreakdownResponse>("/ops/inventory-intelligence/breakdown");
  },


  getInventoryRisks(params?: {
    priority?: InventoryRiskPriority;
    risk_type?: InventoryRiskType;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    in_hand_only?: boolean;
    open_only?: boolean;
  }): Promise<InventoryRiskListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryRiskListResponse>(`/inventory-risks${query}`);
  },

  getInventoryRisksSummary(params?: {
    priority?: InventoryRiskPriority;
    risk_type?: InventoryRiskType;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    in_hand_only?: boolean;
    open_only?: boolean;
  }): Promise<InventoryRiskSummary> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryRiskSummary>(`/inventory-risks/summary${query}`);
  },

  getInventoryRiskDetail(
    inventoryCopyId: number,
    params?: { priority?: InventoryRiskPriority; risk_type?: InventoryRiskType; open_only?: boolean },
  ): Promise<InventoryRiskListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryRiskListResponse>(`/inventory/${inventoryCopyId}/risks${query}`);
  },

  getOpsInventoryRisks(params?: {
    priority?: InventoryRiskPriority;
    risk_type?: InventoryRiskType;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    in_hand_only?: boolean;
    open_only?: boolean;
  }): Promise<InventoryRiskListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryRiskListResponse>(`/ops/inventory-risks${query}`);
  },

  getOpsInventoryRisksSummary(params?: {
    priority?: InventoryRiskPriority;
    risk_type?: InventoryRiskType;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    in_hand_only?: boolean;
    open_only?: boolean;
  }): Promise<InventoryRiskSummary> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryRiskSummary>(`/ops/inventory-risks/summary${query}`);
  },

  getOpsInventoryRiskDetail(
    inventoryCopyId: number,
    params?: { priority?: InventoryRiskPriority; risk_type?: InventoryRiskType; open_only?: boolean },
  ): Promise<InventoryRiskListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryRiskListResponse>(`/ops/inventory/${inventoryCopyId}/risks${query}`);
  },

  getOrderArrivalIntelligence(
    params?: OrderArrivalIntelQueryParams,
  ): Promise<OrderArrivalIntelListResponse> {
    const query =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<OrderArrivalIntelListResponse>(`/order-arrival-intelligence${query}`);
  },

  getOrderArrivalIntelligenceSummary(
    params?: OrderArrivalIntelQueryParams,
  ): Promise<OrderArrivalIntelSummary> {
    const query =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<OrderArrivalIntelSummary>(`/order-arrival-intelligence/summary${query}`);
  },

  getOrderArrivalCalendar(
    params?: OrderArrivalIntelQueryParams,
  ): Promise<OrderArrivalIntelCalendarResponse> {
    const query =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<OrderArrivalIntelCalendarResponse>(`/order-arrival-intelligence/calendar${query}`);
  },

  getOpsOrderArrivalIntelligence(
    params?: OrderArrivalIntelQueryParams,
  ): Promise<OrderArrivalIntelListResponse> {
    const query =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<OrderArrivalIntelListResponse>(`/ops/order-arrival-intelligence${query}`);
  },

  getOpsOrderArrivalIntelligenceSummary(
    params?: OrderArrivalIntelQueryParams,
  ): Promise<OrderArrivalIntelSummary> {
    const query =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<OrderArrivalIntelSummary>(`/ops/order-arrival-intelligence/summary${query}`);
  },

  getOpsOrderArrivalCalendar(
    params?: OrderArrivalIntelQueryParams,
  ): Promise<OrderArrivalIntelCalendarResponse> {
    const query =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<OrderArrivalIntelCalendarResponse>(`/ops/order-arrival-intelligence/calendar${query}`);
  },

  getCollectionAnalyticsSummary(as_of?: string): Promise<CollectionAnalyticsSummary> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionAnalyticsSummary>(`/collection-analytics/summary${q}`);
  },

  getCollectionAnalyticsPublishers(as_of?: string): Promise<CollectionPublisherAnalyticsResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionPublisherAnalyticsResponse>(`/collection-analytics/publishers${q}`);
  },

  getCollectionAnalyticsTimeline(as_of?: string): Promise<CollectionTimelineResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionTimelineResponse>(`/collection-analytics/timeline${q}`);
  },

  getCollectionAnalyticsQuality(as_of?: string): Promise<CollectionQualityAnalyticsResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionQualityAnalyticsResponse>(`/collection-analytics/quality${q}`);
  },

  getCollectionAnalyticsComposition(as_of?: string): Promise<CollectionCompositionResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionCompositionResponse>(`/collection-analytics/composition${q}`);
  },

  getOpsCollectionAnalyticsSummary(as_of?: string): Promise<CollectionAnalyticsSummary> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionAnalyticsSummary>(`/ops/collection-analytics/summary${q}`);
  },

  getOpsCollectionAnalyticsPublishers(as_of?: string): Promise<CollectionPublisherAnalyticsResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionPublisherAnalyticsResponse>(`/ops/collection-analytics/publishers${q}`);
  },

  getOpsCollectionAnalyticsTimeline(as_of?: string): Promise<CollectionTimelineResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionTimelineResponse>(`/ops/collection-analytics/timeline${q}`);
  },

  getOpsCollectionAnalyticsQuality(as_of?: string): Promise<CollectionQualityAnalyticsResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionQualityAnalyticsResponse>(`/ops/collection-analytics/quality${q}`);
  },

  getOpsCollectionAnalyticsComposition(as_of?: string): Promise<CollectionCompositionResponse> {
    const q = as_of ? buildQueryString({ as_of }) : "";
    return request<CollectionCompositionResponse>(`/ops/collection-analytics/composition${q}`);
  },

  getDuplicateOwnershipList(params?: {
    dup_scan_classification?: DuplicateScanClassificationFilter;
    classification?: DuplicateOwnershipClassification;
  }): Promise<DuplicateOwnershipListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DuplicateOwnershipListResponse>(`/duplicate-ownership${query}`);
  },

  getDuplicateOwnershipGroup(groupKey: string): Promise<DuplicateOwnershipGroup> {
    const encoded = encodeURIComponent(groupKey);
    return request<DuplicateOwnershipGroup>(`/duplicate-ownership/${encoded}`);
  },

  getOpsDuplicateOwnershipList(params?: {
    dup_scan_classification?: DuplicateScanClassificationFilter;
    classification?: DuplicateOwnershipClassification;
  }): Promise<DuplicateOwnershipListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DuplicateOwnershipListResponse>(`/ops/duplicate-ownership${query}`);
  },

  getOpsDuplicateOwnershipGroup(groupKey: string): Promise<DuplicateOwnershipGroup> {
    const encoded = encodeURIComponent(groupKey);
    return request<DuplicateOwnershipGroup>(`/ops/duplicate-ownership/${encoded}`);
  },

  getRunDetectionList(params?: {
    series_status?: RunDetectionSeriesStatus;
  }): Promise<RunDetectionListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RunDetectionListResponse>(`/run-detection${query}`);
  },

  getRunDetectionDetail(seriesKey: string): Promise<RunDetectionSeriesDetail> {
    const encoded = encodeURIComponent(seriesKey);
    return request<RunDetectionSeriesDetail>(`/run-detection/${encoded}`);
  },

  getMissingIssues(params?: {
    classification?: MissingIssueClassification;
  }): Promise<MissingIssueListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<MissingIssueListResponse>(`/missing-issues${query}`);
  },

  getOpsRunDetectionList(params?: {
    series_status?: RunDetectionSeriesStatus;
  }): Promise<RunDetectionListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RunDetectionListResponse>(`/ops/run-detection${query}`);
  },

  getOpsRunDetectionDetail(seriesKey: string): Promise<RunDetectionSeriesDetail> {
    const encoded = encodeURIComponent(seriesKey);
    return request<RunDetectionSeriesDetail>(`/ops/run-detection/${encoded}`);
  },

  getOpsMissingIssues(params?: {
    classification?: MissingIssueClassification;
  }): Promise<MissingIssueListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<MissingIssueListResponse>(`/ops/missing-issues${query}`);
  },

  getPortfolioPerformance(): Promise<PortfolioPerformance> {
    return request<PortfolioPerformance>("/portfolio/performance");
  },

  getInventoryCopy(inventoryCopyId: number): Promise<InventoryDetail> {
    return request<InventoryDetail>(`/inventory/${inventoryCopyId}`);
  },

  getInventoryFmvHistory(inventoryCopyId: number): Promise<InventoryFmvSnapshot[]> {
    return request<InventoryFmvSnapshot[]>(`/inventory/${inventoryCopyId}/fmv-history`);
  },

  updateInventoryCopy(
    inventoryCopyId: number,
    updates: InventoryUpdatePayload,
  ): Promise<InventoryItem> {
    return request<InventoryItem>(`/inventory/${inventoryCopyId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  },

  bulkUpdateInventory(payload: BulkInventoryUpdatePayload): Promise<BulkInventoryUpdateResponse> {
    return request<BulkInventoryUpdateResponse>("/inventory/bulk", {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  createOrder(payload: OrderCreatePayload): Promise<OrderCreateResponse> {
    return request<OrderCreateResponse>("/orders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getOrders(params: OrderQueryParams): Promise<OrderListResponse> {
    const query = buildQueryString(params);
    return request<OrderListResponse>(`/orders${query}`);
  },

  getOrder(orderId: number): Promise<OrderDetail> {
    return request<OrderDetail>(`/orders/${orderId}`);
  },

  parseOrder(payload: AiParseOrderPayload): Promise<AiParseOrderResponse> {
    return request<AiParseOrderResponse>("/ai/parse-order", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getImports(params: ImportQueryParams): Promise<DraftImportListResponse> {
    const query = buildQueryString(params);
    return request<DraftImportListResponse>(`/imports${query}`);
  },

  getImport(importId: number): Promise<DraftImport> {
    return request<DraftImport>(`/imports/${importId}`);
  },

  createImport(payload: DraftImportCreatePayload): Promise<DraftImport> {
    return request<DraftImport>("/imports", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createManualImport(payload: ManualDraftImportCreatePayload): Promise<DraftImport> {
    return request<DraftImport>("/imports/manual", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  enqueueImportParseJob(
    payload: DraftImportCreatePayload,
  ): Promise<ImportParseJobEnqueueResponse> {
    return request<ImportParseJobEnqueueResponse>("/imports/parse-jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getImportParseJobStatus(jobId: string): Promise<ImportParseJobStatusResponse> {
    return request<ImportParseJobStatusResponse>(`/imports/parse-jobs/${jobId}`);
  },

  updateImport(importId: number, payload: DraftImportUpdatePayload): Promise<DraftImport> {
    return request<DraftImport>(`/imports/${importId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  confirmImport(importId: number): Promise<DraftImportConfirmResponse> {
    return request<DraftImportConfirmResponse>(`/imports/${importId}/confirm`, {
      method: "POST",
    });
  },

  discardImport(importId: number): Promise<DraftImport> {
    return request<DraftImport>(`/imports/${importId}/discard`, {
      method: "POST",
    });
  },

  listMetadataAliases(params?: {
    alias_type?: MetadataAliasType;
    is_active?: boolean;
  }): Promise<MetadataAlias[]> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<MetadataAlias[]>(`/ops/metadata-aliases${query}`);
  },

  createMetadataAlias(payload: MetadataAliasCreatePayload): Promise<MetadataAlias> {
    return request<MetadataAlias>("/ops/metadata-aliases", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  deactivateMetadataAlias(aliasId: number): Promise<MetadataAlias> {
    return request<MetadataAlias>(`/ops/metadata-aliases/${aliasId}/deactivate`, {
      method: "POST",
    });
  },

  getInventoryDuplicateCandidates(params: InventoryDuplicatesQueryParams = {}): Promise<
    OpsInventoryDuplicateCandidateGroup[]
  > {
    const query = buildQueryString(params as Record<string, string | number | undefined>);
    return request<OpsInventoryDuplicateCandidateGroup[]>(`/ops/inventory/duplicates${query}`);
  },

  postDuplicateCandidateReviewDecision(
    payload: DuplicateCandidateReviewDecisionPayload,
  ): Promise<void> {
    return request(`/ops/inventory/duplicates/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  patchDuplicateCandidateReviewNotes(payload: DuplicateCandidateNotesPayload): Promise<void> {
    return request(`/ops/inventory/duplicates/review/notes`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  getCanonicalSeriesRegistry(params: {
    publisher?: string;
    title?: string;
    earliest_release_year_min?: number;
    earliest_release_year_max?: number;
    latest_release_year_min?: number;
    latest_release_year_max?: number;
  }): Promise<OpsCanonicalSeriesRow[]> {
    const query = buildQueryString(params as Record<string, string | number | undefined>);
    return request<OpsCanonicalSeriesRow[]>(`/ops/canonical-series${query}`);
  },

  getCanonicalCreatorsRegistry(params: {
    name?: string;
    canonical_name?: string;
    normalized_name?: string;
    creator_key?: string;
  }): Promise<OpsCanonicalCreatorRow[]> {
    const query = buildQueryString(params as Record<string, string | number | undefined>);
    return request<OpsCanonicalCreatorRow[]>(`/ops/canonical-creators${query}`);
  },

  getMetadataAudits(params: {
    limit?: number;
    entity_type?: string;
    action?: string;
  }): Promise<OpsMetadataAuditRow[]> {
    const query = buildQueryString(params as Record<string, string | number | undefined>);
    return request<OpsMetadataAuditRow[]>(`/ops/metadata-audits${query}`);
  },

  enqueueImportReenrichment(
    importId: number,
    reason?: string,
  ): Promise<OpsMetadataReenrichmentEnqueueResponse> {
    return request<OpsMetadataReenrichmentEnqueueResponse>(
      `/ops/imports/${importId}/re-enrich${encodeOptionalReasonQuery(reason)}`,
      { method: "POST" },
    );
  },

  enqueueInventoryReenrichment(
    inventoryCopyId: number,
    reason?: string,
  ): Promise<OpsMetadataReenrichmentEnqueueResponse> {
    return request<OpsMetadataReenrichmentEnqueueResponse>(
      `/ops/inventory/${inventoryCopyId}/re-enrich${encodeOptionalReasonQuery(reason)}`,
      { method: "POST" },
    );
  },

  getOcrBatchesForOps(limit: number): Promise<OcrBatch[]> {
    const query = buildQueryString({ limit });
    return request<OcrBatch[]>(`/ops/ocr-batches${query}`);
  },

  createOcrBatchForOps(payload: OcrBatchCreatePayload): Promise<OcrBatch> {
    return request<OcrBatch>("/ops/ocr-batches", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  enqueueOcrBatchForOps(batchId: number): Promise<OcrBatch> {
    return request<OcrBatch>(`/ops/ocr-batches/${batchId}/enqueue`, { method: "POST" });
  },

  retryFailedOcrBatchItemsForOps(batchId: number): Promise<OcrBatch> {
    return request<OcrBatch>(`/ops/ocr-batches/${batchId}/retry-failed`, {
      method: "POST",
    });
  },

  cancelOcrBatchForOps(batchId: number): Promise<OcrBatch> {
    return request<OcrBatch>(`/ops/ocr-batches/${batchId}/cancel`, { method: "POST" });
  },

  getOcrReplaysForOps(limit: number): Promise<OcrReplayRun[]> {
    const query = buildQueryString({ limit });
    return request<OcrReplayRun[]>(`/ops/ocr-replays${query}`);
  },

  createOcrReplayForOps(payload: OcrReplayCreatePayload): Promise<OcrReplayRun> {
    return request<OcrReplayRun>("/ops/ocr-replays", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  startOcrReplayForOps(replayId: number): Promise<OcrReplayRun> {
    return request<OcrReplayRun>(`/ops/ocr-replays/${replayId}/start`, {
      method: "POST",
    });
  },

  cancelOcrReplayForOps(replayId: number): Promise<OcrReplayRun> {
    return request<OcrReplayRun>(`/ops/ocr-replays/${replayId}/cancel`, {
      method: "POST",
    });
  },

  getRelationshipReplaysForOps(limit: number): Promise<RelationshipReplayRun[]> {
    const query = buildQueryString({ limit });
    return request<RelationshipReplayRun[]>(`/ops/relationship-replays${query}`);
  },

  createRelationshipReplayForOps(payload: RelationshipReplayCreatePayload): Promise<RelationshipReplayRun> {
    return request<RelationshipReplayRun>("/ops/relationship-replays", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  startRelationshipReplayForOps(replayId: number): Promise<RelationshipReplayRun> {
    return request<RelationshipReplayRun>(`/ops/relationship-replays/${replayId}/start`, {
      method: "POST",
    });
  },

  cancelRelationshipReplayForOps(replayId: number): Promise<RelationshipReplayRun> {
    return request<RelationshipReplayRun>(`/ops/relationship-replays/${replayId}/cancel`, {
      method: "POST",
    });
  },

  getRecentCoverImagesForOps(params: {
    limit?: number;
    source_type?: string;
    linkage?: "inventory" | "import";
    matching_status?: "not_ready" | "ready" | "needs_review" | "failed";
  }): Promise<OpsRecentCoverImageRow[]> {
    const query = buildQueryString(params as Record<string, string | number | undefined>);
    return request<OpsRecentCoverImageRow[]>(`/ops/cover-images/recent${query}`);
  },

  getDuplicateCoverImagesForOps(params: {
    limit?: number;
    min_count?: number;
    source_type?: string;
    linkage?: "inventory" | "import" | "unlinked";
  }): Promise<OpsCoverDuplicateGroup[]> {
    const query = buildQueryString(params as Record<string, string | number | undefined>);
    return request<OpsCoverDuplicateGroup[]>(`/ops/cover-images/duplicates${query}`);
  },

  assignExistingCoverToInventory(
    inventoryCopyId: number,
    payload: CoverImageAssignExistingPayload,
  ): Promise<CoverImageRead> {
    return request<CoverImageRead>(`/inventory/${inventoryCopyId}/cover-images/assign-existing`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  setInventoryCoverPrimary(inventoryCopyId: number, coverImageId: number): Promise<CoverImageRead> {
    return request<CoverImageRead>(
      `/inventory/${inventoryCopyId}/cover-images/${coverImageId}/primary`,
      { method: "POST" },
    );
  },

  uploadInventoryCoverImage(inventoryCopyId: number, file: File): Promise<CoverImageRead> {
    const body = new FormData();
    body.append("file", file);
    body.append("source_type", "upload");
    const token = getStoredToken();
    const headers = new Headers();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return (async (): Promise<CoverImageRead> => {
      const response = await fetch(
        `${API_BASE_URL}/inventory/${inventoryCopyId}/cover-images`,
        { method: "POST", headers, body },
      );
      if (response.status === 401) {
        clearStoredToken();
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
        throw new ApiError("Authentication required", 401);
      }
      if (!response.ok) {
        let message = "Request failed";
        try {
          const data = (await response.json()) as { detail?: string };
          if (typeof data.detail === "string") {
            message = data.detail;
          }
        } catch {
          //
        }
        throw new ApiError(message, response.status);
      }
      return (await response.json()) as CoverImageRead;
    })();
  },

  uploadImportCoverImage(importId: number, file: File): Promise<CoverImageRead> {
    const body = new FormData();
    body.append("file", file);
    body.append("source_type", "import_image");
    const token = getStoredToken();
    const headers = new Headers();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
    return (async (): Promise<CoverImageRead> => {
      const response = await fetch(`${API_BASE_URL}/imports/${importId}/cover-images`, {
        method: "POST",
        headers,
        body,
      });
      if (response.status === 401) {
        clearStoredToken();
        if (window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
        throw new ApiError("Authentication required", 401);
      }
      if (!response.ok) {
        let message = "Request failed";
        try {
          const data = (await response.json()) as { detail?: string };
          if (typeof data.detail === "string") {
            message = data.detail;
          }
        } catch {
          //
        }
        throw new ApiError(message, response.status);
      }
      return (await response.json()) as CoverImageRead;
    })();
  },

  setImportCoverPrimary(importId: number, coverImageId: number): Promise<CoverImageRead> {
    return request<CoverImageRead>(`/imports/${importId}/cover-images/${coverImageId}/primary`, {
      method: "POST",
    });
  },

  processCoverImage(coverImageId: number): Promise<CoverImageProcessingEnqueueResponse> {
    return request<CoverImageProcessingEnqueueResponse>(
      `/cover-images/${coverImageId}/process`,
      { method: "POST" },
    );
  },

  processCoverImageForOps(coverImageId: number): Promise<CoverImageProcessingEnqueueResponse> {
    return request<CoverImageProcessingEnqueueResponse>(
      `/ops/cover-images/${coverImageId}/process`,
      { method: "POST" },
    );
  },

  evaluateCoverImageMatchingReadiness(coverImageId: number): Promise<CoverImageMatchingEvaluationResponse> {
    return request<CoverImageMatchingEvaluationResponse>(
      `/cover-images/${coverImageId}/evaluate-matching-readiness`,
      { method: "POST" },
    );
  },

  evaluateCoverImageMatchingReadinessForOps(
    coverImageId: number,
  ): Promise<CoverImageMatchingEvaluationResponse> {
    return request<CoverImageMatchingEvaluationResponse>(
      `/ops/cover-images/${coverImageId}/evaluate-matching-readiness`,
      { method: "POST" },
    );
  },

  runCoverImageOcr(coverImageId: number): Promise<CoverImageOcrEnqueueResponse> {
    return request<CoverImageOcrEnqueueResponse>(`/cover-images/${coverImageId}/run-ocr`, {
      method: "POST",
    });
  },

  runCoverImageOcrForOps(coverImageId: number): Promise<CoverImageOcrEnqueueResponse> {
    return request<CoverImageOcrEnqueueResponse>(`/ops/cover-images/${coverImageId}/run-ocr`, {
      method: "POST",
    });
  },

  replayCoverImageOcr(coverImageId: number, payload?: CoverImageOcrReplayPayload): Promise<CoverImageOcrEnqueueResponse> {
    return request<CoverImageOcrEnqueueResponse>(`/cover-images/${coverImageId}/replay-ocr`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  replayCoverImageOcrForOps(
    coverImageId: number,
    payload?: CoverImageOcrReplayPayload,
  ): Promise<CoverImageOcrEnqueueResponse> {
    return request<CoverImageOcrEnqueueResponse>(`/ops/cover-images/${coverImageId}/replay-ocr`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  approveOcrCandidate(ocrCandidateId: number): Promise<CoverImageOcrCandidateRead> {
    return request<CoverImageOcrCandidateRead>(`/ocr-candidates/${ocrCandidateId}/approve`, {
      method: "POST",
    });
  },

  rejectOcrCandidate(ocrCandidateId: number): Promise<CoverImageOcrCandidateRead> {
    return request<CoverImageOcrCandidateRead>(`/ocr-candidates/${ocrCandidateId}/reject`, {
      method: "POST",
    });
  },

  patchOcrCandidateReviewNotes(
    ocrCandidateId: number,
    payload: { review_notes: string | null },
  ): Promise<CoverImageOcrCandidateRead> {
    return request<CoverImageOcrCandidateRead>(
      `/ocr-candidates/${ocrCandidateId}/review-notes`,
      { method: "PATCH", body: JSON.stringify(payload) },
    );
  },

  extractCoverImageBarcodes(coverImageId: number): Promise<CoverImageBarcodeCandidateExtractResponse> {
    return request<CoverImageBarcodeCandidateExtractResponse>(
      `/cover-images/${coverImageId}/extract-barcodes`,
      { method: "POST" },
    );
  },

  approveBarcodeCandidate(barcodeCandidateId: number): Promise<CoverImageBarcodeCandidateRead> {
    return request<CoverImageBarcodeCandidateRead>(
      `/barcode-candidates/${barcodeCandidateId}/approve`,
      { method: "PATCH" },
    );
  },

  rejectBarcodeCandidate(barcodeCandidateId: number): Promise<CoverImageBarcodeCandidateRead> {
    return request<CoverImageBarcodeCandidateRead>(
      `/barcode-candidates/${barcodeCandidateId}/reject`,
      { method: "PATCH" },
    );
  },

  generateCoverImageFingerprints(coverImageId: number): Promise<CoverImageFingerprintGenerateResponse> {
    return request<CoverImageFingerprintGenerateResponse>(
      `/cover-images/${coverImageId}/generate-fingerprints`,
      { method: "POST" },
    );
  },

  generateCoverImageFingerprintsForOps(coverImageId: number): Promise<CoverImageFingerprintGenerateResponse> {
    return request<CoverImageFingerprintGenerateResponse>(
      `/ops/cover-images/${coverImageId}/generate-fingerprints`,
      { method: "POST" },
    );
  },

  analyzeCoverImageOcrQuality(coverImageId: number): Promise<CoverImageOcrQualityAnalysisResponse> {
    return request<CoverImageOcrQualityAnalysisResponse>(
      `/cover-images/${coverImageId}/analyze-ocr-quality`,
      { method: "POST" },
    );
  },

  analyzeCoverImageOcrQualityForOps(coverImageId: number): Promise<CoverImageOcrQualityAnalysisResponse> {
    return request<CoverImageOcrQualityAnalysisResponse>(
      `/ops/cover-images/${coverImageId}/analyze-ocr-quality`,
      { method: "POST" },
    );
  },

  generateCoverImageMatchCandidates(
    coverImageId: number,
  ): Promise<CoverImageMatchCandidateGenerateResponse> {
    return request<CoverImageMatchCandidateGenerateResponse>(
      `/cover-images/${coverImageId}/generate-match-candidates`,
      { method: "POST" },
    );
  },

  getMatchGroup(groupingKey: string): Promise<CoverImageMatchGroupRead> {
    return request<CoverImageMatchGroupRead>(`/match-groups/${encodeURIComponent(groupingKey)}`);
  },

  createCoverLinkDecision(
    payload: CoverImageLinkDecisionCreatePayload,
  ): Promise<CoverImageLinkDecisionRead> {
    return request<CoverImageLinkDecisionRead>("/cover-link-decisions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listCoverLinkDecisions(params?: {
    cover_image_id?: number;
    include_inactive?: boolean;
    limit?: number;
  }): Promise<CoverImageLinkDecisionRead[]> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<CoverImageLinkDecisionRead[]>(`/cover-link-decisions${query}`);
  },

  getCoverLinkDecision(decisionId: number): Promise<CoverImageLinkDecisionRead> {
    return request<CoverImageLinkDecisionRead>(`/cover-link-decisions/${decisionId}`);
  },

  revertCoverLinkDecision(decisionId: number): Promise<CoverImageLinkDecisionRead> {
    return request<CoverImageLinkDecisionRead>(`/cover-link-decisions/${decisionId}/revert`, {
      method: "POST",
    });
  },

  listRecentCoverLinkDecisions(params?: {
    include_inactive?: boolean;
    limit?: number;
  }): Promise<CoverImageLinkDecisionRead[]> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<CoverImageLinkDecisionRead[]>(`/cover-link-decisions/recent${query}`);
  },

  getCoverRelationshipGraph(coverImageId: number): Promise<CoverRelationshipGraphRead> {
    return request<CoverRelationshipGraphRead>(`/cover-images/${coverImageId}/relationship-graph`);
  },

  getCoverRelationshipGraphQuery(coverImageId: number): Promise<CoverRelationshipGraphRead> {
    return request<CoverRelationshipGraphRead>(`/cover-relationship-graph${buildQueryString({ cover_image_id: coverImageId })}`);
  },

  getDuplicateScanCandidates(coverImageId: number): Promise<DuplicateScanCandidatesResponse> {
    return request<DuplicateScanCandidatesResponse>(`/cover-images/${coverImageId}/duplicate-scan-candidates`);
  },

  listDuplicateScanClusters(params?: {
    classification_filter?: DuplicateScanClassificationFilter;
  }): Promise<DuplicateScanClustersListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DuplicateScanClustersListResponse>(`/duplicate-scan-clusters${query}`);
  },

  getVariantFamilyCandidates(coverImageId: number): Promise<VariantFamilyCandidatesResponse> {
    return request<VariantFamilyCandidatesResponse>(
      `/cover-images/${coverImageId}/variant-family-candidates`,
    );
  },

  listVariantFamilyClusters(params?: {
    classification_filter?: VariantFamilyClassificationFilter;
  }): Promise<VariantFamilyClustersListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<VariantFamilyClustersListResponse>(`/variant-family-clusters${query}`);
  },

  generateCanonicalIssueSuggestions(
    coverImageId: number,
  ): Promise<CanonicalIssueSuggestionGenerateResponse> {
    return request<CanonicalIssueSuggestionGenerateResponse>(
      `/cover-images/${coverImageId}/generate-canonical-issue-suggestions`,
      { method: "POST" },
    );
  },

  getCanonicalIssueSuggestions(coverImageId: number): Promise<CanonicalIssueLinkSuggestionRead[]> {
    return request<CanonicalIssueLinkSuggestionRead[]>(
      `/cover-images/${coverImageId}/canonical-issue-suggestions`,
    );
  },

  approveCanonicalIssueSuggestion(
    suggestionId: number,
    payload?: CanonicalIssueSuggestionReviewPayload,
  ): Promise<CanonicalIssueSuggestionReviewActionResponse> {
    return request<CanonicalIssueSuggestionReviewActionResponse>(
      `/canonical-issue-suggestions/${suggestionId}/approve`,
      { method: "PATCH", body: JSON.stringify(payload ?? {}) },
    );
  },

  rejectCanonicalIssueSuggestion(
    suggestionId: number,
    payload?: CanonicalIssueSuggestionReviewPayload,
  ): Promise<CanonicalIssueSuggestionReviewActionResponse> {
    return request<CanonicalIssueSuggestionReviewActionResponse>(
      `/canonical-issue-suggestions/${suggestionId}/reject`,
      { method: "PATCH", body: JSON.stringify(payload ?? {}) },
    );
  },

  ignoreCanonicalIssueSuggestion(
    suggestionId: number,
    payload?: CanonicalIssueSuggestionReviewPayload,
  ): Promise<CanonicalIssueSuggestionReviewActionResponse> {
    return request<CanonicalIssueSuggestionReviewActionResponse>(
      `/canonical-issue-suggestions/${suggestionId}/ignore`,
      { method: "PATCH", body: JSON.stringify(payload ?? {}) },
    );
  },

  acknowledgeCoverMatchCandidate(matchCandidateId: number): Promise<CoverImageMatchCandidateRead> {
    return request<CoverImageMatchCandidateRead>(
      `/match-candidates/${matchCandidateId}/acknowledge`,
      { method: "PATCH" },
    );
  },

  dismissCoverMatchCandidate(matchCandidateId: number): Promise<CoverImageMatchCandidateRead> {
    return request<CoverImageMatchCandidateRead>(`/match-candidates/${matchCandidateId}/dismiss`, {
      method: "PATCH",
    });
  },

  reconcileCoverImageOcrMetadata(coverImageId: number): Promise<CoverImageOcrReconciliationResponse> {
    return request<CoverImageOcrReconciliationResponse>(
      `/cover-images/${coverImageId}/reconcile-ocr-metadata`,
      { method: "POST" },
    );
  },

  acknowledgeOcrReconciliationWarning(warningId: number): Promise<CoverImageOcrReconciliationWarningRead> {
    return request<CoverImageOcrReconciliationWarningRead>(
      `/ocr-reconciliation-warnings/${warningId}/acknowledge`,
      { method: "PATCH" },
    );
  },

  dismissOcrReconciliationWarning(warningId: number): Promise<CoverImageOcrReconciliationWarningRead> {
    return request<CoverImageOcrReconciliationWarningRead>(
      `/ocr-reconciliation-warnings/${warningId}/dismiss`,
      { method: "PATCH" },
    );
  },

  /* Ops OCR drill-down helpers (covers any owner for ops admins) */
  getCoverImageOcrResultsForOps(coverImageId: number): Promise<CoverImageOcrResultRead[]> {
    return request<CoverImageOcrResultRead[]>(`/ops/cover-images/${coverImageId}/ocr-results`);
  },

  getCoverImageOcrReconciliationWarningsForOps(
    coverImageId: number,
  ): Promise<CoverImageOcrReconciliationWarningRead[]> {
    return request<CoverImageOcrReconciliationWarningRead[]>(
      `/ops/cover-images/${coverImageId}/ocr-reconciliation-warnings`,
    );
  },

  getCoverImageBarcodeCandidatesForOps(coverImageId: number): Promise<CoverImageBarcodeCandidateRead[]> {
    return request<CoverImageBarcodeCandidateRead[]>(
      `/ops/cover-images/${coverImageId}/barcode-candidates`,
    );
  },

  getCoverImageFingerprintsForOps(coverImageId: number): Promise<CoverImageFingerprintRead[]> {
    return request<CoverImageFingerprintRead[]>(`/ops/cover-images/${coverImageId}/fingerprints`);
  },

  getCoverImageMatchCandidatesForOps(coverImageId: number): Promise<CoverImageMatchCandidateRead[]> {
    return request<CoverImageMatchCandidateRead[]>(
      `/ops/cover-images/${coverImageId}/match-candidates`,
    );
  },

  getMatchGroupForOps(groupingKey: string): Promise<CoverImageMatchGroupRead> {
    return request<CoverImageMatchGroupRead>(`/ops/match-groups/${encodeURIComponent(groupingKey)}`);
  },

  createCoverLinkDecisionForOps(
    payload: CoverImageLinkDecisionCreatePayload,
  ): Promise<CoverImageLinkDecisionRead> {
    return request<CoverImageLinkDecisionRead>("/ops/cover-link-decisions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listCoverLinkDecisionsForOps(params?: {
    cover_image_id?: number;
    include_inactive?: boolean;
    limit?: number;
  }): Promise<CoverImageLinkDecisionRead[]> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<CoverImageLinkDecisionRead[]>(`/ops/cover-link-decisions${query}`);
  },

  getCoverLinkDecisionForOps(decisionId: number): Promise<CoverImageLinkDecisionRead> {
    return request<CoverImageLinkDecisionRead>(`/ops/cover-link-decisions/${decisionId}`);
  },

  revertCoverLinkDecisionForOps(decisionId: number): Promise<CoverImageLinkDecisionRead> {
    return request<CoverImageLinkDecisionRead>(`/ops/cover-link-decisions/${decisionId}/revert`, {
      method: "POST",
    });
  },

  listRecentCoverLinkDecisionsForOps(params?: {
    include_inactive?: boolean;
    limit?: number;
  }): Promise<CoverImageLinkDecisionRead[]> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<CoverImageLinkDecisionRead[]>(`/ops/cover-link-decisions/recent${query}`);
  },

  getCoverRelationshipGraphForOps(coverImageId: number): Promise<CoverRelationshipGraphRead> {
    return request<CoverRelationshipGraphRead>(`/ops/cover-images/${coverImageId}/relationship-graph`);
  },

  getCoverRelationshipGraphQueryForOps(coverImageId: number): Promise<CoverRelationshipGraphRead> {
    return request<CoverRelationshipGraphRead>(
      `/ops/cover-relationship-graph${buildQueryString({ cover_image_id: coverImageId })}`,
    );
  },

  getDuplicateScanCandidatesForOps(coverImageId: number): Promise<DuplicateScanCandidatesResponse> {
    return request<DuplicateScanCandidatesResponse>(`/ops/cover-images/${coverImageId}/duplicate-scan-candidates`);
  },

  listDuplicateScanClustersForOps(params?: {
    classification_filter?: DuplicateScanClassificationFilter;
  }): Promise<DuplicateScanClustersListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DuplicateScanClustersListResponse>(`/ops/duplicate-scan-clusters${query}`);
  },

  getVariantFamilyCandidatesForOps(coverImageId: number): Promise<VariantFamilyCandidatesResponse> {
    return request<VariantFamilyCandidatesResponse>(
      `/ops/cover-images/${coverImageId}/variant-family-candidates`,
    );
  },

  listVariantFamilyClustersForOps(params?: {
    classification_filter?: VariantFamilyClassificationFilter;
  }): Promise<VariantFamilyClustersListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<VariantFamilyClustersListResponse>(`/ops/variant-family-clusters${query}`);
  },

  generateCanonicalIssueSuggestionsForOps(
    coverImageId: number,
  ): Promise<CanonicalIssueSuggestionGenerateResponse> {
    return request<CanonicalIssueSuggestionGenerateResponse>(
      `/ops/cover-images/${coverImageId}/generate-canonical-issue-suggestions`,
      { method: "POST" },
    );
  },

  getCanonicalIssueSuggestionsForOps(coverImageId: number): Promise<CanonicalIssueLinkSuggestionRead[]> {
    return request<CanonicalIssueLinkSuggestionRead[]>(
      `/ops/cover-images/${coverImageId}/canonical-issue-suggestions`,
    );
  },

  detectRelationshipConflicts(): Promise<RelationshipConflictDetectResponse> {
    return request<RelationshipConflictDetectResponse>("/relationship-conflicts/detect", {
      method: "POST",
    });
  },

  getRelationshipConflicts(params?: {
    severity?: RelationshipConflictSeverity | "all";
    status?: RelationshipConflictStatus | "all";
    conflict_type?: RelationshipConflictType | "all";
  }): Promise<RelationshipConflictListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RelationshipConflictListResponse>(`/relationship-conflicts${query}`);
  },

  getRelationshipConflictsForCover(
    coverImageId: number,
    params?: {
      severity?: RelationshipConflictSeverity | "all";
      status?: RelationshipConflictStatus | "all";
      conflict_type?: RelationshipConflictType | "all";
    },
  ): Promise<RelationshipConflictListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RelationshipConflictListResponse>(`/cover-images/${coverImageId}/relationship-conflicts${query}`);
  },

  acknowledgeRelationshipConflict(
    conflictId: number,
    payload?: RelationshipConflictStatusPayload,
  ): Promise<{ conflict: RelationshipConflictRead }> {
    return request<{ conflict: RelationshipConflictRead }>(`/relationship-conflicts/${conflictId}/acknowledge`, {
      method: "PATCH",
      body: JSON.stringify(payload ?? {}),
    });
  },

  dismissRelationshipConflict(
    conflictId: number,
    payload?: RelationshipConflictStatusPayload,
  ): Promise<{ conflict: RelationshipConflictRead }> {
    return request<{ conflict: RelationshipConflictRead }>(`/relationship-conflicts/${conflictId}/dismiss`, {
      method: "PATCH",
      body: JSON.stringify(payload ?? {}),
    });
  },

  resolveRelationshipConflict(
    conflictId: number,
    payload?: RelationshipConflictStatusPayload,
  ): Promise<{ conflict: RelationshipConflictRead }> {
    return request<{ conflict: RelationshipConflictRead }>(`/relationship-conflicts/${conflictId}/resolve`, {
      method: "PATCH",
      body: JSON.stringify(payload ?? {}),
    });
  },

  detectRelationshipConflictsForOps(): Promise<RelationshipConflictDetectResponse> {
    return request<RelationshipConflictDetectResponse>("/ops/relationship-conflicts/detect", {
      method: "POST",
    });
  },

  getRelationshipConflictsForOps(params?: {
    severity?: RelationshipConflictSeverity | "all";
    status?: RelationshipConflictStatus | "all";
    conflict_type?: RelationshipConflictType | "all";
  }): Promise<RelationshipConflictListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RelationshipConflictListResponse>(`/ops/relationship-conflicts${query}`);
  },

  getRelationshipConflictsForCoverOps(
    coverImageId: number,
    params?: {
      severity?: RelationshipConflictSeverity | "all";
      status?: RelationshipConflictStatus | "all";
      conflict_type?: RelationshipConflictType | "all";
    },
  ): Promise<RelationshipConflictListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RelationshipConflictListResponse>(
      `/ops/cover-images/${coverImageId}/relationship-conflicts${query}`,
    );
  },

  acknowledgeRelationshipConflictForOps(
    conflictId: number,
    payload?: RelationshipConflictStatusPayload,
  ): Promise<{ conflict: RelationshipConflictRead }> {
    return request<{ conflict: RelationshipConflictRead }>(`/ops/relationship-conflicts/${conflictId}/acknowledge`, {
      method: "PATCH",
      body: JSON.stringify(payload ?? {}),
    });
  },

  dismissRelationshipConflictForOps(
    conflictId: number,
    payload?: RelationshipConflictStatusPayload,
  ): Promise<{ conflict: RelationshipConflictRead }> {
    return request<{ conflict: RelationshipConflictRead }>(`/ops/relationship-conflicts/${conflictId}/dismiss`, {
      method: "PATCH",
      body: JSON.stringify(payload ?? {}),
    });
  },

  resolveRelationshipConflictForOps(
    conflictId: number,
    payload?: RelationshipConflictStatusPayload,
  ): Promise<{ conflict: RelationshipConflictRead }> {
    return request<{ conflict: RelationshipConflictRead }>(`/ops/relationship-conflicts/${conflictId}/resolve`, {
      method: "PATCH",
      body: JSON.stringify(payload ?? {}),
    });
  },

  approveCanonicalIssueSuggestionForOps(
    suggestionId: number,
    payload?: CanonicalIssueSuggestionReviewPayload,
  ): Promise<CanonicalIssueSuggestionReviewActionResponse> {
    return request<CanonicalIssueSuggestionReviewActionResponse>(
      `/ops/canonical-issue-suggestions/${suggestionId}/approve`,
      { method: "PATCH", body: JSON.stringify(payload ?? {}) },
    );
  },

  rejectCanonicalIssueSuggestionForOps(
    suggestionId: number,
    payload?: CanonicalIssueSuggestionReviewPayload,
  ): Promise<CanonicalIssueSuggestionReviewActionResponse> {
    return request<CanonicalIssueSuggestionReviewActionResponse>(
      `/ops/canonical-issue-suggestions/${suggestionId}/reject`,
      { method: "PATCH", body: JSON.stringify(payload ?? {}) },
    );
  },

  ignoreCanonicalIssueSuggestionForOps(
    suggestionId: number,
    payload?: CanonicalIssueSuggestionReviewPayload,
  ): Promise<CanonicalIssueSuggestionReviewActionResponse> {
    return request<CanonicalIssueSuggestionReviewActionResponse>(
      `/ops/canonical-issue-suggestions/${suggestionId}/ignore`,
      { method: "PATCH", body: JSON.stringify(payload ?? {}) },
    );
  },

  listCanonicalIssueSuggestionsForOps(params?: {
    review_state?: CanonicalIssueSuggestionReviewState | "all";
    confidence_bucket?: CanonicalIssueSuggestionConfidenceBucket | "all";
    suggestion_type?: CanonicalIssueSuggestionType | "all";
  }): Promise<CanonicalIssueSuggestionOpsListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<CanonicalIssueSuggestionOpsListResponse>(`/ops/canonical-issue-suggestions${query}`);
  },

  getCoverImageOcrQualityAnalysisForOps(coverImageId: number): Promise<CoverImageOcrQualityAnalysisRead[]> {
    return request<CoverImageOcrQualityAnalysisRead[]>(
      `/ops/cover-images/${coverImageId}/ocr-quality-analysis`,
    );
  },

  /* OCR review workspace */
  getOcrReviewSummaryForOps(): Promise<OcrReviewSummaryResponse> {
    return request<OcrReviewSummaryResponse>("/ops/ocr-review-summary");
  },

  getOcrReviewQueueForOps(params?: OcrReviewQueueQueryParams): Promise<OcrReviewQueueResponse> {
    const suffix = params ? buildOcrReviewQueueQueryString(params) : "";
    return request<OcrReviewQueueResponse>(`/ops/ocr-review-queue${suffix}`);
  },

  bulkAcknowledgeOcrReconciliationWarningsForOps(payload: BulkIdsPayload): Promise<BulkMutationResult> {
    return request<BulkMutationResult>("/ops/ocr-review/bulk/reconciliation-warnings/acknowledge", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  bulkDismissOcrReconciliationWarningsForOps(payload: BulkIdsPayload): Promise<BulkMutationResult> {
    return request<BulkMutationResult>("/ops/ocr-review/bulk/reconciliation-warnings/dismiss", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  bulkApproveBarcodeCandidatesForOps(payload: BulkIdsPayload): Promise<BulkMutationResult> {
    return request<BulkMutationResult>("/ops/ocr-review/bulk/barcode-candidates/approve", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  bulkRejectBarcodeCandidatesForOps(payload: BulkIdsPayload): Promise<BulkMutationResult> {
    return request<BulkMutationResult>("/ops/ocr-review/bulk/barcode-candidates/reject", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  fetchCoverImageBlob(path: string): Promise<Blob> {
    return fetchBinary(path);
  },
};

export { ApiError, getStoredToken };
