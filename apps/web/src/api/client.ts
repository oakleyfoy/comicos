const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
const MARKET_API_V1_PREFIX = "/api/v1/market";
const SCAN_API_V1_PREFIX = "/api/v1";

export const TOKEN_STORAGE_KEY = "comic-os-access-token";
const ACTIVE_ORGANIZATION_STORAGE_KEY = "comic-os.active-organization-id";

/** P39-07 standardized pagination nested under list `data` for `/api/v1/market/*`. */
export interface MarketApiV1Pagination {
  total_count: number;
  limit: number;
  offset: number;
  has_next: boolean;
  next_cursor: string | null;
}

/** P39-07 response `meta` block (surfaced alongside `data` for market v1 endpoints). */
export interface MarketApiV1Meta {
  owner_user_id: string | null;
  snapshot_id: string | null;
  checksum: string | null;
  generated_at: string;
  engine_versions: Record<string, string>;
}

export interface MarketApiV1Envelope<T> {
  data: T;
  meta: MarketApiV1Meta;
}

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

export interface UserAuthSessionRead {
  id: number;
  user_id: number;
  device_label: string;
  device_type: string;
  ip_address?: string | null;
  user_agent?: string | null;
  organization_id?: number | null;
  session_status: string;
  issued_at: string;
  last_seen_at: string;
  expires_at: string;
  revoked_at?: string | null;
  is_current: boolean;
}

export interface OrganizationSecurityContextRead {
  id: number;
  user_id: number;
  active_organization_id?: number | null;
  active_organization_slug?: string | null;
  active_organization_display_name?: string | null;
  last_org_switch_at?: string | null;
  session_id: number;
  session_status: string;
  session_expires_at: string;
  role_keys: string[];
  permission_keys: string[];
}

export interface UserAuthSessionListResponse {
  items: UserAuthSessionRead[];
  pagination: MarketApiV1Pagination;
}

export interface RevokeAuthSessionRequest {
  session_id: number;
}

export interface SwitchOrganizationRequest {
  organization_id: number;
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

export type ScanPipelineReplayScope =
  | "ingest"
  | "qa"
  | "routing"
  | "ocr_visibility"
  | "high_res_review";

export type ScanPipelineReplayRunStatus =
  | "pending"
  | "running"
  | "completed"
  | "completed_with_failures"
  | "cancelled";

export type ScanPipelineReplayItemState = "unchanged" | "changed" | "failed" | "cancelled";

/** Ops + owner scan session recap for last booked replay header. */
export interface ScanPipelineReplayRunSummaryRead {
  id: number;
  scan_session_id: number;
  status: ScanPipelineReplayRunStatus;
  changed_items: number;
  unchanged_items: number;
  failed_items: number;
  cancelled_items: number;
  total_items: number;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanPipelineReplayItemRead {
  id: number;
  replay_run_id: number;
  scan_session_item_id: number;
  result_state: ScanPipelineReplayItemState;
  diff_categories: string[];
  baseline_snapshot_json: Record<string, unknown>;
  replay_snapshot_json: Record<string, unknown>;
  diff_summary_json: Record<string, unknown>;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface ScanPipelineReplayRunRead {
  id: number;
  scan_session_id: number;
  owner_user_id: number;
  replay_version: string;
  scopes_json: string[];
  cancellation_requested: boolean;
  status: ScanPipelineReplayRunStatus;
  total_items: number;
  changed_items: number;
  unchanged_items: number;
  failed_items: number;
  cancelled_items: number;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  items: ScanPipelineReplayItemRead[];
}

export interface ScanPipelineReplayListRead {
  items: ScanPipelineReplayRunRead[];
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

export type InventoryActionCenterCategory =
  | "review_relationship_conflict"
  | "review_canonical_suggestion"
  | "review_duplicate_ownership"
  | "review_duplicate_scan"
  | "review_variant_family"
  | "retry_ocr"
  | "review_cover_processing"
  | "scan_missing_cover"
  | "update_preorder_metadata"
  | "review_run_gap"
  | "review_high_confidence_match";

export interface InventoryActionCenterItem {
  action_key: string;
  action_category: InventoryActionCenterCategory;
  priority: InventoryRiskPriority;
  inventory_copy_id: number;
  cover_image_id: number | null;
  publisher: string;
  title: string;
  issue_number: string;
  ownership_state: InventoryOwnershipNormalized;
  release_status: "released" | "not_released_yet" | "unknown";
  preorder_release_state_label: string;
  evidence_summary_lines: string[];
  evidence_json: Record<string, unknown>;
  source: "inventory_risk" | "intelligence_duplicate_scan" | "intelligence_variant_family" | "order_arrival";
}

export interface InventoryActionCenterGrouping {
  action_keys_by_inventory_copy_id: Record<string, string[]>;
  action_keys_by_cover_image_id: Record<string, string[]>;
  action_keys_by_series_key: Record<string, string[]>;
  action_keys_by_publisher: Record<string, string[]>;
  action_keys_by_ownership_state: Record<string, string[]>;
  action_keys_by_preorder_release_state: Record<string, string[]>;
}

export interface InventoryActionCenterTopItem {
  inventory_copy_id: number;
  publisher: string;
  title: string;
  issue_number: string;
  highest_lane_priority: InventoryRiskPriority;
  ownership_state: InventoryOwnershipNormalized;
  action_count: number;
  action_categories: InventoryActionCenterCategory[];
}

export interface InventoryActionCenterSummary {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  total_inventory_copies: number;
  total_actions: number;
  copies_with_actions: number;
  critical_actions: number;
  high_actions: number;
  medium_actions: number;
  low_actions: number;
  info_actions: number;
  by_category: KeyedInventoryCountRow[];
  by_priority_lane: KeyedInventoryCountRow[];
  top_unresolved_inventory: InventoryActionCenterTopItem[];
}

export interface InventoryActionCenterListResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  priority: InventoryRiskPriority | "all";
  action_category: InventoryActionCenterCategory | "all";
  ownership_state: InventoryOwnershipNormalized | "all";
  publisher: string | null;
  release_status: "released" | "not_released_yet" | "unknown" | "all";
  unresolved_only: boolean;
  in_hand_only: boolean;
  inventory_copy_id_filter: number | null;
  summary: InventoryActionCenterSummary;
  grouping: InventoryActionCenterGrouping;
  actions: InventoryActionCenterItem[];
}

export interface InventoryActionCenterAttachment {
  action_keys: string[];
  action_categories: InventoryActionCenterCategory[];
  highest_lane_priority: InventoryRiskPriority | null;
  urgent_lane: boolean;
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

export type PhysicalIntakeState =
  | "awaiting_release"
  | "released_awaiting_receipt"
  | "received_pending_scan"
  | "received_scanned"
  | "intake_blocked"
  | "cancelled"
  | "completed";

export type PhysicalIntakeDashboardBucket =
  | "released_not_received"
  | "received_pending_scan"
  | "overdue_expected_ship"
  | "missing_release_date"
  | "missing_expected_ship_date"
  | "cancelled"
  | "completed";

export interface PhysicalIntakeSummaryCounts {
  released_not_received: number;
  received_pending_scan: number;
  overdue_expected_ship: number;
  missing_release_date: number;
  missing_expected_ship_date: number;
  cancelled: number;
  completed: number;
  awaiting_release: number;
  released_awaiting_receipt: number;
  intake_blocked: number;
  received_scanned: number;
}

export interface PhysicalIntakeSummaryResponse {
  generated_as_of: string;
  counts: PhysicalIntakeSummaryCounts;
}

export interface PhysicalIntakeItemRead {
  inventory_copy_id: number;
  order_item_id: number;
  order_id: number;
  intake_state: PhysicalIntakeState;
  retailer: string;
  publisher: string;
  title: string;
  issue_number: string;
  purchase_date?: string | null;
  release_date?: string | null;
  release_status: string;
  order_status: string;
  asset_state: string;
  expected_ship_date?: string | null;
  received_at?: string | null;
  has_cover_scan: boolean;
  ocr_complete_on_primary_cover: boolean;
  dashboard_buckets: PhysicalIntakeDashboardBucket[];
  order_arrival_classifications: OrderArrivalClassification[];
}

export interface PhysicalIntakeListResponse {
  generated_as_of: string;
  items: PhysicalIntakeItemRead[];
}

export interface MarkInventoryReceivedPayload {
  received_at?: string | null;
}

export interface CreatePhysicalIntakeScanSessionPayload {
  inventory_copy_ids: number[];
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
  current_market_fmv: string | null;
  fmv_snapshot_id: number | null;
  fmv_method: MarketFmvValuationMethod | null;
  fmv_confidence_bucket: MarketFmvConfidenceBucket | null;
  fmv_liquidity_bucket: MarketFmvLiquidityBucket | null;
  fmv_volatility_bucket: MarketFmvVolatilityBucket | null;
  fmv_stale_data: boolean | null;
  fmv_currency_code: string | null;
  valuation_scope: InventoryValuationScope | null;
  valuation_evidence_json: Record<string, unknown> | null;
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
  inventory_action_center?: InventoryActionCenterAttachment | null;
  organization_assignment_id?: number | null;
  organization_assigned_user_id?: number | null;
  organization_assignment_status?: string | null;
  organization_queue_name?: string | null;
  organization_queue_position?: number | null;
  organization_active_review_id?: number | null;
  organization_review_status?: string | null;
  organization_review_type?: string | null;
  organization_review_queue_name?: string | null;
}

export type ScanSessionType =
  | "bulk_ingest"
  | "high_res_review"
  | "intake_receiving"
  | "rescan"
  | "manual_upload";

export type ScanSessionStatus =
  | "pending"
  | "active"
  | "paused"
  | "completed"
  | "completed_with_errors"
  | "cancelled";

export type ScanIngestStatus =
  | "pending"
  | "imported"
  | "queued_for_ocr"
  | "ocr_complete"
  | "review_required"
  | "failed"
  | "skipped";

export type ScannerProfileHardwareType =
  | "fujitsu_bulk"
  | "epson_high_res"
  | "generic_flatbed"
  | "manual_upload";

export type ScannerColorMode = "color" | "grayscale" | "black_and_white";

export type ScannerFileFormat = "png" | "jpg" | "tif";

export type ScannerRecommendedUse =
  | "bulk_ingest"
  | "high_res_review"
  | "intake_receiving"
  | "archival_scan";

export interface ScannerProfileSnapshotRead {
  profile_name: string;
  scanner_type: ScannerProfileHardwareType;
  dpi: number | null;
  color_mode: ScannerColorMode;
  file_format: ScannerFileFormat;
  duplex_enabled: boolean;
  feeder_enabled: boolean;
  recommended_use: ScannerRecommendedUse;
}

export interface ScannerProfileRead {
  id: number;
  owner_user_id: number | null;
  profile_name: string;
  scanner_type: ScannerProfileHardwareType;
  dpi: number | null;
  color_mode: ScannerColorMode;
  file_format: ScannerFileFormat;
  duplex_enabled: boolean;
  feeder_enabled: boolean;
  recommended_use: ScannerRecommendedUse;
  is_default: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScannerProfileListResponse {
  items: ScannerProfileRead[];
}

export interface ScannerProfileCreatePayload {
  profile_name: string;
  scanner_type: ScannerProfileHardwareType;
  dpi?: number | null;
  color_mode?: ScannerColorMode;
  file_format?: ScannerFileFormat;
  duplex_enabled?: boolean;
  feeder_enabled?: boolean;
  recommended_use?: ScannerRecommendedUse;
  is_default?: boolean;
  notes?: string | null;
}

export type ScannerProfileUpdatePayload = Partial<Omit<ScannerProfileCreatePayload, "profile_name">> & {
  profile_name?: string;
};

export type MarketSaleListingType = "auction" | "fixed_price" | "accepted_offer" | "buy_it_now" | "other";
export type MarketSaleNormalizationStatus =
  | "raw"
  | "partially_normalized"
  | "normalized"
  | "normalization_failed"
  | "ignored";
export type MarketSaleGradingCompany = "CGC" | "CBCS" | "PGX" | "other";
export type MarketSaleIssueType =
  | "missing_issue_number"
  | "ambiguous_variant"
  | "invalid_grade"
  | "malformed_title"
  | "missing_sale_price"
  | "duplicate_listing"
  | "unsupported_currency";
export type MarketSaleIssueSeverity = "info" | "warning" | "critical";
export type MarketSourceType = "marketplace" | "auction" | "fixed_price" | "historical_archive" | "other";
export type MarketSourceImportRunStatus = "pending" | "running" | "cancelled" | "completed";
export type MarketSourceImportRunEventType = "created" | "started" | "cancelled" | "completed";

export interface MarketSourceRead {
  id: number;
  source_name: string;
  source_type: MarketSourceType;
  enabled: boolean;
  import_priority: number;
  supports_raw: boolean;
  supports_graded: boolean;
  supports_variants: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketSaleRecordImageUpsertPayload {
  image_url?: string | null;
  image_sha256?: string | null;
  display_order?: number | null;
}

export interface MarketSaleUpsertPayload {
  market_source_id: number;
  source_listing_id?: string | null;
  source_snapshot_id?: number | null;
  listing_type: MarketSaleListingType;
  raw_title: string;
  raw_issue: string;
  raw_publisher?: string | null;
  raw_variant?: string | null;
  raw_grade?: string | null;
  raw_cert_number?: string | null;
  sale_price?: string | null;
  shipping_price?: string | null;
  total_price?: string | null;
  currency_code: string;
  sale_date?: string | null;
  seller_name?: string | null;
  buyer_name?: string | null;
  is_graded?: boolean;
  grading_company?: MarketSaleGradingCompany | null;
  is_signed?: boolean;
  source_url?: string | null;
  source_metadata_json?: Record<string, unknown>;
  images?: MarketSaleRecordImageUpsertPayload[];
}

export interface MarketSaleRecordImageRead {
  id: number;
  market_sale_record_id: number;
  image_url: string | null;
  image_sha256: string | null;
  display_order: number;
  created_at: string;
}

export interface MarketSaleNormalizationIssueRead {
  id: number;
  market_sale_record_id: number;
  issue_type: MarketSaleIssueType;
  severity: MarketSaleIssueSeverity;
  details_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketSourceSnapshotRead {
  id: number;
  market_source_id: number;
  snapshot_date: string;
  import_status: string;
  total_records: number;
  imported_records: number;
  failed_records: number;
  skipped_records: number;
  source_metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MarketSourceImportRunEventRead {
  id: number;
  import_run_id: number;
  event_type: MarketSourceImportRunEventType;
  previous_status: MarketSourceImportRunStatus | null;
  new_status: MarketSourceImportRunStatus;
  actor_user_id: number | null;
  details_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketSourceImportRunSummaryRead {
  id: number;
  market_source_id: number;
  source_name: string;
  source_type: MarketSourceType;
  created_by_user_id: number | null;
  status: MarketSourceImportRunStatus;
  total_records: number;
  imported_records: number;
  failed_records: number;
  skipped_records: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface MarketSourceImportRunRead extends MarketSourceImportRunSummaryRead {
  events: MarketSourceImportRunEventRead[];
}

export interface MarketSourceImportRunListResponse {
  items: MarketSourceImportRunSummaryRead[];
}

export interface MarketSourceImportRunCreatePayload {
  market_source_id: number;
  notes?: string | null;
}

export interface MarketSaleSummaryRead {
  id: number;
  market_source_id: number;
  source_name: string;
  source_type: MarketSourceType;
  source_listing_id: string | null;
  source_snapshot_id: number | null;
  listing_type: MarketSaleListingType;
  raw_title: string;
  normalized_title: string | null;
  raw_issue: string;
  normalized_issue: string | null;
  sale_price: string | null;
  shipping_price: string | null;
  total_price: string | null;
  currency_code: string;
  sale_date: string | null;
  is_graded: boolean;
  grading_company: MarketSaleGradingCompany | null;
  is_signed: boolean;
  normalization_status: MarketSaleNormalizationStatus;
  normalization_issue_count: number;
  created_at: string;
  updated_at: string;
}

export interface MarketSaleRead extends MarketSaleSummaryRead {
  raw_publisher: string | null;
  normalized_publisher: string | null;
  raw_variant: string | null;
  normalized_variant: string | null;
  raw_grade: string | null;
  normalized_grade: string | null;
  raw_cert_number: string | null;
  normalized_cert_number: string | null;
  seller_name: string | null;
  buyer_name: string | null;
  source_url: string | null;
  source_metadata_json: Record<string, unknown>;
  images: MarketSaleRecordImageRead[];
  normalization_issues: MarketSaleNormalizationIssueRead[];
  review_status: MarketSaleReviewStatus;
  review_actions: MarketSaleReviewActionRead[];
  source_snapshot: MarketSourceSnapshotRead | null;
}

export type MarketSaleReviewStatus = "pending" | "reviewed" | "ignored" | "duplicate_flagged";
export type MarketSaleReviewClassification =
  | "needs_title_review"
  | "needs_issue_review"
  | "needs_variant_review"
  | "needs_grade_review"
  | "needs_price_review"
  | "possible_duplicate"
  | "unsupported_currency"
  | "ready_for_comp_review"
  | "ignored";
export type MarketSaleReviewPriority = "critical" | "high" | "medium" | "low" | "info";
export type MarketSaleReviewActionType =
  | "mark_reviewed"
  | "ignore_record"
  | "flag_duplicate"
  | "manual_normalization_update";

export interface MarketSaleReviewActionRead {
  id: number;
  market_sale_record_id: number;
  action_type: MarketSaleReviewActionType;
  actor_user_id: number | null;
  details_json: Record<string, unknown>;
  before_snapshot_json: Record<string, unknown>;
  after_snapshot_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketSaleReviewQueueItemRead extends MarketSaleSummaryRead {
  review_status: MarketSaleReviewStatus;
  queue_classification: MarketSaleReviewClassification;
  queue_priority: MarketSaleReviewPriority;
  queue_reasons: string[];
  issue_types: MarketSaleIssueType[];
}

export interface MarketSaleReviewQueueResponse {
  items: MarketSaleReviewQueueItemRead[];
  total: number;
}

export interface MarketSaleReviewQueueSummaryRead {
  total: number;
  by_classification: Record<MarketSaleReviewClassification, number>;
  by_priority: Record<MarketSaleReviewPriority, number>;
}

export type MarketCompEligibilityStatus = "eligible" | "ineligible" | "needs_review";
export type MarketCompEligibilityClassification =
  | "eligible_raw_comp"
  | "eligible_graded_comp"
  | "ineligible_missing_price"
  | "ineligible_unsupported_currency"
  | "ineligible_unresolved_identity"
  | "ineligible_duplicate_listing"
  | "ineligible_ignored_record"
  | "ineligible_invalid_grade"
  | "needs_review_before_comp";
export type MarketCompCanonicalMatchState = "approved" | "high_confidence" | "needs_review" | "missing";

export interface MarketSaleCompEligibilitySummaryRead extends MarketSaleSummaryRead {
  review_status: MarketSaleReviewStatus;
  eligibility_status: MarketCompEligibilityStatus;
  eligibility_classification: MarketCompEligibilityClassification;
  eligibility_reasons: string[];
  canonical_match_state: MarketCompCanonicalMatchState;
  canonical_match_suggestion_id: number | null;
  canonical_match_confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket | null;
  canonical_match_review_state: MarketSaleMatchSuggestionReviewState | null;
  canonical_match_deterministic_score: number | null;
  match_suggestion_count: number;
}

export interface MarketSaleCompEligibilityRead extends MarketSaleRead {
  review_status: MarketSaleReviewStatus;
  eligibility_status: MarketCompEligibilityStatus;
  eligibility_classification: MarketCompEligibilityClassification;
  eligibility_reasons: string[];
  canonical_match_state: MarketCompCanonicalMatchState;
  canonical_match_suggestion_id: number | null;
  canonical_match_confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket | null;
  canonical_match_review_state: MarketSaleMatchSuggestionReviewState | null;
  canonical_match_deterministic_score: number | null;
  match_suggestion_count: number;
  eligibility_evidence_json: Record<string, unknown>;
  match_suggestions: MarketSaleMatchSuggestionRead[];
}

export interface MarketSaleCompEligibilityListResponse {
  items: MarketSaleCompEligibilitySummaryRead[];
  total: number;
  by_eligibility_status: Record<MarketCompEligibilityStatus, number>;
  by_eligibility_classification: Record<MarketCompEligibilityClassification, number>;
}

export type MarketComparableScope = "raw" | "graded" | "graded_by_company" | "graded_by_grade";
export type MarketComparableClassification =
  | "included_comp"
  | "excluded_duplicate"
  | "excluded_stale"
  | "excluded_wrong_grade"
  | "excluded_wrong_scope"
  | "excluded_unresolved_identity"
  | "excluded_unsupported_currency"
  | "excluded_missing_price"
  | "excluded_review_required";
export type MarketComparableRecencyBucket = "fresh" | "recent" | "aged" | "stale";
export type MarketComparablePriceSpreadBucket = "tight" | "moderate" | "wide" | "volatile";
export type MarketComparableSourceDiversityBucket = "single_source" | "low" | "medium" | "high";
export type MarketComparableGradeConsistencyBucket = "consistent" | "mixed" | "mismatched";
export type MarketComparableDuplicateRiskBucket = "low" | "medium" | "high";

export interface MarketComparableQualitySignalsRead {
  comp_count: number;
  included_count: number;
  excluded_count: number;
  source_diversity_count: number;
  source_diversity_bucket: MarketComparableSourceDiversityBucket;
  sale_recency_days: number | null;
  sale_recency_bucket: MarketComparableRecencyBucket;
  price_spread: string;
  price_spread_ratio: number;
  price_spread_bucket: MarketComparablePriceSpreadBucket;
  grade_consistency_bucket: MarketComparableGradeConsistencyBucket;
  duplicate_risk_bucket: MarketComparableDuplicateRiskBucket;
  volatility_signal: string;
  stale_data_warning: boolean;
}

export interface MarketComparableSaleRead extends MarketSaleCompEligibilityRead {
  comp_classification: MarketComparableClassification;
  comp_reason: string;
  comp_scope: MarketComparableScope;
  comp_group_key: string;
  comp_group_label: string;
  comp_window_start: string | null;
  comp_window_end: string | null;
  comp_included: boolean;
  comp_group_order: number;
  comp_evidence_json: Record<string, unknown>;
}

export interface MarketComparableGroupRead {
  group_key: string;
  group_label: string;
  metadata_identity_key: string | null;
  canonical_issue_id: number | null;
  comp_scope: MarketComparableScope;
  grading_company: string | null;
  normalized_grade: string | null;
  currency_code: string;
  sale_window_start: string | null;
  sale_window_end: string | null;
  included_count: number;
  excluded_count: number;
  comp_count: number;
  source_names: string[];
  source_types: string[];
  quality_signals: MarketComparableQualitySignalsRead;
  included_comps: MarketComparableSaleRead[];
  excluded_comps: MarketComparableSaleRead[];
}

export interface MarketComparableListResponse {
  items: MarketComparableGroupRead[];
  total_groups: number;
  total_comps: number;
  by_classification: Record<MarketComparableClassification, number>;
  by_scope: Record<MarketComparableScope, number>;
}

export interface MarketComparableSnapshotCompsResponse extends MarketComparableListResponse {
  snapshot: MarketFmvSnapshotSummaryRead;
}

export type MarketFmvSnapshotScope = "raw" | "graded" | "graded_by_company" | "graded_by_grade";
export type MarketFmvValuationMethod = "median_recent_sales" | "weighted_recent_sales";
export type MarketFmvConfidenceBucket = "very_high" | "high" | "medium" | "low" | "very_low";
export type MarketFmvLiquidityBucket = "very_high" | "high" | "medium" | "low" | "very_low";
export type MarketFmvVolatilityBucket = "stable" | "moderate" | "volatile";

export interface MarketFmvCompReferenceRead {
  id: number;
  market_fmv_snapshot_id: number;
  market_sale_record_id: number;
  weighting_factor: number;
  included_reason: string;
  excluded_reason: string | null;
  created_at: string;
  market_sale_record: MarketSaleSummaryRead | null;
}

export interface MarketFmvSnapshotSummaryRead {
  id: number;
  canonical_issue_id: number | null;
  metadata_identity_key: string | null;
  snapshot_scope: MarketFmvSnapshotScope;
  grading_company: string | null;
  normalized_grade: string | null;
  currency_code: string;
  snapshot_date: string;
  comp_count: number;
  valuation_method: MarketFmvValuationMethod;
  estimated_fmv: string;
  confidence_bucket: MarketFmvConfidenceBucket;
  liquidity_bucket: MarketFmvLiquidityBucket;
  volatility_bucket: MarketFmvVolatilityBucket;
  stale_data: boolean;
  created_at: string;
  updated_at: string;
}

export interface MarketFmvSnapshotRead extends MarketFmvSnapshotSummaryRead {
  evidence_json: Record<string, unknown>;
  comp_references: MarketFmvCompReferenceRead[];
}

export interface MarketFmvSnapshotListResponse {
  items: MarketFmvSnapshotSummaryRead[];
  total: number;
  by_confidence_bucket: Record<MarketFmvConfidenceBucket, number>;
  by_liquidity_bucket: Record<MarketFmvLiquidityBucket, number>;
  stale_count: number;
}

export interface MarketFmvGenerateResponse {
  snapshot_count: number;
  snapshots: MarketFmvSnapshotSummaryRead[];
}

export interface MarketFmvListParams {
  snapshot_scope?: MarketFmvSnapshotScope;
  grading_company?: string;
  normalized_grade?: string;
  confidence_bucket?: MarketFmvConfidenceBucket;
  liquidity_bucket?: MarketFmvLiquidityBucket;
  stale_data?: boolean;
  currency?: string;
  snapshot_date_from?: string;
  snapshot_date_to?: string;
}

export type MarketTrendSnapshotScope = MarketFmvSnapshotScope;
export type MarketTrendWindow = "seven_day" | "thirty_day" | "ninety_day" | "one_year";
export type MarketTrendDirection = "rising" | "stable" | "falling" | "volatile";
export type MarketTrendStrength = "very_high" | "high" | "medium" | "low" | "very_low";
export type MarketTrendLiquidityDirection = "improving" | "stable" | "weakening";
export type MarketTrendEvidenceType = "comp_reference" | "fmv_snapshot" | "liquidity_signal" | "volatility_signal";

export interface MarketTrendEvidenceRead {
  id: number;
  market_trend_snapshot_id: number;
  market_sale_record_id: number | null;
  market_fmv_snapshot_id: number | null;
  evidence_type: MarketTrendEvidenceType;
  evidence_json: Record<string, unknown>;
  created_at: string;
  market_sale_record: MarketSaleSummaryRead | null;
  market_fmv_snapshot: MarketFmvSnapshotSummaryRead | null;
}

export interface MarketTrendSnapshotSummaryRead {
  id: number;
  canonical_issue_id: number | null;
  metadata_identity_key: string | null;
  snapshot_scope: MarketTrendSnapshotScope;
  grading_company: string | null;
  normalized_grade: string | null;
  currency_code: string;
  trend_window: MarketTrendWindow;
  trend_direction: MarketTrendDirection;
  trend_strength: MarketTrendStrength;
  liquidity_direction: MarketTrendLiquidityDirection;
  comp_count: number;
  percent_change: string;
  volatility_score: number;
  stale_data: boolean;
  evidence_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MarketTrendSnapshotRead extends MarketTrendSnapshotSummaryRead {
  evidence_items: MarketTrendEvidenceRead[];
}

export interface MarketTrendSnapshotListResponse {
  items: MarketTrendSnapshotSummaryRead[];
  total: number;
  by_trend_direction: Record<MarketTrendDirection, number>;
  by_trend_strength: Record<MarketTrendStrength, number>;
  by_liquidity_direction: Record<MarketTrendLiquidityDirection, number>;
  stale_count: number;
}

export interface MarketTrendGenerateResponse {
  snapshot_count: number;
  snapshots: MarketTrendSnapshotSummaryRead[];
}

export type InventoryValuationScope =
  | "raw"
  | "graded"
  | "preorder_pending"
  | "no_market_data"
  | "low_confidence"
  | "cancelled_excluded";

export interface InventoryFmvAttachmentRead {
  inventory_copy_id: number;
  current_market_fmv: string | null;
  fmv_snapshot_id: number | null;
  fmv_method: MarketFmvValuationMethod | null;
  fmv_confidence_bucket: MarketFmvConfidenceBucket | null;
  fmv_liquidity_bucket: MarketFmvLiquidityBucket | null;
  fmv_volatility_bucket: MarketFmvVolatilityBucket | null;
  fmv_stale_data: boolean | null;
  fmv_currency_code: string | null;
  valuation_scope: InventoryValuationScope;
  valuation_evidence_json: Record<string, unknown>;
  market_fmv_snapshot: MarketFmvSnapshotRead | null;
  market_trend_snapshot: MarketTrendSnapshotSummaryRead | null;
}

export interface PortfolioValueCurrencySummaryRead {
  currency_code: string;
  total_active_market_value: string;
  raw_market_value: string;
  graded_market_value: string;
  preorder_informational_value: string;
  low_confidence_value: string;
  stale_value: string;
  no_market_data_count: number;
  cancelled_excluded_count: number;
  duplicate_group_total_value: string;
  duplicate_extra_copy_value: string;
  duplicate_value_exposure: string;
  duplicate_raw_value: string;
  duplicate_graded_value: string;
}

export interface PortfolioValueSummaryResponse {
  scope: "owner" | "ops";
  scope_user_id: number | null;
  generated_as_of_date: string;
  items: PortfolioValueCurrencySummaryRead[];
}

export type ListingSourceType = "manual" | "ebay_export" | "convention" | "whatnot" | "shopify";
export type ListingStatus = "DRAFT" | "READY" | "ACTIVE" | "SOLD" | "CANCELLED" | "ARCHIVED";
export type ListingLifecycleEventType =
  | "CREATED"
  | "UPDATED"
  | "ACTIVATED"
  | "PRICE_CHANGED"
  | "SOLD"
  | "CANCELLED"
  | "ARCHIVED";

export interface ListingLifecycleEventRead {
  id: number;
  listing_id: number;
  event_type: ListingLifecycleEventType;
  prior_status: string | null;
  new_status: string | null;
  metadata_json: Record<string, unknown>;
  created_by_user_id: number | null;
  replay_key: string | null;
  created_at: string;
}

export interface ListingDashboardSummary {
  draft_count: number;
  active_count: number;
  sold_count: number;
  recent_events: ListingLifecycleEventRead[];
}

export type SaleChannel =
  | "manual"
  | "ebay"
  | "whatnot"
  | "shopify"
  | "hipcomic"
  | "shortboxed"
  | "convention"
  | "private_sale";

export type SaleStatus = "DRAFT" | "RECORDED" | "VOIDED";

export type SaleAdjustmentType =
  | "platform_fee"
  | "payment_fee"
  | "shipping_cost"
  | "tax_collected"
  | "shipping_charged"
  | "discount"
  | "refund"
  | "other";

export type SaleLifecycleEventType = "CREATED" | "RECORDED" | "UPDATED" | "VOIDED" | "FINANCIAL_RECALCULATED";

export interface SaleRecordLineItemRead {
  id: number;
  sale_record_id: number;
  listing_id: number | null;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  quantity_sold: number;
  unit_sale_amount: string;
  line_subtotal_amount: string;
  cost_basis_amount: string | null;
  realized_profit_amount: string | null;
  created_at: string;
}

export interface SaleFinancialAdjustmentRead {
  id: number;
  sale_record_id: number;
  adjustment_type: SaleAdjustmentType;
  amount: string;
  currency: string;
  description: string | null;
  created_at: string;
}

export interface SaleLifecycleEventRead {
  id: number;
  sale_record_id: number;
  event_type: SaleLifecycleEventType;
  prior_status: string | null;
  new_status: string | null;
  metadata_json: Record<string, unknown>;
  created_by_user_id: number | null;
  created_at: string;
}

export interface SaleRecordRead {
  id: number;
  owner_user_id: number;
  listing_id: number | null;
  channel: SaleChannel | string;
  status: SaleStatus | string;
  sale_date: string;
  buyer_reference: string | null;
  currency: string;
  gross_sale_amount: string;
  item_subtotal_amount: string;
  shipping_charged_amount: string;
  tax_collected_amount: string;
  platform_fee_amount: string;
  payment_fee_amount: string;
  shipping_cost_amount: string;
  other_cost_amount: string;
  net_proceeds_amount: string;
  acquisition_cost_basis_amount: string | null;
  realized_profit_amount: string | null;
  realized_margin_pct: string | null;
  replay_key: string | null;
  created_at: string;
  updated_at: string;
  recorded_at: string | null;
  voided_at: string | null;
  event_count: number;
  line_item_count: number;
  adjustment_count: number;
}

export interface SaleRecordDetailRead extends SaleRecordRead {
  line_items: SaleRecordLineItemRead[];
  financial_adjustments: SaleFinancialAdjustmentRead[];
  events: SaleLifecycleEventRead[];
}

export interface SaleRecordListResponse {
  items: SaleRecordRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface SaleLifecycleEventListResponse {
  items: SaleLifecycleEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface SaleFinancialAdjustmentListResponse {
  items: SaleFinancialAdjustmentRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface SaleChannelCountRow {
  channel: SaleChannel | string;
  count: number;
}

export interface SalesDashboardSummary {
  completed_sale_count: number;
  gross_sales_total: string;
  net_proceeds_total: string;
  realized_profit_total: string;
  recent_sales: SaleRecordRead[];
  sales_count_by_channel: SaleChannelCountRow[];
}

export type DealerDashboardAlertType =
  | "STALE_LISTING"
  | "EXPORT_FAILURE"
  | "LOW_COMPLETENESS"
  | "LOW_LIQUIDITY"
  | "CONVENTION_PRICING_MISSING"
  | "MISSING_PRIMARY_IMAGE";
export type DealerDashboardAlertSeverity = "info" | "warning" | "critical";
export type DealerDashboardFeedEventType =
  | "LISTING_CREATED"
  | "LISTING_SOLD"
  | "EXPORT_COMPLETED"
  | "EXPORT_FAILED"
  | "SALE_RECORDED"
  | "STALE_DETECTED"
  | "CONVENTION_ASSIGNED"
  | "LIQUIDITY_UPDATED";

export interface DealerDashboardGeneratePayload {
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface DealerDashboardSnapshotRead {
  id: number;
  owner_user_id: number;
  replay_key?: string | null;
  active_listing_count: number;
  export_ready_count: number;
  incomplete_listing_count: number;
  stale_listing_count: number;
  active_convention_count: number;
  assigned_convention_inventory_count: number;
  open_sale_session_count: number;
  gross_sales_30d: string;
  net_sales_30d: string;
  realized_profit_30d: string;
  liquidity_high_count: number;
  liquidity_low_count: number;
  export_run_count_30d: number;
  failed_export_count_30d: number;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface DealerDashboardGetResponse {
  snapshot: DealerDashboardSnapshotRead | null;
}

export interface DealerDashboardGenerateResponse {
  snapshot: DealerDashboardSnapshotRead;
}

export interface DealerDashboardAlertRead {
  id: number;
  owner_user_id: number;
  dashboard_snapshot_id: number;
  alert_type: DealerDashboardAlertType | string;
  severity: DealerDashboardAlertSeverity | string;
  alert_replay_key: string;
  source_listing_id?: number | null;
  source_inventory_item_id?: number | null;
  source_export_run_id?: number | null;
  source_convention_event_id?: number | null;
  message: string;
  acknowledged_at?: string | null;
  created_at: string;
}

export interface DealerDashboardFeedEventRead {
  id: number;
  owner_user_id: number;
  deterministic_key: string;
  dashboard_snapshot_id?: number | null;
  event_type: DealerDashboardFeedEventType | string;
  source_id?: number | null;
  summary: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface DealerDashboardMetricRead {
  id: number;
  dashboard_snapshot_id: number;
  metric_key: string;
  metric_value_decimal?: string | null;
  metric_value_text?: string | null;
  metric_metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface DealerDashboardAlertListResponse {
  items: DealerDashboardAlertRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface DealerDashboardFeedListResponse {
  items: DealerDashboardFeedEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface DealerDashboardMetricListResponse {
  items: DealerDashboardMetricRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export type DealerGradingDashboardAlertType =
  | "NEGATIVE_ROI"
  | "HIGH_RISK"
  | "LOW_CONFIDENCE"
  | "SUBMISSION_DELAY"
  | "RECONCILIATION_FAILURE"
  | "WEAK_LIQUIDITY"
  | "MISSING_EVIDENCE";
export type DealerGradingDashboardSeverity = "info" | "warning" | "critical";
export type DealerGradingDashboardFeedEventType =
  | "CANDIDATE_CREATED"
  | "RECOMMENDATION_GENERATED"
  | "SUBMISSION_BATCH_CREATED"
  | "SUBMISSION_SHIPPED"
  | "GRADES_RETURNED"
  | "RECONCILIATION_COMPLETED"
  | "HIGH_RISK_DETECTED"
  | "ELITE_OPPORTUNITY_DETECTED";

export interface DealerGradingDashboardGeneratePayload {
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface DealerGradingDashboardSnapshotRead {
  id: number;
  owner_user_id: number;
  replay_key?: string | null;
  active_candidate_count: number;
  ready_for_submission_count: number;
  submitted_candidate_count: number;
  graded_candidate_count: number;
  elite_recommendation_count: number;
  high_risk_candidate_count: number;
  low_confidence_candidate_count: number;
  average_estimated_roi?: string | null;
  average_risk_adjusted_roi?: string | null;
  active_submission_batch_count: number;
  grading_pipeline_value?: string | null;
  estimated_total_submission_cost?: string | null;
  expected_total_profit?: string | null;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface DealerGradingDashboardGetResponse {
  snapshot: DealerGradingDashboardSnapshotRead | null;
}

export interface DealerGradingDashboardGenerateResponse {
  snapshot: DealerGradingDashboardSnapshotRead;
}

export interface DealerGradingDashboardMetricRead {
  id: number;
  dashboard_snapshot_id: number;
  metric_key: string;
  metric_value_decimal?: string | null;
  metric_value_text?: string | null;
  metric_metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface DealerGradingDashboardAlertRead {
  id: number;
  owner_user_id: number;
  dashboard_snapshot_id: number;
  alert_type: DealerGradingDashboardAlertType | string;
  severity: DealerGradingDashboardSeverity | string;
  source_candidate_id?: number | null;
  source_submission_batch_id?: number | null;
  source_recommendation_id?: number | null;
  message: string;
  acknowledged_at?: string | null;
  created_at: string;
}

export interface DealerGradingDashboardFeedEventRead {
  id: number;
  owner_user_id: number;
  dashboard_snapshot_id?: number | null;
  event_type: DealerGradingDashboardFeedEventType | string;
  source_id?: number | null;
  summary: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface DealerGradingDashboardMetricListResponse {
  items: DealerGradingDashboardMetricRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface DealerGradingDashboardAlertListResponse {
  items: DealerGradingDashboardAlertRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface DealerGradingDashboardFeedListResponse {
  items: DealerGradingDashboardFeedEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export type PortfolioStrategyDashboardAlertType =
  | "OVEREXPOSURE"
  | "DEAD_CAPITAL"
  | "DUPLICATE_RISK"
  | "LIQUIDITY_IMBALANCE"
  | "CONCENTRATION_CRITICAL"
  | "WEAK_DIVERSIFICATION"
  | "HIGH_RISK_HOLDING"
  | "ACQUISITION_GAP";
export type PortfolioStrategyDashboardSeverity = "info" | "warning" | "critical";
export type PortfolioStrategyDashboardFeedEventType =
  | "PORTFOLIO_CREATED"
  | "EXPOSURE_GENERATED"
  | "DUPLICATE_CLUSTER_CREATED"
  | "HOLD_RECOMMENDATION_CREATED"
  | "SELL_RECOMMENDATION_CREATED"
  | "CONCENTRATION_ALERT"
  | "ACQUISITION_OPPORTUNITY"
  | "LIQUIDITY_WARNING";

export interface PortfolioStrategyDashboardGeneratePayload {
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface PortfolioStrategyDashboardSnapshotRead {
  id: number;
  owner_user_id: number;
  replay_key?: string | null;
  portfolio_count: number;
  total_portfolio_value?: string | null;
  total_cost_basis?: string | null;
  total_realized_sales?: string | null;
  diversification_score?: string | null;
  liquidity_efficiency_score?: string | null;
  concentration_risk_score?: string | null;
  dead_capital_estimate?: string | null;
  duplicate_cluster_count: number;
  overexposed_category_count: number;
  hold_recommendation_count: number;
  sell_recommendation_count: number;
  reduce_exposure_count: number;
  acquisition_opportunity_count: number;
  elite_acquisition_count: number;
  grading_candidate_count: number;
  liquid_inventory_percentage?: string | null;
  illiquid_inventory_percentage?: string | null;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioStrategyDashboardMetricRead {
  id: number;
  dashboard_snapshot_id: number;
  metric_key: string;
  metric_value_decimal?: string | null;
  metric_value_text?: string | null;
  metric_metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface PortfolioStrategyDashboardAlertRead {
  id: number;
  owner_user_id: number;
  alert_type: PortfolioStrategyDashboardAlertType | string;
  severity: PortfolioStrategyDashboardSeverity | string;
  alert_replay_key: string;
  source_portfolio_id?: number | null;
  source_inventory_item_id?: number | null;
  source_snapshot_id?: number | null;
  message: string;
  acknowledged_at?: string | null;
  created_at: string;
}

export interface PortfolioStrategyDashboardFeedEventRead {
  id: number;
  owner_user_id: number;
  deterministic_key: string;
  dashboard_snapshot_id?: number | null;
  event_type: PortfolioStrategyDashboardFeedEventType | string;
  source_id?: number | null;
  summary: string;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface PortfolioStrategyDashboardGetResponse {
  snapshot: PortfolioStrategyDashboardSnapshotRead | null;
}

export interface PortfolioStrategyDashboardGenerateResponse {
  snapshot: PortfolioStrategyDashboardSnapshotRead;
}

export interface PortfolioStrategyDashboardMetricListResponse {
  items: PortfolioStrategyDashboardMetricRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface PortfolioStrategyDashboardAlertListResponse {
  items: PortfolioStrategyDashboardAlertRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface PortfolioStrategyDashboardFeedListResponse {
  items: PortfolioStrategyDashboardFeedEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export type MarketAcquisitionExternalSourceType =
  | "manual_input"
  | "csv_import"
  | "api_feed"
  | "auction_snapshot"
  | "curated_feed";
export type MarketAcquisitionIngestionStatus = "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
export type MarketAcquisitionRawProcessingStatus = "PENDING" | "NORMALIZED" | "FAILED";
export type MarketAcquisitionIngestionEventType =
  | "BATCH_CREATED"
  | "RECORD_PARSED"
  | "RECORD_NORMALIZED"
  | "RECORD_REJECTED"
  | "BATCH_COMPLETED";

export interface MarketAcquisitionIngestionBatchCreatePayload {
  batch_source_type: MarketAcquisitionExternalSourceType;
  batch_file_name?: string | null;
  records: Record<string, unknown>[];
}

export interface MarketAcquisitionRawSourceRead {
  id: number;
  ingestion_batch_id: number;
  raw_record_json: Record<string, unknown>;
  raw_hash: string;
  processing_status: MarketAcquisitionRawProcessingStatus | string;
  error_message?: string | null;
  created_at: string;
}

export interface MarketAcquisitionIngestionEventRead {
  id: number;
  ingestion_batch_id: number;
  event_type: MarketAcquisitionIngestionEventType | string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketAcquisitionIngestionBatchSummaryRead {
  id: number;
  owner_user_id?: number | null;
  batch_source_type: MarketAcquisitionExternalSourceType | string;
  batch_file_name?: string | null;
  batch_checksum: string;
  total_records: number;
  successful_records: number;
  failed_records: number;
  ingestion_status: MarketAcquisitionIngestionStatus | string;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface MarketAcquisitionIngestionBatchRead extends MarketAcquisitionIngestionBatchSummaryRead {
  events: MarketAcquisitionIngestionEventRead[];
}

export interface MarketAcquisitionIngestionBatchListResponse {
  items: MarketAcquisitionIngestionBatchSummaryRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  last_ingestion_at?: string | null;
}

export interface MarketAcquisitionRawSourceListResponse {
  items: MarketAcquisitionRawSourceRead[];
  pagination: MarketApiV1Pagination;
}

export type MarketNormalizationRunStatus = "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
export type MarketNormalizationCandidateStatus = "SUCCESS" | "PARTIAL" | "FAILED";
export type MarketNormalizationConditionBand = "UNKNOWN" | "POOR" | "GOOD" | "VERY_GOOD" | "FINE" | "VF" | "NM";

export interface MarketNormalizationRunSummaryRead {
  id: number;
  ingestion_batch_id: number;
  owner_user_id?: number | null;
  run_status: MarketNormalizationRunStatus | string;
  total_records: number;
  successful_records: number;
  partial_records: number;
  failed_records: number;
  run_checksum: string;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface MarketNormalizationEventRead {
  id: number;
  normalization_run_id: number;
  event_type: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketNormalizationRunDetailRead extends MarketNormalizationRunSummaryRead {
  events: MarketNormalizationEventRead[];
}

export interface MarketNormalizationHealthRead {
  candidate_status_counts: Record<string, number>;
  issue_type_counts: Record<string, number>;
  normalization_flag_counts: Record<string, number>;
  canonical_full_success_rate_pct?: string | null;
  last_normalization_completed_at?: string | null;
}

export interface MarketNormalizationRunListResponse {
  items: MarketNormalizationRunSummaryRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  health: MarketNormalizationHealthRead;
}

export interface MarketAcquisitionNormalizedCandidateRead {
  id: number;
  ingestion_candidate_id: number;
  normalization_run_id: number;
  owner_user_id?: number | null;
  canonical_title: string;
  canonical_publisher?: string | null;
  canonical_issue_number?: string | null;
  canonical_variant?: string | null;
  normalized_condition_band: MarketNormalizationConditionBand | string;
  normalized_price?: string | null;
  normalized_currency?: string | null;
  normalized_fmv_estimate?: string | null;
  normalized_liquidity_hint?: string | null;
  normalized_grade_potential?: string | null;
  canonical_key: string;
  normalization_flags_json?: Record<string, unknown> | null;
  normalization_status: MarketNormalizationCandidateStatus | string;
  created_at: string;
  updated_at: string;
}

export interface MarketNormalizationIssueRead {
  id: number;
  normalization_run_id: number;
  ingestion_candidate_id: number;
  issue_type: string;
  severity: string;
  issue_detail_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface MarketAcquisitionNormalizedCandidateListResponse {
  items: MarketAcquisitionNormalizedCandidateRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketNormalizationIssueListResponse {
  items: MarketNormalizationIssueRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketNormalizationRunCreatePayload {
  ingestion_batch_id: number;
}

export type MarketAcquisitionRecommendationLabel = "IGNORE" | "WATCH" | "BUY" | "STRONG_BUY";
export type MarketAcquisitionConfidenceLevel = "LOW" | "MEDIUM" | "HIGH";
export type MarketAcquisitionRiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface MarketAcquisitionScoreSnapshotRead {
  id: number;
  owner_user_id: number;
  total_candidates_scored: number;
  avg_score?: string | null;
  avg_liquidity_score?: string | null;
  avg_grading_upside_score?: string | null;
  high_value_count: number;
  strong_buy_count: number;
  buy_count: number;
  watch_count: number;
  ignore_count: number;
  portfolio_alignment_score?: string | null;
  liquidity_alignment_score?: string | null;
  diversification_alignment_score?: string | null;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionScoreRead {
  id: number;
  market_acquisition_score_snapshot_id: number;
  normalized_candidate_id: number;
  canonical_comic_issue_id?: number | null;
  owner_user_id?: number | null;
  acquisition_score?: string | null;
  portfolio_fit_score?: string | null;
  liquidity_score?: string | null;
  grading_upside_score?: string | null;
  concentration_reduction_score?: string | null;
  diversification_score?: string | null;
  risk_penalty_score?: string | null;
  final_rank_score?: string | null;
  score_breakdown_json: Record<string, unknown>;
  recommendation_label: MarketAcquisitionRecommendationLabel | string;
  confidence_level: MarketAcquisitionConfidenceLevel | string;
  risk_level: MarketAcquisitionRiskLevel | string;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionScoreEvidenceRead {
  id: number;
  score_id: number;
  evidence_type: string;
  source_id?: number | null;
  source_table?: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketAcquisitionScoreHistoryRead {
  id: number;
  owner_user_id: number;
  normalized_candidate_id: number;
  acquisition_score?: string | null;
  recommendation_label: MarketAcquisitionRecommendationLabel | string;
  confidence_level: MarketAcquisitionConfidenceLevel | string;
  risk_level: MarketAcquisitionRiskLevel | string;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionScoreDetailRead {
  score: MarketAcquisitionScoreRead;
  evidence: MarketAcquisitionScoreEvidenceRead[];
}

export interface MarketAcquisitionScoreRunPayload {
  snapshot_date?: string | null;
}

export interface MarketAcquisitionScoreRunResponse {
  replayed: boolean;
  snapshot: MarketAcquisitionScoreSnapshotRead;
  total_scores: number;
}

export interface MarketAcquisitionScoreListResponse {
  items: MarketAcquisitionScoreRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionScoreSnapshotListResponse {
  items: MarketAcquisitionScoreSnapshotRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionScoreHistoryListResponse {
  items: MarketAcquisitionScoreHistoryRead[];
  pagination: MarketApiV1Pagination;
}

export interface InventoryMarketAcquisitionScoreTeaser {
  normalized_candidate_id: number;
  final_rank_score?: string | null;
  recommendation_label: string;
  confidence_level: string;
  risk_level: string;
  liquidity_score?: string | null;
  grading_upside_score?: string | null;
  snapshot_date: string;
}

export type MarketAcquisitionSignalType =
  | "VALUE_DISLOCATION"
  | "LIQUIDITY_OPPORTUNITY"
  | "PORTFOLIO_GAP_FILL"
  | "CONCENTRATION_REDUCTION"
  | "GRADING_UPSIDE"
  | "REDUNDANT_ASSET"
  | "HIGH_RISK_ASSET";
export type MarketAcquisitionSignalStrength = "LOW" | "MEDIUM" | "HIGH" | "ELITE";

export interface MarketAcquisitionSignalSnapshotRead {
  id: number;
  market_acquisition_score_snapshot_id: number;
  owner_user_id: number;
  total_signals: number;
  elite_signal_count: number;
  high_signal_count: number;
  medium_signal_count: number;
  low_signal_count: number;
  value_dislocation_count: number;
  liquidity_opportunity_count: number;
  portfolio_gap_fill_count: number;
  concentration_reduction_count: number;
  grading_upside_count: number;
  redundant_asset_count: number;
  high_risk_asset_count: number;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionSignalRead {
  id: number;
  market_acquisition_signal_snapshot_id: number;
  scored_candidate_id: number;
  owner_user_id?: number | null;
  signal_type: MarketAcquisitionSignalType | string;
  signal_strength: MarketAcquisitionSignalStrength | string;
  signal_score?: string | null;
  confidence_level: MarketAcquisitionConfidenceLevel | string;
  risk_level: MarketAcquisitionRiskLevel | string;
  signal_reason_json: Record<string, unknown>;
  supporting_factors_json: Record<string, unknown>;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionSignalEvidenceRead {
  id: number;
  market_acquisition_signal_id: number;
  evidence_type: string;
  source_id?: number | null;
  source_table?: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketAcquisitionSignalHistoryRead {
  id: number;
  owner_user_id: number;
  scored_candidate_id: number;
  signal_type: MarketAcquisitionSignalType | string;
  signal_strength: MarketAcquisitionSignalStrength | string;
  signal_score?: string | null;
  confidence_level: MarketAcquisitionConfidenceLevel | string;
  risk_level: MarketAcquisitionRiskLevel | string;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionSignalDetailRead {
  signal: MarketAcquisitionSignalRead;
  evidence: MarketAcquisitionSignalEvidenceRead[];
}

export interface MarketAcquisitionSignalGeneratePayload {
  score_snapshot_id?: number | null;
  snapshot_date?: string | null;
}

export interface MarketAcquisitionSignalGenerateResponse {
  replayed: boolean;
  snapshot: MarketAcquisitionSignalSnapshotRead;
  total_signals: number;
}

export interface MarketAcquisitionSignalListResponse {
  items: MarketAcquisitionSignalRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionSignalSnapshotListResponse {
  items: MarketAcquisitionSignalSnapshotRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionSignalEvidenceListResponse {
  items: MarketAcquisitionSignalEvidenceRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionSignalHistoryListResponse {
  items: MarketAcquisitionSignalHistoryRead[];
  pagination: MarketApiV1Pagination;
}

export interface InventoryMarketAcquisitionSignalTeaser {
  signal_type: string;
  signal_strength: string;
  signal_score?: string | null;
  confidence_level: string;
  risk_level: string;
  snapshot_date: string;
}

export interface MarketAcquisitionOpportunitySnapshotRead {
  id: number;
  market_acquisition_signal_snapshot_id: number;
  owner_user_id?: number | null;
  opportunity_classification: string;
  total_candidates: number;
  total_signals: number;
  elite_signal_count: number;
  high_signal_count: number;
  medium_signal_count: number;
  low_signal_count: number;
  value_dislocation_count: number;
  liquidity_opportunity_count: number;
  portfolio_gap_fill_count: number;
  concentration_reduction_count: number;
  grading_upside_count: number;
  redundant_asset_count: number;
  high_risk_asset_count: number;
  estimated_portfolio_gap_coverage: string;
  estimated_liquidity_gain: string;
  estimated_diversification_gain: string;
  estimated_risk_adjustment: string;
  avg_signal_strength?: string | null;
  avg_acquisition_score?: string | null;
  avg_confidence_level?: string | null;
  avg_risk_level?: string | null;
  snapshot_checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionOpportunityItemRead {
  id: number;
  market_acquisition_opportunity_snapshot_id: number;
  candidate_id: number;
  market_acquisition_signal_id: number;
  owner_user_id?: number | null;
  signal_type: string;
  signal_strength: string;
  acquisition_score?: string | null;
  confidence_level: string;
  risk_level: string;
  contribution_weight: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionOpportunityEvidenceRead {
  id: number;
  market_acquisition_opportunity_snapshot_id: number;
  evidence_type: string;
  source_id?: number | null;
  source_table?: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketAcquisitionOpportunityHistoryRead {
  id: number;
  owner_user_id?: number | null;
  market_acquisition_opportunity_snapshot_id: number;
  snapshot_checksum: string;
  total_candidates: number;
  elite_signal_count: number;
  high_signal_count: number;
  estimated_portfolio_gap_coverage: string;
  estimated_diversification_gain: string;
  snapshot_date: string;
  created_at: string;
}

export interface MarketAcquisitionOpportunityDetailRead {
  snapshot: MarketAcquisitionOpportunitySnapshotRead;
  items: MarketAcquisitionOpportunityItemRead[];
}

export interface MarketAcquisitionOpportunityGeneratePayload {
  signal_snapshot_id?: number | null;
  snapshot_date?: string | null;
}

export interface MarketAcquisitionOpportunityGenerateResponse {
  replayed: boolean;
  snapshot: MarketAcquisitionOpportunitySnapshotRead;
  total_items: number;
}

export interface MarketAcquisitionOpportunityItemListResponse {
  items: MarketAcquisitionOpportunityItemRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionOpportunitySnapshotListResponse {
  items: MarketAcquisitionOpportunitySnapshotRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionOpportunityEvidenceListResponse {
  items: MarketAcquisitionOpportunityEvidenceRead[];
  pagination: MarketApiV1Pagination;
}

export interface MarketAcquisitionOpportunityHistoryListResponse {
  items: MarketAcquisitionOpportunityHistoryRead[];
  pagination: MarketApiV1Pagination;
}

/** P39-06 portfolio-market coupling (deterministic bridge only). */
export interface PortfolioMarketCouplingSnapshotRead {
  id: number;
  owner_user_id: number;
  market_acquisition_opportunity_snapshot_id: number;
  portfolio_total_value?: string | null;
  portfolio_total_items: number;
  portfolio_diversification_score?: string | null;
  portfolio_concentration_score?: string | null;
  portfolio_liquidity_score?: string | null;
  market_opportunity_count: number;
  aligned_opportunity_count: number;
  misaligned_opportunity_count: number;
  high_fit_market_items: number;
  low_fit_market_items: number;
  portfolio_market_alignment_score?: string | null;
  diversification_gap_alignment_score?: string | null;
  liquidity_gap_alignment_score?: string | null;
  concentration_offset_score?: string | null;
  signal_coverage_ratio?: string | null;
  scoring_coverage_ratio?: string | null;
  normalization_coverage_ratio?: string | null;
  snapshot_checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioMarketCouplingEdgeRead {
  id: number;
  snapshot_id: number;
  market_candidate_id: number;
  market_acquisition_opportunity_item_id: number;
  portfolio_item_id?: number | null;
  coupling_type: string;
  coupling_strength: string;
  coupling_score: number;
  explanation_json: Record<string, unknown>;
  created_at: string;
}

export interface PortfolioMarketCouplingEvidenceRead {
  id: number;
  snapshot_id: number;
  evidence_type: string;
  source_id?: number | null;
  source_table?: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface PortfolioMarketCouplingDetailRead {
  snapshot: PortfolioMarketCouplingSnapshotRead;
  edges: PortfolioMarketCouplingEdgeRead[];
  evidence: PortfolioMarketCouplingEvidenceRead[];
}

export interface PortfolioMarketCouplingGeneratePayload {
  opportunity_snapshot_id?: number | null;
}

export interface PortfolioMarketCouplingGenerateResponse {
  replayed: boolean;
  snapshot: PortfolioMarketCouplingSnapshotRead;
  total_edges: number;
}

export interface PortfolioMarketCouplingSnapshotListResponse {
  items: PortfolioMarketCouplingSnapshotRead[];
  pagination: MarketApiV1Pagination;
}

export interface PortfolioMarketCouplingEdgeListResponse {
  items: PortfolioMarketCouplingEdgeRead[];
  pagination: MarketApiV1Pagination;
}

export interface PortfolioMarketCouplingHistoryRead {
  id: number;
  owner_user_id: number;
  snapshot_id: number;
  snapshot_checksum: string;
  alignment_score?: string | null;
  market_opportunity_count: number;
  high_fit_market_items: number;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioMarketCouplingHistoryListResponse {
  items: PortfolioMarketCouplingHistoryRead[];
  pagination: MarketApiV1Pagination;
}

export interface InventoryPortfolioMarketCouplingTeaserRead {
  coupling_snapshot_id: number;
  portfolio_market_alignment_score?: string | null;
  high_fit_market_items: number;
  concentration_conflicts: number;
  snapshot_date: string;
  snapshot_checksum: string;
}

export interface InventoryMarketAcquisitionOpportunityTeaser {
  opportunity_classification: string;
  signal_strength: string;
  snapshot_date: string;
}

export type OperationalReportType =
  | "listing_summary"
  | "sales_summary"
  | "liquidity_summary"
  | "convention_summary"
  | "export_summary"
  | "dealer_dashboard_summary"
  | "inventory_health_summary";

export interface OperationalReportGenerationParamsPayload {
  sale_date_from?: string | null;
  sale_date_to?: string | null;
}

export interface OperationalReportGeneratePayloadInput {
  report_type: OperationalReportType;
  replay_key?: string | null;
  generation_params?: OperationalReportGenerationParamsPayload;
}

export interface OperationalReportFileRead {
  id: number;
  operational_report_run_id: number;
  file_name: string;
  file_type: string;
  storage_path: string;
  checksum: string;
  row_count: number;
  created_at: string;
}

export interface OperationalReportItemRead {
  id: number;
  operational_report_run_id: number;
  row_number: number;
  lineage_domain: string;
  lineage_key: string;
  lineage_json: Record<string, unknown>;
  row_checksum: string | null;
  created_at: string;
}

export interface OperationalReportRunRead {
  id: number;
  owner_user_id: number;
  report_type: string;
  status: string;
  replay_key: string | null;
  generation_params_json: Record<string, unknown>;
  checksum: string | null;
  csv_row_count: number;
  failure_reason: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface OperationalReportRunDetailRead extends OperationalReportRunRead {
  items: OperationalReportItemRead[];
  files: OperationalReportFileRead[];
}

export interface OperationalReportRunListResponse {
  items: OperationalReportRunRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface OperationalReportingDashboardRollup {
  recent_runs: OperationalReportRunRead[];
  failed_runs: OperationalReportRunRead[];
}

export type GradingOperationalReportType =
  | "grading_candidate_summary"
  | "grading_roi_summary"
  | "grading_submission_summary"
  | "grading_reconciliation_summary"
  | "grading_recommendation_summary"
  | "grading_risk_summary"
  | "grading_dashboard_summary"
  | "grader_performance_summary";

export interface GradingOperationalReportGenerationParamsPayload {}

export interface GradingOperationalReportGeneratePayloadInput {
  report_type: GradingOperationalReportType;
  replay_key?: string | null;
  generation_params?: GradingOperationalReportGenerationParamsPayload;
}

export interface GradingOperationalReportFileRead {
  id: number;
  grading_operational_report_run_id: number;
  file_name: string;
  file_type: string;
  storage_path: string;
  checksum: string;
  row_count: number;
  created_at: string;
}

export interface GradingOperationalReportItemRead {
  id: number;
  grading_operational_report_run_id: number;
  row_number: number;
  lineage_domain: string;
  lineage_key: string;
  lineage_json: Record<string, unknown>;
  row_checksum: string | null;
  created_at: string;
}

export interface GradingOperationalReportRunRead {
  id: number;
  owner_user_id: number;
  report_type: string;
  status: string;
  replay_key: string | null;
  generation_params_json: Record<string, unknown>;
  checksum: string | null;
  csv_row_count: number;
  failure_reason: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface GradingOperationalReportRunDetailRead extends GradingOperationalReportRunRead {
  items: GradingOperationalReportItemRead[];
  files: GradingOperationalReportFileRead[];
}

export interface GradingOperationalReportRunListResponse {
  items: GradingOperationalReportRunRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface InventoryGradingCandidateBadge {
  grading_candidate_id: number;
  status: string;
  target_grader: string;
  candidate_priority: string;
  is_pipeline_active: boolean;
}

export interface InventoryGradingSpreadBadge {
  grading_spread_snapshot_id: number;
  spread_status: string;
  target_grader: string;
  target_grade: string | null;
  estimated_net_upside: string | null;
  liquidity_adjusted_upside: string | null;
  checksum: string;
}

export interface InventoryGradingRoiBadge {
  grading_roi_snapshot_id: number;
  roi_status: string;
  target_grader: string;
  target_grade: string | null;
  estimated_total_cost: string | null;
  estimated_net_profit: string | null;
  liquidity_adjusted_roi: string | null;
  break_even_grade: string | null;
  checksum: string;
}

export interface InventoryGradingSubmissionBadge {
  grading_submission_batch_id: number;
  status: string;
  target_grader: string;
  batch_name: string;
  shipment_state: string | null;
  item_count: number;
}

export interface InventoryGradingReconciliationBadge {
  grading_reconciliation_record_id: number;
  target_grader: string;
  final_grade: string | null;
  roi_delta: string | null;
  grading_accuracy_status: string;
  reconciliation_status: string;
}

export interface InventoryGradingRecommendationBadge {
  grading_recommendation_id: number;
  recommended_action: string;
  recommended_grader: string | null;
  recommended_grade_target: string | null;
  confidence_score: string;
  overall_confidence_level: string | null;
  risk_level: string;
  grading_risk_snapshot_id: number | null;
  overall_risk_level: string | null;
  risk_adjusted_roi: string | null;
  recommendation_strength: string;
  rationale_summary: string;
}

export interface InventoryGradingRiskBadge {
  grading_risk_snapshot_id: number;
  overall_risk_level: string;
  overall_confidence_level: string;
  risk_adjusted_roi: string | null;
  confidence_weight: string | null;
  warning_flags_json: unknown[];
}

export interface GradingReconciliationEvidenceRead {
  id: number;
  grading_reconciliation_record_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface GradingReconciliationHistoryRead {
  id: number;
  owner_user_id: number | null;
  grading_candidate_id: number | null;
  inventory_item_id: number | null;
  target_grader: string;
  expected_grade: string | null;
  actual_grade: string | null;
  realized_roi: string | null;
  roi_delta: string | null;
  snapshot_date: string;
  checksum: string;
  created_at: string;
}

export interface GraderPerformanceSnapshotRead {
  id: number;
  owner_user_id: number | null;
  grader: string;
  submission_count: number;
  above_expectation_count: number;
  met_expectation_count: number;
  below_expectation_count: number;
  average_roi_delta: string | null;
  average_turnaround_days: string | null;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface GradingReconciliationRead {
  id: number;
  owner_user_id: number;
  grading_submission_item_id: number;
  grading_candidate_id: number;
  inventory_item_id: number;
  target_grader: string;
  expected_grade: string | null;
  final_grade: string | null;
  expected_raw_value: string | null;
  expected_graded_value: string | null;
  realized_graded_value: string | null;
  expected_roi: string | null;
  realized_roi: string | null;
  roi_delta: string | null;
  grading_accuracy_status: string;
  reconciliation_status: string;
  confidence_level: string;
  checksum: string;
  reconciled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GradingReconciliationDetailRead {
  record: GradingReconciliationRead;
  evidence: GradingReconciliationEvidenceRead[];
  history: GradingReconciliationHistoryRead[];
}

export interface GradingReconciliationListResponse {
  items: GradingReconciliationRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingReconciliationEvidenceListResponse {
  items: GradingReconciliationEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingReconciliationHistoryListResponse {
  items: GradingReconciliationHistoryRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GraderPerformanceSnapshotListResponse {
  items: GraderPerformanceSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingReconciliationDashboardSummary {
  reconciled_count: number;
  above_expectation_count: number;
  below_expectation_count: number;
  average_roi_delta: string | null;
  grader_performance: GraderPerformanceSnapshotRead[];
}

export interface GradingReconciliationReconcilePayload {
  grading_submission_item_id: number;
  final_grade: string;
  realized_graded_value?: string | null;
  reconciled_at?: string | null;
  confidence_level?: "HIGH" | "MEDIUM" | "LOW" | null;
}

export interface GradingRecommendationEvidenceRead {
  id: number;
  grading_recommendation_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface GradingRecommendationScenarioRead {
  id: number;
  grading_recommendation_id: number;
  scenario_name: string;
  target_grade: string | null;
  estimated_value: string | null;
  estimated_roi: string | null;
  confidence_modifier: string | null;
  created_at: string;
}

export interface GradingRecommendationHistoryRead {
  id: number;
  owner_user_id: number | null;
  grading_candidate_id: number | null;
  inventory_item_id: number | null;
  recommended_action: string;
  recommended_grader: string | null;
  recommendation_strength: string;
  confidence_score: string;
  snapshot_date: string;
  checksum: string;
  created_at: string;
}

export interface GradingRecommendationRead {
  id: number;
  owner_user_id: number;
  grading_candidate_id: number | null;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  recommended_action: string;
  recommended_grader: string | null;
  recommended_grade_target: string | null;
  expected_roi: string | null;
  liquidity_adjusted_roi: string | null;
  estimated_net_profit: string | null;
  estimated_total_cost: string | null;
  confidence_score: string;
  overall_confidence_level: string | null;
  recommendation_strength: string;
  risk_level: string;
  grading_risk_snapshot_id: number | null;
  overall_risk_level: string | null;
  risk_adjusted_roi: string | null;
  confidence_weight: string | null;
  recommendation_status: string;
  rationale_summary: string;
  warning_flags_json: unknown[];
  evidence_count: number;
  checksum: string;
  replay_key: string | null;
  snapshot_date: string;
  created_at: string;
}

export interface GradingRecommendationDetailRead {
  recommendation: GradingRecommendationRead;
  evidence: GradingRecommendationEvidenceRead[];
  scenarios: GradingRecommendationScenarioRead[];
  history: GradingRecommendationHistoryRead[];
}

export interface GradingRecommendationListResponse {
  items: GradingRecommendationRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRecommendationEvidenceListResponse {
  items: GradingRecommendationEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRecommendationHistoryListResponse {
  items: GradingRecommendationHistoryRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRecommendationDashboardSummary {
  grade_recommendation_count: number;
  hold_raw_count: number;
  elite_opportunity_count: number;
  high_risk_count: number;
  average_expected_roi: string | null;
}

export interface GradingRecommendationGeneratePayload {
  grading_candidate_id?: number | null;
  inventory_item_id?: number | null;
  canonical_comic_issue_id?: number | null;
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface GradingRiskEvidenceRead {
  id: number;
  grading_risk_snapshot_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface ConfidenceFactorSnapshotRead {
  id: number;
  grading_risk_snapshot_id: number;
  factor_key: string;
  factor_score: string;
  weighting: string;
  created_at: string;
}

export interface RiskHistoryRead {
  id: number;
  owner_user_id: number | null;
  grading_candidate_id: number | null;
  inventory_item_id: number | null;
  overall_risk_level: string;
  overall_confidence_level: string;
  risk_adjusted_roi: string | null;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface GradingRiskSnapshotRead {
  id: number;
  owner_user_id: number;
  grading_candidate_id: number | null;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  recommendation_id: number | null;
  overall_risk_level: string;
  overall_confidence_level: string;
  liquidity_risk_score: string;
  spread_volatility_score: string;
  roi_volatility_score: string;
  grader_variability_score: string;
  reconciliation_variance_score: string;
  market_stability_score: string;
  evidence_strength_score: string;
  risk_adjusted_roi: string | null;
  confidence_weight: string | null;
  warning_flags_json: unknown[];
  evidence_count: number;
  checksum: string;
  replay_key: string | null;
  snapshot_date: string;
  created_at: string;
}

export interface GradingRiskDetailRead {
  snapshot: GradingRiskSnapshotRead;
  evidence: GradingRiskEvidenceRead[];
  confidence_factors: ConfidenceFactorSnapshotRead[];
  history: RiskHistoryRead[];
}

export interface GradingRiskListResponse {
  items: GradingRiskSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRiskEvidenceListResponse {
  items: GradingRiskEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ConfidenceFactorSnapshotListResponse {
  items: ConfidenceFactorSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface RiskHistoryListResponse {
  items: RiskHistoryRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRiskDashboardSummary {
  low_risk_count: number;
  high_risk_count: number;
  high_confidence_count: number;
  low_confidence_count: number;
  average_risk_adjusted_roi: string | null;
}

export interface GradingRiskGeneratePayload {
  grading_candidate_id?: number | null;
  inventory_item_id?: number | null;
  canonical_comic_issue_id?: number | null;
  recommendation_id?: number | null;
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface GradingSubmissionDashboardSummary {
  active_batch_count: number;
  shipped_batch_count: number;
  grading_batch_count: number;
  completed_batch_count: number;
  average_turnaround_days: string | null;
}

export interface GradingSubmissionCreatePayload {
  grading_candidate_ids: number[];
  target_grader: "PSA" | "CGC" | "CBCS";
  batch_name: string;
  submission_date?: string | null;
  estimated_turnaround_days?: number | null;
  replay_key?: string | null;
  notes?: string | null;
}

export interface GradingSubmissionPatchPayload {
  batch_name?: string | null;
  notes?: string | null;
  estimated_turnaround_days?: number | null;
}

export interface GradingSubmissionShipmentCreatePayload {
  shipment_direction: "OUTBOUND" | "RETURN";
  carrier?: string | null;
  tracking_number?: string | null;
  shipped_date?: string | null;
  delivered_date?: string | null;
  insured_amount?: string | null;
  shipping_cost?: string | null;
  notes?: string | null;
}

export interface GradingSubmissionItemRead {
  id: number;
  grading_submission_batch_id: number;
  grading_candidate_id: number;
  inventory_item_id: number;
  declared_value: string | null;
  estimated_grade: string | null;
  final_grade: string | null;
  submission_fee: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GradingSubmissionShipmentRead {
  id: number;
  grading_submission_batch_id: number;
  shipment_direction: string;
  carrier: string | null;
  tracking_number: string | null;
  shipped_date: string | null;
  delivered_date: string | null;
  insured_amount: string | null;
  shipping_cost: string | null;
  notes: string | null;
  created_at: string;
}

export interface GradingSubmissionLifecycleEventRead {
  id: number;
  grading_submission_batch_id: number;
  event_type: string;
  prior_status: string | null;
  new_status: string | null;
  metadata_json: Record<string, unknown>;
  created_by_user_id: number | null;
  created_at: string;
}

export interface GradingSubmissionCostSnapshotRead {
  id: number;
  grading_submission_batch_id: number;
  estimated_grading_fees: string;
  estimated_shipping_cost: string;
  estimated_insurance_cost: string;
  actual_grading_fees: string | null;
  actual_shipping_cost: string | null;
  actual_insurance_cost: string | null;
  checksum: string;
  created_at: string;
}

export interface GradingSubmissionBatchRead {
  id: number;
  owner_user_id: number;
  target_grader: string;
  batch_name: string;
  status: string;
  submission_date: string | null;
  shipped_date: string | null;
  grader_received_date: string | null;
  grading_started_date: string | null;
  return_shipped_date: string | null;
  completed_date: string | null;
  estimated_turnaround_days: number | null;
  actual_turnaround_days: number | null;
  estimated_total_cost: string | null;
  actual_total_cost: string | null;
  item_count: number;
  replay_key: string | null;
  checksum: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface GradingSubmissionDetailRead {
  batch: GradingSubmissionBatchRead;
  items: GradingSubmissionItemRead[];
  shipments: GradingSubmissionShipmentRead[];
  lifecycle_events: GradingSubmissionLifecycleEventRead[];
  cost_snapshots: GradingSubmissionCostSnapshotRead[];
}

export interface GradingSubmissionListResponse {
  items: GradingSubmissionBatchRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingSubmissionShipmentListResponse {
  items: GradingSubmissionShipmentRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingSubmissionEventListResponse {
  items: GradingSubmissionLifecycleEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingCandidateDashboardSummary {
  total_candidates: number;
  pipeline_active_count: number;
  ready_for_submission_count: number;
  submitted_count: number;
  graded_count: number;
  elite_priority_count: number;
}

export interface GradingCandidateRead {
  id: number;
  owner_user_id: number;
  inventory_item_id: number;
  canonical_comic_issue_id: number | null;
  status: string;
  target_grader: string;
  target_grade: string | null;
  estimated_raw_value: string | null;
  estimated_graded_value: string | null;
  estimated_spread: string | null;
  estimated_grading_cost: string | null;
  estimated_roi: string | null;
  candidate_priority: string;
  rationale: string | null;
  replay_key: string | null;
  evidence_count: number;
  latest_snapshot_checksum: string | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  graded_at: string | null;
  archived_at: string | null;
}

export interface GradingCandidateListResponse {
  items: GradingCandidateRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingSpreadDashboardSummary {
  strong_spread_count: number;
  elite_spread_count: number;
  negative_spread_count: number;
  average_estimated_upside: string | null;
  liquidity_adjusted_upside_total: string | null;
}

export interface GradingSpreadGeneratePayload {
  inventory_item_id?: number | null;
  canonical_comic_issue_id?: number | null;
  target_grader: "PSA" | "CGC" | "CBCS";
  target_grade?: string | null;
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface GradingSpreadEvidenceRead {
  id: number;
  grading_spread_snapshot_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface GradingSpreadHistoryRead {
  id: number;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  target_grader: string;
  target_grade: string | null;
  spread_amount: string | null;
  spread_pct: string | null;
  snapshot_date: string;
  checksum: string;
  created_at: string;
}

export interface GradingSpreadRead {
  id: number;
  owner_user_id: number | null;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  target_grader: string;
  target_grade: string | null;
  raw_fmv_amount: string | null;
  graded_fmv_amount: string | null;
  grading_cost_amount: string | null;
  estimated_spread_amount: string | null;
  estimated_spread_pct: string | null;
  estimated_net_upside: string | null;
  liquidity_adjusted_upside: string | null;
  spread_status: string;
  liquidity_modifier: string;
  confidence_level: string;
  evidence_count: number;
  checksum: string;
  snapshot_date: string;
  replay_key: string | null;
  generation_params_json: Record<string, unknown>;
  created_at: string;
}

export interface GradingSpreadDetailRead {
  snapshot: GradingSpreadRead;
  evidence: GradingSpreadEvidenceRead[];
  history: GradingSpreadHistoryRead[];
}

export interface GradingSpreadListResponse {
  items: GradingSpreadRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingSpreadEvidenceListResponse {
  items: GradingSpreadEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingSpreadHistoryListResponse {
  items: GradingSpreadHistoryRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRoiDashboardSummary {
  strong_roi_count: number;
  elite_roi_count: number;
  negative_roi_count: number;
  average_estimated_roi: string | null;
  liquidity_adjusted_roi_total: string | null;
}

export interface GradingRoiGeneratePayload {
  grading_candidate_id?: number | null;
  inventory_item_id?: number | null;
  canonical_comic_issue_id?: number | null;
  target_grader: "PSA" | "CGC" | "CBCS";
  target_grade?: string | null;
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface GradingRoiEvidenceRead {
  id: number;
  grading_roi_snapshot_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface GradingRoiScenarioRead {
  id: number;
  grading_roi_snapshot_id: number;
  scenario_name: string;
  target_grade: string | null;
  estimated_value: string | null;
  estimated_roi_pct: string | null;
  liquidity_adjusted_roi: string | null;
  created_at: string;
}

export interface GradingRoiHistoryRead {
  id: number;
  owner_user_id: number | null;
  grading_candidate_id: number | null;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  target_grader: string;
  target_grade: string | null;
  roi_pct: string | null;
  liquidity_adjusted_roi: string | null;
  snapshot_date: string;
  checksum: string;
  created_at: string;
}

export interface GradingRoiRead {
  id: number;
  owner_user_id: number | null;
  grading_candidate_id: number | null;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  target_grader: string;
  target_grade: string | null;
  raw_fmv_amount: string | null;
  graded_fmv_amount: string | null;
  grading_fee_amount: string | null;
  shipping_cost_amount: string | null;
  insurance_cost_amount: string | null;
  estimated_turnaround_days: number | null;
  estimated_total_cost: string | null;
  estimated_spread_amount: string | null;
  estimated_net_profit: string | null;
  estimated_roi_pct: string | null;
  liquidity_adjusted_roi: string | null;
  break_even_grade: string | null;
  roi_status: string;
  confidence_level: string;
  evidence_count: number;
  checksum: string;
  snapshot_date: string;
  replay_key: string | null;
  generation_params_json: Record<string, unknown>;
  created_at: string;
}

export interface GradingRoiDetailRead {
  snapshot: GradingRoiRead;
  evidence: GradingRoiEvidenceRead[];
  scenarios: GradingRoiScenarioRead[];
  history: GradingRoiHistoryRead[];
}

export interface GradingRoiListResponse {
  items: GradingRoiRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRoiEvidenceListResponse {
  items: GradingRoiEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface GradingRoiHistoryListResponse {
  items: GradingRoiHistoryRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export type LiquidityStatus = "HIGH" | "MODERATE" | "LOW" | "ILLIQUID" | "INSUFFICIENT_DATA";
export type LiquidityConfidence = "HIGH" | "MEDIUM" | "LOW";
export type LiquidityEvidenceType = "SALE" | "ACTIVE_LISTING" | "FAILED_LISTING" | "RELIST" | "STALE";
export type ListingStalenessEventType = "STALE_WARNING" | "STALE_CONFIRMED" | "LONG_RUNNING";

export interface InventoryLiquiditySnapshotRead {
  id: number;
  owner_user_id: number;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  channel: string | null;
  liquidity_status: LiquidityStatus | string;
  days_on_market_median: string | null;
  days_to_sale_median: string | null;
  sell_through_rate_pct: string;
  stale_listing_rate_pct: string;
  relist_rate_pct: string;
  successful_sale_count: number;
  failed_listing_count: number;
  active_listing_count: number;
  liquidity_confidence: LiquidityConfidence | string;
  evaluation_window_days: number;
  snapshot_date: string;
  checksum: string;
  evidence_count: number;
  created_at: string;
}

export interface InventoryLiquidityEvidenceRead {
  id: number;
  liquidity_snapshot_id: number;
  evidence_type: LiquidityEvidenceType | string;
  source_listing_id: number | null;
  source_sale_id: number | null;
  source_export_run_id: number | null;
  days_on_market: string | null;
  evidence_json: Record<string, unknown>;
  created_at: string;
}

export interface ListingVelocitySnapshotRead {
  id: number;
  listing_id: number;
  owner_user_id: number;
  first_activated_at: string | null;
  sold_at: string | null;
  days_active: string | null;
  relist_count: number;
  price_change_count: number;
  final_status: string;
  snapshot_date: string;
  created_at: string;
}

export interface ListingStalenessEventRead {
  id: number;
  listing_id: number;
  owner_user_id: number;
  event_type: ListingStalenessEventType | string;
  threshold_days: number;
  days_active: string;
  created_at: string;
}

export interface InventoryLiquidityListResponse {
  items: InventoryLiquiditySnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface InventoryLiquidityEvidenceListResponse {
  items: InventoryLiquidityEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ListingVelocityListResponse {
  items: ListingVelocitySnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ListingStalenessEventListResponse {
  items: ListingStalenessEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface LiquidityDashboardSummary {
  high_liquidity_count: number;
  stale_inventory_count: number;
  recent_stale_events: ListingStalenessEventRead[];
  median_days_to_sale: string | null;
  sell_through_pct: string;
  recent_snapshots: InventoryLiquiditySnapshotRead[];
}

export type ListingIntelligenceStatus = "STRONG" | "ADEQUATE" | "WEAK" | "INCOMPLETE" | "INSUFFICIENT_DATA";
export type ListingCompletenessStatus = "PASS" | "WARNING" | "FAIL";
export type ListingCompletenessSeverity = "info" | "warning" | "critical";
export type ListingIntelligenceEvidenceType =
  | "LISTING_FIELD"
  | "IMAGE"
  | "PRICE"
  | "EXPORT_RUN"
  | "SALE"
  | "LIQUIDITY"
  | "CONVENTION";

export interface ListingIntelligenceGeneratePayload {
  snapshot_date?: string | null;
  listing_id?: number | null;
  inventory_item_id?: number | null;
  canonical_comic_issue_id?: number | null;
  channel?: string | null;
  replay_key?: string | null;
}

export interface ListingIntelligenceSnapshotRead {
  id: number;
  owner_user_id: number;
  listing_id: number;
  inventory_item_id: number | null;
  canonical_comic_issue_id: number | null;
  channel: string | null;
  replay_key: string | null;
  intelligence_status: ListingIntelligenceStatus | string;
  completeness_score: string;
  image_score: string;
  title_score: string;
  description_score: string;
  pricing_score: string;
  export_readiness_score: string;
  sale_outcome_score: string | null;
  stale_risk_flag: boolean;
  missing_required_fields_json: unknown[];
  warning_flags_json: unknown[];
  evidence_count: number;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface ListingIntelligenceEvidenceRead {
  id: number;
  intelligence_snapshot_id: number;
  evidence_type: ListingIntelligenceEvidenceType | string;
  source_listing_id: number | null;
  source_export_run_id: number | null;
  source_sale_id: number | null;
  source_liquidity_snapshot_id: number | null;
  source_convention_event_id: number | null;
  evidence_key: string;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface ListingCompletenessCheckRead {
  id: number;
  intelligence_snapshot_id: number;
  owner_user_id: number;
  listing_id: number;
  replay_key: string | null;
  status: ListingCompletenessStatus | string;
  check_key:
    | "title_present"
    | "description_present"
    | "condition_present"
    | "price_present"
    | "currency_present"
    | "image_present"
    | "primary_image_present"
    | "inventory_link_present"
    | "exportable_status"
    | string;
  message: string;
  severity: ListingCompletenessSeverity | string;
  snapshot_date: string;
  created_at: string;
}

export interface ListingChannelPerformanceSnapshotRead {
  id: number;
  owner_user_id: number;
  channel: string;
  replay_key: string | null;
  total_listings: number;
  active_listings: number;
  sold_listings: number;
  cancelled_listings: number;
  exported_count: number;
  sales_count: number;
  gross_sales_amount: string;
  net_proceeds_amount: string;
  median_days_to_sale: string | null;
  stale_listing_count: number;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface ListingIntelligenceDashboardSummary {
  strong_listing_count: number;
  incomplete_listing_count: number;
  average_completeness_score: string | null;
  export_ready_count: number;
  stale_risk_count: number;
  recent_weak_or_incomplete: ListingIntelligenceSnapshotRead[];
}

export interface ListingIntelligenceGenerateResponse {
  generated_snapshot_count: number;
  generated_evidence_count: number;
  generated_check_count: number;
  generated_channel_performance_count: number;
  checksum: string;
  snapshot_date: string;
  replay_key: string | null;
}

export interface ListingIntelligenceSnapshotListResponse {
  items: ListingIntelligenceSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ListingIntelligenceEvidenceListResponse {
  items: ListingIntelligenceEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ListingCompletenessCheckListResponse {
  items: ListingCompletenessCheckRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ListingChannelPerformanceListResponse {
  items: ListingChannelPerformanceSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export type ConventionEventType = "convention" | "local_show" | "trade_night" | "private_event" | "popup";
export type ConventionEventStatus = "PLANNED" | "ACTIVE" | "COMPLETED" | "CANCELLED";
export type ConventionAssignmentType = "wall" | "showcase" | "bin" | "featured" | "reserve";
export type ConventionMovementType = "ASSIGNED" | "MOVED" | "REMOVED" | "SOLD" | "RETURNED" | "HOLD";
export type ConventionPricingSource = "default_inventory" | "convention_override" | "negotiated";
export type ConventionSaleSessionStatus = "OPEN" | "CLOSED";

export interface ConventionReplayBody {
  replay_key?: string | null;
}

export interface ConventionEventCreatePayload {
  name: string;
  venue?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  start_date: string;
  end_date: string;
  event_type: ConventionEventType;
  notes?: string | null;
  replay_key?: string | null;
}

export interface ConventionEventPatchPayload {
  name?: string | null;
  venue?: string | null;
  city?: string | null;
  state?: string | null;
  country?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  event_type?: ConventionEventType | null;
  notes?: string | null;
  replay_key?: string | null;
}

export interface ConventionEventRead {
  id: number;
  owner_user_id: number;
  replay_key: string | null;
  name: string;
  venue: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  start_date: string;
  end_date: string;
  event_type: ConventionEventType | string;
  status: ConventionEventStatus | string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  activated_at: string | null;
  completed_at: string | null;
}

export interface ConventionAssignmentCreatePayload {
  convention_event_id: number;
  inventory_item_id: number;
  assignment_type: ConventionAssignmentType;
  local_price_amount?: string | null;
  local_price_currency?: string | null;
  display_location?: string | null;
  priority_rank?: number | null;
  replay_key?: string | null;
}

export interface ConventionAssignmentRead {
  id: number;
  convention_event_id: number;
  inventory_item_id: number;
  replay_key: string | null;
  assignment_type: ConventionAssignmentType | string;
  local_price_amount: string | null;
  local_price_currency: string | null;
  display_location: string | null;
  priority_rank: number | null;
  assigned_at: string;
  removed_at: string | null;
  created_at: string;
}

export interface ConventionMovementCreatePayload {
  convention_event_id: number;
  inventory_item_id: number;
  movement_type: ConventionMovementType;
  from_location?: string | null;
  to_location?: string | null;
  notes?: string | null;
  replay_key?: string | null;
}

export interface ConventionMovementRead {
  id: number;
  convention_event_id: number;
  inventory_item_id: number;
  replay_key: string | null;
  movement_type: ConventionMovementType | string;
  from_location: string | null;
  to_location: string | null;
  notes: string | null;
  created_by_user_id: number;
  created_at: string;
}

export interface ConventionPriceSnapshotCreatePayload {
  convention_event_id: number;
  inventory_item_id: number;
  price_amount: string;
  currency: string;
  pricing_source: ConventionPricingSource;
  replay_key?: string | null;
}

export interface ConventionPriceSnapshotRead {
  id: number;
  convention_event_id: number;
  inventory_item_id: number;
  replay_key: string | null;
  price_amount: string;
  currency: string;
  pricing_source: ConventionPricingSource | string;
  created_at: string;
}

export interface ConventionSaleSessionCreatePayload {
  convention_event_id: number;
  notes?: string | null;
  replay_key?: string | null;
}

export interface ConventionSaleSessionRead {
  id: number;
  convention_event_id: number;
  owner_user_id: number;
  replay_key: string | null;
  status: ConventionSaleSessionStatus | string;
  opened_at: string;
  closed_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface ConventionDashboardSummary {
  active_convention_count: number;
  assigned_inventory_count: number;
  wall_book_count: number;
  showcase_count: number;
  active_sale_session_count: number;
  recent_events: ConventionEventRead[];
}

export interface ConventionEventListResponse {
  items: ConventionEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ConventionAssignmentListResponse {
  items: ConventionAssignmentRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ConventionMovementListResponse {
  items: ConventionMovementRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ConventionPriceSnapshotListResponse {
  items: ConventionPriceSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ConventionSaleSessionListResponse {
  items: ConventionSaleSessionRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface SaleRecordLineItemCreatePayload {
  listing_id?: number | null;
  inventory_item_id?: number | null;
  canonical_comic_issue_id?: number | null;
  quantity_sold: number;
  unit_sale_amount: string;
  line_subtotal_amount?: string | null;
  cost_basis_amount?: string | null;
}

export interface SaleFinancialAdjustmentCreatePayload {
  adjustment_type: SaleAdjustmentType;
  amount: string;
  currency: string;
  description?: string | null;
}

export interface SaleRecordCreatePayload {
  listing_id?: number | null;
  channel: SaleChannel | string;
  sale_date: string;
  currency: string;
  buyer_reference?: string | null;
  line_items: SaleRecordLineItemCreatePayload[];
  financial_adjustments?: SaleFinancialAdjustmentCreatePayload[];
  replay_key?: string | null;
}

export interface SaleRecordPatchPayload {
  listing_id?: number | null;
  channel?: SaleChannel | string | null;
  sale_date?: string | null;
  currency?: string | null;
  buyer_reference?: string | null;
}

export type ListingExportChannel =
  | "ebay"
  | "whatnot"
  | "shopify"
  | "hipcomic"
  | "shortboxed"
  | "generic_csv";

export interface ListingExportRunRead {
  id: number;
  owner_user_id: number;
  template_id: number;
  channel: ListingExportChannel | string;
  status: string;
  requested_listing_count: number;
  exported_listing_count: number;
  skipped_listing_count: number;
  error_count: number;
  replay_key: string | null;
  checksum: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface ListingExportDashboardSummary {
  completed_run_count: number;
  skipped_rows_lifetime_sum: number;
  latest_completed_checksum: string | null;
  recent_runs: ListingExportRunRead[];
}

export interface ListingExportRunListResponse {
  items: ListingExportRunRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ListingExportRunItemRead {
  id: number;
  export_run_id: number;
  listing_id: number | null;
  status: string;
  skip_reason: string | null;
  error_message: string | null;
  row_number: number;
  row_checksum: string | null;
  created_at: string;
}

export interface ListingExportFileRead {
  id: number;
  export_run_id: number;
  file_name: string;
  file_type: string;
  storage_path: string;
  checksum: string;
  row_count: number;
  created_at: string;
}

export interface ListingExportRunDetailRead extends ListingExportRunRead {
  items: ListingExportRunItemRead[];
  files: ListingExportFileRead[];
}

export interface ListingExportRunCreatePayload {
  template_id?: number | null;
  channel?: ListingExportChannel | string | null;
  listing_ids: number[];
  replay_key?: string | null;
}

export interface ListingRead {
  id: number;
  owner_user_id: number;
  replay_key: string | null;
  canonical_comic_issue_id: number | null;
  inventory_copy_id: number;
  source_type: ListingSourceType;
  status: ListingStatus;
  title: string;
  description: string | null;
  condition_summary: string | null;
  asking_price_amount: string | null;
  asking_price_currency: string | null;
  quantity: number;
  created_at: string;
  updated_at: string;
  activated_at: string | null;
  sold_at: string | null;
  archived_at: string | null;
}

export interface ListingListResponse {
  items: ListingRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface ListingReplayBodyPayload {
  replay_key?: string | null;
}

export interface ListingOpsStatusCountRow {
  status: ListingStatus;
  count: number;
}

export interface ListingOpsStatusDistribution {
  rows: ListingOpsStatusCountRow[];
}

export interface ListingDetailRead {
  listing: ListingRead;
  lifecycle_events_tail: ListingLifecycleEventRead[];
  price_history_tail: {
    id: number;
    listing_id: number;
    prior_amount: string | null;
    new_amount: string;
    currency: string;
    reason: string | null;
    replay_key: string | null;
    created_at: string;
  }[];
  images: {
    id: number;
    listing_id: number;
    cover_image_id: number | null;
    scan_session_item_id: number | null;
    display_order: number;
    role: "primary" | "back" | "detail" | "gallery";
    created_at: string;
  }[];
}

export interface OpsListingLifecycleEventListResponse {
  items: ListingLifecycleEventRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface OpsListingPriceHistoryListResponse {
  items: ListingDetailRead["price_history_tail"];
  total_items: number;
  limit: number;
  offset: number;
}

export interface MarketTrendListParams {
  snapshot_scope?: MarketTrendSnapshotScope;
  grading_company?: string;
  grade?: string;
  trend_direction?: MarketTrendDirection;
  trend_strength?: MarketTrendStrength;
  liquidity_direction?: MarketTrendLiquidityDirection;
  stale_data?: boolean;
  currency?: string;
  trend_window?: MarketTrendWindow;
}

export type MarketSaleMatchSuggestionType =
  | "exact_identity_key"
  | "normalized_title_issue_publisher"
  | "normalized_title_issue"
  | "publisher_series_issue"
  | "barcode_supported"
  | "inventory_context_supported"
  | "unresolved_ambiguous";
export type MarketSaleMatchSuggestionConfidenceBucket = "very_high" | "high" | "medium" | "low" | "very_low";
export type MarketSaleMatchSuggestionReviewState = "pending" | "approved" | "rejected" | "ignored";

export interface MarketSaleMatchSuggestionRead {
  id: number;
  market_sale_record_id: number;
  market_source_id: number;
  source_name: string;
  source_type: MarketSourceType;
  source_listing_id: string | null;
  listing_type: MarketSaleListingType;
  raw_title: string;
  normalized_title: string | null;
  raw_issue: string;
  normalized_issue: string | null;
  raw_publisher: string | null;
  normalized_publisher: string | null;
  raw_variant: string | null;
  normalized_variant: string | null;
  raw_grade: string | null;
  normalized_grade: string | null;
  raw_cert_number: string | null;
  normalized_cert_number: string | null;
  sale_price: string | null;
  shipping_price: string | null;
  total_price: string | null;
  currency_code: string;
  sale_date: string | null;
  is_graded: boolean;
  grading_company: MarketSaleGradingCompany | null;
  is_signed: boolean;
  normalization_status: MarketSaleNormalizationStatus;
  normalization_issue_count: number;
  canonical_issue_id: number | null;
  canonical_series_id: number | null;
  canonical_publisher_id: number | null;
  suggested_identity_key: string | null;
  suggestion_type: MarketSaleMatchSuggestionType;
  confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket;
  deterministic_score: number;
  confidence_version: string;
  evidence_json: Record<string, unknown>;
  review_state: MarketSaleMatchSuggestionReviewState;
  reviewed_by_user_id: number | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketSaleMatchSuggestionGenerateResponse {
  sale_id: number;
  suggestion_count: number;
  suggestions: MarketSaleMatchSuggestionRead[];
}

export interface MarketSaleMatchSuggestionReviewActionResponse {
  suggestion: MarketSaleMatchSuggestionRead;
}

export interface MarketSaleMatchSuggestionOpsListResponse {
  suggestions: MarketSaleMatchSuggestionRead[];
  review_state: MarketSaleMatchSuggestionReviewState | "all";
  confidence_bucket: MarketSaleMatchSuggestionConfidenceBucket | "all";
  suggestion_type: MarketSaleMatchSuggestionType | "all";
  total_count: number;
}

export interface MarketSaleNormalizationUpdatePayload {
  normalized_title?: string | null;
  normalized_issue?: string | null;
  normalized_publisher?: string | null;
  normalized_variant?: string | null;
  normalized_grade?: string | null;
  normalized_cert_number?: string | null;
  normalization_status?: MarketSaleNormalizationStatus | null;
  mark_reviewed?: boolean;
  review_note?: string | null;
}

export interface MarketSaleReviewActionPayload {
  reason?: string | null;
}

export interface MarketSaleListResponse {
  items: MarketSaleSummaryRead[];
}

export interface MarketSaleCompEligibilityListParams {
  source?: string;
  eligibility_status?: MarketCompEligibilityStatus;
  eligibility_classification?: MarketCompEligibilityClassification;
  grading_company?: string;
  is_graded?: boolean;
  currency?: string;
  sale_date_from?: string;
  sale_date_to?: string;
}

export interface MarketComparableListParams {
  source?: string;
  metadata_identity_key?: string;
  is_graded?: boolean;
  grading_company?: string;
  normalized_grade?: string;
  currency?: string;
  sale_date_from?: string;
  sale_date_to?: string;
  include_excluded?: boolean;
}

export interface MarketSaleReviewQueueListParams {
  classification?: MarketSaleReviewClassification;
  priority?: MarketSaleReviewPriority;
  review_status?: MarketSaleReviewStatus;
  source?: string;
  source_type?: string;
  issue_type?: string;
}

export type MarketSaleListParams = {
  source?: string;
  publisher?: string;
  normalized_title?: string;
  normalized_issue?: string;
  grading_company?: string;
  is_graded?: boolean;
  normalization_status?: MarketSaleNormalizationStatus;
  sale_date_from?: string;
  sale_date_to?: string;
};

export function scannerRecommendedUseLabel(use: ScannerRecommendedUse): string {
  switch (use) {
    case "bulk_ingest":
      return "Bulk ingest";
    case "high_res_review":
      return "High-res review";
    case "intake_receiving":
      return "Intake / receiving";
    case "archival_scan":
      return "Archival scan";
    default:
      return use;
  }
}

export interface InventoryScanSessionOrigin {
  scan_session_id: number;
  session_type: ScanSessionType;
  status: ScanSessionStatus;
  scan_session_item_id: number;
  sequence_index: number;
  ingest_status: ScanIngestStatus;
  created_at: string;
  scanner_profile_id?: number | null;
  scanner_profile_label?: string | null;
  scanner_profile_snapshot?: ScannerProfileSnapshotRead | null;
}

export interface ScanSessionStatistics {
  total_scans: number;
  ocr_completed: number;
  ocr_pending: number;
  review_required: number;
  failures: number;
  skipped: number;
  average_image_width: number | null;
  average_image_height: number | null;
  duplicate_filename_groups: number;
  duplicate_filename_excess_rows: number;
  duplicate_image_hash_groups: number;
  duplicate_image_hash_excess_rows: number;
}

export interface ScanSessionSummary {
  id: number;
  owner_user_id: number;
  session_type: ScanSessionType;
  status: ScanSessionStatus;
  total_items: number;
  processed_items: number;
  failed_items: number;
  skipped_items: number;
  scanner_profile_id?: number | null;
  scanner_profile?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanSessionItem {
  id: number;
  scan_session_id: number;
  inventory_copy_id?: number | null;
  cover_image_id?: number | null;
  source_filename?: string | null;
  sequence_index: number;
  ingest_status: ScanIngestStatus;
  ingest_error?: string | null;
  image_width?: number | null;
  image_height?: number | null;
  image_sha256?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanSessionDetail extends ScanSessionSummary {
  scanner_profile?: string | null;
  scanner_profile_id?: number | null;
  scanner_profile_snapshot?: ScannerProfileSnapshotRead | null;
  source_device?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  session_notes?: string | null;
  statistics: ScanSessionStatistics;
  items: ScanSessionItem[];
  /** Latest booked scan-pipeline replay (any status); comparison-only tooling. */
  latest_scan_pipeline_replay?: ScanPipelineReplayRunSummaryRead | null;
}

export interface ScanSessionDashboardResponse {
  active_sessions: ScanSessionSummary[];
  recent_sessions: ScanSessionSummary[];
}

/** Aggregate scan pipeline dashboards (deterministic counters + session previews). */
export interface ScannerProfileUsageRow {
  scanner_profile_id?: number | null;
  profile_label: string;
  scan_session_count: number;
}

export interface ScanPipelineDashboardSummary {
  active_sessions: number;
  sessions_completed_with_errors: number;
  failed_items: number;
  review_required_items: number;
  qa_needs_rescan: number;
  qa_corrupt_or_unreadable: number;
  routing_recommend_ocr: number;
  routing_recommend_high_res_review: number;
  high_res_pending: number;
  physical_intake_received_pending_scan: number;
  replay_runs_with_changes: number;
  most_used_scanner_profiles: ScannerProfileUsageRow[];
}

export interface ScanPipelineDashboardResponse {
  summary: ScanPipelineDashboardSummary;
  active_sessions: ScanSessionSummary[];
  recent_sessions: ScanSessionSummary[];
}

export interface ScanSessionListResponse {
  sessions: ScanSessionSummary[];
}

export interface ScanSessionCreatePayload {
  session_type?: ScanSessionType;
  scanner_profile_id?: number | null;
  scanner_profile?: string | null;
  source_device?: string | null;
  session_notes?: string | null;
}

export interface ScanSessionItemAppendPayload {
  inventory_copy_id?: number | null;
  cover_image_id?: number | null;
  source_filename?: string | null;
  image_width?: number | null;
  image_height?: number | null;
  image_sha256?: string | null;
}

export interface ScanSessionItemsAppendPayload {
  items: ScanSessionItemAppendPayload[];
}

export interface ScanSessionItemUpdatePayload {
  ingest_status: ScanIngestStatus;
  ingest_error?: string | null;
  image_width?: number | null;
  image_height?: number | null;
  image_sha256?: string | null;
}

export interface ScanSessionIngestManifestRow {
  inventory_copy_id?: number | null;
  source_filename?: string | null;
  sequence_index?: number | null;
}

export interface ScanSessionIngestManifest {
  items?: ScanSessionIngestManifestRow[];
}

export interface ScanSessionItemsListResponse {
  scan_session_id: number;
  owner_user_id: number;
  session_type: ScanSessionType;
  session_status: ScanSessionStatus;
  statistics: ScanSessionStatistics;
  items: ScanSessionItem[];
}

export type ScanQaClassification =
  | "ready_for_ocr"
  | "needs_high_res_review"
  | "needs_rescan"
  | "corrupt_or_unreadable"
  | "duplicate_scan"
  | "low_resolution"
  | "low_contrast"
  | "blurry"
  | "already_processed"
  | "review_required";

export type ScanQaRoutingRecommendation =
  | "queue_for_ocr"
  | "send_to_high_res_review"
  | "request_rescan"
  | "hold_for_manual_review"
  | "no_action_needed";

export type ScanQaSeverity = "info" | "warning" | "critical";

export interface ScanQaItemRead {
  scan_session_item_id: number;
  cover_image_id?: number | null;
  qa_classification: ScanQaClassification;
  routing_recommendation: ScanQaRoutingRecommendation;
  severity: ScanQaSeverity;
  evidence_json?: Record<string, unknown>;
}

export interface ScanSessionQaSummaryRead {
  scan_session_id: number;
  owner_user_id: number;
  scanner_profile?: string | null;
  persisted_run: boolean;
  items: ScanQaItemRead[];
  totals_by_classification: Record<string, number>;
  totals_by_routing: Record<string, number>;
}

export interface OpsScanQaFleetSummaryRead {
  totals_by_classification: Record<string, number>;
  totals_by_routing: Record<string, number>;
  failure_and_rescan: Record<string, number>;
}

export interface InventoryCoverScanQaRow {
  cover_image_id: number;
  qa_classification: ScanQaClassification;
  routing_recommendation: ScanQaRoutingRecommendation;
  severity: ScanQaSeverity;
  evidence_json?: Record<string, unknown>;
}

export interface InventoryScanQaPanelRead {
  inventory_copy_id: number;
  covers: InventoryCoverScanQaRow[];
}

export type QueueRoutingRecommendationType =
  | "recommend_ocr"
  | "recommend_high_res_review"
  | "recommend_manual_review"
  | "recommend_rescan"
  | "recommend_hold"
  | "recommend_no_action";

export type QueueRoutingPriority = "high" | "medium" | "low";
export type QueueRoutingStatus = "open" | "acknowledged" | "dismissed" | "resolved";

export interface QueueRoutingRecommendationRead {
  id?: number | null;
  scan_session_item_id?: number | null;
  cover_image_id?: number | null;
  scan_session_id?: number | null;
  recommendation_type: QueueRoutingRecommendationType;
  priority: QueueRoutingPriority;
  routing_status: QueueRoutingStatus;
  evidence_json?: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface QueueRoutingListResponse {
  items: QueueRoutingRecommendationRead[];
  totals_by_recommendation: Record<string, number>;
  totals_by_status: Record<string, number>;
  unresolved_count: number;
}

export interface ScanSessionRoutingRead {
  scan_session_id: number;
  owner_user_id: number;
  persisted_run: boolean;
  items: QueueRoutingRecommendationRead[];
  totals_by_recommendation: Record<string, number>;
  totals_by_status: Record<string, number>;
  unresolved_count: number;
}

export type HighResReviewRequestReason =
  | "low_quality_scan"
  | "failed_ocr"
  | "poor_match_confidence"
  | "valuable_review_candidate"
  | "manual_review"
  | "rescan_required";

export type HighResReviewRequestStatus =
  | "pending"
  | "scanned"
  | "linked"
  | "review_complete"
  | "cancelled";

export type HighResReviewRequestPriority = "high" | "medium" | "low";

export interface HighResReviewRequestCreatePayload {
  inventory_copy_id?: number | null;
  source_cover_image_id?: number | null;
  source_scan_session_item_id?: number | null;
  source_ocr_quality_analysis_id?: number | null;
  source_inventory_risk_type?: string | null;
  source_action_center_category?: string | null;
  request_reason: HighResReviewRequestReason;
  priority?: HighResReviewRequestPriority;
  notes?: string | null;
}

export interface HighResReviewRequestSummary {
  id: number;
  owner_user_id: number;
  inventory_copy_id: number;
  source_cover_image_id?: number | null;
  high_res_cover_image_id?: number | null;
  attach_scan_session_id?: number | null;
  request_reason: HighResReviewRequestReason;
  status: HighResReviewRequestStatus;
  priority: HighResReviewRequestPriority;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface HighResReviewRequestDetail extends HighResReviewRequestSummary {
  source_scan_session_item_id?: number | null;
  source_ocr_quality_analysis_id?: number | null;
  source_inventory_risk_type?: string | null;
  source_action_center_category?: string | null;
  attach_scan_session_item_id?: number | null;
  source_cover_scan: CoverImageRead | null;
  review_high_res_scan: CoverImageRead | null;
}

export interface HighResReviewRequestListResponse {
  requests: HighResReviewRequestSummary[];
}

export interface HighResReviewRequestStatsRead {
  by_status: Record<string, number>;
}

export interface InventoryPortfolioMembershipRead {
  portfolio_id: number;
  portfolio_name: string;
  portfolio_type: string;
  allocation_role: string;
}

export interface InventoryPortfolioIntelligenceTeaser {
  memberships: InventoryPortfolioMembershipRead[];
  publisher_exposure_status: string | null;
  publisher_exposure_pct_value: string | null;
}

/** P38-03 deterministic portfolio liquidity bucket overlay (inventory detail teaser). */
export interface InventoryPortfolioLiquidityTeaser {
  portfolio_liquidity_bucket: "HIGH" | "MEDIUM" | "LOW" | "ILLIQUID";
  liquidity_engine_status: string | null;
  portfolio_liquidity_snapshot_id: number | null;
  liquidity_efficiency_score: string | null;
  dead_capital_estimate: string | null;
  liquidity_balance_status: string | null;
  dead_capital_teaser: string | null;
}

/** P38-06 deterministic acquisition-priority teaser for inventory detail. */
export interface InventoryAcquisitionPriorityTeaser {
  acquisition_category: string;
  acquisition_priority: "LOW" | "MEDIUM" | "HIGH" | "ELITE";
  recommendation_strength: "WEAK" | "MODERATE" | "STRONG" | "ELITE";
  rationale_summary: string;
  diversification_impact: string | null;
  liquidity_impact: string | null;
  duplication_risk: string | null;
}

/** P38-05 deterministic concentration-risk teaser for inventory detail. */
export interface InventoryConcentrationRiskTeaser {
  concentration_type: string;
  concentration_key: string;
  exposure_status: "HEALTHY" | "WATCH" | "CONCENTRATED" | "OVEREXPOSED" | "CRITICAL";
  concentration_score: string | null;
  diversification_score: string | null;
  percentage_of_portfolio: string | null;
}

/** P38-04 deterministic portfolio recommendation teaser for inventory detail. */
export interface InventoryPortfolioRecommendationTeaser {
  recommendation_action: "HOLD" | "SELL" | "REDUCE_EXPOSURE" | "GRADE_THEN_SELL" | "CONSOLIDATE" | "WATCH";
  recommendation_strength: "WEAK" | "MODERATE" | "STRONG" | "ELITE";
  confidence_level: "LOW" | "MEDIUM" | "HIGH";
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  rationale_summary: string;
  estimated_capital_release: string | null;
  estimated_liquidity_impact: string | null;
  estimated_portfolio_efficiency_gain: string | null;
  recommendation_status: "ACTIVE" | "SUPERSEDED" | "ARCHIVED";
  recommendation_checksum: string | null;
}

export interface InventoryDetail extends InventoryItem {
  copy_number: number;
  metadata_identity_key?: string | null;
  source_type: string | null;
  order_id: number;
  order_item_id: number;
  variant_id: number;
  created_at: string;
  inventory_fmv: InventoryFmvAttachmentRead | null;
  cover_images: InventoryCoverImage[];
  originating_scan_session?: InventoryScanSessionOrigin | null;
  grading_candidate?: InventoryGradingCandidateBadge | null;
  grading_spread?: InventoryGradingSpreadBadge | null;
  grading_roi?: InventoryGradingRoiBadge | null;
  grading_submission?: InventoryGradingSubmissionBadge | null;
  grading_reconciliation?: InventoryGradingReconciliationBadge | null;
  grading_recommendation?: InventoryGradingRecommendationBadge | null;
  grading_risk?: InventoryGradingRiskBadge | null;
  portfolio_intelligence?: InventoryPortfolioIntelligenceTeaser | null;
  duplicate_intelligence?: InventoryDuplicateIntelligenceTeaser | null;
  portfolio_liquidity?: InventoryPortfolioLiquidityTeaser | null;
  acquisition_priority?: InventoryAcquisitionPriorityTeaser | null;
  concentration_risk?: InventoryConcentrationRiskTeaser | null;
  portfolio_recommendation?: InventoryPortfolioRecommendationTeaser | null;
  market_acquisition_score?: InventoryMarketAcquisitionScoreTeaser | null;
  market_acquisition_signal?: InventoryMarketAcquisitionSignalTeaser | null;
  market_acquisition_opportunity?: InventoryMarketAcquisitionOpportunityTeaser | null;
  portfolio_market_coupling?: InventoryPortfolioMarketCouplingTeaserRead | null;
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

export type CollectionHistoricalTimelineEventKind =
  | "inventory_added"
  | "preorder_created"
  | "release_day"
  | "expected_ship_window"
  | "inventory_received"
  | "scan_completed"
  | "ocr_completed"
  | "ocr_failed"
  | "relationship_reviewed"
  | "canonical_suggestion_reviewed"
  | "conflict_detected"
  | "conflict_resolved"
  | "duplicate_detected"
  | "variant_family_detected";

export type CollectionHistoricalTimelineGrouping =
  | "none"
  | "day"
  | "week"
  | "month"
  | "publisher"
  | "series"
  | "ownership_state"
  | "preorder_vs_in_hand"
  | "inventory_item";

export type CollectionHistoricalTimelineSort = "asc" | "desc";

export interface CollectionHistoricalTimelineFiltersEcho {
  event_type: CollectionHistoricalTimelineEventKind | null;
  publisher: string | null;
  ownership_state: InventoryOwnershipNormalized | null;
  release_status: string | null;
  start_date: string | null;
  end_date: string | null;
  preorder_only: boolean;
  in_hand_only: boolean;
  inventory_copy_id: number | null;
  grouping: CollectionHistoricalTimelineGrouping;
  sort: CollectionHistoricalTimelineSort;
}

export interface CollectionHistoricalTimelineSummary {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  total_events_present: number;
  truncated_to: number;
  earliest_occurrence: string | null;
  latest_occurrence: string | null;
  counts_by_event_type: KeyedInventoryCountRow[];
}

export interface CollectionHistoricalTimelineEventRow {
  stable_id: string;
  event_type: CollectionHistoricalTimelineEventKind;
  occurred_at: string;
  inventory_copy_id: number;
  publisher: string;
  series_title: string;
  issue_number: string;
  ownership_state_snapshot: InventoryOwnershipNormalized;
  release_status_snapshot: string;
  preorder_track: boolean;
  evidence_json: Record<string, unknown>;
}

export interface CollectionHistoricalTimelineEventGroupRow {
  group_key: string;
  events: CollectionHistoricalTimelineEventRow[];
}

export interface CollectionHistoricalTimelineEventsResponse {
  scope_user_id: number | null;
  scope: string;
  generated_as_of_date: string;
  summary: CollectionHistoricalTimelineSummary;
  filters: CollectionHistoricalTimelineFiltersEcho;
  events: CollectionHistoricalTimelineEventRow[];
  groups: CollectionHistoricalTimelineEventGroupRow[];
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
  valuation_scope?: InventoryValuationScope;
  confidence_bucket?: MarketFmvConfidenceBucket;
  liquidity_bucket?: MarketFmvLiquidityBucket;
  stale_data?: boolean;
  currency_code?: string;
  ownership_state?: InventoryOwnershipNormalized;
  risk_priority?: InventoryRiskPriority;
  risk_type?: InventoryRiskType;
  needs_attention?: boolean;
  action_attention?: boolean;
  action_center_category?: InventoryActionCenterCategory;
  arrival_classification?: OrderArrivalClassification;
  sort_by?: SortBy;
  sort_dir?: "asc" | "desc";
  organization_id?: number;
}

export type InventoryReportExportParams = Omit<InventoryQueryParams, "page" | "page_size"> & {
  ownership_state?: InventoryOwnershipNormalized;
  release_status?: InventoryItem["release_status"];
  order_status?: InventoryItem["order_status"];
  preorder_only?: boolean;
  in_hand_only?: boolean;
  start_date?: string;
  end_date?: string;
};


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

function parseStructuredApiError(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const rec = data as Record<string, unknown>;
  const nested = rec.error;
  if (nested && typeof nested === "object" && nested !== null) {
    const m = (nested as { message?: unknown }).message;
    if (typeof m === "string") return m;
  }
  if (typeof rec.detail === "string") return rec.detail;
  return null;
}

function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init?.headers);

  const isFormBody = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isFormBody && !headers.has("Content-Type") && init?.body) {
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
      const data = (await response.json()) as unknown;
      message = parseStructuredApiError(data) ?? message;
    } catch {
      // Ignore invalid error payloads.
    }

    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

/** P39-07: full `{ data, meta }` envelope for owner/ops dashboard panels (deterministic snapshots + checksums). */
export async function fetchMarketV1Envelope<T>(pathSuffix: string, init?: RequestInit): Promise<MarketApiV1Envelope<T>> {
  const suffix = pathSuffix.startsWith("/") ? pathSuffix : `/${pathSuffix}`;
  return request<MarketApiV1Envelope<T>>(`${MARKET_API_V1_PREFIX}${suffix}`, init);
}

async function requestMarketV1<T>(path: string, init?: RequestInit): Promise<T> {
  const envelope = await fetchMarketV1Envelope<T>(path, init);
  return envelope.data;
}

export async function fetchScanV1Envelope<T>(pathSuffix: string, init?: RequestInit): Promise<MarketApiV1Envelope<T>> {
  const suffix = pathSuffix.startsWith("/") ? pathSuffix : `/${pathSuffix}`;
  return request<MarketApiV1Envelope<T>>(`${SCAN_API_V1_PREFIX}${suffix}`, init);
}

async function requestScanV1<T>(path: string, init?: RequestInit): Promise<T> {
  const envelope = await fetchScanV1Envelope<T>(path, init);
  return envelope.data;
}

async function requestEmpty(path: string, init?: RequestInit): Promise<void> {
  const token = getStoredToken();
  const headers = new Headers(init?.headers);

  const isFormBody = typeof FormData !== "undefined" && init?.body instanceof FormData;
  if (!isFormBody && !headers.has("Content-Type") && init?.body) {
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
      const data = (await response.json()) as unknown;
      message = parseStructuredApiError(data) ?? message;
    } catch {
      // Ignore invalid error payloads.
    }

    throw new ApiError(message, response.status);
  }

  await response.blob().catch(() => undefined);
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
      const data = (await response.json()) as unknown;
      message = parseStructuredApiError(data) ?? message;
    } catch {
      // ignore
    }
    throw new ApiError(message, response.status);
  }

  return response.blob();
}

function parseAttachmentFilename(contentDispositionHeader: string | null | undefined, fallback: string): string {
  if (!contentDispositionHeader) {
    return fallback;
  }
  const match = contentDispositionHeader.match(/filename\s*=\s*"([^"]+)"/i);
  const candidate = match?.[1]?.trim();
  return candidate?.length ? candidate : fallback;
}

function browserDownloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.click();
  URL.revokeObjectURL(url);
}

async function downloadAuthenticatedReport(pathFromRoot: string, fallbackFilename: string): Promise<void> {
  const token = getStoredToken();
  const headers = new Headers();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${pathFromRoot}`, { headers });

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

  const filename = parseAttachmentFilename(response.headers.get("Content-Disposition"), fallbackFilename);
  const blob = await response.blob();
  browserDownloadBlob(blob, filename);
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

/** P38-01 deterministic portfolio intelligence (truth layer only). */

export interface PortfolioRead {
  id: number;
  owner_user_id: number;
  name: string;
  description: string | null;
  portfolio_type: string;
  status: string;
  replay_key: string | null;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
}

export interface PortfolioListResponse {
  items: PortfolioRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface PortfolioExposureSnapshotRead {
  id: number;
  owner_user_id: number;
  portfolio_id: number | null;
  generation_scope_key: string;
  replay_key: string | null;
  generation_batch_checksum: string;
  exposure_type: string;
  exposure_key: string;
  item_count: number;
  total_fmv_amount: string | null;
  total_cost_basis_amount: string | null;
  total_realized_sales_amount: string | null;
  percentage_of_portfolio_value: string | null;
  percentage_of_portfolio_count: string | null;
  exposure_status: string;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioExposureEvidenceRead {
  id: number;
  portfolio_exposure_snapshot_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface PortfolioExposureEvidenceListResponse {
  items: PortfolioExposureEvidenceRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface PortfolioExposureSnapshotListResponse {
  items: PortfolioExposureSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface PortfolioExposureGenerateResponse {
  generation_batch_checksum: string;
  snapshot_date: string;
  snapshots: PortfolioExposureSnapshotRead[];
  replayed: boolean;
}

export interface PortfolioAllocationSnapshotRead {
  id: number;
  owner_user_id: number;
  portfolio_id: number | null;
  generation_scope_key: string;
  replay_key: string | null;
  total_item_count: number;
  total_fmv_amount: string | null;
  total_cost_basis_amount: string | null;
  total_realized_sales_amount: string | null;
  graded_item_count: number;
  raw_item_count: number;
  listed_item_count: number;
  sold_item_count: number;
  high_liquidity_count: number;
  low_liquidity_count: number;
  grading_candidate_count: number;
  sale_candidate_count: number;
  duplicate_count: number;
  convention_assigned_count: number;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioAllocationSnapshotListResponse {
  items: PortfolioAllocationSnapshotRead[];
  total_items: number;
  limit: number;
  offset: number;
}

export interface PortfolioAllocationGenerateResponse {
  snapshot_date: string;
  allocation: PortfolioAllocationSnapshotRead | null;
  replayed: boolean;
}

export interface PortfolioIntelligenceExposureTeaser {
  exposure_type: string;
  exposure_key: string;
  exposure_status: string;
  percentage_of_portfolio_value: string | null;
}

export interface PortfolioIntelligenceSummary {
  active_portfolio_count: number;
  latest_allocation_scope_key: string | null;
  latest_allocation_checksum: string | null;
  latest_generation_batch_checksum: string | null;
  total_item_count: number | null;
  total_fmv_amount: string | null;
  total_cost_basis_amount: string | null;
  graded_item_count: number | null;
  raw_item_count: number | null;
  low_liquidity_count: number | null;
  high_liquidity_count: number | null;
  overexposed_rows: PortfolioIntelligenceExposureTeaser[];
}

export interface DuplicateOpportunityBrief {
  cluster_id: number;
  cluster_key: string;
  cluster_type: string;
  duplication_status: string;
  total_cost_basis_amount: string | null;
  graded_item_count: number;
  raw_item_count: number;
}

export interface DuplicateIntelligenceSummary {
  generation_batch_checksum: string | null;
  snapshot_date: string | null;
  cluster_count: number;
  overexposed_cluster_count: number;
  redundant_capital_amount: string | null;
  graded_overlap_cluster_count: number;
  raw_graded_overlap_cluster_count: number;
  graded_duplicate_units: number;
  raw_duplicate_units: number;
  strongest_opportunities: DuplicateOpportunityBrief[];
}

export interface DuplicateClusterGeneratePayload {
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface DuplicateClusterRead {
  id: number;
  owner_user_id: number;
  canonical_comic_issue_id: number | null;
  cluster_key: string;
  cluster_type: string;
  generation_batch_checksum: string;
  replay_key: string;
  total_item_count: number;
  graded_item_count: number;
  raw_item_count: number;
  total_fmv_amount: string | null;
  total_cost_basis_amount: string | null;
  liquidity_profile: string;
  duplication_status: string;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface DuplicateClusterListResponse {
  generation_batch_checksum: string | null;
  snapshot_date: string | null;
  items: DuplicateClusterRead[];
}

export interface DuplicateClusterItemRead {
  id: number;
  duplicate_cluster_id: number;
  inventory_item_id: number;
  portfolio_id: number | null;
  grading_status: string;
  estimated_strength_score: string | null;
  liquidity_score: string | null;
  current_fmv: string | null;
  acquisition_cost: string | null;
  recommendation_priority: string;
  created_at: string;
}

export interface DuplicateClusterItemListResponse {
  items: DuplicateClusterItemRead[];
}

export interface DuplicateConsolidationRecommendationRead {
  id: number;
  owner_user_id: number;
  duplicate_cluster_id: number;
  generation_batch_checksum: string;
  recommendation_action: string;
  rationale_summary: string;
  expected_capital_reduction: string | null;
  estimated_liquidity_improvement: string | null;
  estimated_portfolio_efficiency_gain: string | null;
  confidence_level: string;
  recommendation_status: string;
  checksum: string;
  snapshot_date: string;
  replay_key: string;
  created_at: string;
}

export interface DuplicateConsolidationRecommendationListResponse {
  items: DuplicateConsolidationRecommendationRead[];
}

export interface DuplicateHistorySnapshotRead {
  id: number;
  owner_user_id: number;
  cluster_key: string;
  cluster_type: string;
  total_item_count: number;
  total_fmv_amount: string | null;
  duplication_status: string;
  checksum: string;
  generation_batch_checksum: string;
  snapshot_date: string;
  replay_key: string;
  created_at: string;
}

export interface DuplicateHistoryListResponse {
  items: DuplicateHistorySnapshotRead[];
}

export interface DuplicateClusterGenerateResponse {
  replayed: boolean;
  generation_batch_checksum: string;
  snapshot_date: string;
  snapshot_date_replay_source?: "explicit" | "inferred_prior_batch" | null;
  clusters: DuplicateClusterRead[];
  consolidation_recommendations: DuplicateConsolidationRecommendationRead[];
  duplicate_history_snapshots_written: number;
}

export interface InventoryDuplicateIntelligenceTeaser {
  generation_batch_checksum: string | null;
  cluster_types_present: string[];
  worst_duplication_status: string | null;
  is_strongest_copy_in_clusters: boolean;
  primary_consolidation_action: string | null;
  consolidation_teaser: string | null;
}

/** P38-03 deterministic portfolio liquidity intelligence (capital allocation rollup). */
export interface PortfolioLiquidityBucketRead {
  id: number;
  portfolio_liquidity_snapshot_id: number;
  liquidity_bucket: "HIGH" | "MEDIUM" | "LOW" | "ILLIQUID";
  item_count: number;
  total_fmv: string | null;
  weighted_liquidity_value: string | null;
  percentage_of_portfolio: string | null;
  created_at: string;
}

export interface PortfolioLiquiditySnapshotRead {
  id: number;
  owner_user_id: number;
  portfolio_id: number | null;
  generation_scope_key: string;
  replay_key: string;
  total_portfolio_fmv: string | null;
  liquid_portfolio_value: string | null;
  illiquid_portfolio_value: string | null;
  liquidity_weighted_value: string | null;
  liquidity_efficiency_score: string | null;
  liquidity_drag_score: string | null;
  concentration_risk_score: string | null;
  dead_capital_estimate: string | null;
  liquidity_balance_status: "HEALTHY" | "WATCH" | "IMBALANCED" | "CRITICAL" | "INSUFFICIENT_DATA";
  high_liquidity_count: number;
  medium_liquidity_count: number;
  low_liquidity_count: number;
  illiquid_count: number;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioLiquiditySnapshotListResponse {
  items: PortfolioLiquiditySnapshotRead[];
  total: number;
}

export interface PortfolioLiquiditySnapshotDetailResponse {
  snapshot: PortfolioLiquiditySnapshotRead;
  buckets: PortfolioLiquidityBucketRead[];
}

export interface PortfolioLiquidityGeneratePayload {
  portfolio_id?: number | null;
  replay_key?: string | null;
  snapshot_date?: string | null;
}

export interface PortfolioLiquidityGenerateResponse {
  replayed: boolean;
  snapshot: PortfolioLiquiditySnapshotRead;
  buckets: PortfolioLiquidityBucketRead[];
  history_appended: boolean;
}

export interface PortfolioLiquidityEvidenceRead {
  id: number;
  portfolio_liquidity_snapshot_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface PortfolioLiquidityEvidenceListResponse {
  items: PortfolioLiquidityEvidenceRead[];
  total: number;
}

export interface PortfolioLiquidityHistoryRead {
  id: number;
  owner_user_id: number;
  portfolio_id: number | null;
  generation_scope_key: string;
  replay_key: string;
  liquidity_efficiency_score: string | null;
  liquidity_drag_score: string | null;
  concentration_risk_score: string | null;
  dead_capital_estimate: string | null;
  liquidity_balance_status: "HEALTHY" | "WATCH" | "IMBALANCED" | "CRITICAL" | "INSUFFICIENT_DATA";
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioLiquidityHistoryListResponse {
  items: PortfolioLiquidityHistoryRead[];
  total: number;
}

/** P38-04 deterministic portfolio hold/sell intelligence. */
export interface PortfolioRecommendationRead {
  id: number;
  owner_user_id: number;
  inventory_item_id: number | null;
  portfolio_id: number | null;
  canonical_comic_issue_id: number | null;
  recommendation_action: "HOLD" | "SELL" | "REDUCE_EXPOSURE" | "GRADE_THEN_SELL" | "CONSOLIDATE" | "WATCH";
  recommendation_strength: "WEAK" | "MODERATE" | "STRONG" | "ELITE";
  confidence_level: "LOW" | "MEDIUM" | "HIGH";
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  estimated_liquidity_impact: string | null;
  estimated_capital_release: string | null;
  estimated_portfolio_efficiency_gain: string | null;
  expected_roi_if_graded: string | null;
  rationale_summary: string;
  warning_flags_json: unknown[];
  recommendation_status: "ACTIVE" | "SUPERSEDED" | "ARCHIVED";
  checksum: string;
  replay_key: string | null;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioRecommendationEvidenceRead {
  id: number;
  portfolio_recommendation_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface PortfolioRecommendationScenarioRead {
  id: number;
  portfolio_recommendation_id: number;
  scenario_name: "pessimistic" | "baseline" | "optimistic";
  projected_capital_release: string | null;
  projected_liquidity_gain: string | null;
  projected_portfolio_impact: string | null;
  created_at: string;
}

export interface PortfolioRecommendationHistoryRead {
  id: number;
  owner_user_id: number;
  inventory_item_id: number | null;
  portfolio_id: number | null;
  recommendation_action: string;
  recommendation_strength: string;
  confidence_level: string;
  risk_level: string;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface PortfolioRecommendationListResponse {
  items: PortfolioRecommendationRead[];
  total: number;
}

export interface PortfolioRecommendationDetailRead {
  recommendation: PortfolioRecommendationRead;
  evidence: PortfolioRecommendationEvidenceRead[];
  scenarios: PortfolioRecommendationScenarioRead[];
  history: PortfolioRecommendationHistoryRead[];
}

export interface PortfolioRecommendationGeneratePayload {
  portfolio_id?: number | null;
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface PortfolioRecommendationGenerateResponse {
  replayed: boolean;
  items: PortfolioRecommendationRead[];
  total: number;
  history_appended_count: number;
}

export interface PortfolioRecommendationEvidenceListResponse {
  items: PortfolioRecommendationEvidenceRead[];
  total: number;
}

export interface PortfolioRecommendationHistoryListResponse {
  items: PortfolioRecommendationHistoryRead[];
  total: number;
}

/** P38-05 deterministic portfolio concentration intelligence. */
export interface ConcentrationRiskSnapshotRead {
  id: number;
  owner_user_id: number;
  portfolio_id: number | null;
  concentration_type: string;
  concentration_key: string;
  total_item_count: number;
  total_fmv_amount: string | null;
  percentage_of_portfolio: string | null;
  concentration_score: string | null;
  liquidity_weighted_concentration: string | null;
  exposure_status: "HEALTHY" | "WATCH" | "CONCENTRATED" | "OVEREXPOSED" | "CRITICAL";
  diversification_score: string | null;
  checksum: string;
  replay_key: string | null;
  snapshot_date: string;
  created_at: string;
}

export interface ConcentrationRiskEvidenceRead {
  id: number;
  concentration_risk_snapshot_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface ConcentrationRiskFactorRead {
  id: number;
  concentration_risk_snapshot_id: number;
  factor_key: string;
  factor_score: string | null;
  weighting: string | null;
  created_at: string;
}

export interface ConcentrationRiskHistoryRead {
  id: number;
  owner_user_id: number;
  portfolio_id: number | null;
  concentration_type: string;
  concentration_key: string;
  exposure_status: string;
  concentration_score: string | null;
  diversification_score: string | null;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface ConcentrationRiskDetailRead {
  snapshot: ConcentrationRiskSnapshotRead;
  evidence: ConcentrationRiskEvidenceRead[];
  factors: ConcentrationRiskFactorRead[];
  history: ConcentrationRiskHistoryRead[];
}

export interface ConcentrationRiskListResponse {
  items: ConcentrationRiskSnapshotRead[];
  total: number;
}

export interface ConcentrationRiskGeneratePayload {
  portfolio_id?: number | null;
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface ConcentrationRiskGenerateResponse {
  replayed: boolean;
  items: ConcentrationRiskSnapshotRead[];
  total: number;
  history_appended_count: number;
}

export interface ConcentrationRiskEvidenceListResponse {
  items: ConcentrationRiskEvidenceRead[];
  total: number;
}

export interface ConcentrationRiskFactorListResponse {
  items: ConcentrationRiskFactorRead[];
  total: number;
}

export interface ConcentrationRiskHistoryListResponse {
  items: ConcentrationRiskHistoryRead[];
  total: number;
}

/** P38-06 deterministic acquisition-priority intelligence. */
export interface AcquisitionPrioritySnapshotRead {
  id: number;
  owner_user_id: number;
  canonical_comic_issue_id: number | null;
  acquisition_category: string;
  acquisition_priority: "LOW" | "MEDIUM" | "HIGH" | "ELITE";
  portfolio_impact_score: string | null;
  diversification_impact: string | null;
  liquidity_impact: string | null;
  grading_upside_score: string | null;
  duplication_risk: string | null;
  concentration_reduction_score: string | null;
  estimated_capital_efficiency: string | null;
  recommendation_strength: "WEAK" | "MODERATE" | "STRONG" | "ELITE";
  confidence_level: "LOW" | "MEDIUM" | "HIGH";
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  rationale_summary: string;
  warning_flags_json: unknown[];
  checksum: string;
  replay_key: string | null;
  snapshot_date: string;
  created_at: string;
}

export interface AcquisitionPriorityEvidenceRead {
  id: number;
  acquisition_priority_snapshot_id: number;
  evidence_type: string;
  source_id: number | null;
  source_table: string | null;
  evidence_value_json: Record<string, unknown>;
  created_at: string;
}

export interface AcquisitionPriorityScenarioRead {
  id: number;
  acquisition_priority_snapshot_id: number;
  scenario_name: "pessimistic" | "baseline" | "optimistic";
  projected_liquidity_impact: string | null;
  projected_diversification_impact: string | null;
  projected_portfolio_efficiency: string | null;
  created_at: string;
}

export interface AcquisitionPriorityHistoryRead {
  id: number;
  owner_user_id: number;
  canonical_comic_issue_id: number | null;
  acquisition_category: string;
  acquisition_priority: string;
  recommendation_strength: string;
  confidence_level: string;
  risk_level: string;
  checksum: string;
  snapshot_date: string;
  created_at: string;
}

export interface AcquisitionPriorityDetailRead {
  snapshot: AcquisitionPrioritySnapshotRead;
  evidence: AcquisitionPriorityEvidenceRead[];
  scenarios: AcquisitionPriorityScenarioRead[];
  history: AcquisitionPriorityHistoryRead[];
}

export interface AcquisitionPriorityListResponse {
  items: AcquisitionPrioritySnapshotRead[];
  total: number;
}

export interface AcquisitionPriorityGeneratePayload {
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface AcquisitionPriorityGenerateResponse {
  replayed: boolean;
  items: AcquisitionPrioritySnapshotRead[];
  total: number;
  history_appended_count: number;
}

export interface AcquisitionPriorityEvidenceListResponse {
  items: AcquisitionPriorityEvidenceRead[];
  total: number;
}

export interface AcquisitionPriorityHistoryListResponse {
  items: AcquisitionPriorityHistoryRead[];
  total: number;
}

export interface PortfolioGenerateScopePayload {
  portfolio_id?: number | null;
  snapshot_date?: string | null;
  replay_key?: string | null;
}

export interface PortfolioItemRead {
  id: number;
  portfolio_id: number;
  inventory_item_id: number;
  allocation_role: string;
  allocated_value_amount: string | null;
  allocated_value_source: string | null;
  added_at: string;
  removed_at: string | null;
  created_at: string;
}

export interface PortfolioItemListResponse {
  items: PortfolioItemRead[];
  total_items: number;
  limit: number;
  offset: number;
}

function buildQueryString(
  params:
    | Record<string, string | number | boolean | undefined>
    | InventoryQueryParams
    | InventoryReportExportParams
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


export function inventoryListingQueryToReportQueryString(filters: InventoryQueryParams): string {
  const { page: _page, page_size: _pageSize, ...rest } = filters;
  return buildQueryString(rest as Record<string, string | number | boolean | undefined>);
}

export type ScanIngestionSourceType = "EPSON" | "FUJITSU" | "MOBILE" | "ZIP_IMPORT" | "MANUAL_UPLOAD";
export type ScanUploadSourceType = "drag_drop" | "zip_upload" | "scanner_batch" | "manual_upload";
export type ScanIngestionBatchStatus = "PENDING" | "PROCESSING" | "COMPLETE" | "FAILED";
export type ScanImageProcessingStatus = "INGESTED" | "NORMALIZED" | "FAILED";

export interface ScanBatchUploadPayload {
  source_type: ScanIngestionSourceType;
  upload_source: ScanUploadSourceType;
  scanner_make?: string | null;
  scanner_model?: string | null;
  scanner_profile?: string | null;
  color_mode?: string | null;
  normalized_dpi?: number;
  create_thumbnail?: boolean;
  create_normalized_variant?: boolean;
}

export interface ScanImageVariantRead {
  id: number;
  parent_scan_image_id: number;
  variant_type: string;
  storage_backend: string;
  storage_path: string;
  width: number;
  height: number;
  checksum: string;
  created_at: string;
}

export interface ScanImageSummaryRead {
  id: number;
  owner_user_id: number;
  ingestion_batch_id: number;
  sequence_index: number;
  original_filename: string;
  storage_backend: string;
  storage_path: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  dpi_x: number | null;
  dpi_y: number | null;
  normalized_dpi_x: number | null;
  normalized_dpi_y: number | null;
  file_size_bytes: number;
  sha256_checksum: string;
  scanner_make: string | null;
  scanner_model: string | null;
  scanner_profile: string | null;
  color_mode: string | null;
  processing_status: ScanImageProcessingStatus | string;
  is_duplicate: boolean;
  duplicate_of_scan_image_id: number | null;
  failure_reason: string | null;
  created_at: string;
}

export interface ScanImageRead extends ScanImageSummaryRead {
  variants: ScanImageVariantRead[];
}

export interface ScanIngestionEventRead {
  id: number;
  ingestion_batch_id: number;
  scan_image_id: number | null;
  event_type: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanUploadSessionRead {
  id: number;
  owner_user_id: number;
  upload_source: ScanUploadSourceType | string;
  session_checksum: string;
  total_files: number;
  successful_files: number;
  failed_files: number;
  duplicate_files: number;
  started_at: string;
  completed_at: string | null;
  created_at: string;
}

export interface ScanIngestionBatchSummaryRead {
  id: number;
  owner_user_id: number;
  upload_session_id: number;
  source_type: ScanIngestionSourceType | string;
  batch_status: ScanIngestionBatchStatus | string;
  image_count: number;
  failed_count: number;
  duplicate_count: number;
  ingestion_checksum: string;
  created_at: string;
  completed_at: string | null;
}

export interface ScanIngestionBatchRead extends ScanIngestionBatchSummaryRead {
  upload_session: ScanUploadSessionRead;
  images: ScanImageSummaryRead[];
  events: ScanIngestionEventRead[];
}

export interface ScanIngestionBatchListResponse {
  items: ScanIngestionBatchSummaryRead[];
  pagination: MarketApiV1Pagination;
  source_type_counts: Record<string, number>;
  duplicate_image_count: number;
  failed_image_count: number;
}

export interface ScanImageListResponse {
  items: ScanImageSummaryRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanNormalizationStatus = "PENDING" | "COMPLETE" | "FAILED";
export type ScanNormalizationOrientation = "portrait" | "rotated_left" | "rotated_right" | "upside_down";
export type ScanNormalizationArtifactType =
  | "ROTATED"
  | "CROPPED"
  | "PERSPECTIVE_FIXED"
  | "COLOR_NORMALIZED"
  | "FINAL_NORMALIZED"
  | "THUMBNAIL";

export interface ScanNormalizationRunPayload {
  scan_image_id: number;
}

export interface ScanNormalizationArtifactRead {
  id: number;
  scan_normalization_run_id: number;
  owner_user_id: number;
  scan_image_id: number;
  parent_artifact_id: number | null;
  artifact_type: ScanNormalizationArtifactType | string;
  artifact_order: number;
  storage_backend: string;
  storage_path: string;
  width: number;
  height: number;
  dpi_x: number | null;
  dpi_y: number | null;
  artifact_checksum: string;
  parent_checksum: string | null;
  normalization_status: ScanNormalizationStatus | string;
  metadata_json: Record<string, unknown>;
  preview_data_url: string | null;
  created_at: string;
}

export interface ScanNormalizationIssueRead {
  id: number;
  scan_normalization_run_id: number;
  owner_user_id: number;
  scan_image_id: number;
  issue_type: string;
  severity: string;
  normalization_status: ScanNormalizationStatus | string;
  metric_value: string | null;
  detail_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanNormalizationHistoryRead {
  id: number;
  scan_normalization_run_id: number;
  owner_user_id: number;
  scan_image_id: number;
  history_order: number;
  stage_name: string;
  event_type: string;
  from_checksum: string | null;
  to_checksum: string | null;
  detail_json: Record<string, unknown>;
  notes: string | null;
  created_at: string;
}

export interface ScanNormalizationRunSummaryRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  source_sha256_checksum: string;
  normalization_checksum: string;
  normalization_status: ScanNormalizationStatus | string;
  orientation_code: ScanNormalizationOrientation | string;
  rotation_degrees: number;
  crop_left: number;
  crop_top: number;
  crop_right: number;
  crop_bottom: number;
  perspective_strength: number;
  issue_count: number;
  artifact_count: number;
  replayed_from_run_id: number | null;
  final_artifact_id: number | null;
  summary_json: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface ScanNormalizationRunRead extends ScanNormalizationRunSummaryRead {
  artifacts: ScanNormalizationArtifactRead[];
  issues: ScanNormalizationIssueRead[];
  history: ScanNormalizationHistoryRead[];
  source_preview_data_url: string | null;
  final_preview_data_url: string | null;
}

export interface ScanNormalizationRunListResponse {
  items: ScanNormalizationRunSummaryRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  replay_safe_run_count: number;
}

export interface ScanNormalizationIssueListResponse {
  items: ScanNormalizationIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanNormalizationFailureListResponse {
  items: ScanNormalizationRunSummaryRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanBoundaryStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanBoundaryRunCreate {
  scan_image_id: number;
  normalization_run_id?: number | null;
}

export interface ScanBoundaryRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  normalization_run_id: number;
  source_artifact_id: number;
  source_checksum: string;
  boundary_checksum: string;
  boundary_status: ScanBoundaryStatus | string;
  algorithm_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface ScanBoundaryArtifactRead {
  id: number;
  owner_user_id: number;
  boundary_run_id: number;
  scan_image_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  width_px: number;
  height_px: number;
  metadata_json: Record<string, unknown>;
  preview_data_url: string | null;
  created_at: string;
}

export interface ScanBoundaryIssueRead {
  id: number;
  owner_user_id: number;
  boundary_run_id: number;
  scan_image_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanBoundaryHistoryRead {
  id: number;
  owner_user_id: number;
  boundary_run_id: number;
  scan_image_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanBoundaryRunDetail extends ScanBoundaryRunRead {
  artifacts: ScanBoundaryArtifactRead[];
  issues: ScanBoundaryIssueRead[];
  history: ScanBoundaryHistoryRead[];
  original_scan_checksum: string | null;
  normalized_source_checksum: string | null;
  source_preview_data_url: string | null;
  boundary_overlay_preview_data_url: string | null;
  cover_box_preview_data_url: string | null;
  geometry: Record<string, unknown>;
  confidence_score: number | null;
}

export interface ScanBoundaryRunListResponse {
  items: ScanBoundaryRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  low_confidence_run_count: number;
  unresolved_issue_count: number;
}

export interface ScanBoundaryIssueListResponse {
  items: ScanBoundaryIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanBoundaryFailureListResponse {
  items: ScanBoundaryRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanOcrStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanOcrRunCreate {
  scan_image_id: number;
  normalization_run_id?: number | null;
  boundary_run_id?: number | null;
}

export interface ScanOcrRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  normalization_run_id: number;
  boundary_run_id: number;
  source_artifact_id: number;
  source_checksum: string;
  ocr_checksum: string;
  ocr_status: ScanOcrStatus | string;
  ocr_engine: string;
  ocr_engine_version: string | null;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface ScanOcrTextRegionRead {
  id: number;
  owner_user_id: number;
  ocr_run_id: number;
  region_type: string;
  extracted_text: string;
  normalized_text: string | null;
  confidence_score: number;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  width_px: number;
  height_px: number;
  rotation_angle: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanOcrCandidateRead {
  id: number;
  owner_user_id: number;
  ocr_run_id: number;
  candidate_type: string;
  candidate_value: string;
  normalized_candidate_value: string | null;
  confidence_score: number;
  source_region_id: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanOcrArtifactRead {
  id: number;
  owner_user_id: number;
  ocr_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url: string | null;
  created_at: string;
}

export interface ScanOcrIssueRead {
  id: number;
  owner_user_id: number;
  ocr_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanOcrHistoryRead {
  id: number;
  owner_user_id: number;
  ocr_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanOcrRunDetail extends ScanOcrRunRead {
  regions: ScanOcrTextRegionRead[];
  candidates: ScanOcrCandidateRead[];
  artifacts: ScanOcrArtifactRead[];
  issues: ScanOcrIssueRead[];
  history: ScanOcrHistoryRead[];
  original_scan_checksum: string | null;
  normalization_checksum: string | null;
  boundary_checksum: string | null;
  source_preview_data_url: string | null;
  ocr_overlay_preview_data_url: string | null;
  ocr_region_map_preview_data_url: string | null;
  confidence_summary: Record<string, unknown>;
}

export interface ScanOcrRunListResponse {
  items: ScanOcrRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  low_confidence_count: number;
  unresolved_issue_count: number;
}

export interface ScanOcrCandidateListResponse {
  items: ScanOcrCandidateRead[];
  pagination: MarketApiV1Pagination;
  candidate_type_counts: Record<string, number>;
}

export interface ScanOcrIssueListResponse {
  items: ScanOcrIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanOcrFailureListResponse {
  items: ScanOcrRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanReconciliationStatus =
  | "PENDING"
  | "MATCH_CONFIRMED"
  | "MATCH_PROBABLE"
  | "MATCH_AMBIGUOUS"
  | "NO_MATCH_FOUND"
  | "MULTIPLE_HIGH_CONFIDENCE_MATCHES"
  | "FAILED";

export interface ScanReconciliationRunCreate {
  scan_image_id: number;
  ocr_run_id?: number | null;
}

export interface ScanReconciliationRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  normalization_run_id: number;
  boundary_run_id: number;
  ocr_run_id: number;
  source_checksum: string;
  reconciliation_checksum: string;
  reconciliation_status: ScanReconciliationStatus | string;
  reconciliation_engine_version: string;
  canonical_dataset_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface ScanReconciliationCandidateRead {
  id: number;
  owner_user_id: number;
  reconciliation_run_id: number;
  candidate_rank: number;
  canonical_comic_id: number | null;
  publisher: string | null;
  series_title: string | null;
  issue_number: string | null;
  variant_description: string | null;
  publication_date: string | null;
  confidence_score: number;
  title_similarity_score: number;
  issue_similarity_score: number;
  publisher_similarity_score: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReconciliationDecisionRead {
  id: number;
  owner_user_id: number;
  reconciliation_run_id: number;
  selected_candidate_id: number | null;
  decision_status: string;
  final_confidence_score: number;
  decision_reason: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReconciliationArtifactRead {
  id: number;
  owner_user_id: number;
  reconciliation_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url: string | null;
  created_at: string;
}

export interface ScanReconciliationIssueRead {
  id: number;
  owner_user_id: number;
  reconciliation_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReconciliationHistoryRead {
  id: number;
  owner_user_id: number;
  reconciliation_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReconciliationRunDetail extends ScanReconciliationRunRead {
  candidates: ScanReconciliationCandidateRead[];
  decision: ScanReconciliationDecisionRead | null;
  artifacts: ScanReconciliationArtifactRead[];
  issues: ScanReconciliationIssueRead[];
  history: ScanReconciliationHistoryRead[];
  original_scan_checksum: string | null;
  normalization_checksum: string | null;
  boundary_checksum: string | null;
  ocr_checksum: string | null;
  source_preview_data_url: string | null;
  selected_candidate: ScanReconciliationCandidateRead | null;
}

export interface ScanReconciliationRunListResponse {
  items: ScanReconciliationRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  ambiguous_match_count: number;
  low_confidence_count: number;
}

export interface ScanReconciliationCandidateListResponse {
  items: ScanReconciliationCandidateRead[];
  pagination: MarketApiV1Pagination;
  canonical_match_count: number;
}

export interface ScanReconciliationIssueListResponse {
  items: ScanReconciliationIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanReconciliationFailureListResponse {
  items: ScanReconciliationRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanDefectStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanDefectRunCreate {
  scan_image_id: number;
  boundary_run_id?: number | null;
  ocr_run_id?: number | null;
  reconciliation_run_id?: number | null;
}

export interface ScanDefectRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  normalization_run_id: number;
  boundary_run_id: number;
  ocr_run_id: number | null;
  reconciliation_run_id: number | null;
  source_artifact_id: number;
  source_checksum: string;
  defect_checksum: string;
  defect_status: ScanDefectStatus | string;
  detection_engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface ScanDefectRegionRead {
  id: number;
  owner_user_id: number;
  defect_run_id: number;
  region_type: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  width_px: number;
  height_px: number;
  region_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectEvidenceRead {
  id: number;
  owner_user_id: number;
  defect_run_id: number;
  region_id: number;
  evidence_type: string;
  evidence_category: string;
  severity_hint: string;
  confidence_score: number;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectArtifactRead {
  id: number;
  owner_user_id: number;
  defect_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url: string | null;
  created_at: string;
}

export interface ScanDefectIssueRead {
  id: number;
  owner_user_id: number;
  defect_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectHistoryRead {
  id: number;
  owner_user_id: number;
  defect_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectRunDetail extends ScanDefectRunRead {
  regions: ScanDefectRegionRead[];
  evidence: ScanDefectEvidenceRead[];
  artifacts: ScanDefectArtifactRead[];
  issues: ScanDefectIssueRead[];
  history: ScanDefectHistoryRead[];
  original_scan_checksum: string | null;
  normalization_checksum: string | null;
  boundary_checksum: string | null;
  ocr_checksum: string | null;
  reconciliation_checksum: string | null;
  source_preview_data_url: string | null;
  quality_gates: Array<Record<string, unknown>>;
  evidence_summary: Record<string, unknown>;
  quality_gate_counts: Record<string, number>;
}

export interface ScanDefectRunListResponse {
  items: ScanDefectRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  quality_gate_failure_count: number;
  low_confidence_evidence_count: number;
}

export interface ScanDefectRegionListResponse {
  items: ScanDefectRegionRead[];
  pagination: MarketApiV1Pagination;
  region_type_counts: Record<string, number>;
}

export interface ScanDefectEvidenceListResponse {
  items: ScanDefectEvidenceRead[];
  pagination: MarketApiV1Pagination;
  category_counts: Record<string, number>;
  low_confidence_count: number;
}

export interface ScanDefectIssueListResponse {
  items: ScanDefectIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanDefectFailureListResponse {
  items: ScanDefectRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanSpineTickStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanSpineTickRunCreate {
  scan_image_id: number;
  defect_run_id?: number | null;
}

export interface ScanSpineTickRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  defect_run_id: number;
  source_checksum: string;
  spine_tick_checksum: string;
  detection_status: ScanSpineTickStatus | string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanSpineTickEvidenceRead {
  id: number;
  owner_user_id: number;
  spine_tick_run_id: number;
  defect_evidence_id?: number | null;
  tick_rank: number;
  confidence_score: number;
  severity_hint: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  width_px: number;
  height_px: number;
  angle_degrees: number;
  edge_distance_px: number;
  spine_overlap_ratio: number;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanSpineTickArtifactRead {
  id: number;
  owner_user_id: number;
  spine_tick_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanSpineTickIssueRead {
  id: number;
  owner_user_id: number;
  spine_tick_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanSpineTickHistoryRead {
  id: number;
  owner_user_id: number;
  spine_tick_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanSpineTickRunDetail extends ScanSpineTickRunRead {
  evidence: ScanSpineTickEvidenceRead[];
  artifacts: ScanSpineTickArtifactRead[];
  issues: ScanSpineTickIssueRead[];
  history: ScanSpineTickHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  defect_checksum?: string | null;
  source_preview_data_url?: string | null;
  spine_region_preview_data_url?: string | null;
  evidence_summary: Record<string, unknown>;
}

export interface ScanSpineTickRunListResponse {
  items: ScanSpineTickRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  low_confidence_count: number;
  high_density_anomaly_count: number;
}

export interface ScanSpineTickEvidenceListResponse {
  items: ScanSpineTickEvidenceRead[];
  pagination: MarketApiV1Pagination;
  severity_hint_counts: Record<string, number>;
  low_confidence_count: number;
}

export interface ScanSpineTickIssueListResponse {
  items: ScanSpineTickIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanSpineTickFailureListResponse {
  items: ScanSpineTickRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanCornerEdgeStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanCornerEdgeRunCreate {
  scan_image_id: number;
  defect_run_id?: number | null;
}

export interface ScanCornerEdgeRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  defect_run_id: number;
  source_checksum: string;
  corner_edge_checksum: string;
  detection_status: ScanCornerEdgeStatus | string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanCornerEdgeEvidenceRead {
  id: number;
  owner_user_id: number;
  corner_edge_run_id: number;
  defect_evidence_id?: number | null;
  evidence_rank: number;
  evidence_type: string;
  confidence_score: number;
  severity_hint: string;
  region_type: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  width_px: number;
  height_px: number;
  edge_distance_px: number;
  corner_overlap_ratio: number;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanCornerEdgeArtifactRead {
  id: number;
  owner_user_id: number;
  corner_edge_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanCornerEdgeIssueRead {
  id: number;
  owner_user_id: number;
  corner_edge_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanCornerEdgeHistoryRead {
  id: number;
  owner_user_id: number;
  corner_edge_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanCornerEdgeRunDetail extends ScanCornerEdgeRunRead {
  evidence: ScanCornerEdgeEvidenceRead[];
  artifacts: ScanCornerEdgeArtifactRead[];
  issues: ScanCornerEdgeIssueRead[];
  history: ScanCornerEdgeHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  defect_checksum?: string | null;
  source_preview_data_url?: string | null;
  corner_region_preview_data_url?: string | null;
  edge_region_preview_data_url?: string | null;
  evidence_summary: Record<string, unknown>;
}

export interface ScanCornerEdgeRunListResponse {
  items: ScanCornerEdgeRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  low_confidence_count: number;
  high_density_wear_count: number;
}

export interface ScanCornerEdgeEvidenceListResponse {
  items: ScanCornerEdgeEvidenceRead[];
  pagination: MarketApiV1Pagination;
  evidence_type_counts: Record<string, number>;
  severity_hint_counts: Record<string, number>;
  low_confidence_count: number;
}

export interface ScanCornerEdgeIssueListResponse {
  items: ScanCornerEdgeIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanCornerEdgeFailureListResponse {
  items: ScanCornerEdgeRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanSurfaceDefectStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanSurfaceDefectRunCreate {
  scan_image_id: number;
  defect_run_id?: number | null;
}

export interface ScanSurfaceDefectRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  defect_run_id: number;
  source_checksum: string;
  surface_defect_checksum: string;
  detection_status: ScanSurfaceDefectStatus | string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanSurfaceDefectEvidenceRead {
  id: number;
  owner_user_id: number;
  surface_defect_run_id: number;
  defect_evidence_id?: number | null;
  evidence_rank: number;
  evidence_type: string;
  evidence_category: string;
  confidence_score: number;
  severity_hint: string;
  region_type: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  width_px: number;
  height_px: number;
  surface_area_ratio: number;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanSurfaceDefectArtifactRead {
  id: number;
  owner_user_id: number;
  surface_defect_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanSurfaceDefectIssueRead {
  id: number;
  owner_user_id: number;
  surface_defect_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanSurfaceDefectHistoryRead {
  id: number;
  owner_user_id: number;
  surface_defect_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanSurfaceDefectRunDetail extends ScanSurfaceDefectRunRead {
  evidence: ScanSurfaceDefectEvidenceRead[];
  artifacts: ScanSurfaceDefectArtifactRead[];
  issues: ScanSurfaceDefectIssueRead[];
  history: ScanSurfaceDefectHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  defect_checksum?: string | null;
  source_preview_data_url?: string | null;
  surface_region_preview_data_url?: string | null;
  evidence_summary: Record<string, unknown>;
}

export interface ScanSurfaceDefectRunListResponse {
  items: ScanSurfaceDefectRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  low_confidence_count: number;
  high_density_surface_count: number;
}

export interface ScanSurfaceDefectEvidenceListResponse {
  items: ScanSurfaceDefectEvidenceRead[];
  pagination: MarketApiV1Pagination;
  evidence_type_counts: Record<string, number>;
  evidence_category_counts: Record<string, number>;
  severity_hint_counts: Record<string, number>;
  low_confidence_count: number;
}

export interface ScanSurfaceDefectIssueListResponse {
  items: ScanSurfaceDefectIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanSurfaceDefectFailureListResponse {
  items: ScanSurfaceDefectRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanStructuralDamageStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanStructuralDamageRunCreate {
  scan_image_id: number;
  defect_run_id?: number | null;
}

export interface ScanStructuralDamageRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  defect_run_id: number;
  source_checksum: string;
  structural_damage_checksum: string;
  detection_status: ScanStructuralDamageStatus | string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanStructuralDamageEvidenceRead {
  id: number;
  owner_user_id: number;
  structural_damage_run_id: number;
  defect_evidence_id?: number | null;
  evidence_rank: number;
  evidence_type: string;
  evidence_category: string;
  confidence_score: number;
  severity_hint: string;
  region_type: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  width_px: number;
  height_px: number;
  structural_area_ratio: number;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanStructuralDamageArtifactRead {
  id: number;
  owner_user_id: number;
  structural_damage_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanStructuralDamageIssueRead {
  id: number;
  owner_user_id: number;
  structural_damage_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanStructuralDamageHistoryRead {
  id: number;
  owner_user_id: number;
  structural_damage_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanStructuralDamageRunDetail extends ScanStructuralDamageRunRead {
  evidence: ScanStructuralDamageEvidenceRead[];
  artifacts: ScanStructuralDamageArtifactRead[];
  issues: ScanStructuralDamageIssueRead[];
  history: ScanStructuralDamageHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  defect_checksum?: string | null;
  source_preview_data_url?: string | null;
  structural_region_preview_data_url?: string | null;
  evidence_summary: Record<string, unknown>;
}

export interface ScanStructuralDamageRunListResponse {
  items: ScanStructuralDamageRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  low_confidence_count: number;
  major_structural_count: number;
}

export interface ScanStructuralDamageEvidenceListResponse {
  items: ScanStructuralDamageEvidenceRead[];
  pagination: MarketApiV1Pagination;
  evidence_type_counts: Record<string, number>;
  evidence_category_counts: Record<string, number>;
  severity_hint_counts: Record<string, number>;
  low_confidence_count: number;
}

export interface ScanStructuralDamageIssueListResponse {
  items: ScanStructuralDamageIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanStructuralDamageFailureListResponse {
  items: ScanStructuralDamageRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanDefectAggregationStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanDefectAggregationRunCreate {
  scan_image_id: number;
  defect_run_id?: number | null;
}

export interface ScanDefectAggregationRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  source_checksum: string;
  aggregation_checksum: string;
  aggregation_status: ScanDefectAggregationStatus | string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanDefectAggregateClusterRead {
  id: number;
  owner_user_id: number;
  aggregation_run_id: number;
  cluster_rank: number;
  cluster_type: string;
  cluster_region: string;
  cluster_confidence: number;
  aggregate_severity_hint: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  cluster_area_ratio: number;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectAggregateEvidenceRead {
  id: number;
  owner_user_id: number;
  aggregation_run_id: number;
  cluster_id: number;
  source_detector: string;
  source_evidence_id: number;
  evidence_type: string;
  confidence_score: number;
  contribution_weight: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectAggregationArtifactRead {
  id: number;
  owner_user_id: number;
  aggregation_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanDefectAggregationIssueRead {
  id: number;
  owner_user_id: number;
  aggregation_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectAggregationHistoryRead {
  id: number;
  owner_user_id: number;
  aggregation_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanDefectAggregationRunDetail extends ScanDefectAggregationRunRead {
  clusters: ScanDefectAggregateClusterRead[];
  evidence: ScanDefectAggregateEvidenceRead[];
  artifacts: ScanDefectAggregationArtifactRead[];
  issues: ScanDefectAggregationIssueRead[];
  history: ScanDefectAggregationHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  defect_checksum?: string | null;
  spine_tick_checksum?: string | null;
  corner_edge_checksum?: string | null;
  surface_defect_checksum?: string | null;
  structural_damage_checksum?: string | null;
  source_preview_data_url?: string | null;
  region_summaries: Record<string, unknown>;
}

export interface ScanDefectAggregationRunListResponse {
  items: ScanDefectAggregationRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  low_confidence_clusters: number;
  unresolved_issue_count: number;
  aggregate_anomaly_density: number;
}

export interface ScanDefectAggregateClusterListResponse {
  items: ScanDefectAggregateClusterRead[];
  pagination: MarketApiV1Pagination;
  cluster_type_counts: Record<string, number>;
  severity_hint_counts: Record<string, number>;
  mixed_cluster_count: number;
}

export interface ScanDefectAggregateEvidenceListResponse {
  items: ScanDefectAggregateEvidenceRead[];
  pagination: MarketApiV1Pagination;
  source_detector_counts: Record<string, number>;
}

export interface ScanDefectAggregationIssueListResponse {
  items: ScanDefectAggregationIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanDefectAggregationFailureListResponse {
  items: ScanDefectAggregationRunRead[];
  pagination: MarketApiV1Pagination;
}

export type ScanGradingAssistanceStatus = "PENDING" | "COMPLETE" | "FAILED";

export interface ScanGradingAssistanceRunCreate {
  scan_image_id: number;
  aggregation_run_id?: number | null;
  reconciliation_run_id?: number | null;
}

export interface ScanGradingAssistanceRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  aggregation_run_id: number;
  reconciliation_run_id?: number | null;
  source_checksum: string;
  grading_assistance_checksum: string;
  assistance_status: ScanGradingAssistanceStatus | string;
  engine_version: string;
  rubric_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanGradingAssistanceCategoryRead {
  id: number;
  owner_user_id: number;
  grading_assistance_run_id: number;
  category_type: string;
  category_status: string;
  suggested_range_low: number;
  suggested_range_high: number;
  confidence_score: number;
  evidence_count: number;
  summary_text: string;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanGradingAssistanceFindingRead {
  id: number;
  owner_user_id: number;
  grading_assistance_run_id: number;
  category_id: number;
  source_cluster_id?: number | null;
  source_detector: string;
  finding_type: string;
  finding_severity_hint: string;
  confidence_score: number;
  grade_pressure_hint: string;
  finding_text: string;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanGradingAssistanceArtifactRead {
  id: number;
  owner_user_id: number;
  grading_assistance_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanGradingAssistanceIssueRead {
  id: number;
  owner_user_id: number;
  grading_assistance_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanGradingAssistanceHistoryRead {
  id: number;
  owner_user_id: number;
  grading_assistance_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanGradingAssistanceRunDetail extends ScanGradingAssistanceRunRead {
  categories: ScanGradingAssistanceCategoryRead[];
  findings: ScanGradingAssistanceFindingRead[];
  artifacts: ScanGradingAssistanceArtifactRead[];
  issues: ScanGradingAssistanceIssueRead[];
  history: ScanGradingAssistanceHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  defect_checksum?: string | null;
  spine_tick_checksum?: string | null;
  corner_edge_checksum?: string | null;
  surface_defect_checksum?: string | null;
  structural_damage_checksum?: string | null;
  aggregation_checksum?: string | null;
  reconciliation_checksum?: string | null;
  source_preview_data_url?: string | null;
  overall_support: Record<string, unknown>;
  review_flags: Array<Record<string, unknown>>;
}

export interface ScanGradingAssistanceRunListResponse {
  items: ScanGradingAssistanceRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  review_required_count: number;
  low_confidence_support_count: number;
}

export interface ScanGradingAssistanceCategoryListResponse {
  items: ScanGradingAssistanceCategoryRead[];
  pagination: MarketApiV1Pagination;
  category_type_counts: Record<string, number>;
  category_status_counts: Record<string, number>;
}

export interface ScanGradingAssistanceFindingListResponse {
  items: ScanGradingAssistanceFindingRead[];
  pagination: MarketApiV1Pagination;
  finding_type_counts: Record<string, number>;
  grade_pressure_hint_counts: Record<string, number>;
}

export interface ScanGradingAssistanceIssueListResponse {
  items: ScanGradingAssistanceIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanGradingAssistanceFailureListResponse {
  items: ScanGradingAssistanceRunRead[];
  pagination: MarketApiV1Pagination;
}

export interface ScanVisualEvidenceRunCreate {
  scan_image_id: number;
  aggregation_run_id?: number | null;
  grading_assistance_run_id?: number | null;
}

export interface ScanVisualEvidenceRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  aggregation_run_id?: number | null;
  grading_assistance_run_id?: number | null;
  source_checksum: string;
  visual_evidence_checksum: string;
  evidence_status: string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanVisualEvidencePackageRead {
  id: number;
  owner_user_id: number;
  visual_evidence_run_id: number;
  package_type: string;
  package_status: string;
  package_title: string;
  package_summary: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanVisualEvidenceItemRead {
  id: number;
  owner_user_id: number;
  visual_evidence_run_id: number;
  package_id: number;
  item_rank: number;
  source_system: string;
  source_record_id: number;
  item_type: string;
  item_title: string;
  item_summary: string;
  confidence_score: number;
  severity_hint?: string | null;
  region_type?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanVisualEvidenceAnnotationRead {
  id: number;
  owner_user_id: number;
  visual_evidence_run_id: number;
  item_id: number;
  annotation_type: string;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  label: string;
  confidence_score: number;
  display_order: number;
  style_hint: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanVisualEvidenceArtifactRead {
  id: number;
  owner_user_id: number;
  visual_evidence_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanVisualEvidenceIssueRead {
  id: number;
  owner_user_id: number;
  visual_evidence_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanVisualEvidenceHistoryRead {
  id: number;
  owner_user_id: number;
  visual_evidence_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanVisualEvidenceRunDetail extends ScanVisualEvidenceRunRead {
  packages: ScanVisualEvidencePackageRead[];
  items: ScanVisualEvidenceItemRead[];
  annotations: ScanVisualEvidenceAnnotationRead[];
  artifacts: ScanVisualEvidenceArtifactRead[];
  issues: ScanVisualEvidenceIssueRead[];
  history: ScanVisualEvidenceHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  ocr_checksum?: string | null;
  reconciliation_checksum?: string | null;
  defect_checksum?: string | null;
  aggregation_checksum?: string | null;
  grading_assistance_checksum?: string | null;
  source_preview_data_url?: string | null;
  overlay_preview_data_url?: string | null;
}

export interface ScanVisualEvidenceRunListResponse {
  items: ScanVisualEvidenceRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  incomplete_review_packet_count: number;
  low_confidence_package_count: number;
}

export interface ScanVisualEvidencePackageListResponse {
  items: ScanVisualEvidencePackageRead[];
  pagination: MarketApiV1Pagination;
  package_type_counts: Record<string, number>;
}

export interface ScanVisualEvidenceItemListResponse {
  items: ScanVisualEvidenceItemRead[];
  pagination: MarketApiV1Pagination;
  source_system_counts: Record<string, number>;
}

export interface ScanVisualEvidenceAnnotationListResponse {
  items: ScanVisualEvidenceAnnotationRead[];
  pagination: MarketApiV1Pagination;
  annotation_type_counts: Record<string, number>;
}

export interface ScanVisualEvidenceIssueListResponse {
  items: ScanVisualEvidenceIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanVisualEvidenceFailureListResponse {
  items: ScanVisualEvidenceRunRead[];
  pagination: MarketApiV1Pagination;
}

export interface ScanReviewSessionCreate {
  scan_image_id: number;
  visual_evidence_run_id?: number | null;
  grading_assistance_run_id?: number | null;
  reconciliation_run_id?: number | null;
}

export interface ScanReviewDecisionCreate {
  decision_type: string;
  decision_status: string;
  decision_value: string;
  confidence_score?: number | null;
  reason_text: string;
  metadata_json?: Record<string, unknown>;
}

export interface ScanReviewNoteCreate {
  note_type: string;
  note_text: string;
  source_system?: string | null;
  source_record_id?: number | null;
  metadata_json?: Record<string, unknown>;
}

export interface ScanReviewEvidenceActionCreate {
  source_system: string;
  source_record_id: number;
  action_type: string;
  action_status: string;
  reason_text: string;
  metadata_json?: Record<string, unknown>;
}

export interface ScanReviewSessionRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  visual_evidence_run_id?: number | null;
  grading_assistance_run_id?: number | null;
  reconciliation_run_id?: number | null;
  review_status: string;
  review_checksum: string;
  snapshot_checksum: string;
  reviewer_user_id?: number | null;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface ScanReviewDecisionRead {
  id: number;
  owner_user_id: number;
  review_session_id: number;
  decision_type: string;
  decision_status: string;
  decision_value: string;
  confidence_score?: number | null;
  reason_text: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReviewNoteRead {
  id: number;
  owner_user_id: number;
  review_session_id: number;
  note_type: string;
  note_text: string;
  source_system?: string | null;
  source_record_id?: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReviewEvidenceActionRead {
  id: number;
  owner_user_id: number;
  review_session_id: number;
  source_system: string;
  source_record_id: number;
  action_type: string;
  action_status: string;
  reason_text: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReviewArtifactRead {
  id: number;
  owner_user_id: number;
  review_session_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanReviewIssueRead {
  id: number;
  owner_user_id: number;
  review_session_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReviewHistoryRead {
  id: number;
  owner_user_id: number;
  review_session_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReviewSessionDetail extends ScanReviewSessionRead {
  decisions: ScanReviewDecisionRead[];
  notes: ScanReviewNoteRead[];
  evidence_actions: ScanReviewEvidenceActionRead[];
  artifacts: ScanReviewArtifactRead[];
  issues: ScanReviewIssueRead[];
  history: ScanReviewHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  ocr_checksum?: string | null;
  reconciliation_checksum?: string | null;
  defect_checksum?: string | null;
  aggregation_checksum?: string | null;
  grading_assistance_checksum?: string | null;
  visual_evidence_checksum?: string | null;
  source_preview_data_url?: string | null;
  review_snapshot: Record<string, unknown>;
}

export interface ScanReviewSessionListResponse {
  items: ScanReviewSessionRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  blocked_review_count: number;
  rescan_request_count: number;
  completed_review_count: number;
}

export interface ScanReviewIssueListResponse {
  items: ScanReviewIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanHistoricalComparisonRunCreate {
  scan_image_id: number;
  reconciliation_run_id?: number | null;
  visual_evidence_run_id?: number | null;
  review_session_id?: number | null;
  max_prior_scans?: number;
}

export interface ScanHistoricalComparisonRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  reconciliation_run_id?: number | null;
  visual_evidence_run_id?: number | null;
  review_session_id?: number | null;
  source_checksum: string;
  historical_comparison_checksum: string;
  comparison_status: string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanHistoricalComparisonPairRead {
  id: number;
  owner_user_id: number;
  comparison_run_id: number;
  current_scan_image_id: number;
  prior_scan_image_id: number;
  current_identity_key: string;
  prior_identity_key: string;
  match_basis: string;
  match_confidence: number;
  current_checksum: string;
  prior_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanHistoricalComparisonDeltaRead {
  id: number;
  owner_user_id: number;
  comparison_run_id: number;
  pair_id: number;
  delta_rank: number;
  delta_type: string;
  delta_category: string;
  delta_direction: string;
  confidence_score: number;
  severity_hint: string;
  region_type?: string | null;
  x_min: number;
  y_min: number;
  x_max: number;
  y_max: number;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanHistoricalComparisonArtifactRead {
  id: number;
  owner_user_id: number;
  comparison_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanHistoricalComparisonIssueRead {
  id: number;
  owner_user_id: number;
  comparison_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanHistoricalComparisonHistoryRead {
  id: number;
  owner_user_id: number;
  comparison_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanHistoricalComparisonRunDetail extends ScanHistoricalComparisonRunRead {
  pairs: ScanHistoricalComparisonPairRead[];
  deltas: ScanHistoricalComparisonDeltaRead[];
  artifacts: ScanHistoricalComparisonArtifactRead[];
  issues: ScanHistoricalComparisonIssueRead[];
  history: ScanHistoricalComparisonHistoryRead[];
  current_original_scan_checksum?: string | null;
  current_normalization_checksum?: string | null;
  current_boundary_checksum?: string | null;
  current_reconciliation_checksum?: string | null;
  current_aggregation_checksum?: string | null;
  current_grading_assistance_checksum?: string | null;
  current_review_checksum?: string | null;
  prior_lineage: Array<Record<string, unknown>>;
  current_preview_data_url?: string | null;
  side_by_side_preview_data_url?: string | null;
  delta_overlay_preview_data_url?: string | null;
}

export interface ScanHistoricalComparisonRunListResponse {
  items: ScanHistoricalComparisonRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  inconclusive_count: number;
  scans_with_prior_history_count: number;
}

export interface ScanHistoricalComparisonPairListResponse {
  items: ScanHistoricalComparisonPairRead[];
  pagination: MarketApiV1Pagination;
  match_basis_counts: Record<string, number>;
}

export interface ScanHistoricalComparisonDeltaListResponse {
  items: ScanHistoricalComparisonDeltaRead[];
  pagination: MarketApiV1Pagination;
  delta_type_counts: Record<string, number>;
  delta_direction_counts: Record<string, number>;
}

export interface ScanHistoricalComparisonIssueListResponse {
  items: ScanHistoricalComparisonIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanAuthenticationRunCreate {
  scan_image_id: number;
  reconciliation_run_id?: number | null;
  visual_evidence_run_id?: number | null;
  historical_comparison_run_id?: number | null;
  review_session_id?: number | null;
}

export interface ScanAuthenticationRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  reconciliation_run_id?: number | null;
  visual_evidence_run_id?: number | null;
  historical_comparison_run_id?: number | null;
  review_session_id?: number | null;
  source_checksum: string;
  authentication_checksum: string;
  authentication_status: string;
  engine_version: string;
  rubric_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanAuthenticationSignalRead {
  id: number;
  owner_user_id: number;
  authentication_run_id: number;
  signal_rank: number;
  signal_type: string;
  signal_category: string;
  signal_status: string;
  confidence_score: number;
  source_system: string;
  source_record_id?: number | null;
  measurement_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanAuthenticationFindingRead {
  id: number;
  owner_user_id: number;
  authentication_run_id: number;
  finding_rank: number;
  finding_type: string;
  finding_status: string;
  confidence_score: number;
  review_priority: string;
  finding_text: string;
  source_signal_ids_json: number[];
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanAuthenticationArtifactRead {
  id: number;
  owner_user_id: number;
  authentication_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  preview_data_url?: string | null;
  created_at: string;
}

export interface ScanAuthenticationIssueRead {
  id: number;
  owner_user_id: number;
  authentication_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanAuthenticationHistoryRead {
  id: number;
  owner_user_id: number;
  authentication_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanAuthenticationRunDetail extends ScanAuthenticationRunRead {
  signals: ScanAuthenticationSignalRead[];
  findings: ScanAuthenticationFindingRead[];
  artifacts: ScanAuthenticationArtifactRead[];
  issues: ScanAuthenticationIssueRead[];
  history: ScanAuthenticationHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  ocr_checksum?: string | null;
  reconciliation_checksum?: string | null;
  visual_evidence_checksum?: string | null;
  historical_comparison_checksum?: string | null;
  review_checksum?: string | null;
  source_preview_data_url?: string | null;
  review_flag_count: number;
}

export interface ScanAuthenticationRunListResponse {
  items: ScanAuthenticationRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  unresolved_conflict_count: number;
  review_required_count: number;
}

export interface ScanAuthenticationSignalListResponse {
  items: ScanAuthenticationSignalRead[];
  pagination: MarketApiV1Pagination;
  signal_status_counts: Record<string, number>;
}

export interface ScanAuthenticationFindingListResponse {
  items: ScanAuthenticationFindingRead[];
  pagination: MarketApiV1Pagination;
  finding_status_counts: Record<string, number>;
  review_priority_counts: Record<string, number>;
}

export interface ScanAuthenticationIssueListResponse {
  items: ScanAuthenticationIssueRead[];
  pagination: MarketApiV1Pagination;
  issue_type_counts: Record<string, number>;
}

export interface ScanIntelligenceFeedRunCreate {
  scan_image_id: number;
  reconciliation_run_id?: number | null;
  grading_assistance_run_id?: number | null;
  visual_evidence_run_id?: number | null;
  review_session_id?: number | null;
  historical_comparison_run_id?: number | null;
  authentication_run_id?: number | null;
}

export interface ScanIntelligenceFeedRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id: number;
  upload_session_id?: number | null;
  ingestion_batch_id?: number | null;
  normalization_run_id?: number | null;
  boundary_run_id?: number | null;
  ocr_run_id?: number | null;
  reconciliation_run_id?: number | null;
  defect_run_id?: number | null;
  spine_tick_run_id?: number | null;
  corner_edge_run_id?: number | null;
  surface_defect_run_id?: number | null;
  structural_damage_run_id?: number | null;
  defect_aggregation_run_id?: number | null;
  grading_assistance_run_id?: number | null;
  visual_evidence_run_id?: number | null;
  review_session_id?: number | null;
  historical_comparison_run_id?: number | null;
  authentication_run_id?: number | null;
  source_checksum: string;
  feed_checksum: string;
  feed_status: string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  total_events: number;
  total_issues: number;
  review_required_count: number;
  error_count: number;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanIntelligenceFeedEventRead {
  id: number;
  owner_user_id: number;
  feed_run_id: number;
  event_rank: number;
  timeline_rank: number;
  event_category: string;
  event_type: string;
  severity: string;
  source_system: string;
  event_occurred_at: string;
  source_record_id?: number | null;
  source_checksum?: string | null;
  lineage_checksum?: string | null;
  event_key: string;
  event_payload_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanIntelligenceFeedArtifactRead {
  id: number;
  owner_user_id: number;
  feed_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  media_type?: string | null;
  text_preview?: string | null;
  body_base64?: string | null;
  created_at: string;
}

export interface ScanIntelligenceFeedIssueRead {
  id: number;
  owner_user_id: number;
  feed_run_id: number;
  issue_type: string;
  severity: string;
  source_system: string;
  source_record_id?: number | null;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanIntelligenceFeedHistoryRead {
  id: number;
  owner_user_id: number;
  feed_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanIntelligenceFeedRunDetail extends ScanIntelligenceFeedRunRead {
  events: ScanIntelligenceFeedEventRead[];
  artifacts: ScanIntelligenceFeedArtifactRead[];
  issues: ScanIntelligenceFeedIssueRead[];
  history: ScanIntelligenceFeedHistoryRead[];
  original_scan_checksum?: string | null;
  normalization_checksum?: string | null;
  boundary_checksum?: string | null;
  ocr_checksum?: string | null;
  reconciliation_checksum?: string | null;
  defect_checksum?: string | null;
  spine_tick_checksum?: string | null;
  corner_edge_checksum?: string | null;
  surface_defect_checksum?: string | null;
  structural_damage_checksum?: string | null;
  defect_aggregation_checksum?: string | null;
  grading_assistance_checksum?: string | null;
  visual_evidence_checksum?: string | null;
  review_checksum?: string | null;
  historical_comparison_checksum?: string | null;
  authentication_checksum?: string | null;
}

export interface ScanIntelligenceFeedRunListResponse {
  items: ScanIntelligenceFeedRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  total_event_count: number;
  total_review_required_count: number;
  total_error_count: number;
}

export interface ScanIntelligenceFeedEventListResponse {
  items: ScanIntelligenceFeedEventRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
  category_counts: Record<string, number>;
  source_system_counts: Record<string, number>;
}

export interface ScanIntelligenceFeedIssueListResponse {
  items: ScanIntelligenceFeedIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
  issue_type_counts: Record<string, number>;
  source_system_counts: Record<string, number>;
}

export interface ScanReplayRunCreate {
  scan_image_id?: number | null;
  replay_scope: "SINGLE_SCAN" | "FULL_P40_PIPELINE" | "SELECTED_STAGE" | "OPS_AUDIT" | "BATCH_REPLAY";
  selected_phase_key?: string | null;
}

export interface ScanReplayRunRead {
  id: number;
  owner_user_id: number;
  scan_image_id?: number | null;
  replay_scope: string;
  source_checksum: string;
  replay_checksum: string;
  replay_status: string;
  engine_version: string;
  input_manifest_json: Record<string, unknown>;
  output_manifest_json: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
}

export interface ScanReplayStepRead {
  id: number;
  owner_user_id: number;
  replay_run_id: number;
  step_rank: number;
  phase_key: string;
  source_record_id?: number | null;
  expected_checksum?: string | null;
  observed_checksum?: string | null;
  replay_step_status: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReplayCheckRead {
  id: number;
  owner_user_id: number;
  replay_run_id: number;
  step_id?: number | null;
  check_type: string;
  check_status: string;
  expected_value?: string | null;
  observed_value?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReplayDiscrepancyRead {
  id: number;
  owner_user_id: number;
  replay_run_id: number;
  step_id?: number | null;
  discrepancy_type: string;
  severity: string;
  expected_value?: string | null;
  observed_value?: string | null;
  discrepancy_message: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReplayArtifactRead {
  id: number;
  owner_user_id: number;
  replay_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  media_type?: string | null;
  text_preview?: string | null;
  body_base64?: string | null;
  created_at: string;
}

export interface ScanReplayIssueRead {
  id: number;
  owner_user_id: number;
  replay_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReplayHistoryRead {
  id: number;
  owner_user_id: number;
  replay_run_id: number;
  event_type: string;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface ScanReplayRunDetail extends ScanReplayRunRead {
  steps: ScanReplayStepRead[];
  checks: ScanReplayCheckRead[];
  discrepancies: ScanReplayDiscrepancyRead[];
  artifacts: ScanReplayArtifactRead[];
  issues: ScanReplayIssueRead[];
  history: ScanReplayHistoryRead[];
  original_scan_checksum?: string | null;
  scan_feed_checksum?: string | null;
  lineage_chain: Array<Record<string, unknown>>;
  critical_discrepancy_count: number;
}

export interface ScanReplayRunListResponse {
  items: ScanReplayRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  critical_discrepancy_count: number;
  mismatch_count: number;
}

export interface ScanReplayStepListResponse {
  items: ScanReplayStepRead[];
  pagination: MarketApiV1Pagination;
  step_status_counts: Record<string, number>;
}

export interface ScanReplayCheckListResponse {
  items: ScanReplayCheckRead[];
  pagination: MarketApiV1Pagination;
  check_status_counts: Record<string, number>;
  check_type_counts: Record<string, number>;
}

export interface ScanReplayDiscrepancyListResponse {
  items: ScanReplayDiscrepancyRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
  discrepancy_type_counts: Record<string, number>;
}

export interface ScanReplayIssueListResponse {
  items: ScanReplayIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
  issue_type_counts: Record<string, number>;
}

export interface AutomationJobCreate {
  queue_key: string;
  queue_name?: string | null;
  queue_category:
    | "SCAN_PIPELINE"
    | "REPLAY"
    | "NOTIFICATION"
    | "MAINTENANCE"
    | "BATCH"
    | "REVIEW"
    | "SYSTEM";
  organization_id?: number | null;
  parent_job_id?: number | null;
  job_key: string;
  job_type: string;
  priority: "LOW" | "NORMAL" | "HIGH" | "CRITICAL";
  payload_snapshot_json: Record<string, unknown>;
  source_record_type?: string | null;
  source_record_id?: number | null;
  source_checksum?: string | null;
  available_at?: string | null;
  max_attempts?: number;
  replay_safe?: boolean;
  idempotency_key?: string | null;
  metadata_json?: Record<string, unknown>;
}

export interface AutomationQueueRead {
  id: number;
  queue_key: string;
  queue_name: string;
  queue_category: string;
  queue_status: string;
  deterministic_ordering_enabled: boolean;
  max_concurrency: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
  total_jobs: number;
  pending_jobs: number;
  failed_jobs: number;
  dead_letter_jobs: number;
  reserved_jobs: number;
}

export interface AutomationJobAttemptRead {
  id: number;
  job_id: number;
  attempt_number: number;
  attempt_status: string;
  worker_identifier?: string | null;
  started_at: string;
  completed_at?: string | null;
  failure_reason?: string | null;
  execution_time_ms?: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationJobDependencyRead {
  id: number;
  job_id: number;
  depends_on_job_id: number;
  dependency_status: string;
  created_at: string;
}

export interface AutomationJobArtifactRead {
  id: number;
  job_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  media_type?: string | null;
  text_preview?: string | null;
  body_base64?: string | null;
  created_at: string;
}

export interface AutomationJobIssueRead {
  id: number;
  job_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationJobHistoryRead {
  id: number;
  job_id: number;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationJobRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  queue_id: number;
  parent_job_id?: number | null;
  job_key: string;
  job_type: string;
  job_status: string;
  priority: string;
  deterministic_rank: number;
  payload_snapshot_json: Record<string, unknown>;
  payload_checksum: string;
  source_record_type?: string | null;
  source_record_id?: number | null;
  source_checksum?: string | null;
  reservation_token?: string | null;
  reserved_until?: string | null;
  available_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  failed_at?: string | null;
  max_attempts: number;
  current_attempt_count: number;
  replay_safe: boolean;
  idempotency_key?: string | null;
  job_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
  queue_key?: string | null;
  queue_name?: string | null;
  queue_status?: string | null;
}

export interface AutomationJobDetail extends AutomationJobRead {
  attempts: AutomationJobAttemptRead[];
  dependencies: AutomationJobDependencyRead[];
  artifacts: AutomationJobArtifactRead[];
  issues: AutomationJobIssueRead[];
  history: AutomationJobHistoryRead[];
  dependency_graph: Array<Record<string, unknown>>;
}

export interface AutomationJobListResponse {
  items: AutomationJobRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  priority_counts: Record<string, number>;
  queue_counts: Record<string, number>;
  failed_job_count: number;
  dead_letter_count: number;
  reserved_job_count: number;
}

export interface AutomationQueueListResponse {
  items: AutomationQueueRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  queue_category_counts: Record<string, number>;
}

export interface AutomationJobAttemptListResponse {
  items: AutomationJobAttemptRead[];
  pagination: MarketApiV1Pagination;
}

export interface AutomationJobHistoryListResponse {
  items: AutomationJobHistoryRead[];
  pagination: MarketApiV1Pagination;
}

export interface AutomationJobIssueListResponse {
  items: AutomationJobIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
}

export interface AutomationWorkerRead {
  id: number;
  worker_key: string;
  worker_identifier: string;
  worker_type: string;
  worker_status: string;
  process_identifier?: string | null;
  hostname?: string | null;
  queue_scope_json: Record<string, unknown>;
  current_job_id?: number | null;
  max_concurrency: number;
  last_heartbeat_at?: string | null;
  startup_at: string;
  shutdown_at?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  active_lease_count: number;
  active_execution_count: number;
  stale: boolean;
  heartbeat_age_seconds?: number | null;
}

export interface AutomationWorkerHeartbeatRead {
  id: number;
  worker_id: number;
  heartbeat_status: string;
  active_job_count: number;
  memory_usage_mb?: number | null;
  cpu_usage_percent?: number | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkerLeaseRead {
  id: number;
  worker_id: number;
  job_id: number;
  reservation_token: string;
  lease_status: string;
  lease_expires_at: string;
  acquired_at: string;
  released_at?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkerExecutionRead {
  id: number;
  worker_id: number;
  job_id: number;
  execution_status: string;
  execution_rank: number;
  started_at: string;
  completed_at?: string | null;
  execution_time_ms?: number | null;
  execution_snapshot_json: Record<string, unknown>;
  execution_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkerIssueRead {
  id: number;
  worker_id: number;
  job_id?: number | null;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkerHistoryRead {
  id: number;
  worker_id: number;
  job_id?: number | null;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkerDetail extends AutomationWorkerRead {
  heartbeats: AutomationWorkerHeartbeatRead[];
  leases: AutomationWorkerLeaseRead[];
  executions: AutomationWorkerExecutionRead[];
  issues: AutomationWorkerIssueRead[];
  history: AutomationWorkerHistoryRead[];
}

export interface AutomationWorkerListResponse {
  items: AutomationWorkerRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  worker_type_counts: Record<string, number>;
  stale_count: number;
  active_execution_count: number;
  runtime_issue_count: number;
}

export interface AutomationWorkerExecutionListResponse {
  items: AutomationWorkerExecutionRead[];
  pagination: MarketApiV1Pagination;
  execution_status_counts: Record<string, number>;
}

export interface AutomationWorkerHistoryListResponse {
  items: AutomationWorkerHistoryRead[];
  pagination: MarketApiV1Pagination;
}

export interface AutomationWorkerIssueListResponse {
  items: AutomationWorkerIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
}

export interface AutomationScheduleCreate {
  schedule_name: string;
  schedule_type: string;
  cron_expression?: string | null;
  interval_seconds?: number | null;
  next_run_at?: string | null;
  replay_safe?: boolean;
  metadata_json?: Record<string, unknown>;
  workflow_key?: string | null;
}

export interface AutomationTriggerCreate {
  trigger_type: string;
  source_event_type: string;
  source_record_type?: string | null;
  source_record_id?: number | null;
  source_checksum?: string | null;
  trigger_payload_json?: Record<string, unknown>;
  metadata_json?: Record<string, unknown>;
  workflow_key?: string | null;
}

export interface AutomationScheduleRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  schedule_key: string;
  schedule_name: string;
  schedule_type: string;
  schedule_status: string;
  cron_expression?: string | null;
  interval_seconds?: number | null;
  next_run_at?: string | null;
  last_run_at?: string | null;
  replay_safe: boolean;
  deterministic_ordering_enabled: boolean;
  schedule_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationTriggerRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  trigger_key: string;
  trigger_type: string;
  trigger_status: string;
  source_event_type: string;
  source_record_type?: string | null;
  source_record_id?: number | null;
  source_checksum?: string | null;
  trigger_payload_json: Record<string, unknown>;
  trigger_checksum: string;
  triggered_at: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkflowStepRead {
  id: number;
  workflow_id: number;
  step_rank: number;
  step_key: string;
  job_type: string;
  dependency_mode: string;
  delay_seconds?: number | null;
  required_success: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkflowExecutionRead {
  id: number;
  workflow_id: number;
  trigger_id?: number | null;
  schedule_id?: number | null;
  execution_status: string;
  execution_checksum: string;
  execution_manifest_json: Record<string, unknown>;
  started_at: string;
  completed_at?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkflowIssueRead {
  id: number;
  workflow_id: number;
  execution_id?: number | null;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkflowHistoryRead {
  id: number;
  workflow_id: number;
  execution_id?: number | null;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationWorkflowRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  workflow_key: string;
  workflow_name: string;
  workflow_status: string;
  workflow_category: string;
  replay_safe: boolean;
  deterministic_ordering_enabled: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
  steps: AutomationWorkflowStepRead[];
  latest_execution?: AutomationWorkflowExecutionRead | null;
  blocked_step_count: number;
  pending_trigger_count: number;
}

export interface AutomationScheduleListResponse {
  items: AutomationScheduleRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  type_counts: Record<string, number>;
}

export interface AutomationTriggerListResponse {
  items: AutomationTriggerRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  type_counts: Record<string, number>;
  pending_trigger_count: number;
}

export interface AutomationWorkflowListResponse {
  items: AutomationWorkflowRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  category_counts: Record<string, number>;
  blocked_workflow_count: number;
  failed_execution_count: number;
}

export interface AutomationWorkflowExecutionListResponse {
  items: AutomationWorkflowExecutionRead[];
  pagination: MarketApiV1Pagination;
  execution_status_counts: Record<string, number>;
}

export interface AutomationWorkflowHistoryListResponse {
  items: AutomationWorkflowHistoryRead[];
  pagination: MarketApiV1Pagination;
}

export interface AutomationWorkflowIssueListResponse {
  items: AutomationWorkflowIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
}

export interface AutomationRetryPolicyRead {
  id: number;
  policy_key: string;
  policy_name: string;
  retry_mode: string;
  max_attempts: number;
  base_delay_seconds: number;
  max_delay_seconds: number;
  deterministic_backoff_enabled: boolean;
  dead_letter_enabled: boolean;
  replay_safe: boolean;
  policy_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRecoveryArtifactRead {
  id: number;
  recovery_run_id: number;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRecoveryHistoryRead {
  id: number;
  recovery_run_id: number;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRecoveryIssueRead {
  id: number;
  recovery_run_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationFailureEventRead {
  id: number;
  job_id?: number | null;
  worker_execution_id?: number | null;
  failure_type: string;
  failure_severity: string;
  failure_snapshot_json: Record<string, unknown>;
  failure_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationDeadLetterRead {
  id: number;
  original_job_id: number;
  dead_letter_reason: string;
  dead_letter_status: string;
  failure_count: number;
  source_checksum?: string | null;
  dead_letter_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRecoveryRunRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  job_id: number;
  worker_execution_id?: number | null;
  retry_policy_id?: number | null;
  recovery_status: string;
  recovery_type: string;
  recovery_rank: number;
  recovery_checksum: string;
  recovery_manifest_json: Record<string, unknown>;
  started_at: string;
  completed_at?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  retry_policy?: AutomationRetryPolicyRead | null;
  dead_letter?: AutomationDeadLetterRead | null;
  failure_events: AutomationFailureEventRead[];
  artifacts: AutomationRecoveryArtifactRead[];
  issues: AutomationRecoveryIssueRead[];
  history: AutomationRecoveryHistoryRead[];
}

export interface AutomationRecoveryListResponse {
  items: AutomationRecoveryRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  recovery_type_counts: Record<string, number>;
  dead_letter_count: number;
  critical_failure_count: number;
}

export interface AutomationDeadLetterListResponse {
  items: AutomationDeadLetterRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
}

export interface AutomationFailureEventListResponse {
  items: AutomationFailureEventRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
}

export interface AutomationRecoveryIssueListResponse {
  items: AutomationRecoveryIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
}

export interface AutomationBatchArtifactRead {
  id: number;
  batch_run_id?: number | null;
  maintenance_job_id?: number | null;
  artifact_type: string;
  storage_backend: string;
  storage_path: string;
  artifact_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationBatchIssueRead {
  id: number;
  batch_run_id?: number | null;
  maintenance_job_id?: number | null;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationBatchHistoryRead {
  id: number;
  batch_run_id?: number | null;
  maintenance_job_id?: number | null;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationBatchChunkRead {
  id: number;
  batch_run_id: number;
  chunk_rank: number;
  chunk_status: string;
  partition_key: string;
  item_start: number;
  item_end: number;
  item_count: number;
  chunk_checksum: string;
  worker_execution_id?: number | null;
  started_at?: string | null;
  completed_at?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationMaintenanceResultRead {
  id: number;
  maintenance_job_id: number;
  result_type: string;
  result_status: string;
  result_snapshot_json: Record<string, unknown>;
  result_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationMaintenanceJobRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  maintenance_key: string;
  maintenance_type: string;
  maintenance_status: string;
  maintenance_scope: string;
  replay_safe: boolean;
  maintenance_checksum: string;
  metadata_json: Record<string, unknown>;
  started_at: string;
  completed_at?: string | null;
  created_at: string;
  results: AutomationMaintenanceResultRead[];
}

export interface AutomationBatchRunRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  batch_key: string;
  batch_type: string;
  batch_status: string;
  source_scope: string;
  deterministic_partitioning_enabled: boolean;
  replay_safe: boolean;
  total_item_count: number;
  completed_item_count: number;
  failed_item_count: number;
  batch_checksum: string;
  manifest_json: Record<string, unknown>;
  started_at: string;
  completed_at?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
  chunks: AutomationBatchChunkRead[];
  maintenance_jobs: AutomationMaintenanceJobRead[];
  artifacts: AutomationBatchArtifactRead[];
  issues: AutomationBatchIssueRead[];
  history: AutomationBatchHistoryRead[];
}

export interface AutomationBatchListResponse {
  items: AutomationBatchRunRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  batch_type_counts: Record<string, number>;
  failed_batch_count: number;
  maintenance_job_count: number;
  integrity_audit_count: number;
}

export interface AutomationBatchChunkListResponse {
  items: AutomationBatchChunkRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
}

export interface AutomationMaintenanceJobListResponse {
  items: AutomationMaintenanceJobRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  maintenance_type_counts: Record<string, number>;
}

export interface AutomationMaintenanceResultListResponse {
  items: AutomationMaintenanceResultRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
}

export interface AutomationBatchIssueListResponse {
  items: AutomationBatchIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
}

export interface AutomationNotificationArtifactRead {
  artifact_type: string;
  storage_path: string;
  artifact_checksum: string;
}

export interface AutomationNotificationDeliveryRead {
  id: number;
  notification_id: number;
  delivery_channel: string;
  delivery_status: string;
  delivery_rank: number;
  destination_key: string;
  attempted_at?: string | null;
  delivered_at?: string | null;
  failure_reason?: string | null;
  delivery_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationNotificationPreferenceRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  preference_key: string;
  notification_type: string;
  delivery_channel: string;
  enabled: boolean;
  escalation_enabled: boolean;
  quiet_hours_json?: Record<string, unknown> | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationAlertRead {
  id: number;
  alert_key: string;
  alert_type: string;
  alert_severity: string;
  alert_status: string;
  source_notification_id?: number | null;
  escalation_level: string;
  alert_checksum: string;
  replay_safe: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
  acknowledged_at?: string | null;
}

export interface AutomationNotificationIssueRead {
  id: number;
  notification_id?: number | null;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationNotificationHistoryRead {
  id: number;
  notification_id?: number | null;
  alert_id?: number | null;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  event_message: string;
  event_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationNotificationRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  notification_key: string;
  notification_type: string;
  notification_status: string;
  source_event_type: string;
  source_record_type?: string | null;
  source_record_id?: number | null;
  source_checksum?: string | null;
  notification_payload_json: Record<string, unknown>;
  notification_checksum: string;
  replay_safe: boolean;
  created_at: string;
  delivered_at?: string | null;
  metadata_json: Record<string, unknown>;
  rendered_subject?: string | null;
  rendered_body?: string | null;
  notification_manifest_json: Record<string, unknown>;
  deliveries: AutomationNotificationDeliveryRead[];
  alerts: AutomationAlertRead[];
  issues: AutomationNotificationIssueRead[];
  history: AutomationNotificationHistoryRead[];
  artifacts: AutomationNotificationArtifactRead[];
}

export interface AutomationNotificationListResponse {
  items: AutomationNotificationRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  type_counts: Record<string, number>;
  queued_count: number;
  failed_delivery_count: number;
  active_alert_count: number;
  critical_alert_count: number;
}

export interface AutomationAlertListResponse {
  items: AutomationAlertRead[];
  pagination: MarketApiV1Pagination;
  status_counts: Record<string, number>;
  severity_counts: Record<string, number>;
}

export interface AutomationNotificationPreferenceListResponse {
  items: AutomationNotificationPreferenceRead[];
  pagination: MarketApiV1Pagination;
}

export interface AutomationNotificationIssueListResponse {
  items: AutomationNotificationIssueRead[];
  pagination: MarketApiV1Pagination;
  severity_counts: Record<string, number>;
}

export interface AutomationOpsSnapshotRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  snapshot_key: string;
  snapshot_type: string;
  snapshot_status: string;
  queue_depth: number;
  active_workers: number;
  active_workflows: number;
  failed_jobs: number;
  dead_letter_count: number;
  replay_warning_count: number;
  checksum_warning_count: number;
  snapshot_checksum: string;
  snapshot_manifest_json: Record<string, unknown>;
  replay_safe: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationOpsMetricRead {
  id: number;
  snapshot_id: number;
  metric_key: string;
  metric_category: string;
  metric_value: string;
  metric_status: string;
  metric_rank: number;
  metric_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationOpsAuditRead {
  id: number;
  owner_user_id?: number | null;
  snapshot_id?: number | null;
  audit_key: string;
  audit_type: string;
  audit_status: string;
  audit_scope: string;
  replay_safe: boolean;
  audit_checksum: string;
  audit_result_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationOpsIssueRead {
  id: number;
  snapshot_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationOpsListResponse {
  items: AutomationOpsSnapshotRead[] | AutomationOpsMetricRead[] | AutomationOpsAuditRead[] | AutomationOpsIssueRead[];
  pagination: MarketApiV1Pagination;
  replay_warning_count?: number;
  critical_issue_count?: number;
  failed_audit_count?: number;
}

export interface AutomationOpsSystemHealthRead {
  snapshot_status: string;
  queue_depth: number;
  active_workers: number;
  failed_jobs: number;
  dead_letter_count: number;
  replay_warning_count: number;
  checksum_warning_count: number;
  critical_issue_count: number;
  failed_audit_count: number;
  latest_snapshot_id?: number | null;
  latest_snapshot_checksum?: string | null;
}

export interface AutomationAnalyticsSnapshotRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  snapshot_key: string;
  analytics_type: string;
  analytics_scope: string;
  analytics_status: string;
  replay_safe: boolean;
  deterministic_ordering_enabled: boolean;
  snapshot_checksum: string;
  snapshot_manifest_json: Record<string, unknown>;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationAnalyticsMetricRead {
  id: number;
  snapshot_id: number;
  metric_key: string;
  metric_category: string;
  metric_value: string;
  metric_delta?: string | null;
  metric_status: string;
  metric_rank: number;
  metric_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationAnalyticsTrendRead {
  id: number;
  snapshot_id: number;
  trend_key: string;
  trend_type: string;
  trend_direction: string;
  historical_window: number;
  trend_value: string;
  trend_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationAnalyticsComparisonRead {
  id: number;
  snapshot_id: number;
  comparison_key: string;
  comparison_type: string;
  baseline_snapshot_id?: number | null;
  comparison_result_json: Record<string, unknown>;
  comparison_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationAnalyticsIssueRead {
  id: number;
  snapshot_id: number;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationAnalyticsListResponse {
  items: AutomationAnalyticsSnapshotRead[] | AutomationAnalyticsMetricRead[] | AutomationAnalyticsTrendRead[] | AutomationAnalyticsComparisonRead[] | AutomationAnalyticsIssueRead[];
  pagination: MarketApiV1Pagination;
  replay_drift_count?: number;
  failure_warning_count?: number;
  utilization_warning_count?: number;
}

export interface AutomationAnalyticsSystemIntelligenceRead {
  analytics_status: string;
  queue_throughput: number;
  worker_utilization: string;
  failure_rate: string;
  replay_warning_trend_count: number;
  dead_letter_growth: number;
  workflow_throughput: number;
  notification_delivery_rate: string;
  batch_completion_rate: string;
  latest_snapshot_id?: number | null;
  latest_snapshot_checksum?: string | null;
}

export interface OrganizationCreateRequest {
  display_name: string;
  slug?: string | null;
  organization_type?: string;
}

export interface OrganizationInviteRequest {
  email: string;
  expires_in_days?: number;
}

export interface OrganizationArchiveRequest {
  reason?: string | null;
}

export interface OrganizationRoleAssignmentRequest {
  role_key: string;
}

export interface OrganizationResponse {
  id: number;
  public_id: string;
  owner_user_id: number;
  display_name: string;
  slug: string;
  organization_type: string;
  status: string;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;
  active_member_count: number;
  pending_invitation_count: number;
  current_user_role_keys: string[];
  current_user_permission_keys: string[];
}

export interface OrganizationMemberResponse {
  id: number;
  organization_id: number;
  user_id: number;
  user_email: string;
  membership_status: string;
  joined_at: string;
  invited_by_user_id?: number | null;
  removed_at?: string | null;
  is_owner: boolean;
  role_keys: string[];
  effective_permission_keys: string[];
}

export interface OrganizationInvitationResponse {
  id: number;
  organization_id: number;
  email: string;
  invitation_token: string;
  status: string;
  expires_at: string;
  accepted_at?: string | null;
  invited_by_user_id: number;
  created_at: string;
}

export interface OrganizationEventResponse {
  id: number;
  organization_id: number;
  actor_user_id?: number | null;
  event_type: string;
  event_payload_json: Record<string, unknown>;
  created_at: string;
}

export interface OrganizationRoleResponse {
  id: number;
  organization_id: number;
  role_key: string;
  display_name: string;
  system_managed: boolean;
  created_at: string;
  permission_keys: string[];
}

export interface OrganizationMembershipRoleResponse {
  id: number;
  organization_member_id: number;
  organization_role_id: number;
  role_key: string;
  display_name: string;
  assigned_by_user_id: number;
  assigned_at: string;
  permission_keys: string[];
}

export type OrganizationInventoryQueueName =
  | "intake"
  | "grading_review"
  | "scan_review"
  | "marketplace_ready"
  | "archived";

export interface OrganizationInventoryAssignmentResponse {
  id: number;
  organization_id: number;
  inventory_item_id: number;
  assigned_user_id: number;
  assigned_by_user_id: number;
  assignment_status: string;
  assignment_notes?: string | null;
  assigned_at: string;
  completed_at?: string | null;
}

export interface OrganizationInventoryQueueResponse {
  id: number;
  organization_id: number;
  queue_name: OrganizationInventoryQueueName | string;
  inventory_item_id: number;
  queue_position: number;
  queue_status: string;
  created_at: string;
}

export interface OrganizationInventoryWorkflowEventResponse {
  id: number;
  organization_id: number;
  inventory_item_id?: number | null;
  actor_user_id?: number | null;
  workflow_event_type: string;
  workflow_payload_json: Record<string, unknown>;
  created_at: string;
}

export interface OrganizationInventoryAssignmentListResponse {
  items: OrganizationInventoryAssignmentResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationInventoryQueueListResponse {
  items: OrganizationInventoryQueueResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationInventoryWorkflowEventListResponse {
  items: OrganizationInventoryWorkflowEventResponse[];
  pagination: MarketApiV1Pagination;
}

export type OrganizationReviewQueueName =
  | "intake_review"
  | "grading_review"
  | "authentication_review"
  | "marketplace_approval"
  | "archival_review";

export interface OrganizationReviewResponse {
  id: number;
  organization_id: number;
  inventory_item_id: number;
  review_type: string;
  review_status: string;
  assigned_user_id?: number | null;
  created_by_user_id: number;
  requested_at: string;
  completed_at?: string | null;
  approval_queue_name?: string | null;
  approval_queue_position?: number | null;
}

export interface OrganizationReviewDecisionResponse {
  id: number;
  organization_review_id: number;
  actor_user_id: number;
  decision_type: string;
  decision_notes?: string | null;
  created_at: string;
}

export interface OrganizationApprovalQueueResponse {
  id: number;
  organization_id: number;
  queue_name: OrganizationReviewQueueName | string;
  review_id: number;
  queue_position: number;
  queue_status: string;
  created_at: string;
}

export interface OrganizationReviewListResponse {
  items: OrganizationReviewResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationReviewDecisionListResponse {
  items: OrganizationReviewDecisionResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationApprovalQueueListResponse {
  items: OrganizationApprovalQueueResponse[];
  pagination: MarketApiV1Pagination;
}

export type OrganizationActivityCategory =
  | "organization"
  | "inventory"
  | "reviews"
  | "storefront"
  | "security"
  | "permissions";

export interface OrganizationActivityEventResponse {
  id: number;
  organization_id: number;
  actor_user_id?: number | null;
  activity_type: string;
  activity_payload_json: Record<string, unknown>;
  visibility_scope: string;
  created_at: string;
  category?: string | null;
}

export interface OrganizationActivityListResponse {
  items: OrganizationActivityEventResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationNotificationResponse {
  id: number;
  organization_id: number;
  target_user_id: number;
  notification_type: string;
  notification_title: string;
  notification_body: string;
  notification_status: string;
  activity_event_id?: number | null;
  created_at: string;
  read_at?: string | null;
  acknowledged_at?: string | null;
}

export interface OrganizationNotificationListResponse {
  items: OrganizationNotificationResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationNotificationUnreadCountResponse {
  unread_count: number;
}

export interface OrganizationDealerDashboardSectionSummary {
  section_key: string;
  metrics: Record<string, number | string | boolean | null>;
}

export interface OrganizationDealerDashboardSnapshotResponse {
  id: number;
  organization_id: number;
  snapshot_type: string;
  snapshot_payload_json: Record<string, unknown>;
  generated_at: string;
}

export interface OrganizationDealerDashboardSummaryResponse {
  organization_id: number;
  snapshot?: OrganizationDealerDashboardSnapshotResponse | null;
  sections: OrganizationDealerDashboardSectionSummary[];
  generated_at: string;
}

export interface OrganizationDealerOperationalMetricResponse {
  id: number;
  organization_id: number;
  metric_key: string;
  metric_value_json: Record<string, unknown>;
  metric_group: string;
  metric_period: string;
  generated_at: string;
}

export interface OrganizationDealerOperationalMetricListResponse {
  items: OrganizationDealerOperationalMetricResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationDealerDashboardSnapshotListResponse {
  items: OrganizationDealerDashboardSnapshotResponse[];
  pagination: MarketApiV1Pagination;
}

export type OrganizationAuditCategory =
  | "organization"
  | "permissions"
  | "inventory"
  | "reviews"
  | "storefront"
  | "security"
  | "sessions"
  | "notifications";

export type OrganizationComplianceSeverity = "info" | "warning" | "elevated" | "critical";

export interface OrganizationAuditLedgerResponse {
  id: number;
  organization_id: number;
  actor_user_id?: number | null;
  audit_category: string;
  audit_action: string;
  resource_type: string;
  resource_id?: string | null;
  audit_payload_json: Record<string, unknown>;
  created_at: string;
}

export interface OrganizationAuditLedgerListResponse {
  items: OrganizationAuditLedgerResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationComplianceEventResponse {
  id: number;
  organization_id: number;
  compliance_event_type: string;
  severity_level: string;
  event_payload_json: Record<string, unknown>;
  created_at: string;
}

export interface OrganizationComplianceEventListResponse {
  items: OrganizationComplianceEventResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationAuditAccessLogResponse {
  id: number;
  organization_id: number;
  actor_user_id: number;
  accessed_resource_type: string;
  accessed_resource_id?: string | null;
  access_result: string;
  created_at: string;
}

export interface OrganizationAuditAccessLogListResponse {
  items: OrganizationAuditAccessLogResponse[];
  pagination: MarketApiV1Pagination;
}

export interface PublicStorefrontResponse {
  profile: DealerProfileResponse;
  settings: DealerStorefrontSettingsResponse;
}

export interface DealerProfileResponse {
  id: number;
  organization_id: number;
  public_slug: string;
  display_name: string;
  tagline?: string | null;
  description?: string | null;
  logo_asset_id?: number | null;
  banner_asset_id?: number | null;
  website_url?: string | null;
  instagram_url?: string | null;
  whatnot_url?: string | null;
  location_label?: string | null;
  profile_status: string;
  created_at: string;
  updated_at: string;
}

export interface DealerStorefrontSettingsResponse {
  id: number;
  organization_id: number;
  storefront_visibility: string;
  public_inventory_enabled: boolean;
  featured_inventory_limit: number;
  featured_inventory_sort: string;
  featured_manual_inventory_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface PublicStorefrontInventoryItem {
  inventory_copy_id: number;
  title: string;
  publisher: string;
  issue_number: string;
  cover_name?: string | null;
  grade_status: string;
  current_fmv?: string | null;
  release_year?: number | null;
}

export interface PublicStorefrontInventoryListResponse {
  items: PublicStorefrontInventoryItem[];
  pagination: MarketApiV1Pagination;
}

export interface MarketplaceAccountConnectRequest {
  marketplace_type: string;
  marketplace_account_id: string;
  display_name: string;
  credential_type: string;
  credential_reference: string;
}

export interface MarketplaceAccountDisconnectRequest {
  account_id: number;
  reason?: string | null;
}

export interface MarketplaceAccountVerifyRequest {
  account_id: number;
  verification_status?: string;
  reason?: string | null;
}

export interface MarketplaceRegistryEntryResponse {
  marketplace_key: string;
  display_name: string;
  status: string;
  capability_flags: string[];
}

export interface MarketplacePermissionResponse {
  can_view: boolean;
  can_manage: boolean;
  role_keys: string[];
  permission_keys: string[];
}

export interface MarketplaceCredentialResponse {
  id: number;
  marketplace_account_id: number;
  credential_type: string;
  credential_reference: string;
  credential_status: string;
  rotated_at?: string | null;
  created_at: string;
}

export interface MarketplaceConnectionEventResponse {
  id: number;
  organization_id: number;
  marketplace_account_id?: number | null;
  actor_user_id?: number | null;
  event_type: string;
  event_payload_json: Record<string, unknown>;
  created_at: string;
}

export interface MarketplaceAccountResponse {
  id: number;
  organization_id: number;
  marketplace_type: string;
  marketplace_account_id: string;
  display_name: string;
  account_status: string;
  verification_status: string;
  connected_at: string;
  disconnected_at?: string | null;
  created_at: string;
}

export interface MarketplaceAccountDetailResponse {
  account: MarketplaceAccountResponse;
  credentials: MarketplaceCredentialResponse[];
  connection_events: MarketplaceConnectionEventResponse[];
  registry_entry: MarketplaceRegistryEntryResponse;
  permissions: MarketplacePermissionResponse;
}

export interface MarketplaceAccountListResponse {
  items: MarketplaceAccountResponse[];
  registry: MarketplaceRegistryEntryResponse[];
  permissions: MarketplacePermissionResponse;
  pagination: MarketApiV1Pagination;
}

export interface OrganizationListResponse {
  items: OrganizationResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationMemberListResponse {
  items: OrganizationMemberResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationEventListResponse {
  items: OrganizationEventResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationRoleListResponse {
  items: OrganizationRoleResponse[];
  pagination: MarketApiV1Pagination;
}

export interface OrganizationMembershipRoleListResponse {
  items: OrganizationMembershipRoleResponse[];
  pagination: MarketApiV1Pagination;
}

export interface AutomationRuleVersionRead {
  id: number;
  rule_id: number;
  version_number: number;
  version_status: string;
  condition_expression: string;
  action_definition_json: Array<Record<string, unknown>>;
  evaluation_scope: string;
  replay_safe: boolean;
  version_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRuleRead {
  id: number;
  owner_user_id?: number | null;
  organization_id?: number | null;
  rule_key: string;
  rule_name: string;
  rule_category: string;
  rule_status: string;
  current_version_id?: number | null;
  replay_safe: boolean;
  deterministic_ordering_enabled: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
  current_version?: AutomationRuleVersionRead | null;
}

export interface AutomationRuleEvaluationRead {
  id: number;
  rule_id: number;
  rule_version_id: number;
  evaluation_type: string;
  evaluation_status: string;
  evaluation_scope: string;
  evaluation_input_json: Record<string, unknown>;
  evaluation_result_json: Record<string, unknown>;
  matched: boolean;
  evaluation_rank: number;
  evaluation_checksum: string;
  replay_safe: boolean;
  started_at: string;
  completed_at?: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRuleActionRead {
  id: number;
  evaluation_id: number;
  action_type: string;
  action_status: string;
  action_rank: number;
  target_scope: string;
  action_payload_json: Record<string, unknown>;
  action_checksum: string;
  replay_safe: boolean;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRuleIssueRead {
  id: number;
  rule_id: number;
  rule_version_id?: number | null;
  evaluation_id?: number | null;
  issue_type: string;
  severity: string;
  issue_message: string;
  issue_checksum: string;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AutomationRuleListResponse {
  items: Array<AutomationRuleRead | AutomationRuleVersionRead | AutomationRuleEvaluationRead | AutomationRuleActionRead | AutomationRuleIssueRead>;
  pagination: MarketApiV1Pagination;
  active_rule_count?: number;
  failed_evaluation_count?: number;
  replay_drift_count?: number;
  action_failure_count?: number;
  paused_rule_count?: number;
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

  listAuthSessions(params?: { limit?: number; offset?: number }): Promise<UserAuthSessionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<UserAuthSessionListResponse>(`/auth/sessions${q}`);
  },

  getSecurityContext(): Promise<OrganizationSecurityContextRead> {
    return requestScanV1<OrganizationSecurityContextRead>("/auth/security-context");
  },

  revokeAuthSession(payload: RevokeAuthSessionRequest): Promise<UserAuthSessionRead> {
    return requestScanV1<UserAuthSessionRead>("/auth/sessions/revoke", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  revokeAllAuthSessions(): Promise<UserAuthSessionListResponse> {
    return requestScanV1<UserAuthSessionListResponse>("/auth/sessions/revoke-all", {
      method: "POST",
    });
  },

  switchActiveOrganization(payload: SwitchOrganizationRequest): Promise<OrganizationSecurityContextRead> {
    return requestScanV1<OrganizationSecurityContextRead>("/auth/security-context/switch-organization", {
      method: "POST",
      body: JSON.stringify(payload),
    });
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

  getInventoryActionCenter(params?: {
    priority?: InventoryRiskPriority;
    action_category?: InventoryActionCenterCategory;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    release_status?: InventoryItem["release_status"];
    unresolved_only?: boolean;
    in_hand_only?: boolean;
    inventory_copy_id?: number;
  }): Promise<InventoryActionCenterListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryActionCenterListResponse>(`/inventory-action-center${query}`);
  },

  getInventoryActionCenterSummary(params?: {
    priority?: InventoryRiskPriority;
    action_category?: InventoryActionCenterCategory;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    release_status?: InventoryItem["release_status"];
    unresolved_only?: boolean;
    in_hand_only?: boolean;
    inventory_copy_id?: number;
  }): Promise<InventoryActionCenterSummary> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryActionCenterSummary>(`/inventory-action-center/summary${query}`);
  },

  getOpsInventoryActionCenter(params?: {
    priority?: InventoryRiskPriority;
    action_category?: InventoryActionCenterCategory;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    release_status?: InventoryItem["release_status"];
    unresolved_only?: boolean;
    in_hand_only?: boolean;
    inventory_copy_id?: number;
  }): Promise<InventoryActionCenterListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryActionCenterListResponse>(`/ops/inventory-action-center${query}`);
  },

  getOpsInventoryActionCenterSummary(params?: {
    priority?: InventoryRiskPriority;
    action_category?: InventoryActionCenterCategory;
    ownership_state?: InventoryOwnershipNormalized;
    publisher?: string;
    release_status?: InventoryItem["release_status"];
    unresolved_only?: boolean;
    in_hand_only?: boolean;
    inventory_copy_id?: number;
  }): Promise<InventoryActionCenterSummary> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<InventoryActionCenterSummary>(`/ops/inventory-action-center/summary${query}`);
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

  getCollectionHistoricalTimeline(params?: {
    event_type?: CollectionHistoricalTimelineEventKind;
    publisher?: string;
    ownership_state?: InventoryOwnershipNormalized;
    release_status?: InventoryItem["release_status"];
    start_date?: string;
    end_date?: string;
    preorder_only?: boolean;
    in_hand_only?: boolean;
    grouping?: CollectionHistoricalTimelineGrouping;
    sort?: CollectionHistoricalTimelineSort;
    limit?: number;
  }): Promise<CollectionHistoricalTimelineEventsResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<CollectionHistoricalTimelineEventsResponse>(`/collection-timeline${query}`);
  },

  getCollectionHistoricalTimelineSummary(params?: {
    event_type?: CollectionHistoricalTimelineEventKind;
    publisher?: string;
    ownership_state?: InventoryOwnershipNormalized;
    release_status?: InventoryItem["release_status"];
    start_date?: string;
    end_date?: string;
    preorder_only?: boolean;
    in_hand_only?: boolean;
  }): Promise<CollectionHistoricalTimelineSummary> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<CollectionHistoricalTimelineSummary>(`/collection-timeline/summary${query}`);
  },

  getInventoryHistoricalTimeline(inventoryCopyId: number, params?: {
    event_type?: CollectionHistoricalTimelineEventKind;
    grouping?: CollectionHistoricalTimelineGrouping;
    sort?: CollectionHistoricalTimelineSort;
    limit?: number;
  }): Promise<CollectionHistoricalTimelineEventsResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<CollectionHistoricalTimelineEventsResponse>(
      `/inventory/${inventoryCopyId}/timeline${query}`,
    );
  },

  getOpsCollectionHistoricalTimeline(params?: {
    event_type?: CollectionHistoricalTimelineEventKind;
    publisher?: string;
    ownership_state?: InventoryOwnershipNormalized;
    release_status?: InventoryItem["release_status"];
    start_date?: string;
    end_date?: string;
    preorder_only?: boolean;
    in_hand_only?: boolean;
    grouping?: CollectionHistoricalTimelineGrouping;
    sort?: CollectionHistoricalTimelineSort;
    limit?: number;
  }): Promise<CollectionHistoricalTimelineEventsResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<CollectionHistoricalTimelineEventsResponse>(`/ops/collection-timeline${query}`);
  },

  getOpsCollectionHistoricalTimelineSummary(params?: {
    event_type?: CollectionHistoricalTimelineEventKind;
    publisher?: string;
    ownership_state?: InventoryOwnershipNormalized;
    release_status?: InventoryItem["release_status"];
    start_date?: string;
    end_date?: string;
    preorder_only?: boolean;
    in_hand_only?: boolean;
  }): Promise<CollectionHistoricalTimelineSummary> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<CollectionHistoricalTimelineSummary>(`/ops/collection-timeline/summary${query}`);
  },

  getOpsInventoryHistoricalTimeline(inventoryCopyId: number, params?: {
    event_type?: CollectionHistoricalTimelineEventKind;
    grouping?: CollectionHistoricalTimelineGrouping;
    sort?: CollectionHistoricalTimelineSort;
    limit?: number;
  }): Promise<CollectionHistoricalTimelineEventsResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<CollectionHistoricalTimelineEventsResponse>(
      `/ops/inventory/${inventoryCopyId}/timeline${query}`,
    );
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

  getScanSessionDashboard(): Promise<ScanSessionDashboardResponse> {
    return request<ScanSessionDashboardResponse>("/scan-sessions/dashboard");
  },

  getScanPipelineDashboardSummary(): Promise<ScanPipelineDashboardSummary> {
    return request<ScanPipelineDashboardSummary>("/scan-pipeline-dashboard/summary");
  },

  getScanPipelineDashboard(): Promise<ScanPipelineDashboardResponse> {
    return request<ScanPipelineDashboardResponse>("/scan-pipeline-dashboard");
  },

  getMarketSources(): Promise<MarketSourceRead[]> {
    return request<MarketSourceRead[]>("/market-sources");
  },

  getMarketSource(marketSourceId: number): Promise<MarketSourceRead> {
    return request<MarketSourceRead>(`/market-sources/${marketSourceId}`);
  },

  getMarketImportRuns(): Promise<MarketSourceImportRunListResponse> {
    return request<MarketSourceImportRunListResponse>("/market-import-runs");
  },

  getMarketImportRun(runId: number): Promise<MarketSourceImportRunRead> {
    return request<MarketSourceImportRunRead>(`/market-import-runs/${runId}`);
  },

  getOpsMarketSources(): Promise<MarketSourceRead[]> {
    return request<MarketSourceRead[]>("/ops/market-sources");
  },

  getOpsMarketImportRuns(): Promise<MarketSourceImportRunListResponse> {
    return request<MarketSourceImportRunListResponse>("/ops/market-import-runs");
  },

  createOpsMarketImportRun(payload: MarketSourceImportRunCreatePayload): Promise<MarketSourceImportRunRead> {
    return request<MarketSourceImportRunRead>("/ops/market-import-runs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  startOpsMarketImportRun(runId: number): Promise<MarketSourceImportRunRead> {
    return request<MarketSourceImportRunRead>(`/ops/market-import-runs/${runId}/start`, {
      method: "POST",
    });
  },

  cancelOpsMarketImportRun(runId: number): Promise<MarketSourceImportRunRead> {
    return request<MarketSourceImportRunRead>(`/ops/market-import-runs/${runId}/cancel`, {
      method: "POST",
    });
  },

  completeOpsMarketImportRun(runId: number): Promise<MarketSourceImportRunRead> {
    return request<MarketSourceImportRunRead>(`/ops/market-import-runs/${runId}/complete`, {
      method: "POST",
    });
  },

  getMarketSales(params?: MarketSaleListParams): Promise<MarketSaleListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleListResponse>(`/market-sales${query}`);
  },

  getMarketSale(marketSaleRecordId: number): Promise<MarketSaleRead> {
    return request<MarketSaleRead>(`/market-sales/${marketSaleRecordId}`);
  },

  getMarketSaleNormalizationIssues(marketSaleRecordId: number): Promise<MarketSaleNormalizationIssueRead[]> {
    return request<MarketSaleNormalizationIssueRead[]>(`/market-sales/${marketSaleRecordId}/normalization-issues`);
  },

  getMarketSaleReviewQueue(params?: MarketSaleReviewQueueListParams): Promise<MarketSaleReviewQueueResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleReviewQueueResponse>(`/market-sale-review-queue${query}`);
  },

  getMarketSaleReviewQueueSummary(params?: MarketSaleReviewQueueListParams): Promise<MarketSaleReviewQueueSummaryRead> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleReviewQueueSummaryRead>(`/market-sale-review-queue/summary${query}`);
  },

  getMarketCompEligibility(params?: MarketSaleCompEligibilityListParams): Promise<MarketSaleCompEligibilityListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleCompEligibilityListResponse>(`/market-comp-eligibility${query}`);
  },

  getMarketComps(params?: MarketComparableListParams): Promise<MarketComparableListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketComparableListResponse>(`/market-comps${query}`);
  },

  getMarketCompsByIdentity(
    metadataIdentityKey: string,
    params?: Omit<MarketComparableListParams, "metadata_identity_key">,
  ): Promise<MarketComparableListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketComparableListResponse>(`/market-comps/by-identity/${encodeURIComponent(metadataIdentityKey)}${query}`);
  },

  getMarketFmv(params?: MarketFmvListParams): Promise<MarketFmvSnapshotListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketFmvSnapshotListResponse>(`/market-fmv${query}`);
  },

  getMarketFmvSnapshot(snapshotId: number): Promise<MarketFmvSnapshotRead> {
    return request<MarketFmvSnapshotRead>(`/market-fmv/${snapshotId}`);
  },

  getMarketFmvByIdentity(metadataIdentityKey: string): Promise<MarketFmvSnapshotListResponse> {
    return request<MarketFmvSnapshotListResponse>(`/market-fmv/by-identity/${encodeURIComponent(metadataIdentityKey)}`);
  },

  getMarketTrends(params?: MarketTrendListParams): Promise<MarketTrendSnapshotListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketTrendSnapshotListResponse>(`/market-trends${query}`);
  },

  getMarketTrendsByIdentity(
    metadataIdentityKey: string,
    params?: Omit<MarketTrendListParams, "metadata_identity_key">,
  ): Promise<MarketTrendSnapshotListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketTrendSnapshotListResponse>(`/market-trends/by-identity/${encodeURIComponent(metadataIdentityKey)}${query}`);
  },

  getMarketTrendSnapshot(snapshotId: number): Promise<MarketTrendSnapshotRead> {
    return request<MarketTrendSnapshotRead>(`/market-trends/${snapshotId}`);
  },

  getMarketSaleCompEligibility(marketSaleRecordId: number): Promise<MarketSaleCompEligibilityRead> {
    return request<MarketSaleCompEligibilityRead>(`/market-sales/${marketSaleRecordId}/comp-eligibility`);
  },

  getMarketFmvSnapshotComps(
    snapshotId: number,
    params?: { include_excluded?: boolean },
  ): Promise<MarketComparableSnapshotCompsResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketComparableSnapshotCompsResponse>(`/market-fmv/${snapshotId}/comps${query}`);
  },

  getMarketSaleMatchSuggestions(marketSaleRecordId: number): Promise<MarketSaleMatchSuggestionRead[]> {
    return request<MarketSaleMatchSuggestionRead[]>(`/market-sales/${marketSaleRecordId}/match-suggestions`);
  },

  getMarketMatchSuggestions(params?: {
    source?: string;
    confidence_bucket?: MarketSaleMatchSuggestionConfidenceBucket | "all";
    review_state?: MarketSaleMatchSuggestionReviewState | "all";
    suggestion_type?: MarketSaleMatchSuggestionType | "all";
  }): Promise<MarketSaleMatchSuggestionOpsListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<MarketSaleMatchSuggestionOpsListResponse>(`/market-match-suggestions${query}`);
  },

  getOpsMarketSales(params?: MarketSaleListParams): Promise<MarketSaleListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleListResponse>(`/ops/market-sales${query}`);
  },

  getOpsMarketSale(marketSaleRecordId: number): Promise<MarketSaleRead> {
    return request<MarketSaleRead>(`/ops/market-sales/${marketSaleRecordId}`);
  },

  getOpsMarketSaleNormalizationIssues(marketSaleRecordId: number): Promise<MarketSaleNormalizationIssueRead[]> {
    return request<MarketSaleNormalizationIssueRead[]>(
      `/ops/market-sales/${marketSaleRecordId}/normalization-issues`,
    );
  },

  getOpsMarketSaleReviewQueue(params?: MarketSaleReviewQueueListParams): Promise<MarketSaleReviewQueueResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleReviewQueueResponse>(`/ops/market-sale-review-queue${query}`);
  },

  getOpsMarketSaleReviewQueueSummary(
    params?: MarketSaleReviewQueueListParams,
  ): Promise<MarketSaleReviewQueueSummaryRead> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleReviewQueueSummaryRead>(`/ops/market-sale-review-queue/summary${query}`);
  },

  getOpsMarketCompEligibility(params?: MarketSaleCompEligibilityListParams): Promise<MarketSaleCompEligibilityListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketSaleCompEligibilityListResponse>(`/ops/market-comp-eligibility${query}`);
  },

  getOpsMarketComps(params?: MarketComparableListParams): Promise<MarketComparableListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketComparableListResponse>(`/ops/market-comps${query}`);
  },

  getOpsMarketCompsByIdentity(
    metadataIdentityKey: string,
    params?: Omit<MarketComparableListParams, "metadata_identity_key">,
  ): Promise<MarketComparableListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketComparableListResponse>(`/ops/market-comps/by-identity/${encodeURIComponent(metadataIdentityKey)}${query}`);
  },

  getOpsMarketFmv(params?: MarketFmvListParams): Promise<MarketFmvSnapshotListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketFmvSnapshotListResponse>(`/ops/market-fmv${query}`);
  },

  getOpsMarketFmvSnapshot(snapshotId: number): Promise<MarketFmvSnapshotRead> {
    return request<MarketFmvSnapshotRead>(`/ops/market-fmv/${snapshotId}`);
  },

  generateOpsMarketFmvSnapshots(): Promise<MarketFmvGenerateResponse> {
    return request<MarketFmvGenerateResponse>("/ops/market-fmv/generate", {
      method: "POST",
    });
  },

  getOpsMarketTrends(params?: MarketTrendListParams): Promise<MarketTrendSnapshotListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketTrendSnapshotListResponse>(`/ops/market-trends${query}`);
  },

  getOpsMarketTrendSnapshot(snapshotId: number): Promise<MarketTrendSnapshotRead> {
    return request<MarketTrendSnapshotRead>(`/ops/market-trends/${snapshotId}`);
  },

  generateOpsMarketTrends(): Promise<MarketTrendGenerateResponse> {
    return request<MarketTrendGenerateResponse>("/ops/market-trends/generate", {
      method: "POST",
    });
  },

  getOpsMarketSaleCompEligibility(marketSaleRecordId: number): Promise<MarketSaleCompEligibilityRead> {
    return request<MarketSaleCompEligibilityRead>(`/ops/market-sales/${marketSaleRecordId}/comp-eligibility`);
  },

  getOpsMarketFmvSnapshotComps(
    snapshotId: number,
    params?: { include_excluded?: boolean },
  ): Promise<MarketComparableSnapshotCompsResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<MarketComparableSnapshotCompsResponse>(`/ops/market-fmv/${snapshotId}/comps${query}`);
  },

  getOpsMarketSaleMatchSuggestions(marketSaleRecordId: number): Promise<MarketSaleMatchSuggestionRead[]> {
    return request<MarketSaleMatchSuggestionRead[]>(`/ops/market-sales/${marketSaleRecordId}/match-suggestions`);
  },

  generateOpsMarketSaleMatchSuggestions(marketSaleRecordId: number): Promise<MarketSaleMatchSuggestionGenerateResponse> {
    return request<MarketSaleMatchSuggestionGenerateResponse>(
      `/ops/market-sales/${marketSaleRecordId}/generate-match-suggestions`,
      { method: "POST" },
    );
  },

  listOpsMarketMatchSuggestions(params?: {
    source?: string;
    confidence_bucket?: MarketSaleMatchSuggestionConfidenceBucket | "all";
    review_state?: MarketSaleMatchSuggestionReviewState | "all";
    suggestion_type?: MarketSaleMatchSuggestionType | "all";
  }): Promise<MarketSaleMatchSuggestionOpsListResponse> {
    const query = params ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<MarketSaleMatchSuggestionOpsListResponse>(`/ops/market-match-suggestions${query}`);
  },

  approveOpsMarketMatchSuggestion(suggestionId: number): Promise<MarketSaleMatchSuggestionReviewActionResponse> {
    return request<MarketSaleMatchSuggestionReviewActionResponse>(
      `/ops/market-match-suggestions/${suggestionId}/approve`,
      { method: "PATCH" },
    );
  },

  rejectOpsMarketMatchSuggestion(suggestionId: number): Promise<MarketSaleMatchSuggestionReviewActionResponse> {
    return request<MarketSaleMatchSuggestionReviewActionResponse>(
      `/ops/market-match-suggestions/${suggestionId}/reject`,
      { method: "PATCH" },
    );
  },

  ignoreOpsMarketMatchSuggestion(suggestionId: number): Promise<MarketSaleMatchSuggestionReviewActionResponse> {
    return request<MarketSaleMatchSuggestionReviewActionResponse>(
      `/ops/market-match-suggestions/${suggestionId}/ignore`,
      { method: "PATCH" },
    );
  },

  patchOpsMarketSaleNormalization(
    marketSaleRecordId: number,
    payload: MarketSaleNormalizationUpdatePayload,
  ): Promise<MarketSaleRead> {
    return request<MarketSaleRead>(`/ops/market-sales/${marketSaleRecordId}/normalization`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  ignoreOpsMarketSale(marketSaleRecordId: number, payload?: MarketSaleReviewActionPayload): Promise<MarketSaleRead> {
    return request<MarketSaleRead>(`/ops/market-sales/${marketSaleRecordId}/ignore`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  flagDuplicateOpsMarketSale(
    marketSaleRecordId: number,
    payload?: MarketSaleReviewActionPayload,
  ): Promise<MarketSaleRead> {
    return request<MarketSaleRead>(`/ops/market-sales/${marketSaleRecordId}/flag-duplicate`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  upsertOpsMarketSale(payload: MarketSaleUpsertPayload): Promise<MarketSaleRead> {
    return request<MarketSaleRead>("/ops/market-sales", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  createScanSession(payload?: ScanSessionCreatePayload): Promise<ScanSessionSummary> {
    return request<ScanSessionSummary>("/scan-sessions", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  listScanSessions(params?: {
    status?: ScanSessionStatus;
    session_type?: ScanSessionType;
    limit?: number;
    offset?: number;
  }): Promise<ScanSessionListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<ScanSessionListResponse>(`/scan-sessions${query}`);
  },

  getScanSession(sessionId: number): Promise<ScanSessionDetail> {
    return request<ScanSessionDetail>(`/scan-sessions/${sessionId}`);
  },

  getScanSessionItems(
    sessionId: number,
    params?: {
      limit?: number;
      offset?: number;
    },
  ): Promise<ScanSessionItemsListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<ScanSessionItemsListResponse>(`/scan-sessions/${sessionId}/items${query}`);
  },

  getScanSessionQa(sessionId: number): Promise<ScanSessionQaSummaryRead> {
    return request<ScanSessionQaSummaryRead>(`/scan-sessions/${sessionId}/qa`);
  },

  getScanSessionRouting(sessionId: number): Promise<ScanSessionRoutingRead> {
    return request<ScanSessionRoutingRead>(`/scan-sessions/${sessionId}/routing`);
  },

  generateScanSessionRouting(sessionId: number): Promise<ScanSessionRoutingRead> {
    return request<ScanSessionRoutingRead>(`/scan-sessions/${sessionId}/generate-routing`, {
      method: "POST",
    });
  },

  listScanRoutingRecommendations(): Promise<QueueRoutingListResponse> {
    return request<QueueRoutingListResponse>("/scan-routing-recommendations");
  },

  acknowledgeScanRoutingRecommendation(recommendationId: number): Promise<QueueRoutingRecommendationRead> {
    return request<QueueRoutingRecommendationRead>(`/scan-routing-recommendations/${recommendationId}/acknowledge`, {
      method: "POST",
    });
  },

  dismissScanRoutingRecommendation(recommendationId: number): Promise<QueueRoutingRecommendationRead> {
    return request<QueueRoutingRecommendationRead>(`/scan-routing-recommendations/${recommendationId}/dismiss`, {
      method: "POST",
    });
  },

  getScanSessionItemQa(sessionId: number, itemId: number): Promise<ScanQaItemRead> {
    return request<ScanQaItemRead>(`/scan-sessions/${sessionId}/items/${itemId}/qa`);
  },

  runScanSessionQa(sessionId: number): Promise<ScanSessionQaSummaryRead> {
    return request<ScanSessionQaSummaryRead>(`/scan-sessions/${sessionId}/run-qa`, { method: "POST" });
  },

  ingestScanSessionFiles(
    sessionId: number,
    files: File[],
    manifest?: ScanSessionIngestManifest,
  ): Promise<ScanSessionDetail> {
    const fd = new FormData();
    const payload: ScanSessionIngestManifest = manifest ?? { items: [] };
    fd.append("manifest", JSON.stringify(payload));
    for (const f of files) {
      fd.append("files", f);
    }
    return request<ScanSessionDetail>(`/scan-sessions/${sessionId}/ingest-files`, {
      method: "POST",
      body: fd,
    });
  },

  appendScanSessionItems(sessionId: number, payload: ScanSessionItemsAppendPayload): Promise<ScanSessionDetail> {
    return request<ScanSessionDetail>(`/scan-sessions/${sessionId}/items`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  patchScanSessionItem(
    sessionId: number,
    itemId: number,
    payload: ScanSessionItemUpdatePayload,
  ): Promise<ScanSessionDetail> {
    return request<ScanSessionDetail>(`/scan-sessions/${sessionId}/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  startScanSession(sessionId: number): Promise<ScanSessionSummary> {
    return request<ScanSessionSummary>(`/scan-sessions/${sessionId}/start`, { method: "POST" });
  },

  pauseScanSession(sessionId: number): Promise<ScanSessionSummary> {
    return request<ScanSessionSummary>(`/scan-sessions/${sessionId}/pause`, { method: "POST" });
  },

  cancelScanSession(sessionId: number): Promise<ScanSessionSummary> {
    return request<ScanSessionSummary>(`/scan-sessions/${sessionId}/cancel`, { method: "POST" });
  },

  completeScanSession(sessionId: number): Promise<ScanSessionSummary> {
    return request<ScanSessionSummary>(`/scan-sessions/${sessionId}/complete`, { method: "POST" });
  },

  listScannerProfiles(): Promise<ScannerProfileListResponse> {
    return request<ScannerProfileListResponse>("/scanner-profiles");
  },

  getScannerProfile(profileId: number): Promise<ScannerProfileRead> {
    return request<ScannerProfileRead>(`/scanner-profiles/${profileId}`);
  },

  createScannerProfile(payload: ScannerProfileCreatePayload): Promise<ScannerProfileRead> {
    return request<ScannerProfileRead>("/scanner-profiles", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateScannerProfile(profileId: number, payload: ScannerProfileUpdatePayload): Promise<ScannerProfileRead> {
    return request<ScannerProfileRead>(`/scanner-profiles/${profileId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  deleteScannerProfile(profileId: number): Promise<void> {
    return requestEmpty(`/scanner-profiles/${profileId}`, { method: "DELETE" });
  },

  listOpsScannerProfiles(): Promise<ScannerProfileListResponse> {
    return request<ScannerProfileListResponse>("/ops/scanner-profiles");
  },

  createHighResReviewRequest(payload: HighResReviewRequestCreatePayload): Promise<HighResReviewRequestDetail> {
    return request<HighResReviewRequestDetail>("/high-res-review-requests", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getHighResReviewRequestsStats(): Promise<HighResReviewRequestStatsRead> {
    return request<HighResReviewRequestStatsRead>("/high-res-review-requests/stats");
  },

  listHighResReviewRequests(params?: {
    inventory_copy_id?: number;
    status?: HighResReviewRequestStatus;
    priority?: HighResReviewRequestPriority;
    reason?: HighResReviewRequestReason;
    limit?: number;
    offset?: number;
  }): Promise<HighResReviewRequestListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<HighResReviewRequestListResponse>(`/high-res-review-requests${query}`);
  },

  getHighResReviewRequest(requestId: number): Promise<HighResReviewRequestDetail> {
    return request<HighResReviewRequestDetail>(`/high-res-review-requests/${requestId}`);
  },

  attachHighResReviewScan(requestId: number, file: File, sourceFilename?: string | null): Promise<HighResReviewRequestDetail> {
    const fd = new FormData();
    fd.append("file", file);
    if (sourceFilename != null && sourceFilename !== "") {
      fd.append("source_filename", sourceFilename);
    }
    return request<HighResReviewRequestDetail>(`/high-res-review-requests/${requestId}/attach-scan`, {
      method: "POST",
      body: fd,
    });
  },

  cancelHighResReviewRequest(requestId: number): Promise<HighResReviewRequestDetail> {
    return request<HighResReviewRequestDetail>(`/high-res-review-requests/${requestId}/cancel`, { method: "POST" });
  },

  completeHighResReviewRequest(requestId: number): Promise<HighResReviewRequestDetail> {
    return request<HighResReviewRequestDetail>(`/high-res-review-requests/${requestId}/complete`, { method: "POST" });
  },

  listOpsHighResReviewRequests(params?: {
    owner_user_id?: number;
    inventory_copy_id?: number;
    status?: HighResReviewRequestStatus;
    priority?: HighResReviewRequestPriority;
    reason?: HighResReviewRequestReason;
    limit?: number;
    offset?: number;
  }): Promise<HighResReviewRequestListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<HighResReviewRequestListResponse>(`/ops/high-res-review-requests${query}`);
  },

  getOpsHighResReviewRequestStats(): Promise<HighResReviewRequestStatsRead> {
    return request<HighResReviewRequestStatsRead>("/ops/high-res-review-requests/stats");
  },

  getOpsHighResReviewRequest(requestId: number): Promise<HighResReviewRequestDetail> {
    return request<HighResReviewRequestDetail>(`/ops/high-res-review-requests/${requestId}`);
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

  listOpsScanSessions(params?: {
    owner_user_id?: number;
    status?: ScanSessionStatus;
    session_type?: ScanSessionType;
    limit?: number;
    offset?: number;
  }): Promise<ScanSessionListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<ScanSessionListResponse>(`/ops/scan-sessions${query}`);
  },

  getOpsScanSession(sessionId: number): Promise<ScanSessionDetail> {
    return request<ScanSessionDetail>(`/ops/scan-sessions/${sessionId}`);
  },

  getOpsScanSessionItems(
    sessionId: number,
    params?: {
      limit?: number;
      offset?: number;
    },
  ): Promise<ScanSessionItemsListResponse> {
    const query = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<ScanSessionItemsListResponse>(`/ops/scan-sessions/${sessionId}/items${query}`);
  },

  getOpsScanSessionQa(sessionId: number): Promise<ScanSessionQaSummaryRead> {
    return request<ScanSessionQaSummaryRead>(`/ops/scan-sessions/${sessionId}/qa`);
  },

  getOpsScanSessionItemQa(sessionId: number, itemId: number): Promise<ScanQaItemRead> {
    return request<ScanQaItemRead>(`/ops/scan-sessions/${sessionId}/items/${itemId}/qa`);
  },

  getOpsScanQaFleetSummary(): Promise<OpsScanQaFleetSummaryRead> {
    return request<OpsScanQaFleetSummaryRead>("/ops/scan-qa/summary");
  },

  getOpsScanPipelineDashboardSummary(): Promise<ScanPipelineDashboardSummary> {
    return request<ScanPipelineDashboardSummary>("/ops/scan-pipeline-dashboard/summary");
  },

  getOpsScanPipelineDashboard(): Promise<ScanPipelineDashboardResponse> {
    return request<ScanPipelineDashboardResponse>("/ops/scan-pipeline-dashboard");
  },

  getOpsScanRoutingRecommendations(): Promise<QueueRoutingListResponse> {
    return request<QueueRoutingListResponse>("/ops/scan-routing-recommendations");
  },

  getOpsScanSessionRouting(sessionId: number): Promise<ScanSessionRoutingRead> {
    return request<ScanSessionRoutingRead>(`/ops/scan-sessions/${sessionId}/routing`);
  },

  getPortfolioPerformance(): Promise<PortfolioPerformance> {
    return request<PortfolioPerformance>("/portfolio/performance");
  },

  getPhysicalIntakeSummary(): Promise<PhysicalIntakeSummaryResponse> {
    return request<PhysicalIntakeSummaryResponse>("/physical-intake/summary");
  },

  getPhysicalIntake(params?: { intake_state?: PhysicalIntakeState }): Promise<PhysicalIntakeListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<PhysicalIntakeListResponse>(`/physical-intake${query}`);
  },

  createPhysicalIntakeScanSession(payload: CreatePhysicalIntakeScanSessionPayload): Promise<ScanSessionDetail> {
    return request<ScanSessionDetail>("/physical-intake/create-scan-session", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  markInventoryPhysicallyReceived(
    inventoryCopyId: number,
    payload?: MarkInventoryReceivedPayload | null,
  ): Promise<InventoryItem> {
    return request<InventoryItem>(`/inventory/${inventoryCopyId}/mark-received`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  getOpsPhysicalIntakeSummary(): Promise<PhysicalIntakeSummaryResponse> {
    return request<PhysicalIntakeSummaryResponse>("/ops/physical-intake/summary");
  },

  getOpsPhysicalIntake(params?: { intake_state?: PhysicalIntakeState }): Promise<PhysicalIntakeListResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<PhysicalIntakeListResponse>(`/ops/physical-intake${query}`);
  },

  getInventoryCopy(inventoryCopyId: number): Promise<InventoryDetail> {
    return request<InventoryDetail>(`/inventory/${inventoryCopyId}`);
  },

  getInventoryFmvList(params: InventoryQueryParams): Promise<InventoryResponse> {
    const query = buildQueryString(params);
    return request<InventoryResponse>(`/inventory-fmv${query}`);
  },

  getOpsInventoryFmvList(params: InventoryQueryParams): Promise<InventoryResponse> {
    const query = buildQueryString(params);
    return request<InventoryResponse>(`/ops/inventory-fmv${query}`);
  },

  getInventoryFmvDetail(inventoryCopyId: number): Promise<InventoryFmvAttachmentRead> {
    return request<InventoryFmvAttachmentRead>(`/inventory/${inventoryCopyId}/fmv`);
  },

  getOpsInventoryFmvDetail(inventoryCopyId: number): Promise<InventoryFmvAttachmentRead> {
    return request<InventoryFmvAttachmentRead>(`/ops/inventory/${inventoryCopyId}/fmv`);
  },

  getPortfolioValueSummary(params?: {
    publisher?: string;
    ownership_state?: InventoryOwnershipNormalized;
    valuation_scope?: InventoryValuationScope;
    confidence_bucket?: MarketFmvConfidenceBucket;
    liquidity_bucket?: MarketFmvLiquidityBucket;
    stale_data?: boolean;
    currency_code?: string;
  }): Promise<PortfolioValueSummaryResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<PortfolioValueSummaryResponse>(`/portfolio-value/summary${query}`);
  },

  getOpsPortfolioValueSummary(params?: {
    publisher?: string;
    ownership_state?: InventoryOwnershipNormalized;
    valuation_scope?: InventoryValuationScope;
    confidence_bucket?: MarketFmvConfidenceBucket;
    liquidity_bucket?: MarketFmvLiquidityBucket;
    stale_data?: boolean;
    currency_code?: string;
  }): Promise<PortfolioValueSummaryResponse> {
    const query =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<PortfolioValueSummaryResponse>(`/ops/portfolio-value/summary${query}`);
  },

  getInventoryFmvHistory(inventoryCopyId: number): Promise<InventoryFmvSnapshot[]> {
    return request<InventoryFmvSnapshot[]>(`/inventory/${inventoryCopyId}/fmv-history`);
  },

  getInventoryCoverScanQa(inventoryCopyId: number): Promise<InventoryScanQaPanelRead> {
    return request<InventoryScanQaPanelRead>(`/inventory/${inventoryCopyId}/scan-qa`);
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

  listOpsScanPipelineReplays(params?: {
    scan_session_id?: number;
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanPipelineReplayListRead> {
    const query = buildQueryString(params as Record<string, string | number | undefined>);
    return request<ScanPipelineReplayListRead>(`/ops/scan-pipeline-replays${query}`);
  },

  getOpsScanPipelineReplay(replayId: number): Promise<ScanPipelineReplayRunRead> {
    return request<ScanPipelineReplayRunRead>(`/ops/scan-pipeline-replays/${replayId}`);
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

  /** Deterministic CSV/JSON exports (`GET /reports/...`): uses server ``Content-Disposition`` filename when provided. */

  downloadOwnerReportsInventoryCsvAll(): Promise<void> {
    return downloadAuthenticatedReport("/reports/inventory.csv", "inventory.csv");
  },

  downloadOwnerReportsInventoryCsvFiltered(listingFilters: InventoryQueryParams): Promise<void> {
    const query = inventoryListingQueryToReportQueryString(listingFilters);
    return downloadAuthenticatedReport(`/reports/inventory.csv${query}`, "inventory.csv");
  },

  downloadOwnerReportsInventoryJsonAll(): Promise<void> {
    return downloadAuthenticatedReport("/reports/inventory.json", "inventory.json");
  },

  downloadOwnerReportsInventoryJsonFiltered(listingFilters: InventoryQueryParams): Promise<void> {
    const query = inventoryListingQueryToReportQueryString(listingFilters);
    return downloadAuthenticatedReport(`/reports/inventory.json${query}`, "inventory.json");
  },

  downloadOwnerReportsActionCenterCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/action-center.csv", "inventory-action-center.csv");
  },

  downloadOwnerReportsOrderArrivalCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/order-arrival.csv", "order-arrival-intelligence.csv");
  },

  downloadOwnerReportsRunDetectionCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/run-detection.csv", "run-detection-series.csv");
  },

  downloadOwnerReportsTimelineCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/timeline.csv", "collection-timeline.csv");
  },

  downloadOwnerReportsCollectionSummaryJson(): Promise<void> {
    return downloadAuthenticatedReport("/reports/collection-summary.json", "collection-summary.json");
  },

  /** Market / FMV deterministic CSV + JSON snapshots (owner scope, read-only exports). */

  downloadOwnerReportsMarketSalesCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/market-sales.csv", "market-sales.csv");
  },

  downloadOwnerReportsMarketEligibleCompsCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/market-eligible-comps.csv", "market-eligible-comps.csv");
  },

  downloadOwnerReportsMarketFmvSnapshotsCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/market-fmv-snapshots.csv", "market-fmv-snapshots.csv");
  },

  downloadOwnerReportsMarketTrendsCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/market-trends.csv", "market-trends.csv");
  },

  downloadOwnerReportsMarketNormalizationIssuesCsv(): Promise<void> {
    return downloadAuthenticatedReport(
      "/reports/market-normalization-issues-summary.csv",
      "market-normalization-issues-summary.csv",
    );
  },

  downloadOwnerReportsPortfolioValueSummaryCsv(filters?: {
    publisher?: string;
    ownership_state?: string;
  }): Promise<void> {
    const q = filters ? buildQueryString(filters as Record<string, string | number | boolean | undefined>) : "";
    return downloadAuthenticatedReport(`/reports/portfolio-value-summary.csv${q}`, "portfolio-value-summary.csv");
  },

  downloadOwnerReportsInventoryNoMarketDataCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/inventory-no-market-data.csv", "inventory-no-market-data.csv");
  },

  downloadOwnerReportsInventoryNoMarketDataJson(): Promise<void> {
    return downloadAuthenticatedReport("/reports/inventory-no-market-data.json", "inventory-no-market-data.json");
  },

  downloadOwnerReportsInventoryFmvLowConfidenceCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/inventory-fmv-low-confidence.csv", "inventory-fmv-low-confidence.csv");
  },

  downloadOwnerReportsInventoryFmvStaleCsv(): Promise<void> {
    return downloadAuthenticatedReport("/reports/inventory-fmv-stale.csv", "inventory-fmv-stale.csv");
  },

  downloadOwnerReportsMarketDeterministicSummaryJson(filters?: {
    publisher?: string;
    ownership_state?: string;
  }): Promise<void> {
    const q = filters ? buildQueryString(filters as Record<string, string | number | boolean | undefined>) : "";
    return downloadAuthenticatedReport(
      `/reports/market-deterministic-summary.json${q}`,
      "market-deterministic-summary.json",
    );
  },

  /** Fleet-scoped deterministic exports (`GET /ops/reports/...`, ops admins only). */

  downloadOpsReportsInventoryCsvAll(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/inventory.csv", "ops-inventory-all-accounts.csv");
  },

  downloadOpsReportsInventoryJsonAll(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/inventory.json", "ops-inventory-all-accounts.json");
  },

  downloadOpsReportsActionCenterCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/action-center.csv", "ops-inventory-action-center.csv");
  },

  downloadOpsReportsOrderArrivalCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/order-arrival.csv", "ops-order-arrival-intelligence.csv");
  },

  downloadOpsReportsRunDetectionCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/run-detection.csv", "ops-run-detection-series.csv");
  },

  downloadOpsReportsTimelineCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/timeline.csv", "ops-collection-timeline.csv");
  },

  downloadOpsReportsCollectionSummaryJson(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/collection-summary.json", "ops-collection-summary.json");
  },

  /** Market / FMV deterministic exports (ops admins). */

  downloadOpsReportsMarketSalesCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/market-sales.csv", "ops-market-sales.csv");
  },

  downloadOpsReportsMarketEligibleCompsCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/market-eligible-comps.csv", "ops-market-eligible-comps.csv");
  },

  downloadOpsReportsMarketFmvSnapshotsCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/market-fmv-snapshots.csv", "ops-market-fmv-snapshots.csv");
  },

  downloadOpsReportsMarketTrendsCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/market-trends.csv", "ops-market-trends.csv");
  },

  downloadOpsReportsMarketNormalizationIssuesCsv(): Promise<void> {
    return downloadAuthenticatedReport(
      "/ops/reports/market-normalization-issues-summary.csv",
      "ops-market-normalization-issues-summary.csv",
    );
  },

  downloadOpsReportsPortfolioValueSummaryCsv(filters?: {
    publisher?: string;
    ownership_state?: string;
  }): Promise<void> {
    const q = filters ? buildQueryString(filters as Record<string, string | number | boolean | undefined>) : "";
    return downloadAuthenticatedReport(`/ops/reports/portfolio-value-summary.csv${q}`, "ops-portfolio-value-summary.csv");
  },

  downloadOpsReportsInventoryNoMarketDataCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/inventory-no-market-data.csv", "ops-inventory-no-market-data.csv");
  },

  downloadOpsReportsInventoryNoMarketDataJson(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/inventory-no-market-data.json", "ops-inventory-no-market-data.json");
  },

  downloadOpsReportsInventoryFmvLowConfidenceCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/inventory-fmv-low-confidence.csv", "ops-inventory-fmv-low-confidence.csv");
  },

  downloadOpsReportsInventoryFmvStaleCsv(): Promise<void> {
    return downloadAuthenticatedReport("/ops/reports/inventory-fmv-stale.csv", "ops-inventory-fmv-stale.csv");
  },

  downloadOpsReportsMarketDeterministicSummaryJson(filters?: {
    publisher?: string;
    ownership_state?: string;
  }): Promise<void> {
    const q = filters ? buildQueryString(filters as Record<string, string | number | boolean | undefined>) : "";
    return downloadAuthenticatedReport(
      `/ops/reports/market-deterministic-summary.json${q}`,
      "ops-market-deterministic-summary.json",
    );
  },

  getListingIntelligenceDashboardSummary(): Promise<ListingIntelligenceDashboardSummary> {
    return request<ListingIntelligenceDashboardSummary>("/listing-intelligence/dashboard-summary");
  },

  getOpsListingIntelligenceDashboardSummary(params?: { owner_user_id?: number }): Promise<ListingIntelligenceDashboardSummary> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<ListingIntelligenceDashboardSummary>(`/ops/listing-intelligence/dashboard-summary${q}`);
  },

  generateListingIntelligence(payload: ListingIntelligenceGeneratePayload): Promise<ListingIntelligenceGenerateResponse> {
    return request<ListingIntelligenceGenerateResponse>("/listing-intelligence/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getDealerDashboard(): Promise<DealerDashboardGetResponse> {
    return request<DealerDashboardGetResponse>("/dealer-dashboard");
  },

  generateDealerDashboard(payload: DealerDashboardGeneratePayload): Promise<DealerDashboardGenerateResponse> {
    return request<DealerDashboardGenerateResponse>("/dealer-dashboard/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listDealerDashboardMetrics(params?: {
    dashboard_snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<DealerDashboardMetricListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<DealerDashboardMetricListResponse>(`/dealer-dashboard/metrics${q}`);
  },

  listDealerDashboardAlerts(params?: {
    severity?: string;
    alert_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerDashboardAlertListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerDashboardAlertListResponse>(`/dealer-dashboard/alerts${q}`);
  },

  listDealerDashboardFeed(params?: {
    event_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerDashboardFeedListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerDashboardFeedListResponse>(`/dealer-dashboard/feed${q}`);
  },

  getOpsDealerDashboard(params?: { owner_user_id?: number }): Promise<DealerDashboardGetResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<DealerDashboardGetResponse>(`/ops/dealer-dashboard${q}`);
  },

  listOpsDealerDashboardMetrics(params?: {
    owner_user_id?: number;
    dashboard_snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<DealerDashboardMetricListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<DealerDashboardMetricListResponse>(`/ops/dealer-dashboard/metrics${q}`);
  },

  listOpsDealerDashboardAlerts(params?: {
    owner_user_id?: number;
    severity?: string;
    alert_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerDashboardAlertListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerDashboardAlertListResponse>(`/ops/dealer-dashboard/alerts${q}`);
  },

  listOpsDealerDashboardFeed(params?: {
    owner_user_id?: number;
    event_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerDashboardFeedListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerDashboardFeedListResponse>(`/ops/dealer-dashboard/feed${q}`);
  },

  getDealerGradingDashboard(): Promise<DealerGradingDashboardGetResponse> {
    return request<DealerGradingDashboardGetResponse>("/dealer-grading-dashboard");
  },

  generateDealerGradingDashboard(
    payload: DealerGradingDashboardGeneratePayload,
  ): Promise<DealerGradingDashboardGenerateResponse> {
    return request<DealerGradingDashboardGenerateResponse>("/dealer-grading-dashboard/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listDealerGradingDashboardMetrics(params?: {
    dashboard_snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<DealerGradingDashboardMetricListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<DealerGradingDashboardMetricListResponse>(`/dealer-grading-dashboard/metrics${q}`);
  },

  listDealerGradingDashboardAlerts(params?: {
    severity?: string;
    alert_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerGradingDashboardAlertListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerGradingDashboardAlertListResponse>(`/dealer-grading-dashboard/alerts${q}`);
  },

  listDealerGradingDashboardFeed(params?: {
    event_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerGradingDashboardFeedListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerGradingDashboardFeedListResponse>(`/dealer-grading-dashboard/feed${q}`);
  },

  getOpsDealerGradingDashboard(params?: { owner_user_id?: number }): Promise<DealerGradingDashboardGetResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<DealerGradingDashboardGetResponse>(`/ops/dealer-grading-dashboard${q}`);
  },

  listOpsDealerGradingDashboardMetrics(params?: {
    owner_user_id?: number;
    dashboard_snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<DealerGradingDashboardMetricListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<DealerGradingDashboardMetricListResponse>(`/ops/dealer-grading-dashboard/metrics${q}`);
  },

  listOpsDealerGradingDashboardAlerts(params?: {
    owner_user_id?: number;
    severity?: string;
    alert_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerGradingDashboardAlertListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerGradingDashboardAlertListResponse>(`/ops/dealer-grading-dashboard/alerts${q}`);
  },

  listOpsDealerGradingDashboardFeed(params?: {
    owner_user_id?: number;
    event_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<DealerGradingDashboardFeedListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<DealerGradingDashboardFeedListResponse>(`/ops/dealer-grading-dashboard/feed${q}`);
  },

  getPortfolioStrategyDashboard(): Promise<PortfolioStrategyDashboardGetResponse> {
    return request<PortfolioStrategyDashboardGetResponse>("/portfolio-strategy-dashboard");
  },

  generatePortfolioStrategyDashboard(
    payload: PortfolioStrategyDashboardGeneratePayload,
  ): Promise<PortfolioStrategyDashboardGenerateResponse> {
    return request<PortfolioStrategyDashboardGenerateResponse>("/portfolio-strategy-dashboard/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listPortfolioStrategyDashboardMetrics(params?: {
    dashboard_snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioStrategyDashboardMetricListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<PortfolioStrategyDashboardMetricListResponse>(`/portfolio-strategy-dashboard/metrics${q}`);
  },

  listPortfolioStrategyDashboardAlerts(params?: {
    severity?: string;
    alert_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioStrategyDashboardAlertListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<PortfolioStrategyDashboardAlertListResponse>(`/portfolio-strategy-dashboard/alerts${q}`);
  },

  listPortfolioStrategyDashboardFeed(params?: {
    event_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioStrategyDashboardFeedListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<PortfolioStrategyDashboardFeedListResponse>(`/portfolio-strategy-dashboard/feed${q}`);
  },

  getOpsPortfolioStrategyDashboard(params?: { owner_user_id?: number }): Promise<PortfolioStrategyDashboardGetResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<PortfolioStrategyDashboardGetResponse>(`/ops/portfolio-strategy-dashboard${q}`);
  },

  listOpsPortfolioStrategyDashboardMetrics(params?: {
    owner_user_id?: number;
    dashboard_snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioStrategyDashboardMetricListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<PortfolioStrategyDashboardMetricListResponse>(`/ops/portfolio-strategy-dashboard/metrics${q}`);
  },

  listOpsPortfolioStrategyDashboardAlerts(params?: {
    owner_user_id?: number;
    severity?: string;
    alert_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioStrategyDashboardAlertListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<PortfolioStrategyDashboardAlertListResponse>(`/ops/portfolio-strategy-dashboard/alerts${q}`);
  },

  listOpsPortfolioStrategyDashboardFeed(params?: {
    owner_user_id?: number;
    event_type?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioStrategyDashboardFeedListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<PortfolioStrategyDashboardFeedListResponse>(`/ops/portfolio-strategy-dashboard/feed${q}`);
  },

  createMarketIngestionBatch(
    payload: MarketAcquisitionIngestionBatchCreatePayload,
  ): Promise<MarketAcquisitionIngestionBatchRead> {
    return requestMarketV1<MarketAcquisitionIngestionBatchRead>("/market-ingestion/batch", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMarketIngestionBatches(params?: {
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionIngestionBatchListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionIngestionBatchListResponse>(`/market-ingestion/batches${q}`);
  },

  getMarketIngestionBatch(batchId: number): Promise<MarketAcquisitionIngestionBatchRead> {
    return requestMarketV1<MarketAcquisitionIngestionBatchRead>(`/market-ingestion/batches/${batchId}`);
  },

  listMarketIngestionBatchRaw(
    batchId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<MarketAcquisitionRawSourceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionRawSourceListResponse>(`/market-ingestion/batches/${batchId}/raw${q}`);
  },

  listOpsMarketIngestionBatches(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionIngestionBatchListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionIngestionBatchListResponse>(`/ops/market-ingestion/batches${q}`);
  },

  getOpsMarketIngestionBatch(batchId: number): Promise<MarketAcquisitionIngestionBatchRead> {
    return requestMarketV1<MarketAcquisitionIngestionBatchRead>(`/ops/market-ingestion/batches/${batchId}`);
  },

  listOpsMarketIngestionRaw(params?: {
    owner_user_id?: number;
    ingestion_batch_id?: number;
    processing_status?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionRawSourceListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionRawSourceListResponse>(`/ops/market-ingestion/raw${q}`);
  },

  uploadScanBatch(payload: ScanBatchUploadPayload, files: File[]): Promise<ScanIngestionBatchRead> {
    const form = new FormData();
    form.append("payload", JSON.stringify(payload));
    for (const file of files) {
      form.append("files", file);
    }
    return requestScanV1<ScanIngestionBatchRead>("/scan-ingestion/upload", {
      method: "POST",
      body: form,
    });
  },

  listScanBatches(params?: {
    limit?: number;
    offset?: number;
  }): Promise<ScanIngestionBatchListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanIngestionBatchListResponse>(`/scan-ingestion/batches${q}`);
  },

  getScanBatch(batchId: number): Promise<ScanIngestionBatchRead> {
    return requestScanV1<ScanIngestionBatchRead>(`/scan-ingestion/batches/${batchId}`);
  },

  getScanImage(scanImageId: number): Promise<ScanImageRead> {
    return requestScanV1<ScanImageRead>(`/scan-images/${scanImageId}`);
  },

  getScanUploadSession(uploadSessionId: number): Promise<ScanUploadSessionRead> {
    return requestScanV1<ScanUploadSessionRead>(`/scan-upload-sessions/${uploadSessionId}`);
  },

  listOpsScanBatches(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanIngestionBatchListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanIngestionBatchListResponse>(`/ops/scan-ingestion/batches${q}`);
  },

  listOpsScanFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanImageListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanImageListResponse>(`/ops/scan-ingestion/failures${q}`);
  },

  runScanNormalization(payload: ScanNormalizationRunPayload): Promise<ScanNormalizationRunRead> {
    return requestScanV1<ScanNormalizationRunRead>("/scan-normalization/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listNormalizationRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanNormalizationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanNormalizationRunListResponse>(`/scan-normalization/runs${q}`);
  },

  getNormalizationRun(runId: number): Promise<ScanNormalizationRunRead> {
    return requestScanV1<ScanNormalizationRunRead>(`/scan-normalization/runs/${runId}`);
  },

  listNormalizationIssues(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanNormalizationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanNormalizationIssueListResponse>(`/scan-normalization/issues${q}`);
  },

  getNormalizationArtifacts(artifactId: number): Promise<ScanNormalizationArtifactRead> {
    return requestScanV1<ScanNormalizationArtifactRead>(`/scan-normalization/artifacts/${artifactId}`);
  },

  listOpsNormalizationRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanNormalizationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanNormalizationRunListResponse>(`/ops/scan-normalization/runs${q}`);
  },

  listOpsNormalizationIssues(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanNormalizationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanNormalizationIssueListResponse>(`/ops/scan-normalization/issues${q}`);
  },

  listOpsNormalizationFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanNormalizationFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanNormalizationFailureListResponse>(`/ops/scan-normalization/failures${q}`);
  },

  runScanBoundaryMapping(payload: ScanBoundaryRunCreate): Promise<ScanBoundaryRunDetail> {
    return requestScanV1<ScanBoundaryRunDetail>("/scan-boundary/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanBoundaryRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanBoundaryRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanBoundaryRunListResponse>(`/scan-boundary/runs${q}`);
  },

  getScanBoundaryRun(runId: number): Promise<ScanBoundaryRunDetail> {
    return requestScanV1<ScanBoundaryRunDetail>(`/scan-boundary/runs/${runId}`);
  },

  listScanBoundaryIssues(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanBoundaryIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanBoundaryIssueListResponse>(`/scan-boundary/issues${q}`);
  },

  getScanBoundaryArtifact(artifactId: number): Promise<ScanBoundaryArtifactRead> {
    return requestScanV1<ScanBoundaryArtifactRead>(`/scan-boundary/artifacts/${artifactId}`);
  },

  listOpsScanBoundaryRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanBoundaryRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanBoundaryRunListResponse>(`/ops/scan-boundary/runs${q}`);
  },

  listOpsScanBoundaryIssues(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanBoundaryIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanBoundaryIssueListResponse>(`/ops/scan-boundary/issues${q}`);
  },

  listOpsScanBoundaryFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanBoundaryFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanBoundaryFailureListResponse>(`/ops/scan-boundary/failures${q}`);
  },

  runScanOcr(payload: ScanOcrRunCreate): Promise<ScanOcrRunDetail> {
    return requestScanV1<ScanOcrRunDetail>("/scan-ocr/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanOcrRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanOcrRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanOcrRunListResponse>(`/scan-ocr/runs${q}`);
  },

  getScanOcrRun(runId: number): Promise<ScanOcrRunDetail> {
    return requestScanV1<ScanOcrRunDetail>(`/scan-ocr/runs/${runId}`);
  },

  listScanOcrCandidates(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanOcrCandidateListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanOcrCandidateListResponse>(`/scan-ocr/candidates${q}`);
  },

  listScanOcrIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanOcrIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanOcrIssueListResponse>(`/scan-ocr/issues${q}`);
  },

  getScanOcrArtifact(artifactId: number): Promise<ScanOcrArtifactRead> {
    return requestScanV1<ScanOcrArtifactRead>(`/scan-ocr/artifacts/${artifactId}`);
  },

  listOpsScanOcrRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanOcrRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanOcrRunListResponse>(`/ops/scan-ocr/runs${q}`);
  },

  listOpsScanOcrIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanOcrIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanOcrIssueListResponse>(`/ops/scan-ocr/issues${q}`);
  },

  listOpsScanOcrFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanOcrFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanOcrFailureListResponse>(`/ops/scan-ocr/failures${q}`);
  },

  runScanReconciliation(payload: ScanReconciliationRunCreate): Promise<ScanReconciliationRunDetail> {
    return requestScanV1<ScanReconciliationRunDetail>("/scan-reconciliation/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanReconciliationRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReconciliationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReconciliationRunListResponse>(`/scan-reconciliation/runs${q}`);
  },

  getScanReconciliationRun(runId: number): Promise<ScanReconciliationRunDetail> {
    return requestScanV1<ScanReconciliationRunDetail>(`/scan-reconciliation/runs/${runId}`);
  },

  listScanReconciliationCandidates(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReconciliationCandidateListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReconciliationCandidateListResponse>(`/scan-reconciliation/candidates${q}`);
  },

  listScanReconciliationIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReconciliationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReconciliationIssueListResponse>(`/scan-reconciliation/issues${q}`);
  },

  getScanReconciliationArtifact(artifactId: number): Promise<ScanReconciliationArtifactRead> {
    return requestScanV1<ScanReconciliationArtifactRead>(`/scan-reconciliation/artifacts/${artifactId}`);
  },

  listOpsScanReconciliationRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReconciliationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReconciliationRunListResponse>(`/ops/scan-reconciliation/runs${q}`);
  },

  listOpsScanReconciliationIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReconciliationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReconciliationIssueListResponse>(`/ops/scan-reconciliation/issues${q}`);
  },

  listOpsScanReconciliationFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReconciliationFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReconciliationFailureListResponse>(`/ops/scan-reconciliation/failures${q}`);
  },

  runScanDefectFoundation(payload: ScanDefectRunCreate): Promise<ScanDefectRunDetail> {
    return requestScanV1<ScanDefectRunDetail>("/scan-defects/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanDefectRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectRunListResponse>(`/scan-defects/runs${q}`);
  },

  getScanDefectRun(runId: number): Promise<ScanDefectRunDetail> {
    return requestScanV1<ScanDefectRunDetail>(`/scan-defects/runs/${runId}`);
  },

  listScanDefectRegions(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectRegionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectRegionListResponse>(`/scan-defects/regions${q}`);
  },

  listScanDefectEvidence(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectEvidenceListResponse>(`/scan-defects/evidence${q}`);
  },

  listScanDefectIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectIssueListResponse>(`/scan-defects/issues${q}`);
  },

  getScanDefectArtifact(artifactId: number): Promise<ScanDefectArtifactRead> {
    return requestScanV1<ScanDefectArtifactRead>(`/scan-defects/artifacts/${artifactId}`);
  },

  listScanDefectQualityGates(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectIssueListResponse>(`/scan-defects/issues${q}`);
  },

  listOpsScanDefectRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectRunListResponse>(`/ops/scan-defects/runs${q}`);
  },

  listOpsScanDefectIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectIssueListResponse>(`/ops/scan-defects/issues${q}`);
  },

  listOpsScanDefectFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectFailureListResponse>(`/ops/scan-defects/failures${q}`);
  },

  listOpsScanDefectQualityGates(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectIssueListResponse>(`/ops/scan-defects/quality-gates${q}`);
  },

  runScanSpineTickDetection(payload: ScanSpineTickRunCreate): Promise<ScanSpineTickRunDetail> {
    return requestScanV1<ScanSpineTickRunDetail>("/scan-spine-ticks/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanSpineTickRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSpineTickRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSpineTickRunListResponse>(`/scan-spine-ticks/runs${q}`);
  },

  getScanSpineTickRun(runId: number): Promise<ScanSpineTickRunDetail> {
    return requestScanV1<ScanSpineTickRunDetail>(`/scan-spine-ticks/runs/${runId}`);
  },

  listScanSpineTickEvidence(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSpineTickEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSpineTickEvidenceListResponse>(`/scan-spine-ticks/evidence${q}`);
  },

  listScanSpineTickIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSpineTickIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSpineTickIssueListResponse>(`/scan-spine-ticks/issues${q}`);
  },

  getScanSpineTickArtifact(artifactId: number): Promise<ScanSpineTickArtifactRead> {
    return requestScanV1<ScanSpineTickArtifactRead>(`/scan-spine-ticks/artifacts/${artifactId}`);
  },

  listOpsScanSpineTickRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSpineTickRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSpineTickRunListResponse>(`/ops/scan-spine-ticks/runs${q}`);
  },

  listOpsScanSpineTickIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSpineTickIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSpineTickIssueListResponse>(`/ops/scan-spine-ticks/issues${q}`);
  },

  listOpsScanSpineTickFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSpineTickFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSpineTickFailureListResponse>(`/ops/scan-spine-ticks/failures${q}`);
  },

  runScanCornerEdgeDetection(payload: ScanCornerEdgeRunCreate): Promise<ScanCornerEdgeRunDetail> {
    return requestScanV1<ScanCornerEdgeRunDetail>("/scan-corner-edges/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanCornerEdgeRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanCornerEdgeRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanCornerEdgeRunListResponse>(`/scan-corner-edges/runs${q}`);
  },

  getScanCornerEdgeRun(runId: number): Promise<ScanCornerEdgeRunDetail> {
    return requestScanV1<ScanCornerEdgeRunDetail>(`/scan-corner-edges/runs/${runId}`);
  },

  listScanCornerEdgeEvidence(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanCornerEdgeEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanCornerEdgeEvidenceListResponse>(`/scan-corner-edges/evidence${q}`);
  },

  listScanCornerEdgeIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanCornerEdgeIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanCornerEdgeIssueListResponse>(`/scan-corner-edges/issues${q}`);
  },

  getScanCornerEdgeArtifact(artifactId: number): Promise<ScanCornerEdgeArtifactRead> {
    return requestScanV1<ScanCornerEdgeArtifactRead>(`/scan-corner-edges/artifacts/${artifactId}`);
  },

  listOpsScanCornerEdgeRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanCornerEdgeRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanCornerEdgeRunListResponse>(`/ops/scan-corner-edges/runs${q}`);
  },

  listOpsScanCornerEdgeIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanCornerEdgeIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanCornerEdgeIssueListResponse>(`/ops/scan-corner-edges/issues${q}`);
  },

  listOpsScanCornerEdgeFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanCornerEdgeFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanCornerEdgeFailureListResponse>(`/ops/scan-corner-edges/failures${q}`);
  },

  runScanSurfaceDefectDetection(payload: ScanSurfaceDefectRunCreate): Promise<ScanSurfaceDefectRunDetail> {
    return requestScanV1<ScanSurfaceDefectRunDetail>("/scan-surface-defects/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanSurfaceDefectRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSurfaceDefectRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSurfaceDefectRunListResponse>(`/scan-surface-defects/runs${q}`);
  },

  getScanSurfaceDefectRun(runId: number): Promise<ScanSurfaceDefectRunDetail> {
    return requestScanV1<ScanSurfaceDefectRunDetail>(`/scan-surface-defects/runs/${runId}`);
  },

  listScanSurfaceDefectEvidence(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSurfaceDefectEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSurfaceDefectEvidenceListResponse>(`/scan-surface-defects/evidence${q}`);
  },

  listScanSurfaceDefectIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSurfaceDefectIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSurfaceDefectIssueListResponse>(`/scan-surface-defects/issues${q}`);
  },

  getScanSurfaceDefectArtifact(artifactId: number): Promise<ScanSurfaceDefectArtifactRead> {
    return requestScanV1<ScanSurfaceDefectArtifactRead>(`/scan-surface-defects/artifacts/${artifactId}`);
  },

  listOpsScanSurfaceDefectRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSurfaceDefectRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSurfaceDefectRunListResponse>(`/ops/scan-surface-defects/runs${q}`);
  },

  listOpsScanSurfaceDefectIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSurfaceDefectIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSurfaceDefectIssueListResponse>(`/ops/scan-surface-defects/issues${q}`);
  },

  listOpsScanSurfaceDefectFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanSurfaceDefectFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanSurfaceDefectFailureListResponse>(`/ops/scan-surface-defects/failures${q}`);
  },

  runScanStructuralDamageDetection(payload: ScanStructuralDamageRunCreate): Promise<ScanStructuralDamageRunDetail> {
    return requestScanV1<ScanStructuralDamageRunDetail>("/scan-structural-damage/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanStructuralDamageRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanStructuralDamageRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanStructuralDamageRunListResponse>(`/scan-structural-damage/runs${q}`);
  },

  getScanStructuralDamageRun(runId: number): Promise<ScanStructuralDamageRunDetail> {
    return requestScanV1<ScanStructuralDamageRunDetail>(`/scan-structural-damage/runs/${runId}`);
  },

  listScanStructuralDamageEvidence(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanStructuralDamageEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanStructuralDamageEvidenceListResponse>(`/scan-structural-damage/evidence${q}`);
  },

  listScanStructuralDamageIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanStructuralDamageIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanStructuralDamageIssueListResponse>(`/scan-structural-damage/issues${q}`);
  },

  getScanStructuralDamageArtifact(artifactId: number): Promise<ScanStructuralDamageArtifactRead> {
    return requestScanV1<ScanStructuralDamageArtifactRead>(`/scan-structural-damage/artifacts/${artifactId}`);
  },

  listOpsScanStructuralDamageRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanStructuralDamageRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanStructuralDamageRunListResponse>(`/ops/scan-structural-damage/runs${q}`);
  },

  listOpsScanStructuralDamageIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanStructuralDamageIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanStructuralDamageIssueListResponse>(`/ops/scan-structural-damage/issues${q}`);
  },

  listOpsScanStructuralDamageFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanStructuralDamageFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanStructuralDamageFailureListResponse>(`/ops/scan-structural-damage/failures${q}`);
  },

  runScanDefectAggregation(payload: ScanDefectAggregationRunCreate): Promise<ScanDefectAggregationRunDetail> {
    return requestScanV1<ScanDefectAggregationRunDetail>("/scan-defect-aggregation/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanDefectAggregationRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectAggregationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectAggregationRunListResponse>(`/scan-defect-aggregation/runs${q}`);
  },

  getScanDefectAggregationRun(runId: number): Promise<ScanDefectAggregationRunDetail> {
    return requestScanV1<ScanDefectAggregationRunDetail>(`/scan-defect-aggregation/runs/${runId}`);
  },

  listScanDefectAggregateClusters(params?: {
    scan_image_id?: number;
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectAggregateClusterListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectAggregateClusterListResponse>(`/scan-defect-aggregation/clusters${q}`);
  },

  listScanDefectAggregationEvidence(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectAggregateEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectAggregateEvidenceListResponse>(`/scan-defect-aggregation/evidence${q}`);
  },

  listScanDefectAggregationIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectAggregationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectAggregationIssueListResponse>(`/scan-defect-aggregation/issues${q}`);
  },

  getScanDefectAggregationArtifact(artifactId: number): Promise<ScanDefectAggregationArtifactRead> {
    return requestScanV1<ScanDefectAggregationArtifactRead>(`/scan-defect-aggregation/artifacts/${artifactId}`);
  },

  listOpsScanDefectAggregationRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectAggregationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectAggregationRunListResponse>(`/ops/scan-defect-aggregation/runs${q}`);
  },

  listOpsScanDefectAggregationIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectAggregationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectAggregationIssueListResponse>(`/ops/scan-defect-aggregation/issues${q}`);
  },

  listOpsScanDefectAggregationFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanDefectAggregationFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanDefectAggregationFailureListResponse>(`/ops/scan-defect-aggregation/failures${q}`);
  },

  runScanGradingAssistance(payload: ScanGradingAssistanceRunCreate): Promise<ScanGradingAssistanceRunDetail> {
    return requestScanV1<ScanGradingAssistanceRunDetail>("/scan-grading-assistance/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanGradingAssistanceRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanGradingAssistanceRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanGradingAssistanceRunListResponse>(`/scan-grading-assistance/runs${q}`);
  },

  getScanGradingAssistanceRun(runId: number): Promise<ScanGradingAssistanceRunDetail> {
    return requestScanV1<ScanGradingAssistanceRunDetail>(`/scan-grading-assistance/runs/${runId}`);
  },

  listScanGradingAssistanceCategories(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanGradingAssistanceCategoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanGradingAssistanceCategoryListResponse>(`/scan-grading-assistance/categories${q}`);
  },

  listScanGradingAssistanceFindings(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanGradingAssistanceFindingListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanGradingAssistanceFindingListResponse>(`/scan-grading-assistance/findings${q}`);
  },

  listScanGradingAssistanceIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanGradingAssistanceIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanGradingAssistanceIssueListResponse>(`/scan-grading-assistance/issues${q}`);
  },

  getScanGradingAssistanceArtifact(artifactId: number): Promise<ScanGradingAssistanceArtifactRead> {
    return requestScanV1<ScanGradingAssistanceArtifactRead>(`/scan-grading-assistance/artifacts/${artifactId}`);
  },

  listOpsScanGradingAssistanceRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanGradingAssistanceRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanGradingAssistanceRunListResponse>(`/ops/scan-grading-assistance/runs${q}`);
  },

  listOpsScanGradingAssistanceIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanGradingAssistanceIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanGradingAssistanceIssueListResponse>(`/ops/scan-grading-assistance/issues${q}`);
  },

  listOpsScanGradingAssistanceFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanGradingAssistanceFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanGradingAssistanceFailureListResponse>(`/ops/scan-grading-assistance/failures${q}`);
  },

  runScanVisualEvidence(payload: ScanVisualEvidenceRunCreate): Promise<ScanVisualEvidenceRunDetail> {
    return requestScanV1<ScanVisualEvidenceRunDetail>("/scan-visual-evidence/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanVisualEvidenceRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidenceRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidenceRunListResponse>(`/scan-visual-evidence/runs${q}`);
  },

  getScanVisualEvidenceRun(runId: number): Promise<ScanVisualEvidenceRunDetail> {
    return requestScanV1<ScanVisualEvidenceRunDetail>(`/scan-visual-evidence/runs/${runId}`);
  },

  listScanVisualEvidencePackages(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidencePackageListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidencePackageListResponse>(`/scan-visual-evidence/packages${q}`);
  },

  listScanVisualEvidenceItems(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidenceItemListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidenceItemListResponse>(`/scan-visual-evidence/items${q}`);
  },

  listScanVisualEvidenceAnnotations(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidenceAnnotationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidenceAnnotationListResponse>(`/scan-visual-evidence/annotations${q}`);
  },

  listScanVisualEvidenceIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidenceIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidenceIssueListResponse>(`/scan-visual-evidence/issues${q}`);
  },

  getScanVisualEvidenceArtifact(artifactId: number): Promise<ScanVisualEvidenceArtifactRead> {
    return requestScanV1<ScanVisualEvidenceArtifactRead>(`/scan-visual-evidence/artifacts/${artifactId}`);
  },

  listOpsScanVisualEvidenceRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidenceRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidenceRunListResponse>(`/ops/scan-visual-evidence/runs${q}`);
  },

  listOpsScanVisualEvidenceIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidenceIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidenceIssueListResponse>(`/ops/scan-visual-evidence/issues${q}`);
  },

  listOpsScanVisualEvidenceFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanVisualEvidenceFailureListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanVisualEvidenceFailureListResponse>(`/ops/scan-visual-evidence/failures${q}`);
  },

  createScanReviewSession(payload: ScanReviewSessionCreate): Promise<ScanReviewSessionDetail> {
    return requestScanV1<ScanReviewSessionDetail>("/scan-review/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanReviewSessions(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReviewSessionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReviewSessionListResponse>(`/scan-review/sessions${q}`);
  },

  getScanReviewSession(reviewSessionId: number): Promise<ScanReviewSessionDetail> {
    return requestScanV1<ScanReviewSessionDetail>(`/scan-review/sessions/${reviewSessionId}`);
  },

  recordScanReviewDecision(reviewSessionId: number, payload: ScanReviewDecisionCreate): Promise<ScanReviewSessionDetail> {
    return requestScanV1<ScanReviewSessionDetail>(`/scan-review/sessions/${reviewSessionId}/decisions`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  recordScanReviewNote(reviewSessionId: number, payload: ScanReviewNoteCreate): Promise<ScanReviewSessionDetail> {
    return requestScanV1<ScanReviewSessionDetail>(`/scan-review/sessions/${reviewSessionId}/notes`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  recordScanReviewEvidenceAction(reviewSessionId: number, payload: ScanReviewEvidenceActionCreate): Promise<ScanReviewSessionDetail> {
    return requestScanV1<ScanReviewSessionDetail>(`/scan-review/sessions/${reviewSessionId}/evidence-actions`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  completeScanReviewSession(reviewSessionId: number): Promise<ScanReviewSessionDetail> {
    return requestScanV1<ScanReviewSessionDetail>(`/scan-review/sessions/${reviewSessionId}/complete`, {
      method: "POST",
    });
  },

  listScanReviewIssues(params?: {
    review_session_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReviewIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReviewIssueListResponse>(`/scan-review/issues${q}`);
  },

  getScanReviewArtifact(artifactId: number): Promise<ScanReviewArtifactRead> {
    return requestScanV1<ScanReviewArtifactRead>(`/scan-review/artifacts/${artifactId}`);
  },

  listOpsScanReviewSessions(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReviewSessionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReviewSessionListResponse>(`/ops/scan-review/sessions${q}`);
  },

  listOpsScanReviewIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReviewIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReviewIssueListResponse>(`/ops/scan-review/issues${q}`);
  },

  listOpsScanReviewBlocked(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReviewSessionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReviewSessionListResponse>(`/ops/scan-review/blocked${q}`);
  },

  listOpsScanReviewRescans(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReviewSessionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReviewSessionListResponse>(`/ops/scan-review/rescans${q}`);
  },

  runScanHistoricalComparison(payload: ScanHistoricalComparisonRunCreate): Promise<ScanHistoricalComparisonRunDetail> {
    return requestScanV1<ScanHistoricalComparisonRunDetail>("/scan-historical-comparison/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanHistoricalComparisonRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonRunListResponse>(`/scan-historical-comparison/runs${q}`);
  },

  getScanHistoricalComparisonRun(runId: number): Promise<ScanHistoricalComparisonRunDetail> {
    return requestScanV1<ScanHistoricalComparisonRunDetail>(`/scan-historical-comparison/runs/${runId}`);
  },

  listScanHistoricalComparisonPairs(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonPairListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonPairListResponse>(`/scan-historical-comparison/pairs${q}`);
  },

  listScanHistoricalComparisonDeltas(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonDeltaListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonDeltaListResponse>(`/scan-historical-comparison/deltas${q}`);
  },

  listScanHistoricalComparisonIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonIssueListResponse>(`/scan-historical-comparison/issues${q}`);
  },

  getScanHistoricalComparisonArtifact(artifactId: number): Promise<ScanHistoricalComparisonArtifactRead> {
    return requestScanV1<ScanHistoricalComparisonArtifactRead>(`/scan-historical-comparison/artifacts/${artifactId}`);
  },

  listOpsScanHistoricalComparisonRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonRunListResponse>(`/ops/scan-historical-comparison/runs${q}`);
  },

  listOpsScanHistoricalComparisonIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonIssueListResponse>(`/ops/scan-historical-comparison/issues${q}`);
  },

  listOpsScanHistoricalComparisonFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonRunListResponse>(`/ops/scan-historical-comparison/failures${q}`);
  },

  listOpsScanHistoricalComparisonInconclusive(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanHistoricalComparisonRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanHistoricalComparisonRunListResponse>(`/ops/scan-historical-comparison/inconclusive${q}`);
  },

  runScanAuthentication(payload: ScanAuthenticationRunCreate): Promise<ScanAuthenticationRunDetail> {
    return requestScanV1<ScanAuthenticationRunDetail>("/scan-authentication/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanAuthenticationRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationRunListResponse>(`/scan-authentication/runs${q}`);
  },

  getScanAuthenticationRun(runId: number): Promise<ScanAuthenticationRunDetail> {
    return requestScanV1<ScanAuthenticationRunDetail>(`/scan-authentication/runs/${runId}`);
  },

  listScanAuthenticationSignals(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationSignalListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationSignalListResponse>(`/scan-authentication/signals${q}`);
  },

  listScanAuthenticationFindings(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationFindingListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationFindingListResponse>(`/scan-authentication/findings${q}`);
  },

  listScanAuthenticationIssues(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationIssueListResponse>(`/scan-authentication/issues${q}`);
  },

  getScanAuthenticationArtifact(artifactId: number): Promise<ScanAuthenticationArtifactRead> {
    return requestScanV1<ScanAuthenticationArtifactRead>(`/scan-authentication/artifacts/${artifactId}`);
  },

  listOpsScanAuthenticationRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationRunListResponse>(`/ops/scan-authentication/runs${q}`);
  },

  listOpsScanAuthenticationIssues(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationIssueListResponse>(`/ops/scan-authentication/issues${q}`);
  },

  listOpsScanAuthenticationFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationRunListResponse>(`/ops/scan-authentication/failures${q}`);
  },

  listOpsScanAuthenticationConflicts(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanAuthenticationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanAuthenticationRunListResponse>(`/ops/scan-authentication/conflicts${q}`);
  },

  runScanIntelligenceFeed(payload: ScanIntelligenceFeedRunCreate): Promise<ScanIntelligenceFeedRunDetail> {
    return requestScanV1<ScanIntelligenceFeedRunDetail>("/scan-intelligence-feed/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanIntelligenceFeedRuns(params?: {
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedRunListResponse>(`/scan-intelligence-feed/runs${q}`);
  },

  getScanIntelligenceFeedRun(runId: number): Promise<ScanIntelligenceFeedRunDetail> {
    return requestScanV1<ScanIntelligenceFeedRunDetail>(`/scan-intelligence-feed/runs/${runId}`);
  },

  listScanIntelligenceFeedEvents(params?: {
    run_id?: number;
    severity?: string;
    event_category?: string;
    source_system?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedEventListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedEventListResponse>(`/scan-intelligence-feed/events${q}`);
  },

  listScanIntelligenceFeedIssues(params?: {
    run_id?: number;
    severity?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedIssueListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedIssueListResponse>(`/scan-intelligence-feed/issues${q}`);
  },

  getScanIntelligenceFeedArtifact(artifactId: number): Promise<ScanIntelligenceFeedArtifactRead> {
    return requestScanV1<ScanIntelligenceFeedArtifactRead>(`/scan-intelligence-feed/artifacts/${artifactId}`);
  },

  listOpsScanIntelligenceFeedRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedRunListResponse>(`/ops/scan-intelligence-feed/runs${q}`);
  },

  listOpsScanIntelligenceFeedEvents(params?: {
    owner_user_id?: number;
    run_id?: number;
    severity?: string;
    event_category?: string;
    source_system?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedEventListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedEventListResponse>(`/ops/scan-intelligence-feed/events${q}`);
  },

  listOpsScanIntelligenceFeedIssues(params?: {
    owner_user_id?: number;
    run_id?: number;
    severity?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedIssueListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedIssueListResponse>(`/ops/scan-intelligence-feed/issues${q}`);
  },

  listOpsScanIntelligenceFeedFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedEventListResponse>(`/ops/scan-intelligence-feed/failures${q}`);
  },

  listOpsScanIntelligenceFeedReviewRequired(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanIntelligenceFeedEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanIntelligenceFeedEventListResponse>(`/ops/scan-intelligence-feed/review-required${q}`);
  },

  runScanReplay(payload: ScanReplayRunCreate): Promise<ScanReplayRunDetail> {
    return requestScanV1<ScanReplayRunDetail>("/scan-replay/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listScanReplayRuns(params?: {
    scan_image_id?: number;
    replay_scope?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayRunListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanReplayRunListResponse>(`/scan-replay/runs${q}`);
  },

  getScanReplayRun(runId: number): Promise<ScanReplayRunDetail> {
    return requestScanV1<ScanReplayRunDetail>(`/scan-replay/runs/${runId}`);
  },

  listScanReplaySteps(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayStepListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReplayStepListResponse>(`/scan-replay/steps${q}`);
  },

  listScanReplayChecks(params?: {
    run_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayCheckListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReplayCheckListResponse>(`/scan-replay/checks${q}`);
  },

  listScanReplayDiscrepancies(params?: {
    run_id?: number;
    severity?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayDiscrepancyListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanReplayDiscrepancyListResponse>(`/scan-replay/discrepancies${q}`);
  },

  listScanReplayIssues(params?: {
    run_id?: number;
    severity?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayIssueListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanReplayIssueListResponse>(`/scan-replay/issues${q}`);
  },

  getScanReplayArtifact(artifactId: number): Promise<ScanReplayArtifactRead> {
    return requestScanV1<ScanReplayArtifactRead>(`/scan-replay/artifacts/${artifactId}`);
  },

  listOpsScanReplayRuns(params?: {
    owner_user_id?: number;
    scan_image_id?: number;
    replay_scope?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayRunListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanReplayRunListResponse>(`/ops/scan-replay/runs${q}`);
  },

  listOpsScanReplayDiscrepancies(params?: {
    owner_user_id?: number;
    run_id?: number;
    severity?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayDiscrepancyListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanReplayDiscrepancyListResponse>(`/ops/scan-replay/discrepancies${q}`);
  },

  listOpsScanReplayIssues(params?: {
    owner_user_id?: number;
    run_id?: number;
    severity?: string;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayIssueListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<ScanReplayIssueListResponse>(`/ops/scan-replay/issues${q}`);
  },

  listOpsScanReplayFailures(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayDiscrepancyListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReplayDiscrepancyListResponse>(`/ops/scan-replay/failures${q}`);
  },

  listOpsScanReplayCritical(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ScanReplayDiscrepancyListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<ScanReplayDiscrepancyListResponse>(`/ops/scan-replay/critical${q}`);
  },

  createAutomationJob(payload: AutomationJobCreate): Promise<AutomationJobDetail> {
    return requestScanV1<AutomationJobDetail>("/automation/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listAutomationJobs(params?: {
    queue_key?: string;
    job_status?: string;
    limit?: number;
    offset?: number;
  }): Promise<AutomationJobListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<AutomationJobListResponse>(`/automation/jobs${q}`);
  },

  getAutomationJob(jobId: number): Promise<AutomationJobDetail> {
    return requestScanV1<AutomationJobDetail>(`/automation/jobs/${jobId}`);
  },

  listAutomationJobAttempts(jobId: number): Promise<AutomationJobAttemptListResponse> {
    return requestScanV1<AutomationJobAttemptListResponse>(`/automation/jobs/${jobId}/attempts`);
  },

  listAutomationJobHistory(jobId: number): Promise<AutomationJobHistoryListResponse> {
    return requestScanV1<AutomationJobHistoryListResponse>(`/automation/jobs/${jobId}/history`);
  },

  listAutomationJobIssues(jobId: number): Promise<AutomationJobIssueListResponse> {
    return requestScanV1<AutomationJobIssueListResponse>(`/automation/jobs/${jobId}/issues`);
  },

  getAutomationJobArtifact(jobId: number, artifactId: number): Promise<AutomationJobArtifactRead> {
    return requestScanV1<AutomationJobArtifactRead>(`/automation/jobs/${jobId}/artifacts/${artifactId}`);
  },

  listAutomationQueues(params?: { limit?: number; offset?: number }): Promise<AutomationQueueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationQueueListResponse>(`/ops/automation/queues${q}`);
  },

  listOpsAutomationJobs(params?: {
    owner_user_id?: number;
    organization_id?: number;
    queue_key?: string;
    job_status?: string;
    limit?: number;
    offset?: number;
  }): Promise<AutomationJobListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<AutomationJobListResponse>(`/ops/automation/jobs${q}`);
  },

  listOpsAutomationFailedJobs(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<AutomationJobListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationJobListResponse>(`/ops/automation/jobs/failed${q}`);
  },

  listOpsAutomationDeadLetterJobs(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<AutomationJobListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationJobListResponse>(`/ops/automation/jobs/dead-letter${q}`);
  },

  listOpsAutomationIssues(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationJobIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationJobIssueListResponse>(`/ops/automation/issues${q}`);
  },

  getOpsAutomationQueueHealth(params?: { limit?: number; offset?: number }): Promise<AutomationQueueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationQueueListResponse>(`/ops/automation/queue-health${q}`);
  },

  listAutomationWorkers(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkerListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkerListResponse>(`/automation/workers${q}`);
  },

  getAutomationWorker(workerId: number): Promise<AutomationWorkerDetail> {
    return requestScanV1<AutomationWorkerDetail>(`/automation/workers/${workerId}`);
  },

  listAutomationWorkerExecutions(workerId: number, params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkerExecutionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkerExecutionListResponse>(`/automation/workers/${workerId}/executions${q}`);
  },

  listAutomationWorkerHistory(workerId: number, params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkerHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkerHistoryListResponse>(`/automation/workers/${workerId}/history${q}`);
  },

  listAutomationWorkerIssues(workerId: number, params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkerIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkerIssueListResponse>(`/automation/workers/${workerId}/issues${q}`);
  },

  listOpsAutomationWorkers(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkerListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkerListResponse>(`/ops/automation/workers${q}`);
  },

  listOpsAutomationWorkerIssues(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkerIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkerIssueListResponse>(`/ops/automation/workers/issues${q}`);
  },

  listOpsAutomationStaleWorkers(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkerListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkerListResponse>(`/ops/automation/workers/stale${q}`);
  },

  createAutomationSchedule(payload: AutomationScheduleCreate): Promise<AutomationScheduleRead> {
    return requestScanV1<AutomationScheduleRead>("/automation/schedules", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listAutomationSchedules(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationScheduleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationScheduleListResponse>(`/automation/schedules${q}`);
  },

  getAutomationSchedule(scheduleId: number): Promise<AutomationScheduleRead> {
    return requestScanV1<AutomationScheduleRead>(`/automation/schedules/${scheduleId}`);
  },

  createAutomationTrigger(payload: AutomationTriggerCreate): Promise<AutomationTriggerRead> {
    return requestScanV1<AutomationTriggerRead>("/automation/triggers", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listAutomationTriggers(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationTriggerListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationTriggerListResponse>(`/automation/triggers${q}`);
  },

  listAutomationWorkflows(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkflowListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkflowListResponse>(`/automation/workflows${q}`);
  },

  getAutomationWorkflow(workflowId: number): Promise<AutomationWorkflowRead> {
    return requestScanV1<AutomationWorkflowRead>(`/automation/workflows/${workflowId}`);
  },

  listAutomationWorkflowExecutions(
    workflowId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<AutomationWorkflowExecutionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkflowExecutionListResponse>(`/automation/workflows/${workflowId}/executions${q}`);
  },

  listAutomationWorkflowHistory(
    workflowId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<AutomationWorkflowHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkflowHistoryListResponse>(`/automation/workflows/${workflowId}/history${q}`);
  },

  listOpsAutomationWorkflows(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkflowListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkflowListResponse>(`/ops/automation/workflows${q}`);
  },

  listOpsAutomationTriggers(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationTriggerListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationTriggerListResponse>(`/ops/automation/triggers${q}`);
  },

  listOpsBlockedAutomationWorkflows(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkflowListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkflowListResponse>(`/ops/automation/workflows/blocked${q}`);
  },

  listOpsAutomationWorkflowIssues(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationWorkflowIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationWorkflowIssueListResponse>(`/ops/automation/workflows/issues${q}`);
  },

  listAutomationRecoveryRuns(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationRecoveryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRecoveryListResponse>(`/automation/recovery/runs${q}`);
  },

  getAutomationRecoveryRun(runId: number): Promise<AutomationRecoveryRunRead> {
    return requestScanV1<AutomationRecoveryRunRead>(`/automation/recovery/runs/${runId}`);
  },

  listAutomationDeadLetterJobs(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationDeadLetterListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationDeadLetterListResponse>(`/automation/dead-letter${q}`);
  },

  listAutomationFailureEvents(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationFailureEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationFailureEventListResponse>(`/automation/failures${q}`);
  },

  listAutomationRecoveryIssues(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationRecoveryIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRecoveryIssueListResponse>(`/automation/recovery/issues${q}`);
  },

  listOpsAutomationRecoveryRuns(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationRecoveryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRecoveryListResponse>(`/ops/automation/recovery/runs${q}`);
  },

  listOpsAutomationFailureEvents(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationFailureEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationFailureEventListResponse>(`/ops/automation/failures${q}`);
  },

  listOpsAutomationRecoveryCritical(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationRecoveryIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRecoveryIssueListResponse>(`/ops/automation/recovery/critical${q}`);
  },

  listAutomationBatchRuns(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationBatchListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationBatchListResponse>(`/automation/batch/runs${q}`);
  },

  getAutomationBatchRun(batchRunId: number): Promise<AutomationBatchRunRead> {
    return requestScanV1<AutomationBatchRunRead>(`/automation/batch/runs/${batchRunId}`);
  },

  listAutomationBatchChunks(
    batchRunId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<AutomationBatchChunkListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationBatchChunkListResponse>(`/automation/batch/runs/${batchRunId}/chunks${q}`);
  },

  listAutomationMaintenanceJobs(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationMaintenanceJobListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationMaintenanceJobListResponse>(`/automation/maintenance/jobs${q}`);
  },

  listAutomationMaintenanceResults(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationMaintenanceResultListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationMaintenanceResultListResponse>(`/automation/maintenance/results${q}`);
  },

  listAutomationBatchIssues(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationBatchIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationBatchIssueListResponse>(`/automation/batch/issues${q}`);
  },

  listOpsAutomationBatchRuns(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationBatchListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationBatchListResponse>(`/ops/automation/batch/runs${q}`);
  },

  listOpsAutomationIntegrityAudits(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationMaintenanceJobListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationMaintenanceJobListResponse>(`/ops/automation/integrity-audit${q}`);
  },

  listOpsAutomationStorageAudits(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationMaintenanceJobListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationMaintenanceJobListResponse>(`/ops/automation/storage-audit${q}`);
  },

  listAutomationNotifications(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationNotificationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationNotificationListResponse>(`/automation/notifications${q}`);
  },

  getAutomationNotification(notificationId: number): Promise<AutomationNotificationRead> {
    return requestScanV1<AutomationNotificationRead>(`/automation/notifications/${notificationId}`);
  },

  listAutomationAlerts(params?: { limit?: number; offset?: number }): Promise<AutomationAlertListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAlertListResponse>(`/automation/alerts${q}`);
  },

  listAutomationNotificationPreferences(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationNotificationPreferenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationNotificationPreferenceListResponse>(`/automation/preferences${q}`);
  },

  listAutomationNotificationIssues(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationNotificationIssueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationNotificationIssueListResponse>(`/automation/notification/issues${q}`);
  },

  listOpsAutomationNotifications(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationNotificationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationNotificationListResponse>(`/ops/automation/notifications${q}`);
  },

  listOpsAutomationCriticalAlerts(params?: {
    limit?: number;
    offset?: number;
  }): Promise<AutomationAlertListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAlertListResponse>(`/ops/automation/alerts/critical${q}`);
  },

  listAutomationOpsSnapshots(params?: { limit?: number; offset?: number }): Promise<AutomationOpsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationOpsListResponse>(`/automation/ops/snapshots${q}`);
  },

  getAutomationOpsSnapshot(snapshotId: number): Promise<AutomationOpsSnapshotRead> {
    return requestScanV1<AutomationOpsSnapshotRead>(`/automation/ops/snapshots/${snapshotId}`);
  },

  listAutomationOpsMetrics(params?: {
    snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<AutomationOpsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationOpsListResponse>(`/automation/ops/metrics${q}`);
  },

  listAutomationOpsAudits(params?: { limit?: number; offset?: number }): Promise<AutomationOpsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationOpsListResponse>(`/automation/ops/audits${q}`);
  },

  listAutomationOpsIssues(params?: {
    snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<AutomationOpsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationOpsListResponse>(`/automation/ops/issues${q}`);
  },

  listOpsAutomationSystemHealth(params?: { owner_user_id?: number }): Promise<AutomationOpsSystemHealthRead> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationOpsSystemHealthRead>(`/ops/automation/system-health${q}`);
  },

  listAutomationAnalyticsSnapshots(params?: { limit?: number; offset?: number }): Promise<AutomationAnalyticsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAnalyticsListResponse>(`/automation/analytics/snapshots${q}`);
  },

  getAutomationAnalyticsSnapshot(snapshotId: number): Promise<AutomationAnalyticsSnapshotRead> {
    return requestScanV1<AutomationAnalyticsSnapshotRead>(`/automation/analytics/snapshots/${snapshotId}`);
  },

  listAutomationAnalyticsMetrics(params?: { snapshot_id?: number; limit?: number; offset?: number }): Promise<AutomationAnalyticsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAnalyticsListResponse>(`/automation/analytics/metrics${q}`);
  },

  listAutomationAnalyticsTrends(params?: { snapshot_id?: number; limit?: number; offset?: number }): Promise<AutomationAnalyticsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAnalyticsListResponse>(`/automation/analytics/trends${q}`);
  },

  listAutomationAnalyticsComparisons(params?: { snapshot_id?: number; limit?: number; offset?: number }): Promise<AutomationAnalyticsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAnalyticsListResponse>(`/automation/analytics/comparisons${q}`);
  },

  listAutomationAnalyticsIssues(params?: { snapshot_id?: number; limit?: number; offset?: number }): Promise<AutomationAnalyticsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAnalyticsListResponse>(`/automation/analytics/issues${q}`);
  },

  listOpsAutomationAnalytics(params?: { limit?: number; offset?: number }): Promise<AutomationAnalyticsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAnalyticsListResponse>(`/ops/automation/analytics/snapshots${q}`);
  },

  listOpsAutomationAnalyticsFailures(params?: { limit?: number; offset?: number }): Promise<AutomationAnalyticsListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationAnalyticsListResponse>(`/ops/automation/analytics/failures${q}`);
  },

  createOrganization(payload: OrganizationCreateRequest): Promise<OrganizationResponse> {
    return requestScanV1<OrganizationResponse>("/organizations", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listOrganizations(params?: { limit?: number; offset?: number }): Promise<OrganizationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationListResponse>(`/organizations${q}`);
  },

  getOrganization(organizationId: number): Promise<OrganizationResponse> {
    return requestScanV1<OrganizationResponse>(`/organizations/${organizationId}`);
  },

  listMarketplaceAccounts(organizationId: number, params?: { limit?: number; offset?: number }): Promise<MarketplaceAccountListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<MarketplaceAccountListResponse>(`/organizations/${organizationId}/marketplaces${q}`);
  },

  getMarketplaceAccount(organizationId: number, accountId: number): Promise<MarketplaceAccountDetailResponse> {
    return requestScanV1<MarketplaceAccountDetailResponse>(`/organizations/${organizationId}/marketplaces/${accountId}`);
  },

  connectMarketplaceAccount(
    organizationId: number,
    payload: MarketplaceAccountConnectRequest,
  ): Promise<MarketplaceAccountDetailResponse> {
    return requestScanV1<MarketplaceAccountDetailResponse>(`/organizations/${organizationId}/marketplaces/connect`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  disconnectMarketplaceAccount(
    organizationId: number,
    payload: MarketplaceAccountDisconnectRequest,
  ): Promise<MarketplaceAccountDetailResponse> {
    return requestScanV1<MarketplaceAccountDetailResponse>(`/organizations/${organizationId}/marketplaces/disconnect`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  verifyMarketplaceAccount(
    organizationId: number,
    payload: MarketplaceAccountVerifyRequest,
  ): Promise<MarketplaceAccountDetailResponse> {
    return requestScanV1<MarketplaceAccountDetailResponse>(`/organizations/${organizationId}/marketplaces/verify`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  inviteOrganizationMember(organizationId: number, payload: OrganizationInviteRequest): Promise<OrganizationInvitationResponse> {
    return requestScanV1<OrganizationInvitationResponse>(`/organizations/${organizationId}/invite`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  archiveOrganization(organizationId: number, payload: OrganizationArchiveRequest): Promise<OrganizationResponse> {
    return requestScanV1<OrganizationResponse>(`/organizations/${organizationId}/archive`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  acceptOrganizationInvitation(token: string): Promise<OrganizationMemberResponse> {
    return requestScanV1<OrganizationMemberResponse>(`/organizations/invitations/${encodeURIComponent(token)}/accept`, {
      method: "POST",
    });
  },

  listOrganizationMembers(organizationId: number, params?: { limit?: number; offset?: number }): Promise<OrganizationMemberListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationMemberListResponse>(`/organizations/${organizationId}/members${q}`);
  },

  listOrganizationEvents(organizationId: number, params?: { limit?: number; offset?: number }): Promise<OrganizationEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationEventListResponse>(`/organizations/${organizationId}/events${q}`);
  },

  listOrganizationRoles(organizationId: number, params?: { limit?: number; offset?: number }): Promise<OrganizationRoleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationRoleListResponse>(`/organizations/${organizationId}/roles${q}`);
  },

  listOrganizationMemberRoles(
    organizationId: number,
    memberId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<OrganizationMembershipRoleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationMembershipRoleListResponse>(`/organizations/${organizationId}/members/${memberId}/roles${q}`);
  },

  assignOrganizationMemberRole(
    organizationId: number,
    memberId: number,
    payload: OrganizationRoleAssignmentRequest,
  ): Promise<OrganizationMembershipRoleResponse> {
    return requestScanV1<OrganizationMembershipRoleResponse>(`/organizations/${organizationId}/members/${memberId}/roles`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  removeOrganizationMemberRole(
    organizationId: number,
    memberId: number,
    roleId: number,
  ): Promise<OrganizationMembershipRoleResponse> {
    return requestScanV1<OrganizationMembershipRoleResponse>(`/organizations/${organizationId}/members/${memberId}/roles/${roleId}`, {
      method: "DELETE",
    });
  },

  listOrganizationInventoryAssignments(
    organizationId: number,
    params?: { limit?: number; offset?: number; assignment_status?: string },
  ): Promise<OrganizationInventoryAssignmentListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationInventoryAssignmentListResponse>(`/organizations/${organizationId}/inventory/assignments${q}`);
  },

  listOrganizationInventoryQueues(
    organizationId: number,
    params?: { limit?: number; offset?: number; queue_name?: string },
  ): Promise<OrganizationInventoryQueueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationInventoryQueueListResponse>(`/organizations/${organizationId}/inventory/queues${q}`);
  },

  listOrganizationInventoryWorkflowEvents(
    organizationId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<OrganizationInventoryWorkflowEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationInventoryWorkflowEventListResponse>(`/organizations/${organizationId}/inventory/workflow-events${q}`);
  },

  assignOrganizationInventoryItem(
    organizationId: number,
    payload: { inventory_item_id: number; assigned_user_id: number; assignment_notes?: string | null },
  ): Promise<OrganizationInventoryAssignmentResponse> {
    return requestScanV1<OrganizationInventoryAssignmentResponse>(`/organizations/${organizationId}/inventory/assign`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  unassignOrganizationInventoryItem(
    organizationId: number,
    payload: { inventory_item_id: number; assignment_notes?: string | null },
  ): Promise<OrganizationInventoryAssignmentResponse> {
    return requestScanV1<OrganizationInventoryAssignmentResponse>(`/organizations/${organizationId}/inventory/unassign`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  completeOrganizationInventoryAssignment(
    organizationId: number,
    payload: { inventory_item_id: number; assignment_notes?: string | null },
  ): Promise<OrganizationInventoryAssignmentResponse> {
    return requestScanV1<OrganizationInventoryAssignmentResponse>(`/organizations/${organizationId}/inventory/complete`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  moveOrganizationInventoryQueue(
    organizationId: number,
    payload: { inventory_item_id: number; queue_name: OrganizationInventoryQueueName; queue_position?: number },
  ): Promise<OrganizationInventoryQueueResponse> {
    return requestScanV1<OrganizationInventoryQueueResponse>(`/organizations/${organizationId}/inventory/queues/move`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listOrganizationReviews(
    organizationId: number,
    params?: { limit?: number; offset?: number; review_status?: string },
  ): Promise<OrganizationReviewListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationReviewListResponse>(`/organizations/${organizationId}/reviews${q}`);
  },

  listOrganizationReviewQueues(
    organizationId: number,
    params?: { limit?: number; offset?: number; queue_name?: string },
  ): Promise<OrganizationApprovalQueueListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationApprovalQueueListResponse>(`/organizations/${organizationId}/reviews/queues${q}`);
  },

  listOrganizationReviewDecisions(
    organizationId: number,
    reviewId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<OrganizationReviewDecisionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationReviewDecisionListResponse>(
      `/organizations/${organizationId}/reviews/${reviewId}/decisions${q}`,
    );
  },

  createOrganizationReview(
    organizationId: number,
    payload: {
      inventory_item_id: number;
      review_type: string;
      assigned_user_id?: number | null;
      queue_name?: OrganizationReviewQueueName | null;
    },
  ): Promise<OrganizationReviewResponse> {
    return requestScanV1<OrganizationReviewResponse>(`/organizations/${organizationId}/reviews`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  assignOrganizationReview(
    organizationId: number,
    reviewId: number,
    payload: { assigned_user_id: number },
  ): Promise<OrganizationReviewResponse> {
    return requestScanV1<OrganizationReviewResponse>(`/organizations/${organizationId}/reviews/${reviewId}/assign`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  approveOrganizationReview(
    organizationId: number,
    reviewId: number,
    payload: { decision_notes?: string | null },
  ): Promise<OrganizationReviewResponse> {
    return requestScanV1<OrganizationReviewResponse>(`/organizations/${organizationId}/reviews/${reviewId}/approve`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  rejectOrganizationReview(
    organizationId: number,
    reviewId: number,
    payload: { decision_notes?: string | null },
  ): Promise<OrganizationReviewResponse> {
    return requestScanV1<OrganizationReviewResponse>(`/organizations/${organizationId}/reviews/${reviewId}/reject`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  moveOrganizationReviewQueue(
    organizationId: number,
    payload: { review_id: number; queue_name: OrganizationReviewQueueName; queue_position?: number },
  ): Promise<OrganizationApprovalQueueResponse> {
    return requestScanV1<OrganizationApprovalQueueResponse>(`/organizations/${organizationId}/reviews/queues/move`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listOrganizationActivity(
    organizationId: number,
    params?: { limit?: number; offset?: number; category?: OrganizationActivityCategory },
  ): Promise<OrganizationActivityListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationActivityListResponse>(`/organizations/${organizationId}/activity${q}`);
  },

  listOrganizationNotifications(
    organizationId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<OrganizationNotificationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationNotificationListResponse>(`/organizations/${organizationId}/notifications${q}`);
  },

  getOrganizationNotificationUnreadCount(
    organizationId: number,
  ): Promise<OrganizationNotificationUnreadCountResponse> {
    return requestScanV1<OrganizationNotificationUnreadCountResponse>(
      `/organizations/${organizationId}/notifications/unread-count`,
    );
  },

  markOrganizationNotificationRead(
    organizationId: number,
    notificationId: number,
  ): Promise<{ notification_id: number; notification_status: string; read_at?: string | null; acknowledged_at?: string | null }> {
    return requestScanV1(`/organizations/${organizationId}/notifications/${notificationId}/read`, { method: "POST" });
  },

  acknowledgeOrganizationNotification(
    organizationId: number,
    notificationId: number,
  ): Promise<{ notification_id: number; notification_status: string; read_at?: string | null; acknowledged_at?: string | null }> {
    return requestScanV1(`/organizations/${organizationId}/notifications/${notificationId}/acknowledge`, {
      method: "POST",
    });
  },

  listOrganizationAudit(
    organizationId: number,
    params?: {
      limit?: number;
      offset?: number;
      category?: OrganizationAuditCategory;
      actor?: number;
      resource_type?: string;
    },
  ): Promise<OrganizationAuditLedgerListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationAuditLedgerListResponse>(`/organizations/${organizationId}/audit${q}`);
  },

  listOrganizationComplianceEvents(
    organizationId: number,
    params?: { limit?: number; offset?: number; severity?: OrganizationComplianceSeverity },
  ): Promise<OrganizationComplianceEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationComplianceEventListResponse>(`/organizations/${organizationId}/compliance-events${q}`);
  },

  listOrganizationAuditAccessLogs(
    organizationId: number,
    params?: { limit?: number; offset?: number; actor?: number; resource_type?: string },
  ): Promise<OrganizationAuditAccessLogListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationAuditAccessLogListResponse>(`/organizations/${organizationId}/audit/access-log${q}`);
  },

  getOrganizationDealerDashboard(
    organizationId: number,
    params?: { refresh?: boolean },
  ): Promise<OrganizationDealerDashboardSummaryResponse> {
    const q =
      params && params.refresh !== undefined
        ? buildQueryString({ refresh: params.refresh ? "true" : "false" })
        : "";
    return requestScanV1<OrganizationDealerDashboardSummaryResponse>(`/organizations/${organizationId}/dashboard${q}`);
  },

  listOrganizationDealerDashboardMetrics(
    organizationId: number,
    params?: { limit?: number; offset?: number; metric_period?: string },
  ): Promise<OrganizationDealerOperationalMetricListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestScanV1<OrganizationDealerOperationalMetricListResponse>(
      `/organizations/${organizationId}/dashboard/metrics${q}`,
    );
  },

  listOrganizationDealerDashboardSnapshots(
    organizationId: number,
    params?: { limit?: number; offset?: number },
  ): Promise<OrganizationDealerDashboardSnapshotListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<OrganizationDealerDashboardSnapshotListResponse>(
      `/organizations/${organizationId}/dashboard/snapshots${q}`,
    );
  },

  getPublicStorefront(publicSlug: string): Promise<PublicStorefrontResponse> {
    return requestScanV1<PublicStorefrontResponse>(`/storefronts/${encodeURIComponent(publicSlug)}`);
  },

  getPublicStorefrontInventory(
    publicSlug: string,
    params?: { limit?: number; offset?: number },
  ): Promise<PublicStorefrontInventoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<PublicStorefrontInventoryListResponse>(`/storefronts/${encodeURIComponent(publicSlug)}/inventory${q}`);
  },

  getPublicStorefrontFeatured(publicSlug: string): Promise<PublicStorefrontInventoryListResponse> {
    return requestScanV1<PublicStorefrontInventoryListResponse>(`/storefronts/${encodeURIComponent(publicSlug)}/featured`);
  },

  upsertDealerStorefrontProfile(
    organizationId: number,
    payload: {
      public_slug: string;
      display_name: string;
      tagline?: string | null;
      description?: string | null;
      logo_asset_id?: number | null;
      banner_asset_id?: number | null;
      website_url?: string | null;
      instagram_url?: string | null;
      whatnot_url?: string | null;
      location_label?: string | null;
      profile_status?: "ACTIVE" | "DRAFT" | "DISABLED";
    },
  ): Promise<DealerProfileResponse> {
    return requestScanV1<DealerProfileResponse>(`/organizations/${organizationId}/storefront/profile`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updateDealerStorefrontSettings(
    organizationId: number,
    payload: {
      storefront_visibility?: "PUBLIC" | "UNLISTED" | "PRIVATE";
      public_inventory_enabled?: boolean;
      featured_inventory_limit?: number;
      featured_inventory_sort?: "newest" | "recently_updated" | "highest_value" | "manually_selected";
      featured_manual_inventory_ids?: number[];
    },
  ): Promise<DealerStorefrontSettingsResponse> {
    return requestScanV1<DealerStorefrontSettingsResponse>(`/organizations/${organizationId}/storefront/settings`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listAutomationRules(params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/automation/rules${q}`);
  },

  getAutomationRule(ruleId: number): Promise<AutomationRuleRead> {
    return requestScanV1<AutomationRuleRead>(`/automation/rules/${ruleId}`);
  },

  listAutomationRuleVersions(ruleId: number, params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/automation/rules/${ruleId}/versions${q}`);
  },

  listAutomationRuleEvaluations(ruleId: number, params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/automation/rules/${ruleId}/evaluations${q}`);
  },

  listAutomationRuleActions(ruleId: number, params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/automation/rules/${ruleId}/actions${q}`);
  },

  listAutomationRuleIssues(params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/automation/rules/issues${q}`);
  },

  listOpsAutomationRules(params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/ops/automation/rules${q}`);
  },

  listOpsAutomationRuleFailures(params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/ops/automation/rules/failures${q}`);
  },

  listOpsAutomationRuleDrift(params?: { limit?: number; offset?: number }): Promise<AutomationRuleListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestScanV1<AutomationRuleListResponse>(`/ops/automation/rules/drift${q}`);
  },

  createMarketNormalizationRun(payload: MarketNormalizationRunCreatePayload): Promise<MarketNormalizationRunDetailRead> {
    return requestMarketV1<MarketNormalizationRunDetailRead>("/market-normalization/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMarketNormalizationRuns(params?: {
    ingestion_batch_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<MarketNormalizationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestMarketV1<MarketNormalizationRunListResponse>(`/market-normalization/runs${q}`);
  },

  listMarketNormalizationCandidates(params?: {
    ingestion_batch_id?: number;
    normalization_status?: string;
    publisher?: string;
    condition_band?: string;
    created_since?: string;
    created_until?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionNormalizedCandidateListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionNormalizedCandidateListResponse>(`/market-normalization/candidates${q}`);
  },

  listMarketNormalizationIssues(params?: {
    ingestion_batch_id?: number;
    issue_type?: string;
    severity?: string;
    created_since?: string;
    created_until?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketNormalizationIssueListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketNormalizationIssueListResponse>(`/market-normalization/issues${q}`);
  },

  listOpsMarketNormalizationRuns(params?: {
    owner_user_id?: number;
    ingestion_batch_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<MarketNormalizationRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return requestMarketV1<MarketNormalizationRunListResponse>(`/ops/market-normalization/runs${q}`);
  },

  getOpsMarketNormalizationRun(runId: number): Promise<MarketNormalizationRunDetailRead> {
    return requestMarketV1<MarketNormalizationRunDetailRead>(`/ops/market-normalization/runs/${runId}`);
  },

  listOpsMarketNormalizationCandidates(params?: {
    owner_user_id?: number;
    ingestion_batch_id?: number;
    normalization_status?: string;
    publisher?: string;
    condition_band?: string;
    created_since?: string;
    created_until?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionNormalizedCandidateListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionNormalizedCandidateListResponse>(`/ops/market-normalization/candidates${q}`);
  },

  listOpsMarketNormalizationIssues(params?: {
    owner_user_id?: number;
    ingestion_batch_id?: number;
    issue_type?: string;
    severity?: string;
    created_since?: string;
    created_until?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketNormalizationIssueListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketNormalizationIssueListResponse>(`/ops/market-normalization/issues${q}`);
  },

  runMarketScoring(payload: MarketAcquisitionScoreRunPayload): Promise<MarketAcquisitionScoreRunResponse> {
    return requestMarketV1<MarketAcquisitionScoreRunResponse>("/market-scoring/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMarketScoringScores(params?: {
    recommendation_label?: string;
    confidence_level?: string;
    risk_level?: string;
    score_min?: number;
    score_max?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionScoreListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionScoreListResponse>(`/market-scoring/scores${q}`);
  },

  getMarketScoringScore(scoreId: number): Promise<MarketAcquisitionScoreDetailRead> {
    return requestMarketV1<MarketAcquisitionScoreDetailRead>(`/market-scoring/scores/${scoreId}`);
  },

  listMarketScoringSnapshots(params?: {
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionScoreSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionScoreSnapshotListResponse>(`/market-scoring/snapshots${q}`);
  },

  listMarketScoringHistory(params?: {
    recommendation_label?: string;
    confidence_level?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionScoreHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionScoreHistoryListResponse>(`/market-scoring/history${q}`);
  },

  listOpsMarketScoringScores(params?: {
    owner_user_id?: number;
    recommendation_label?: string;
    confidence_level?: string;
    risk_level?: string;
    score_min?: number;
    score_max?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionScoreListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionScoreListResponse>(`/ops/market-scoring/scores${q}`);
  },

  getOpsMarketScoringScore(scoreId: number): Promise<MarketAcquisitionScoreDetailRead> {
    return requestMarketV1<MarketAcquisitionScoreDetailRead>(`/ops/market-scoring/scores/${scoreId}`);
  },

  listOpsMarketScoringSnapshots(params?: {
    owner_user_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionScoreSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionScoreSnapshotListResponse>(`/ops/market-scoring/snapshots${q}`);
  },

  listOpsMarketScoringHistory(params?: {
    owner_user_id?: number;
    recommendation_label?: string;
    confidence_level?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionScoreHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionScoreHistoryListResponse>(`/ops/market-scoring/history${q}`);
  },

  generateMarketSignals(payload: MarketAcquisitionSignalGeneratePayload): Promise<MarketAcquisitionSignalGenerateResponse> {
    return requestMarketV1<MarketAcquisitionSignalGenerateResponse>("/market-signals/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMarketSignals(params?: {
    signal_type?: string;
    signal_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalListResponse>(`/market-signals${q}`);
  },

  getMarketSignal(signalId: number): Promise<MarketAcquisitionSignalDetailRead> {
    return requestMarketV1<MarketAcquisitionSignalDetailRead>(`/market-signals/${signalId}`);
  },

  listMarketSignalSnapshots(params?: {
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalSnapshotListResponse>(`/market-signal-snapshots${q}`);
  },

  listMarketSignalEvidence(params?: {
    signal_type?: string;
    signal_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    signal_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalEvidenceListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalEvidenceListResponse>(`/market-signal-evidence${q}`);
  },

  listMarketSignalHistory(params?: {
    signal_type?: string;
    signal_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalHistoryListResponse>(`/market-signal-history${q}`);
  },

  listOpsMarketSignals(params?: {
    owner_user_id?: number;
    signal_type?: string;
    signal_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalListResponse>(`/ops/market-signals${q}`);
  },

  getOpsMarketSignal(signalId: number): Promise<MarketAcquisitionSignalDetailRead> {
    return requestMarketV1<MarketAcquisitionSignalDetailRead>(`/ops/market-signals/${signalId}`);
  },

  listOpsMarketSignalSnapshots(params?: {
    owner_user_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalSnapshotListResponse>(`/ops/market-signal-snapshots${q}`);
  },

  listOpsMarketSignalEvidence(params?: {
    owner_user_id?: number;
    signal_type?: string;
    signal_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    signal_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalEvidenceListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalEvidenceListResponse>(`/ops/market-signal-evidence${q}`);
  },

  listOpsMarketSignalHistory(params?: {
    owner_user_id?: number;
    signal_type?: string;
    signal_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionSignalHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionSignalHistoryListResponse>(`/ops/market-signal-history${q}`);
  },

  generateMarketOpportunities(payload: MarketAcquisitionOpportunityGeneratePayload): Promise<MarketAcquisitionOpportunityGenerateResponse> {
    return requestMarketV1<MarketAcquisitionOpportunityGenerateResponse>("/market-opportunities/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listMarketOpportunityItems(params?: {
    opportunity_snapshot_id?: number;
    signal_type?: string;
    signal_strength?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunityItemListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunityItemListResponse>(`/market-opportunities${q}`);
  },

  getMarketOpportunitySnapshot(snapshotId: number): Promise<MarketAcquisitionOpportunityDetailRead> {
    return requestMarketV1<MarketAcquisitionOpportunityDetailRead>(`/market-opportunities/${snapshotId}`);
  },

  listMarketOpportunitySnapshots(params?: {
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunitySnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunitySnapshotListResponse>(`/market-opportunities/snapshots${q}`);
  },

  listMarketOpportunityEvidence(params?: {
    opportunity_snapshot_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunityEvidenceListResponse>(`/market-opportunities/evidence${q}`);
  },

  listMarketOpportunityHistory(params?: {
    opportunity_snapshot_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunityHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunityHistoryListResponse>(`/market-opportunities/history${q}`);
  },

  generatePortfolioMarketCoupling(
    payload?: PortfolioMarketCouplingGeneratePayload,
  ): Promise<PortfolioMarketCouplingGenerateResponse> {
    return requestMarketV1<PortfolioMarketCouplingGenerateResponse>("/market-portfolio-coupling/generate", {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  listPortfolioMarketCouplingSnapshots(params?: {
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    min_alignment_score?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioMarketCouplingSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<PortfolioMarketCouplingSnapshotListResponse>(`/market-portfolio-coupling/snapshots${q}`);
  },

  getPortfolioMarketCouplingSnapshot(snapshotId: number): Promise<PortfolioMarketCouplingDetailRead> {
    return requestMarketV1<PortfolioMarketCouplingDetailRead>(`/market-portfolio-coupling/${snapshotId}`);
  },

  listPortfolioMarketCouplingEdges(params?: {
    coupling_snapshot_id?: number;
    coupling_type?: string;
    coupling_strength?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    min_coupling_score?: number;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioMarketCouplingEdgeListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<PortfolioMarketCouplingEdgeListResponse>(`/market-portfolio-coupling/edges${q}`);
  },

  listPortfolioMarketCouplingHistory(params?: {
    coupling_snapshot_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    min_alignment_score?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioMarketCouplingHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<PortfolioMarketCouplingHistoryListResponse>(`/market-portfolio-coupling/history${q}`);
  },

  listOpsPortfolioMarketCouplingSnapshots(params?: {
    owner_user_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    min_alignment_score?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioMarketCouplingSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<PortfolioMarketCouplingSnapshotListResponse>(`/ops/market-portfolio-coupling/snapshots${q}`);
  },

  getOpsPortfolioMarketCouplingSnapshot(
    snapshotId: number,
    params?: { owner_user_id?: number },
  ): Promise<PortfolioMarketCouplingDetailRead> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<PortfolioMarketCouplingDetailRead>(`/ops/market-portfolio-coupling/${snapshotId}${q}`);
  },

  listOpsPortfolioMarketCouplingEdges(params?: {
    owner_user_id?: number;
    coupling_snapshot_id?: number;
    coupling_type?: string;
    coupling_strength?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    min_coupling_score?: number;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioMarketCouplingEdgeListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<PortfolioMarketCouplingEdgeListResponse>(`/ops/market-portfolio-coupling/edges${q}`);
  },

  listOpsPortfolioMarketCouplingHistory(params?: {
    owner_user_id?: number;
    coupling_snapshot_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    min_alignment_score?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioMarketCouplingHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<PortfolioMarketCouplingHistoryListResponse>(`/ops/market-portfolio-coupling/history${q}`);
  },

  listOpsMarketOpportunityItems(params?: {
    owner_user_id?: number;
    opportunity_snapshot_id?: number;
    signal_type?: string;
    signal_strength?: string;
    risk_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunityItemListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunityItemListResponse>(`/ops/market-opportunities${q}`);
  },

  getOpsMarketOpportunitySnapshot(snapshotId: number): Promise<MarketAcquisitionOpportunityDetailRead> {
    return requestMarketV1<MarketAcquisitionOpportunityDetailRead>(`/ops/market-opportunities/${snapshotId}`);
  },

  listOpsMarketOpportunitySnapshots(params?: {
    owner_user_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunitySnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunitySnapshotListResponse>(`/ops/market-opportunities/snapshots${q}`);
  },

  listOpsMarketOpportunityEvidence(params?: {
    owner_user_id?: number;
    opportunity_snapshot_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunityEvidenceListResponse>(`/ops/market-opportunities/evidence${q}`);
  },

  listOpsMarketOpportunityHistory(params?: {
    owner_user_id?: number;
    opportunity_snapshot_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<MarketAcquisitionOpportunityHistoryListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return requestMarketV1<MarketAcquisitionOpportunityHistoryListResponse>(`/ops/market-opportunities/history${q}`);
  },

  getListingIntelligence(params?: {
    listing_id?: number;
    inventory_item_id?: number;
    canonical_comic_issue_id?: number;
    channel?: string;
    intelligence_status?: ListingIntelligenceStatus | string;
    stale_risk_flag?: boolean;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListingIntelligenceSnapshotListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingIntelligenceSnapshotListResponse>(`/listing-intelligence${q}`);
  },

  getListingIntelligenceSnapshot(snapshotId: number): Promise<ListingIntelligenceSnapshotRead> {
    return request<ListingIntelligenceSnapshotRead>(`/listing-intelligence/${snapshotId}`);
  },

  getListingIntelligenceEvidence(params?: {
    listing_id?: number;
    inventory_item_id?: number;
    canonical_comic_issue_id?: number;
    channel?: string;
    intelligence_status?: ListingIntelligenceStatus | string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListingIntelligenceEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingIntelligenceEvidenceListResponse>(`/listing-intelligence/evidence${q}`);
  },

  getListingCompletenessChecks(params?: {
    listing_id?: number;
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    status?: ListingCompletenessStatus | string;
    severity?: ListingCompletenessSeverity | string;
    limit?: number;
    offset?: number;
  }): Promise<ListingCompletenessCheckListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingCompletenessCheckListResponse>(`/listing-completeness-checks${q}`);
  },

  getListingChannelPerformance(params?: {
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListingChannelPerformanceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingChannelPerformanceListResponse>(`/listing-channel-performance${q}`);
  },

  getOpsListingIntelligence(params?: {
    owner_user_id?: number;
    listing_id?: number;
    inventory_item_id?: number;
    canonical_comic_issue_id?: number;
    channel?: string;
    intelligence_status?: ListingIntelligenceStatus | string;
    stale_risk_flag?: boolean;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListingIntelligenceSnapshotListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingIntelligenceSnapshotListResponse>(`/ops/listing-intelligence${q}`);
  },

  getOpsListingIntelligenceSnapshot(snapshotId: number): Promise<ListingIntelligenceSnapshotRead> {
    return request<ListingIntelligenceSnapshotRead>(`/ops/listing-intelligence/${snapshotId}`);
  },

  getOpsListingIntelligenceEvidence(params?: {
    owner_user_id?: number;
    listing_id?: number;
    inventory_item_id?: number;
    canonical_comic_issue_id?: number;
    channel?: string;
    intelligence_status?: ListingIntelligenceStatus | string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListingIntelligenceEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingIntelligenceEvidenceListResponse>(`/ops/listing-intelligence-evidence${q}`);
  },

  getOpsListingCompletenessChecks(params?: {
    owner_user_id?: number;
    listing_id?: number;
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    status?: ListingCompletenessStatus | string;
    severity?: ListingCompletenessSeverity | string;
    limit?: number;
    offset?: number;
  }): Promise<ListingCompletenessCheckListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingCompletenessCheckListResponse>(`/ops/listing-completeness-checks${q}`);
  },

  getOpsListingChannelPerformance(params?: {
    owner_user_id?: number;
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ListingChannelPerformanceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<ListingChannelPerformanceListResponse>(`/ops/listing-channel-performance${q}`);
  },

  downloadOpsOperationalReportCsv(reportId: number): Promise<void> {
    return downloadAuthenticatedReport(`/ops/reports/${reportId}/download`, `ops-operational-report-${reportId}.csv`);
  },

  generateOperationalReport(payload: OperationalReportGeneratePayloadInput): Promise<OperationalReportRunDetailRead> {
    return request<OperationalReportRunDetailRead>("/reports/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getOperationalReport(reportId: number): Promise<OperationalReportRunDetailRead> {
    return request<OperationalReportRunDetailRead>(`/reports/${reportId}`);
  },

  getOperationalReportRollups(): Promise<OperationalReportingDashboardRollup> {
    return request<OperationalReportingDashboardRollup>("/reports/dashboard-rollups");
  },

  listOperationalReports(params?: {
    report_type?: OperationalReportType | string;
    status?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<OperationalReportRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<OperationalReportRunListResponse>(`/reports${q}`);
  },

  downloadOperationalReportCsv(reportId: number): Promise<void> {
    return downloadAuthenticatedReport(`/reports/${reportId}/download`, `operational-report-${reportId}.csv`);
  },

  getOpsOperationalReports(params?: {
    owner_user_id?: number;
    report_type?: OperationalReportType | string;
    status?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<OperationalReportRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<OperationalReportRunListResponse>(`/ops/reports${q}`);
  },

  getOpsOperationalReportRollups(ownerUserId?: number): Promise<OperationalReportingDashboardRollup> {
    const q =
      typeof ownerUserId === "number" && Number.isFinite(ownerUserId)
        ? buildQueryString({ owner_user_id: ownerUserId })
        : "";
    return request<OperationalReportingDashboardRollup>(`/ops/reports/dashboard-rollups${q}`);
  },

  generateGradingReport(payload: GradingOperationalReportGeneratePayloadInput): Promise<GradingOperationalReportRunDetailRead> {
    return request<GradingOperationalReportRunDetailRead>("/grading-reports/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getGradingReport(reportId: number): Promise<GradingOperationalReportRunDetailRead> {
    return request<GradingOperationalReportRunDetailRead>(`/grading-reports/${reportId}`);
  },

  listGradingReports(params?: {
    report_type?: GradingOperationalReportType | string;
    status?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingOperationalReportRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingOperationalReportRunListResponse>(`/grading-reports${q}`);
  },

  downloadGradingReportCsv(reportId: number): Promise<void> {
    return downloadAuthenticatedReport(`/grading-reports/${reportId}/download`, `grading-report-${reportId}.csv`);
  },

  getOpsGradingReports(params?: {
    owner_user_id?: number;
    report_type?: GradingOperationalReportType | string;
    status?: string;
    created_from?: string;
    created_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingOperationalReportRunListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingOperationalReportRunListResponse>(`/ops/grading-reports${q}`);
  },

  getOpsGradingReport(reportId: number): Promise<GradingOperationalReportRunDetailRead> {
    return request<GradingOperationalReportRunDetailRead>(`/ops/grading-reports/${reportId}`);
  },

  downloadOpsGradingReportCsv(reportId: number): Promise<void> {
    return downloadAuthenticatedReport(`/ops/grading-reports/${reportId}/download`, `ops-grading-report-${reportId}.csv`);
  },

  getGradingCandidateDashboardSummary(): Promise<GradingCandidateDashboardSummary> {
    return request<GradingCandidateDashboardSummary>("/grading-candidates/dashboard-summary");
  },

  listGradingCandidates(params?: {
    status?: string;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingCandidateListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingCandidateListResponse>(`/grading-candidates${q}`);
  },

  getOpsGradingCandidates(params?: {
    owner_user_id?: number;
    status?: string;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingCandidateListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingCandidateListResponse>(`/ops/grading-candidates${q}`);
  },

  getGradingSubmissionDashboardSummary(): Promise<GradingSubmissionDashboardSummary> {
    return request<GradingSubmissionDashboardSummary>("/grading-submission-batches/dashboard-summary");
  },

  generateGradingSubmissionBatch(payload: GradingSubmissionCreatePayload): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>("/grading-submission-batches", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listGradingSubmissionBatches(params?: {
    target_grader?: string;
    status?: string;
    submission_date_from?: string;
    submission_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingSubmissionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSubmissionListResponse>(`/grading-submission-batches${q}`);
  },

  getGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}`);
  },

  patchGradingSubmissionBatch(batchId: number, payload: GradingSubmissionPatchPayload): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  readyGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/ready`, { method: "POST" });
  },

  shipGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/ship`, { method: "POST" });
  },

  receiveGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/receive`, { method: "POST" });
  },

  gradingGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/grading`, { method: "POST" });
  },

  returnShipGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/return-ship`, { method: "POST" });
  },

  completeGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/complete`, { method: "POST" });
  },

  cancelGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/cancel`, { method: "POST" });
  },

  addGradingSubmissionShipment(batchId: number, payload: GradingSubmissionShipmentCreatePayload): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/grading-submission-batches/${batchId}/shipments`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getOpsGradingSubmissionDashboardSummary(ownerUserId?: number): Promise<GradingSubmissionDashboardSummary> {
    const q = typeof ownerUserId === "number" && Number.isFinite(ownerUserId) ? buildQueryString({ owner_user_id: ownerUserId }) : "";
    return request<GradingSubmissionDashboardSummary>(`/ops/grading-submission-batches/dashboard-summary${q}`);
  },

  listOpsGradingSubmissionBatches(params?: {
    owner_user_id?: number;
    target_grader?: string;
    status?: string;
    submission_date_from?: string;
    submission_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingSubmissionListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSubmissionListResponse>(`/ops/grading-submission-batches${q}`);
  },

  getOpsGradingSubmissionBatch(batchId: number): Promise<GradingSubmissionDetailRead> {
    return request<GradingSubmissionDetailRead>(`/ops/grading-submission-batches/${batchId}`);
  },

  listOpsGradingSubmissionEvents(params?: {
    owner_user_id?: number;
    batch_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingSubmissionEventListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSubmissionEventListResponse>(`/ops/grading-submission-events${q}`);
  },

  listOpsGradingSubmissionShipments(params?: {
    owner_user_id?: number;
    batch_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingSubmissionShipmentListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSubmissionShipmentListResponse>(`/ops/grading-submission-shipments${q}`);
  },

  getGradingReconciliationDashboardSummary(): Promise<GradingReconciliationDashboardSummary> {
    return request<GradingReconciliationDashboardSummary>("/grading-reconciliation/dashboard-summary");
  },

  reconcileGradingResult(payload: GradingReconciliationReconcilePayload): Promise<GradingReconciliationDetailRead> {
    return request<GradingReconciliationDetailRead>("/grading-reconciliation/reconcile", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listGradingReconciliation(params?: {
    grading_candidate_id?: number;
    inventory_item_id?: number;
    target_grader?: string;
    reconciliation_status?: string;
    grading_accuracy_status?: string;
    confidence_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingReconciliationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingReconciliationListResponse>(`/grading-reconciliation${q}`);
  },

  getGradingReconciliation(recordId: number): Promise<GradingReconciliationDetailRead> {
    return request<GradingReconciliationDetailRead>(`/grading-reconciliation/${recordId}`);
  },

  getGradingReconciliationEvidence(params?: {
    record_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingReconciliationEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingReconciliationEvidenceListResponse>(`/grading-reconciliation/evidence${q}`);
  },

  getGradingReconciliationHistory(params?: {
    grading_candidate_id?: number;
    inventory_item_id?: number;
    target_grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingReconciliationHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingReconciliationHistoryListResponse>(`/grading-reconciliation/history${q}`);
  },

  getGraderPerformance(params?: {
    grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GraderPerformanceSnapshotListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GraderPerformanceSnapshotListResponse>(`/grader-performance${q}`);
  },

  getOpsGradingReconciliationDashboardSummary(ownerUserId?: number): Promise<GradingReconciliationDashboardSummary> {
    const q = typeof ownerUserId === "number" && Number.isFinite(ownerUserId) ? buildQueryString({ owner_user_id: ownerUserId }) : "";
    return request<GradingReconciliationDashboardSummary>(`/ops/grading-reconciliation/dashboard-summary${q}`);
  },

  listOpsGradingReconciliation(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    inventory_item_id?: number;
    target_grader?: string;
    reconciliation_status?: string;
    grading_accuracy_status?: string;
    confidence_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingReconciliationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingReconciliationListResponse>(`/ops/grading-reconciliation${q}`);
  },

  getOpsGradingReconciliation(recordId: number): Promise<GradingReconciliationDetailRead> {
    return request<GradingReconciliationDetailRead>(`/ops/grading-reconciliation/${recordId}`);
  },

  getOpsGradingReconciliationEvidence(params?: {
    owner_user_id?: number;
    record_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingReconciliationEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingReconciliationEvidenceListResponse>(`/ops/grading-reconciliation-evidence${q}`);
  },

  getOpsGradingReconciliationHistory(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    inventory_item_id?: number;
    target_grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingReconciliationHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingReconciliationHistoryListResponse>(`/ops/grading-reconciliation-history${q}`);
  },

  getOpsGraderPerformance(params?: {
    owner_user_id?: number;
    grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GraderPerformanceSnapshotListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GraderPerformanceSnapshotListResponse>(`/ops/grader-performance${q}`);
  },

  getGradingRecommendationDashboardSummary(): Promise<GradingRecommendationDashboardSummary> {
    return request<GradingRecommendationDashboardSummary>("/grading-recommendations/dashboard-summary");
  },

  generateGradingRecommendation(payload: GradingRecommendationGeneratePayload): Promise<GradingRecommendationDetailRead> {
    return request<GradingRecommendationDetailRead>("/grading-recommendations/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listGradingRecommendations(params?: {
    grading_candidate_id?: number;
    inventory_item_id?: number;
    recommended_action?: string;
    recommendation_strength?: string;
    confidence_score?: string | number;
    risk_level?: string;
    recommended_grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRecommendationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRecommendationListResponse>(`/grading-recommendations${q}`);
  },

  getGradingRecommendation(recommendationId: number): Promise<GradingRecommendationDetailRead> {
    return request<GradingRecommendationDetailRead>(`/grading-recommendations/${recommendationId}`);
  },

  getGradingRecommendationEvidence(params?: {
    recommendation_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingRecommendationEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRecommendationEvidenceListResponse>(`/grading-recommendations/evidence${q}`);
  },

  getGradingRecommendationHistory(params?: {
    grading_candidate_id?: number;
    inventory_item_id?: number;
    recommended_action?: string;
    recommended_grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRecommendationHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRecommendationHistoryListResponse>(`/grading-recommendations/history${q}`);
  },

  getOpsGradingRecommendationDashboardSummary(ownerUserId?: number): Promise<GradingRecommendationDashboardSummary> {
    const q = typeof ownerUserId === "number" && Number.isFinite(ownerUserId) ? buildQueryString({ owner_user_id: ownerUserId }) : "";
    return request<GradingRecommendationDashboardSummary>(`/ops/grading-recommendations/dashboard-summary${q}`);
  },

  listOpsGradingRecommendations(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    inventory_item_id?: number;
    recommended_action?: string;
    recommendation_strength?: string;
    confidence_score?: string | number;
    risk_level?: string;
    recommended_grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRecommendationListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRecommendationListResponse>(`/ops/grading-recommendations${q}`);
  },

  getOpsGradingRecommendation(recommendationId: number): Promise<GradingRecommendationDetailRead> {
    return request<GradingRecommendationDetailRead>(`/ops/grading-recommendations/${recommendationId}`);
  },

  getOpsGradingRecommendationEvidence(params?: {
    owner_user_id?: number;
    recommendation_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingRecommendationEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRecommendationEvidenceListResponse>(`/ops/grading-recommendation-evidence${q}`);
  },

  getOpsGradingRecommendationHistory(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    inventory_item_id?: number;
    recommended_action?: string;
    recommended_grader?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRecommendationHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRecommendationHistoryListResponse>(`/ops/grading-recommendation-history${q}`);
  },

  getGradingRiskDashboardSummary(): Promise<GradingRiskDashboardSummary> {
    return request<GradingRiskDashboardSummary>("/grading-risk/dashboard-summary");
  },

  generateGradingRisk(payload: GradingRiskGeneratePayload): Promise<GradingRiskDetailRead> {
    return request<GradingRiskDetailRead>("/grading-risk/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listGradingRisk(params?: {
    grading_candidate_id?: number;
    inventory_item_id?: number;
    overall_risk_level?: string;
    overall_confidence_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRiskListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRiskListResponse>(`/grading-risk${q}`);
  },

  getGradingRisk(snapshotId: number): Promise<GradingRiskDetailRead> {
    return request<GradingRiskDetailRead>(`/grading-risk/${snapshotId}`);
  },

  getGradingRiskEvidence(params?: {
    snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingRiskEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRiskEvidenceListResponse>(`/grading-risk/evidence${q}`);
  },

  getGradingConfidenceFactors(params?: {
    snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConfidenceFactorSnapshotListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<ConfidenceFactorSnapshotListResponse>(`/grading-confidence-factors${q}`);
  },

  getGradingRiskHistory(params?: {
    grading_candidate_id?: number;
    inventory_item_id?: number;
    overall_risk_level?: string;
    overall_confidence_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<RiskHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RiskHistoryListResponse>(`/grading-risk/history${q}`);
  },

  getOpsGradingRiskDashboardSummary(ownerUserId?: number): Promise<GradingRiskDashboardSummary> {
    const q = typeof ownerUserId === "number" && Number.isFinite(ownerUserId) ? buildQueryString({ owner_user_id: ownerUserId }) : "";
    return request<GradingRiskDashboardSummary>(`/ops/grading-risk/dashboard-summary${q}`);
  },

  listOpsGradingRisk(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    inventory_item_id?: number;
    overall_risk_level?: string;
    overall_confidence_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRiskListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRiskListResponse>(`/ops/grading-risk${q}`);
  },

  getOpsGradingRisk(snapshotId: number): Promise<GradingRiskDetailRead> {
    return request<GradingRiskDetailRead>(`/ops/grading-risk/${snapshotId}`);
  },

  getOpsGradingRiskEvidence(params?: {
    owner_user_id?: number;
    snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingRiskEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRiskEvidenceListResponse>(`/ops/grading-risk-evidence${q}`);
  },

  getOpsGradingConfidenceFactors(params?: {
    owner_user_id?: number;
    snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConfidenceFactorSnapshotListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<ConfidenceFactorSnapshotListResponse>(`/ops/grading-confidence-factors${q}`);
  },

  getOpsGradingRiskHistory(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    inventory_item_id?: number;
    overall_risk_level?: string;
    overall_confidence_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<RiskHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<RiskHistoryListResponse>(`/ops/grading-risk-history${q}`);
  },

  getGradingSpreadDashboardSummary(): Promise<GradingSpreadDashboardSummary> {
    return request<GradingSpreadDashboardSummary>("/grading-spreads/dashboard-summary");
  },

  getGradingRoiDashboardSummary(): Promise<GradingRoiDashboardSummary> {
    return request<GradingRoiDashboardSummary>("/grading-roi/dashboard-summary");
  },

  generateGradingSpread(payload: GradingSpreadGeneratePayload): Promise<GradingSpreadDetailRead> {
    return request<GradingSpreadDetailRead>("/grading-spreads/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listGradingSpreads(params?: {
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    target_grader?: string;
    target_grade?: string;
    spread_status?: string;
    confidence_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingSpreadListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSpreadListResponse>(`/grading-spreads${q}`);
  },

  generateGradingRoi(payload: GradingRoiGeneratePayload): Promise<GradingRoiDetailRead> {
    return request<GradingRoiDetailRead>("/grading-roi/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listGradingRoi(params?: {
    grading_candidate_id?: number;
    inventory_item_id?: number;
    canonical_comic_issue_id?: number;
    target_grader?: string;
    target_grade?: string;
    roi_status?: string;
    confidence_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRoiListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRoiListResponse>(`/grading-roi${q}`);
  },

  getGradingRoi(roiId: number): Promise<GradingRoiDetailRead> {
    return request<GradingRoiDetailRead>(`/grading-roi/${roiId}`);
  },

  getGradingRoiEvidence(params?: {
    roi_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingRoiEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRoiEvidenceListResponse>(`/grading-roi/evidence${q}`);
  },

  getGradingRoiHistory(params?: {
    grading_candidate_id?: number;
    canonical_comic_issue_id?: number;
    target_grader?: string;
    target_grade?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRoiHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRoiHistoryListResponse>(`/grading-roi/history${q}`);
  },

  getOpsGradingRoiDashboardSummary(ownerUserId?: number): Promise<GradingRoiDashboardSummary> {
    const q = typeof ownerUserId === "number" && Number.isFinite(ownerUserId) ? buildQueryString({ owner_user_id: ownerUserId }) : "";
    return request<GradingRoiDashboardSummary>(`/ops/grading-roi/dashboard-summary${q}`);
  },

  getOpsGradingRoi(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    inventory_item_id?: number;
    canonical_comic_issue_id?: number;
    target_grader?: string;
    target_grade?: string;
    roi_status?: string;
    confidence_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRoiListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRoiListResponse>(`/ops/grading-roi${q}`);
  },

  getOpsGradingRoiById(roiId: number): Promise<GradingRoiDetailRead> {
    return request<GradingRoiDetailRead>(`/ops/grading-roi/${roiId}`);
  },

  getOpsGradingRoiEvidence(params?: {
    owner_user_id?: number;
    roi_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingRoiEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRoiEvidenceListResponse>(`/ops/grading-roi/evidence${q}`);
  },

  getOpsGradingRoiHistory(params?: {
    owner_user_id?: number;
    grading_candidate_id?: number;
    canonical_comic_issue_id?: number;
    target_grader?: string;
    target_grade?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingRoiHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingRoiHistoryListResponse>(`/ops/grading-roi/history${q}`);
  },

  getGradingSpread(spreadId: number): Promise<GradingSpreadDetailRead> {
    return request<GradingSpreadDetailRead>(`/grading-spreads/${spreadId}`);
  },

  getGradingSpreadEvidence(params?: {
    spread_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingSpreadEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSpreadEvidenceListResponse>(`/grading-spreads/evidence${q}`);
  },

  getGradingSpreadHistory(params?: {
    canonical_comic_issue_id?: number;
    target_grader?: string;
    target_grade?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingSpreadHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSpreadHistoryListResponse>(`/grading-spread-history${q}`);
  },

  getOpsGradingSpreadDashboardSummary(ownerUserId?: number): Promise<GradingSpreadDashboardSummary> {
    const q = typeof ownerUserId === "number" && Number.isFinite(ownerUserId) ? buildQueryString({ owner_user_id: ownerUserId }) : "";
    return request<GradingSpreadDashboardSummary>(`/ops/grading-spreads/dashboard-summary${q}`);
  },

  getOpsGradingSpreads(params?: {
    owner_user_id?: number;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    target_grader?: string;
    target_grade?: string;
    spread_status?: string;
    confidence_level?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingSpreadListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSpreadListResponse>(`/ops/grading-spreads${q}`);
  },

  getOpsGradingSpread(spreadId: number): Promise<GradingSpreadDetailRead> {
    return request<GradingSpreadDetailRead>(`/ops/grading-spreads/${spreadId}`);
  },

  getOpsGradingSpreadEvidence(params?: {
    owner_user_id?: number;
    spread_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GradingSpreadEvidenceListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSpreadEvidenceListResponse>(`/ops/grading-spread-evidence${q}`);
  },

  getOpsGradingSpreadHistory(params?: {
    owner_user_id?: number;
    canonical_comic_issue_id?: number;
    target_grader?: string;
    target_grade?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<GradingSpreadHistoryListResponse> {
    const q = params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<GradingSpreadHistoryListResponse>(`/ops/grading-spread-history${q}`);
  },

  getListingExportDashboardSummary(): Promise<ListingExportDashboardSummary> {
    return request<ListingExportDashboardSummary>("/listing-export-runs/dashboard-summary");
  },

  getOpsListingExportRuns(params?: {
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ListingExportRunListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ListingExportRunListResponse>(`/ops/listing-export-runs${q}`);
  },

  downloadOpsListingExportCsv(exportRunId: number): Promise<void> {
    return downloadAuthenticatedReport(
      `/ops/listing-export-runs/${exportRunId}/download`,
      `ops-listing-export-run-${exportRunId}.csv`,
    );
  },

  createListingExportRun(payload: ListingExportRunCreatePayload): Promise<ListingExportRunDetailRead> {
    return request<ListingExportRunDetailRead>("/listing-export-runs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getListingRegistrySummary(): Promise<ListingDashboardSummary> {
    return request<ListingDashboardSummary>("/listings/summary");
  },

  getSalesDashboardSummary(): Promise<SalesDashboardSummary> {
    return request<SalesDashboardSummary>("/sales/dashboard-summary");
  },

  getSales(params?: {
    channel?: SaleChannel | string;
    status?: SaleStatus | string;
    sale_date_from?: string;
    sale_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<SaleRecordListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<SaleRecordListResponse>(`/sales${q}`);
  },

  getSale(saleId: number): Promise<SaleRecordDetailRead> {
    return request<SaleRecordDetailRead>(`/sales/${saleId}`);
  },

  createSale(payload: SaleRecordCreatePayload): Promise<SaleRecordDetailRead> {
    return request<SaleRecordDetailRead>("/sales", { method: "POST", body: JSON.stringify(payload) });
  },

  patchSale(saleId: number, payload: SaleRecordPatchPayload): Promise<SaleRecordDetailRead> {
    return request<SaleRecordDetailRead>(`/sales/${saleId}`, { method: "PATCH", body: JSON.stringify(payload) });
  },

  recordSale(saleId: number): Promise<SaleRecordDetailRead> {
    return request<SaleRecordDetailRead>(`/sales/${saleId}/record`, { method: "POST" });
  },

  voidSale(saleId: number): Promise<SaleRecordDetailRead> {
    return request<SaleRecordDetailRead>(`/sales/${saleId}/void`, { method: "POST" });
  },

  getSaleEvents(saleId: number): Promise<SaleLifecycleEventListResponse> {
    return request<SaleLifecycleEventListResponse>(`/sales/${saleId}/events`);
  },

  getOpsSales(params?: {
    owner_user_id?: number;
    channel?: SaleChannel | string;
    status?: SaleStatus | string;
    sale_date_from?: string;
    sale_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<SaleRecordListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<SaleRecordListResponse>(`/ops/sales${q}`);
  },

  getOpsSale(saleId: number): Promise<SaleRecordDetailRead> {
    return request<SaleRecordDetailRead>(`/ops/sales/${saleId}`);
  },

  getOpsSaleEvents(params?: {
    owner_user_id?: number;
    channel?: SaleChannel | string;
    status?: SaleStatus | string;
    sale_date_from?: string;
    sale_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<SaleLifecycleEventListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<SaleLifecycleEventListResponse>(`/ops/sale-events${q}`);
  },

  getOpsSaleFinancialAdjustments(params?: {
    owner_user_id?: number;
    channel?: SaleChannel | string;
    status?: SaleStatus | string;
    sale_date_from?: string;
    sale_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<SaleFinancialAdjustmentListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<SaleFinancialAdjustmentListResponse>(`/ops/sale-financial-adjustments${q}`);
  },

  getLiquidityDashboardSummary(params?: { snapshot_date?: string }): Promise<LiquidityDashboardSummary> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<LiquidityDashboardSummary>(`/liquidity/dashboard-summary${q}`);
  },

  getLiquidity(params?: {
    channel?: string;
    liquidity_status?: LiquidityStatus | string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    snapshot_date?: string;
    evaluation_window_days?: number;
    limit?: number;
    offset?: number;
  }): Promise<InventoryLiquidityListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<InventoryLiquidityListResponse>(`/liquidity${q}`);
  },

  getLiquiditySnapshot(snapshotId: number): Promise<InventoryLiquiditySnapshotRead> {
    return request<InventoryLiquiditySnapshotRead>(`/liquidity/${snapshotId}`);
  },

  getLiquidityEvidence(params?: {
    channel?: string;
    liquidity_status?: LiquidityStatus | string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    snapshot_date?: string;
    limit?: number;
    offset?: number;
  }): Promise<InventoryLiquidityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<InventoryLiquidityEvidenceListResponse>(`/liquidity/evidence${q}`);
  },

  getListingVelocity(params?: {
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ListingVelocityListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ListingVelocityListResponse>(`/listing-velocity${q}`);
  },

  getListingStalenessEvents(params?: {
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ListingStalenessEventListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ListingStalenessEventListResponse>(`/listing-staleness-events${q}`);
  },

  getOpsLiquidityDashboardSummary(params?: { owner_user_id?: number; snapshot_date?: string }): Promise<LiquidityDashboardSummary> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<LiquidityDashboardSummary>(`/ops/liquidity/dashboard-summary${q}`);
  },

  getOpsLiquidity(params?: {
    owner_user_id?: number;
    channel?: string;
    liquidity_status?: LiquidityStatus | string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<InventoryLiquidityListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<InventoryLiquidityListResponse>(`/ops/liquidity${q}`);
  },

  getOpsLiquiditySnapshot(snapshotId: number): Promise<InventoryLiquiditySnapshotRead> {
    return request<InventoryLiquiditySnapshotRead>(`/ops/liquidity/${snapshotId}`);
  },

  getOpsLiquidityEvidence(params?: {
    owner_user_id?: number;
    channel?: string;
    liquidity_status?: LiquidityStatus | string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<InventoryLiquidityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<InventoryLiquidityEvidenceListResponse>(`/ops/liquidity-evidence${q}`);
  },

  getOpsListingVelocity(params?: {
    owner_user_id?: number;
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ListingVelocityListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ListingVelocityListResponse>(`/ops/listing-velocity${q}`);
  },

  getOpsListingStalenessEvents(params?: {
    owner_user_id?: number;
    channel?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    canonical_comic_issue_id?: number;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ListingStalenessEventListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ListingStalenessEventListResponse>(`/ops/listing-staleness-events${q}`);
  },

  getConventionDashboardSummary(): Promise<ConventionDashboardSummary> {
    return request<ConventionDashboardSummary>("/convention/dashboard-summary");
  },

  getOpsConventionDashboardSummary(params?: { owner_user_id?: number }): Promise<ConventionDashboardSummary> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionDashboardSummary>(`/ops/convention/dashboard-summary${q}`);
  },

  getConventionEvents(params?: {
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionEventListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionEventListResponse>(`/convention-events${q}`);
  },

  createConventionEvent(payload: ConventionEventCreatePayload): Promise<ConventionEventRead> {
    return request<ConventionEventRead>("/convention-events", { method: "POST", body: JSON.stringify(payload) });
  },

  getConventionEvent(conventionEventId: number): Promise<ConventionEventRead> {
    return request<ConventionEventRead>(`/convention-events/${conventionEventId}`);
  },

  patchConventionEvent(conventionEventId: number, payload: ConventionEventPatchPayload): Promise<ConventionEventRead> {
    return request<ConventionEventRead>(`/convention-events/${conventionEventId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  activateConventionEvent(conventionEventId: number, payload?: ConventionReplayBody): Promise<ConventionEventRead> {
    return request<ConventionEventRead>(`/convention-events/${conventionEventId}/activate`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  completeConventionEvent(conventionEventId: number, payload?: ConventionReplayBody): Promise<ConventionEventRead> {
    return request<ConventionEventRead>(`/convention-events/${conventionEventId}/complete`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  getConventionAssignments(params?: {
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionAssignmentListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionAssignmentListResponse>(`/convention-assignments${q}`);
  },

  createConventionAssignment(payload: ConventionAssignmentCreatePayload): Promise<ConventionAssignmentRead> {
    return request<ConventionAssignmentRead>("/convention-assignments", { method: "POST", body: JSON.stringify(payload) });
  },

  getConventionMovements(params?: {
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionMovementListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionMovementListResponse>(`/convention-movements${q}`);
  },

  createConventionMovement(payload: ConventionMovementCreatePayload): Promise<ConventionMovementRead> {
    return request<ConventionMovementRead>("/convention-movements", { method: "POST", body: JSON.stringify(payload) });
  },

  getConventionPriceSnapshots(params?: {
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionPriceSnapshotListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionPriceSnapshotListResponse>(`/convention-price-snapshots${q}`);
  },

  createConventionPriceSnapshot(payload: ConventionPriceSnapshotCreatePayload): Promise<ConventionPriceSnapshotRead> {
    return request<ConventionPriceSnapshotRead>("/convention-price-snapshots", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  getConventionSaleSessions(params?: {
    event_type?: ConventionEventType | string;
    status?: ConventionSaleSessionStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionSaleSessionListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionSaleSessionListResponse>(`/convention-sale-sessions${q}`);
  },

  createConventionSaleSession(payload: ConventionSaleSessionCreatePayload): Promise<ConventionSaleSessionRead> {
    return request<ConventionSaleSessionRead>("/convention-sale-sessions", { method: "POST", body: JSON.stringify(payload) });
  },

  closeConventionSaleSession(conventionSaleSessionId: number, payload?: ConventionReplayBody): Promise<ConventionSaleSessionRead> {
    return request<ConventionSaleSessionRead>(`/convention-sale-sessions/${conventionSaleSessionId}/close`, {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
    });
  },

  getOpsConventionEvents(params?: {
    owner_user_id?: number;
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionEventListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionEventListResponse>(`/ops/convention-events${q}`);
  },

  getOpsConventionAssignments(params?: {
    owner_user_id?: number;
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionAssignmentListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionAssignmentListResponse>(`/ops/convention-assignments${q}`);
  },

  getOpsConventionMovements(params?: {
    owner_user_id?: number;
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionMovementListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionMovementListResponse>(`/ops/convention-movements${q}`);
  },

  getOpsConventionPriceSnapshots(params?: {
    owner_user_id?: number;
    event_type?: ConventionEventType | string;
    status?: ConventionEventStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionPriceSnapshotListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionPriceSnapshotListResponse>(`/ops/convention-price-snapshots${q}`);
  },

  getOpsConventionSaleSessions(params?: {
    owner_user_id?: number;
    event_type?: ConventionEventType | string;
    status?: ConventionSaleSessionStatus | string;
    date_from?: string;
    date_to?: string;
    inventory_item_id?: number;
    convention_event_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ConventionSaleSessionListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ConventionSaleSessionListResponse>(`/ops/convention-sale-sessions${q}`);
  },

  getListingRegistryList(params?: {
    status?: ListingStatus;
    inventory_copy_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<ListingListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ListingListResponse>(`/listings${q}`);
  },

  createListing(payload: {
    inventory_copy_id: number;
    canonical_comic_issue_id?: number | null;
    source_type: ListingSourceType;
    title: string;
    description?: string | null;
    asking_price_amount?: string | null;
    asking_price_currency?: string | null;
    replay_key?: string | null;
  }): Promise<ListingRead> {
    return request<ListingRead>("/listings", { method: "POST", body: JSON.stringify(payload) });
  },

  getOpsListingRegistryList(params?: {
    owner_user_id?: number;
    status?: ListingStatus;
    limit?: number;
    offset?: number;
  }): Promise<ListingListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<ListingListResponse>(`/ops/listings${q}`);
  },

  getOpsListingStatusDistribution(): Promise<ListingOpsStatusDistribution> {
    return request<ListingOpsStatusDistribution>("/ops/listings/status-distribution");
  },

  getOpsListingLifecycleEvents(params?: {
    listing_id?: number;
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<OpsListingLifecycleEventListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<OpsListingLifecycleEventListResponse>(`/ops/listing-events${q}`);
  },

  getOpsListingPriceHistory(params?: {
    listing_id?: number;
    owner_user_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<OpsListingPriceHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | undefined>)
        : "";
    return request<OpsListingPriceHistoryListResponse>(`/ops/listing-price-history${q}`);
  },

  fetchCoverImageBlob(path: string): Promise<Blob> {
    return fetchBinary(path);
  },

  /** P38-01 portfolio registry */
  getPortfolioIntelligenceSummary(): Promise<PortfolioIntelligenceSummary> {
    return request<PortfolioIntelligenceSummary>("/portfolio-intelligence/summary");
  },

  generatePortfolioExposures(payload: PortfolioGenerateScopePayload): Promise<PortfolioExposureGenerateResponse> {
    return request<PortfolioExposureGenerateResponse>("/portfolio-exposures/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  generatePortfolioAllocations(payload: PortfolioGenerateScopePayload): Promise<PortfolioAllocationGenerateResponse> {
    return request<PortfolioAllocationGenerateResponse>("/portfolio-allocations/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listOpsPortfolios(params?: {
    owner_user_id?: number;
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | undefined>) : "";
    return request<PortfolioListResponse>(`/ops/portfolios${q}`);
  },

  listOpsPortfolioItems(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    include_removed?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioItemListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, boolean | number | undefined>) : "";
    return request<PortfolioItemListResponse>(`/ops/portfolio-items${q}`);
  },

  listOpsPortfolioExposures(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    generation_batch_checksum?: string;
    latest_batch?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioExposureSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, string | number | boolean | undefined>) : "";
    return request<PortfolioExposureSnapshotListResponse>(`/ops/portfolio-exposures${q}`);
  },

  listOpsPortfolioExposureEvidence(params?: {
    owner_user_id?: number;
    portfolio_exposure_snapshot_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioExposureEvidenceListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<PortfolioExposureEvidenceListResponse>(`/ops/portfolio-exposure-evidence${q}`);
  },

  listOpsPortfolioAllocations(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioAllocationSnapshotListResponse> {
    const q =
      params && Object.keys(params).length ? buildQueryString(params as Record<string, number | undefined>) : "";
    return request<PortfolioAllocationSnapshotListResponse>(`/ops/portfolio-allocations${q}`);
  },

  /** P38-02 duplicate & consolidation intelligence */
  getDuplicateIntelligenceSummary(): Promise<DuplicateIntelligenceSummary> {
    return request<DuplicateIntelligenceSummary>("/duplicate-intelligence/summary");
  },

  generateDuplicateClusters(payload: DuplicateClusterGeneratePayload): Promise<DuplicateClusterGenerateResponse> {
    return request<DuplicateClusterGenerateResponse>("/duplicate-clusters/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listOpsDuplicateClusters(params?: {
    owner_user_id?: number;
    canonical_comic_issue_id?: number;
    cluster_type?: string;
    duplication_status?: string;
    liquidity_profile?: string;
    recommendation_action?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    latest_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<DuplicateClusterListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<DuplicateClusterListResponse>(`/ops/duplicate-clusters${q}`);
  },

  listOpsDuplicateClusterItems(params?: {
    owner_user_id?: number;
    duplicate_cluster_id?: number;
    inventory_item_id?: number;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    latest_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<DuplicateClusterItemListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<DuplicateClusterItemListResponse>(`/ops/duplicate-cluster-items${q}`);
  },

  listOpsDuplicateConsolidationRecommendations(params?: {
    owner_user_id?: number;
    recommendation_action?: string;
    status?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    latest_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<DuplicateConsolidationRecommendationListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<DuplicateConsolidationRecommendationListResponse>(`/ops/duplicate-consolidation-recommendations${q}`);
  },

  listOpsDuplicateHistory(params?: {
    owner_user_id?: number;
    cluster_key_prefix?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    latest_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<DuplicateHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<DuplicateHistoryListResponse>(`/ops/duplicate-history${q}`);
  },

  generatePortfolioLiquidity(payload: PortfolioLiquidityGeneratePayload): Promise<PortfolioLiquidityGenerateResponse> {
    return request<PortfolioLiquidityGenerateResponse>("/portfolio-liquidity/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listPortfolioLiquidity(params?: {
    portfolio_id?: number;
    liquidity_balance_status?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    latest_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioLiquiditySnapshotListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioLiquiditySnapshotListResponse>(`/portfolio-liquidity${q}`);
  },

  getPortfolioLiquiditySnapshot(snapshotId: number): Promise<PortfolioLiquiditySnapshotDetailResponse> {
    return request<PortfolioLiquiditySnapshotDetailResponse>(`/portfolio-liquidity/${snapshotId}`);
  },

  listPortfolioLiquidityEvidence(params?: {
    portfolio_liquidity_snapshot_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioLiquidityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioLiquidityEvidenceListResponse>(`/portfolio-liquidity-evidence${q}`);
  },

  listPortfolioLiquidityHistory(params?: {
    portfolio_id?: number;
    liquidity_balance_status?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioLiquidityHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioLiquidityHistoryListResponse>(`/portfolio-liquidity-history${q}`);
  },

  listOpsPortfolioLiquidity(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    liquidity_balance_status?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    latest_only?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioLiquiditySnapshotListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioLiquiditySnapshotListResponse>(`/ops/portfolio-liquidity${q}`);
  },

  getOpsPortfolioLiquiditySnapshot(snapshotId: number, params?: { owner_user_id?: number }): Promise<PortfolioLiquiditySnapshotDetailResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, number | undefined>)
        : "";
    return request<PortfolioLiquiditySnapshotDetailResponse>(`/ops/portfolio-liquidity/${snapshotId}${q}`);
  },

  listOpsPortfolioLiquidityEvidence(params?: {
    owner_user_id?: number;
    portfolio_liquidity_snapshot_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioLiquidityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioLiquidityEvidenceListResponse>(`/ops/portfolio-liquidity-evidence${q}`);
  },

  listOpsPortfolioLiquidityHistory(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    liquidity_balance_status?: string;
    snapshot_date_from?: string;
    snapshot_date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioLiquidityHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioLiquidityHistoryListResponse>(`/ops/portfolio-liquidity-history${q}`);
  },

  generatePortfolioRecommendations(payload: PortfolioRecommendationGeneratePayload): Promise<PortfolioRecommendationGenerateResponse> {
    return request<PortfolioRecommendationGenerateResponse>("/portfolio-recommendations/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listPortfolioRecommendations(params?: {
    portfolio_id?: number;
    inventory_item_id?: number;
    recommendation_action?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioRecommendationListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioRecommendationListResponse>(`/portfolio-recommendations${q}`);
  },

  getPortfolioRecommendation(recommendationId: number): Promise<PortfolioRecommendationDetailRead> {
    return request<PortfolioRecommendationDetailRead>(`/portfolio-recommendations/${recommendationId}`);
  },

  listPortfolioRecommendationEvidence(params?: {
    recommendation_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioRecommendationEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioRecommendationEvidenceListResponse>(`/portfolio-recommendation-evidence${q}`);
  },

  listPortfolioRecommendationHistory(params?: {
    portfolio_id?: number;
    inventory_item_id?: number;
    recommendation_action?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioRecommendationHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioRecommendationHistoryListResponse>(`/portfolio-recommendation-history${q}`);
  },

  listOpsPortfolioRecommendations(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    inventory_item_id?: number;
    recommendation_action?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioRecommendationListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioRecommendationListResponse>(`/ops/portfolio-recommendations${q}`);
  },

  getOpsPortfolioRecommendation(recommendationId: number, params?: { owner_user_id?: number }): Promise<PortfolioRecommendationDetailRead> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, number | undefined>)
        : "";
    return request<PortfolioRecommendationDetailRead>(`/ops/portfolio-recommendations/${recommendationId}${q}`);
  },

  listOpsPortfolioRecommendationEvidence(params?: {
    owner_user_id?: number;
    recommendation_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioRecommendationEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioRecommendationEvidenceListResponse>(`/ops/portfolio-recommendation-evidence${q}`);
  },

  listOpsPortfolioRecommendationHistory(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    inventory_item_id?: number;
    recommendation_action?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<PortfolioRecommendationHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<PortfolioRecommendationHistoryListResponse>(`/ops/portfolio-recommendation-history${q}`);
  },

  generateConcentrationRisk(payload: ConcentrationRiskGeneratePayload): Promise<ConcentrationRiskGenerateResponse> {
    return request<ConcentrationRiskGenerateResponse>("/concentration-risk/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listConcentrationRisk(params?: {
    portfolio_id?: number;
    concentration_type?: string;
    concentration_key?: string;
    exposure_status?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskListResponse>(`/concentration-risk${q}`);
  },

  getConcentrationRisk(snapshotId: number): Promise<ConcentrationRiskDetailRead> {
    return request<ConcentrationRiskDetailRead>(`/concentration-risk/${snapshotId}`);
  },

  listConcentrationRiskEvidence(params?: {
    concentration_risk_snapshot_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskEvidenceListResponse>(`/concentration-risk-evidence${q}`);
  },

  listConcentrationRiskFactors(params?: {
    concentration_risk_snapshot_id?: number;
    factor_key?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskFactorListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskFactorListResponse>(`/concentration-risk-factors${q}`);
  },

  listConcentrationRiskHistory(params?: {
    portfolio_id?: number;
    concentration_type?: string;
    concentration_key?: string;
    exposure_status?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskHistoryListResponse>(`/concentration-risk-history${q}`);
  },

  listOpsConcentrationRisk(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    concentration_type?: string;
    concentration_key?: string;
    exposure_status?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskListResponse>(`/ops/concentration-risk${q}`);
  },

  getOpsConcentrationRisk(snapshotId: number, params?: { owner_user_id?: number }): Promise<ConcentrationRiskDetailRead> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, number | undefined>)
        : "";
    return request<ConcentrationRiskDetailRead>(`/ops/concentration-risk/${snapshotId}${q}`);
  },

  listOpsConcentrationRiskEvidence(params?: {
    owner_user_id?: number;
    concentration_risk_snapshot_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskEvidenceListResponse>(`/ops/concentration-risk-evidence${q}`);
  },

  listOpsConcentrationRiskFactors(params?: {
    owner_user_id?: number;
    concentration_risk_snapshot_id?: number;
    factor_key?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskFactorListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskFactorListResponse>(`/ops/concentration-risk-factors${q}`);
  },

  listOpsConcentrationRiskHistory(params?: {
    owner_user_id?: number;
    portfolio_id?: number;
    concentration_type?: string;
    concentration_key?: string;
    exposure_status?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<ConcentrationRiskHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<ConcentrationRiskHistoryListResponse>(`/ops/concentration-risk-history${q}`);
  },

  generateAcquisitionPriorities(payload: AcquisitionPriorityGeneratePayload): Promise<AcquisitionPriorityGenerateResponse> {
    return request<AcquisitionPriorityGenerateResponse>("/acquisition-priorities/generate", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  listAcquisitionPriorities(params?: {
    acquisition_category?: string;
    acquisition_priority?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<AcquisitionPriorityListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<AcquisitionPriorityListResponse>(`/acquisition-priorities${q}`);
  },

  getAcquisitionPriority(snapshotId: number): Promise<AcquisitionPriorityDetailRead> {
    return request<AcquisitionPriorityDetailRead>(`/acquisition-priorities/${snapshotId}`);
  },

  listAcquisitionPriorityEvidence(params?: {
    acquisition_priority_snapshot_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<AcquisitionPriorityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<AcquisitionPriorityEvidenceListResponse>(`/acquisition-priority-evidence${q}`);
  },

  listAcquisitionPriorityHistory(params?: {
    acquisition_category?: string;
    acquisition_priority?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<AcquisitionPriorityHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<AcquisitionPriorityHistoryListResponse>(`/acquisition-priority-history${q}`);
  },

  listOpsAcquisitionPriorities(params?: {
    owner_user_id?: number;
    acquisition_category?: string;
    acquisition_priority?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<AcquisitionPriorityListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<AcquisitionPriorityListResponse>(`/ops/acquisition-priorities${q}`);
  },

  getOpsAcquisitionPriority(snapshotId: number, params?: { owner_user_id?: number }): Promise<AcquisitionPriorityDetailRead> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, number | undefined>)
        : "";
    return request<AcquisitionPriorityDetailRead>(`/ops/acquisition-priorities/${snapshotId}${q}`);
  },

  listOpsAcquisitionPriorityEvidence(params?: {
    owner_user_id?: number;
    acquisition_priority_snapshot_id?: number;
    evidence_type?: string;
    limit?: number;
    offset?: number;
  }): Promise<AcquisitionPriorityEvidenceListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<AcquisitionPriorityEvidenceListResponse>(`/ops/acquisition-priority-evidence${q}`);
  },

  listOpsAcquisitionPriorityHistory(params?: {
    owner_user_id?: number;
    acquisition_category?: string;
    acquisition_priority?: string;
    recommendation_strength?: string;
    confidence_level?: string;
    risk_level?: string;
    date_from?: string;
    date_to?: string;
    limit?: number;
    offset?: number;
  }): Promise<AcquisitionPriorityHistoryListResponse> {
    const q =
      params && Object.keys(params).length
        ? buildQueryString(params as Record<string, string | number | boolean | undefined>)
        : "";
    return request<AcquisitionPriorityHistoryListResponse>(`/ops/acquisition-priority-history${q}`);
  },
};

export { ApiError, getStoredToken };
