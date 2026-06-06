from urllib.parse import quote

from datetime import date, datetime
from decimal import Decimal
import json
from typing import Annotated, Literal

from pydantic import ValidationError

from fastapi import Depends, FastAPI, File, Form, HTTPException, Body, Query, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
    request_validation_exception_handler as default_request_validation_exception_handler,
)
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.api.report_params import (
    OrderArrivalExportParams,
    TimelineExportParams,
    parse_inventory_export_filters,
    parse_order_arrival_export_params,
    parse_timeline_export_params,
)
from app.core.config import Settings, get_settings, validate_production_settings
from app.http_cors import register_cors_middleware
from app.core.security import create_access_token, get_password_hash, token_expiration_utc, verify_password
from app.db.session import get_session
from app.models import GradingOperationalReportRun, InventoryCopy, OperationalReportRun, PortfolioStrategyDashboardSnapshot, User
from app.schemas.ai import ParseOrderRequest, ParseOrderResponse
from app.schemas.auth import TokenResponse, UserLogin, UserRead, UserRegister

from app.schemas.collection_analytics import (
    CollectionAnalyticsSummary,
    CollectionCompositionResponse,
    CollectionPublisherAnalyticsResponse,
    CollectionQualityAnalyticsResponse,
    CollectionTimelineResponse,
)
from app.schemas.collection_timeline import (
    CollectionTimelineEventType,
    CollectionTimelineEventsResponse,
    CollectionTimelineGrouping,
    CollectionTimelineSort,
    CollectionTimelineSummary,
    OwnershipStateFilter as CollectionTimelineOwnershipStateFilter,
)
from app.schemas.canonical_issue_link_suggestions import (
    CanonicalIssueLinkSuggestionRead,
    CanonicalIssueSuggestionGenerateResponse,
    CanonicalIssueSuggestionOpsListResponse,
    CanonicalIssueSuggestionReviewActionResponse,
    CanonicalIssueSuggestionReviewPayload,
)
from app.schemas.cover_images import (
    CoverImageAssignExistingPayload,
    CoverImageBarcodeCandidateExtractResponse,
    CoverImageBarcodeCandidateRead,
    CoverImageFingerprintGenerateResponse,
    CoverImageFingerprintRead,
    CoverImageMatchCandidateGenerateResponse,
    CoverImageMatchCandidateRead,
    CoverImageMatchGroupRead,
    CoverImageMatchingEvaluationResponse,
    CoverImageOcrCandidateExtractResponse,
    CoverImageOcrCandidateRead,
    CoverImageOcrCandidateReviewNotesPayload,
    CoverImageOcrEnqueueResponse,
    CoverImageOcrQualityAnalysisRead,
    CoverImageOcrQualityAnalysisResponse,
    CoverImageOcrReconciliationResponse,
    CoverImageOcrReconciliationWarningRead,
    CoverImageOcrRegionExtractResponse,
    CoverImageOcrRegionRead,
    CoverImageOcrReplayPayload,
    CoverImageOcrResultRead,
    CoverImageProcessingEnqueueResponse,
    CoverImageRead,
    CoverImageReturnToDraftPayload,
    OpsCoverDuplicateGroup,
    OpsCoverImageRecentRow,
)
from app.schemas.cover_link_decisions import (
    CoverImageLinkDecisionCreate,
    CoverImageLinkDecisionRead,
)
from app.schemas.cover_relationship_graph import CoverRelationshipGraphRead
from app.schemas.debug import RuntimeDebugResponse
from app.schemas.duplicate_candidate_review import (
    DuplicateCandidateNotesUpdate,
    DuplicateCandidateReviewCreate,
    DuplicateCandidateReviewRead,
)
from app.schemas.duplicate_scan import (
    DuplicateScanCandidatesResponse,
    DuplicateScanClassificationFilter,
    DuplicateScanClustersListResponse,
)
from app.schemas.duplicate_ownership import (
    DuplicateOwnershipClassification,
    DuplicateOwnershipGroupRead,
    DuplicateOwnershipListRead,
)
from app.schemas.run_detection import (
    MissingIssueClassification,
    MissingIssueListRead,
    RunDetectionListRead,
    RunDetectionSeriesDetailRead,
    RunDetectionSeriesStatus,
)
from app.schemas.gmail import (
    GmailConnectStartResponse,
    GmailDisconnectResponse,
    GmailImportedDraftRead,
    GmailStatusResponse,
    GmailSyncEnqueueResponse,
    GmailSyncSettingsUpdate,
    GmailSyncStatusResponse,
)
from app.schemas.imports import (
    DraftImportConfirmResponse,
    DraftImportCreate,
    DraftImportListResponse,
    DraftImportRead,
    DraftImportStatus,
    DraftImportUpdate,
    ManualDraftImportCreate,
)
from app.schemas.inventory import (
    BulkInventoryUpdateRequest,
    BulkInventoryUpdateResponse,
    BulkMarkInventoryReceivedRequest,
    BulkMarkInventoryReceivedResponse,
    InventoryDetailResponse,
    InventoryFmvSnapshotResponse,
    InventoryListResponse,
    InventoryRow,
    InventorySummaryResponse,
    InventoryUpdate,
    PortfolioPerformanceResponse,
    ReleaseCalendarPresence,
)
from app.schemas.inventory_fmv import InventoryFmvAttachmentRead, InventoryValuationScope, PortfolioValueSummaryResponse
from app.schemas.listing_registry import (
    ListingCreate,
    ListingDashboardSummary,
    ListingDetailRead,
    ListingListResponse,
    ListingOpsStatusCountRow,
    ListingOpsStatusDistribution,
    ListingRead,
    ListingReplayBody,
    ListingUpdate,
    OpsListingLifecycleEventListResponse,
    OpsListingPriceHistoryListResponse,
)
from app.schemas.listing_export import (
    ListingExportDashboardSummary,
    ListingExportRunCreate,
    ListingExportRunDetailRead,
    ListingExportRunListResponse,
    ListingExportTemplateRead,
    OpsListingExportFileListResponse,
)
from app.schemas.listing_intelligence import (
    ListingChannelPerformanceListResponse,
    ListingChannelPerformanceSnapshotRead,
    ListingCompletenessCheckListResponse,
    ListingCompletenessCheckRead,
    ListingIntelligenceDashboardSummary,
    ListingIntelligenceEvidenceListResponse,
    ListingIntelligenceEvidenceRead,
    ListingIntelligenceGeneratePayload,
    ListingIntelligenceGenerateResponse,
    ListingIntelligenceSnapshotListResponse,
    ListingIntelligenceSnapshotRead,
)
from app.schemas.dealer_dashboard import (
    DealerDashboardAlertListResponse,
    DealerDashboardFeedListResponse,
    DealerDashboardGeneratePayload,
    DealerDashboardGenerateResponse,
    DealerDashboardGetResponse,
    DealerDashboardMetricListResponse,
)
from app.schemas.dealer_grading_dashboard import (
    DealerGradingDashboardAlertListResponse,
    DealerGradingDashboardFeedListResponse,
    DealerGradingDashboardGeneratePayload,
    DealerGradingDashboardGenerateResponse,
    DealerGradingDashboardGetResponse,
    DealerGradingDashboardMetricListResponse,
)
from app.schemas.portfolio_strategy_dashboard import (
    PortfolioStrategyDashboardAlertListResponse,
    PortfolioStrategyDashboardFeedListResponse,
    PortfolioStrategyDashboardGeneratePayload,
    PortfolioStrategyDashboardGenerateResponse,
    PortfolioStrategyDashboardGetResponse,
    PortfolioStrategyDashboardMetricListResponse,
)
from app.schemas.market_ingestion import (
    MarketAcquisitionIngestionBatchCreatePayload,
    MarketAcquisitionIngestionBatchListResponse,
    MarketAcquisitionIngestionBatchRead,
    MarketAcquisitionRawSourceListResponse,
)
from app.schemas.market_normalization import (
    MarketAcquisitionNormalizedCandidateListResponse,
    MarketNormalizationIssueListResponse,
    MarketNormalizationRunCreatePayload,
    MarketNormalizationRunDetailRead,
    MarketNormalizationRunListResponse,
)
from app.schemas.market_scoring import (
    MarketAcquisitionScoreDetailRead,
    MarketAcquisitionScoreHistoryListResponse,
    MarketAcquisitionScoreListResponse,
    MarketAcquisitionScoreRunPayload,
    MarketAcquisitionScoreRunResponse,
    MarketAcquisitionScoreSnapshotListResponse,
)
from app.schemas.market_signal import (
    MarketAcquisitionSignalDetailRead,
    MarketAcquisitionSignalEvidenceListResponse,
    MarketAcquisitionSignalGeneratePayload,
    MarketAcquisitionSignalGenerateResponse,
    MarketAcquisitionSignalHistoryListResponse,
    MarketAcquisitionSignalListResponse,
    MarketAcquisitionSignalSnapshotListResponse,
)
from app.schemas.market_opportunity import (
    MarketAcquisitionOpportunityDetailRead,
    MarketAcquisitionOpportunityEvidenceListResponse,
    MarketAcquisitionOpportunityGeneratePayload,
    MarketAcquisitionOpportunityGenerateResponse,
    MarketAcquisitionOpportunityHistoryListResponse,
    MarketAcquisitionOpportunityItemListResponse,
    MarketAcquisitionOpportunitySnapshotListResponse,
)
from app.schemas.portfolio_market_coupling import (
    PortfolioMarketCouplingDetailRead,
    PortfolioMarketCouplingEdgeListResponse,
    PortfolioMarketCouplingGeneratePayload,
    PortfolioMarketCouplingGenerateResponse,
    PortfolioMarketCouplingHistoryListResponse,
    PortfolioMarketCouplingSnapshotListResponse,
)
from app.schemas.operational_reporting import (
    OperationalReportGeneratePayload,
    OperationalReportRunDetailRead,
    OperationalReportRunListResponse,
    OperationalReportingDashboardRollup,
)
from app.schemas.grading_operational_reporting import (
    GradingOperationalReportGeneratePayload,
    GradingOperationalReportRunDetailRead,
    GradingOperationalReportRunListResponse,
)
from app.schemas.duplicate_consolidation import (
    DuplicateClusterGeneratePayload,
    DuplicateClusterGenerateResponse,
    DuplicateClusterItemListResponse,
    DuplicateClusterListResponse,
    DuplicateClusterRead,
    DuplicateConsolidationRecommendationListResponse,
    DuplicateHistoryListResponse,
    DuplicateIntelligenceSummary,
)
from app.schemas.portfolio_liquidity import (
    PortfolioLiquidityEvidenceListResponse,
    PortfolioLiquidityGeneratePayload,
    PortfolioLiquidityGenerateResponse,
    PortfolioLiquidityHistoryListResponse,
    PortfolioLiquiditySnapshotDetailResponse,
    PortfolioLiquiditySnapshotListResponse,
)
from app.schemas.portfolio_recommendation import (
    PortfolioRecommendationDetailRead,
    PortfolioRecommendationEvidenceListResponse,
    PortfolioRecommendationGeneratePayload,
    PortfolioRecommendationGenerateResponse,
    PortfolioRecommendationHistoryListResponse,
    PortfolioRecommendationListResponse,
)
from app.schemas.acquisition_priority import (
    AcquisitionPriorityDetailRead,
    AcquisitionPriorityEvidenceListResponse,
    AcquisitionPriorityGeneratePayload,
    AcquisitionPriorityGenerateResponse,
    AcquisitionPriorityHistoryListResponse,
    AcquisitionPriorityListResponse,
)
from app.schemas.concentration_risk import (
    ConcentrationRiskDetailRead,
    ConcentrationRiskEvidenceListResponse,
    ConcentrationRiskFactorListResponse,
    ConcentrationRiskGeneratePayload,
    ConcentrationRiskGenerateResponse,
    ConcentrationRiskHistoryListResponse,
    ConcentrationRiskListResponse,
)
from app.schemas.portfolio import (
    PortfolioAllocationGenerateResponse,
    PortfolioAllocationSnapshotListResponse,
    PortfolioCreatePayload,
    PortfolioExposureEvidenceListResponse,
    PortfolioExposureGenerateResponse,
    PortfolioExposureSnapshotListResponse,
    PortfolioGenerateScopePayload,
    PortfolioIntelligenceSummary,
    PortfolioItemCreatePayload,
    PortfolioItemListResponse,
    PortfolioItemRead,
    PortfolioListResponse,
    PortfolioRead,
    PortfolioUpdatePayload,
)
from app.schemas.grading_candidate import (
    GradingCandidateCreatePayload,
    GradingCandidateDashboardSummary,
    GradingCandidateDetailRead,
    GradingCandidateEvidenceCreatePayload,
    GradingCandidateEvidenceListResponse,
    GradingCandidateGradePayload,
    GradingCandidateLifecycleEventListResponse,
    GradingCandidateListResponse,
    GradingCandidatePatchPayload,
    GradingCandidateRejectPayload,
)
from app.schemas.grading_spread import (
    GradingSpreadDashboardSummary,
    GradingSpreadDetailRead,
    GradingSpreadEvidenceListResponse,
    GradingSpreadGeneratePayload,
    GradingSpreadHistoryListResponse,
    GradingSpreadListResponse,
)
from app.schemas.grading_roi import (
    GradingRoiDashboardSummary,
    GradingRoiDetailRead,
    GradingRoiEvidenceListResponse,
    GradingRoiGeneratePayload,
    GradingRoiHistoryListResponse,
    GradingRoiListResponse,
)
from app.schemas.grading_reconciliation import (
    GraderPerformanceSnapshotListResponse,
    GradingReconciliationDashboardSummary,
    GradingReconciliationDetailRead,
    GradingReconciliationEvidenceListResponse,
    GradingReconciliationHistoryListResponse,
    GradingReconciliationListResponse,
    GradingReconciliationReconcilePayload,
)
from app.schemas.grading_recommendation import (
    GradingRecommendationDashboardSummary,
    GradingRecommendationDetailRead,
    GradingRecommendationEvidenceListResponse,
    GradingRecommendationGeneratePayload,
    GradingRecommendationHistoryListResponse,
    GradingRecommendationListResponse,
)
from app.schemas.grading_risk import (
    ConfidenceFactorSnapshotListResponse,
    GradingRiskDashboardSummary,
    GradingRiskDetailRead,
    GradingRiskEvidenceListResponse,
    GradingRiskGeneratePayload,
    GradingRiskListResponse,
    RiskHistoryListResponse,
)
from app.schemas.grading_submission import (
    GradingSubmissionCreatePayload,
    GradingSubmissionDashboardSummary,
    GradingSubmissionDetailRead,
    GradingSubmissionEventListResponse,
    GradingSubmissionListResponse,
    GradingSubmissionPatchPayload,
    GradingSubmissionShipmentCreatePayload,
    GradingSubmissionShipmentListResponse,
)
from app.schemas.convention_operations import (
    ConventionAssignmentCreate,
    ConventionAssignmentListResponse,
    ConventionAssignmentRead,
    ConventionDashboardSummary,
    ConventionEventCreate,
    ConventionEventListResponse,
    ConventionEventPatch,
    ConventionEventRead,
    ConventionMovementCreate,
    ConventionMovementListResponse,
    ConventionMovementRead,
    ConventionPriceSnapshotCreate,
    ConventionPriceSnapshotListResponse,
    ConventionPriceSnapshotRead,
    ConventionReplayBody,
    ConventionSaleSessionCreate,
    ConventionSaleSessionListResponse,
    ConventionSaleSessionRead,
)
from app.schemas.liquidity_engine import (
    InventoryLiquidityEvidenceListResponse,
    InventoryLiquidityListResponse,
    InventoryLiquiditySnapshotRead,
    LiquidityDashboardSummary,
    ListingStalenessEventListResponse,
    ListingVelocityListResponse,
)
from app.schemas.sales_ledger import (
    SaleFinancialAdjustmentListResponse,
    SaleLifecycleEventListResponse,
    SaleRecordCreate,
    SaleRecordDetailRead,
    SaleRecordListResponse,
    SaleRecordPatch,
    SalesDashboardSummary,
)
from app.schemas.inventory_risks import (
    InventoryRiskListResponse,
    InventoryRiskPriority,
    InventoryRiskSummary,
    InventoryRiskType,
)
from app.schemas.inventory_action_center import (
    InventoryActionCenterCategory,
    InventoryActionCenterListResponse,
    InventoryActionCenterSummary,
    InventoryReleaseStatusFilter,
)
from app.schemas.inventory_arrival_tracking import InventoryArrivalTrackingResponse
from app.schemas.order_arrival_intelligence import (
    OrderArrivalClassification,
    OrderArrivalIntelCalendarResponse,
    OrderArrivalIntelListResponse,
    OrderArrivalIntelSummary,
)
from app.schemas.physical_intake import (
    CreatePhysicalIntakeScanSessionPayload,
    MarkInventoryReceivedPayload,
    PhysicalIntakeListResponse,
    PhysicalIntakeState,
    PhysicalIntakeSummaryResponse,
)
from app.schemas.inventory_intelligence import (
    InventoryIntelligenceBreakdown,
    InventoryIntelligenceHealthSummary,
    InventoryIntelligenceSummary,
)
from app.schemas.jobs import ImportParseJobEnqueueResponse, ImportParseJobStatusResponse
from app.schemas.metadata_aliases import (
    MetadataAliasCreate,
    MetadataAliasRead,
    MetadataAliasType,
    MetadataAliasUpdate,
)
from app.schemas.ocr_batches import OcrBatchCreatePayload, OcrBatchRead
from app.schemas.ocr_pipeline_health import OpsOcrPipelineRecoverResponse
from app.schemas.ocr_replays import OcrReplayCreatePayload, OcrReplayRunRead
from app.schemas.ocr_review_queue import (
    BulkIdsPayload,
    BulkMutationResult,
    OcrReviewQueueResponse,
    OcrReviewSummaryResponse,
)
from app.schemas.ops import (
    OpsCanonicalCreatorRow,
    OpsCanonicalSeriesRow,
    OpsDashboardResponse,
    OpsInventoryDuplicateCandidateGroup,
    OpsMetadataAuditRow,
    OpsMetadataReenrichmentEnqueueResponse,
)
from app.schemas.orders import (
    OrderCreate,
    OrderCreateResponse,
    OrderDetailResponse,
    OrderListResponse,
)
from app.schemas.relationship_conflicts import (
    CoverRelationshipConflictActionResponse,
    CoverRelationshipConflictDetectResponse,
    CoverRelationshipConflictListResponse,
    CoverRelationshipConflictStatusPayload,
    RelationshipConflictSeverity,
    RelationshipConflictStatus,
    RelationshipConflictType,
)
from app.schemas.relationship_replays import (
    RelationshipReplayCreatePayload,
    RelationshipReplayRunRead,
)
from app.schemas.variant_family import (
    VariantFamilyCandidatesResponse,
    VariantFamilyClassificationFilter,
    VariantFamilyClustersListResponse,
)
from app.schemas.scan_sessions import (
    ScanSessionCreatePayload,
    ScanSessionDashboardResponse,
    ScanSessionDetailRead,
    ScanSessionIngestManifest,
    ScanSessionIngestManifestRow,
    ScanSessionItemsAppendPayload,
    ScanSessionItemsListRead,
    ScanSessionItemUpdatePayload,
    ScanSessionListResponse,
    ScanSessionStatus,
    ScanSessionSummaryRead,
    ScanSessionType,
)
from app.schemas.scan_qa import (
    InventoryScanQaPanelRead,
    OpsScanQaFleetSummaryRead,
    ScanQaItemRead,
    ScanSessionQaSummaryRead,
)
from app.schemas.scanner_profiles import (
    ScannerProfileCreatePayload,
    ScannerProfileListResponse,
    ScannerProfileRead,
    ScannerProfileUpdatePayload,
)
from app.schemas.scan_pipeline_replays import (
    ScanPipelineReplayCreatePayload,
    ScanPipelineReplayListRead,
    ScanPipelineReplayRunRead,
)
from app.schemas.scan_pipeline_dashboard import (
    ScanPipelineDashboardRead,
    ScanPipelineDashboardSummaryRead,
)
from app.schemas.queue_routing import (
    QueueRoutingListResponse,
    QueueRoutingRecommendationRead,
    ScanSessionRoutingRead,
)
from app.schemas.high_res_review_requests import (
    HighResReviewRequestCreatePayload,
    HighResReviewRequestListResponse,
    HighResReviewRequestRead,
    HighResReviewRequestStatsRead,
)
from app.schemas.market_sales import (
    MarketSaleListResponse,
    MarketSaleRead,
    MarketSaleReviewActionPayload,
    MarketSaleNormalizationIssueRead,
    MarketSaleNormalizationUpdatePayload,
    MarketSaleReviewQueueResponse,
    MarketSaleReviewQueueSummaryRead,
    MarketSourceImportRunCreatePayload,
    MarketSourceImportRunListResponse,
    MarketSourceImportRunRead,
    MarketSourceRead,
    MarketSaleUpsertPayload,
)
from app.schemas.market_sale_comp_eligibility import (
    MarketSaleCompEligibilityListResponse,
    MarketSaleCompEligibilityRead,
    MarketCompEligibilityClassification,
    MarketCompEligibilityStatus,
)
from app.schemas.market_fmv import (
    MarketFmvConfidenceBucket,
    MarketFmvGenerateResponse,
    MarketFmvLiquidityBucket,
    MarketFmvSnapshotListResponse,
    MarketFmvSnapshotRead,
    MarketFmvSnapshotScope,
)
from app.schemas.market_trends import (
    MarketTrendDirection,
    MarketTrendGenerateResponse,
    MarketTrendLiquidityDirection,
    MarketTrendSnapshotListResponse,
    MarketTrendSnapshotRead,
    MarketTrendSnapshotScope,
    MarketTrendStrength,
    MarketTrendWindow,
)
from app.schemas.market_sale_comps import MarketComparableListResponse, MarketComparableSnapshotCompsResponse
from app.schemas.market_sale_match_suggestions import (
    MarketSaleMatchSuggestionGenerateResponse,
    MarketSaleMatchSuggestionOpsListResponse,
    MarketSaleMatchSuggestionRead,
    MarketSaleMatchSuggestionReviewActionResponse,
    MarketSaleMatchSuggestionConfidenceBucket,
    MarketSaleMatchSuggestionReviewState,
    MarketSaleMatchSuggestionType,
)
from app.services.ai_order_parser import (
    AiOrderParserError,
    AiOrderParserNotConfiguredError,
    parse_order_draft_from_text,
)
from app.services.background_jobs import (
    enqueue_cover_image_ocr_for_ops,
    enqueue_cover_image_ocr_for_user,
    enqueue_cover_image_ocr_replay_for_ops,
    enqueue_cover_image_ocr_replay_for_user,
    enqueue_cover_image_processing_for_ops,
    enqueue_cover_image_processing_for_user,
    enqueue_gmail_sync_job_for_user,
    enqueue_import_parse_job_for_user,
    enqueue_metadata_reenrichment_for_draft_import,
    enqueue_metadata_reenrichment_for_inventory_copy,
    get_gmail_sync_job_status_for_user,
    get_import_parse_job_status_for_user,
)
from app.services.canonical_creators import list_canonical_creators_registry
from app.services.canonical_issue_link_suggestions import (
    approve_canonical_issue_suggestion_for_ops,
    approve_canonical_issue_suggestion_for_owner,
    generate_canonical_issue_suggestions_for_ops,
    generate_canonical_issue_suggestions_for_owner,
    ignore_canonical_issue_suggestion_for_ops,
    ignore_canonical_issue_suggestion_for_owner,
    list_canonical_issue_suggestions_for_cover_ops,
    list_canonical_issue_suggestions_for_cover_owner,
    list_canonical_issue_suggestions_for_ops,
    reject_canonical_issue_suggestion_for_ops,
    reject_canonical_issue_suggestion_for_owner,
)
from app.services.canonical_series import list_canonical_series_registry
from app.services.cover_images import (
    acknowledge_cover_match_candidate_for_ops,
    acknowledge_cover_match_candidate_for_owner,
    acknowledge_ocr_reconciliation_warning_for_ops,
    acknowledge_ocr_reconciliation_warning_for_owner,
    analyze_cover_image_ocr_quality_for_ops,
    analyze_cover_image_ocr_quality_for_owner,
    approve_cover_image_barcode_candidate_for_ops,
    approve_cover_image_barcode_candidate_for_owner,
    approve_cover_image_ocr_candidate_for_ops,
    approve_cover_image_ocr_candidate_for_owner,
    assign_existing_cover_image_to_inventory_copy,
    dismiss_cover_match_candidate_for_ops,
    dismiss_cover_match_candidate_for_owner,
    dismiss_ocr_reconciliation_warning_for_ops,
    dismiss_ocr_reconciliation_warning_for_owner,
    evaluate_cover_image_matching_readiness,
    extract_cover_image_barcode_candidates_for_ops,
    extract_cover_image_barcode_candidates_for_owner,
    extract_cover_image_ocr_candidates_for_ops,
    extract_cover_image_ocr_candidates_for_owner,
    extract_cover_image_ocr_regions_for_ops,
    extract_cover_image_ocr_regions_for_owner,
    generate_cover_image_fingerprints_for_ops,
    generate_cover_image_fingerprints_for_owner,
    generate_cover_image_match_candidates_for_ops,
    generate_cover_image_match_candidates_for_owner,
    get_cover_derivative_or_404,
    get_cover_entity_for_processing_by_ops_or_404,
    get_cover_entity_for_processing_by_owner,
    get_cover_entity_or_404,
    get_cover_match_group_for_ops,
    get_cover_match_group_for_owner,
    get_cover_ocr_region_or_404,
    list_cover_barcode_candidate_reads_for_cover,
    list_cover_fingerprint_reads_for_cover,
    list_cover_image_ocr_reconciliation_warnings,
    list_cover_match_candidate_reads_for_cover,
    list_cover_ocr_candidate_reads_for_cover,
    list_cover_ocr_quality_analysis_reads_for_cover,
    list_cover_ocr_region_reads_for_cover,
    list_cover_ocr_result_reads_for_cover,
    list_duplicate_cover_image_groups_for_ops,
    list_recent_cover_uploads_for_ops,
    patch_cover_image_ocr_candidate_review_notes_for_ops,
    patch_cover_image_ocr_candidate_review_notes_for_owner,
    persist_cover_upload,
    reconcile_cover_image_ocr_metadata_for_ops,
    reconcile_cover_image_ocr_metadata_for_owner,
    reject_cover_image_barcode_candidate_for_ops,
    reject_cover_image_barcode_candidate_for_owner,
    reject_cover_image_ocr_candidate_for_ops,
    reject_cover_image_ocr_candidate_for_owner,
    resolve_filesystem_path,
    return_cover_image_to_draft_import,
    set_draft_import_primary_cover_image,
    set_inventory_primary_cover_image,
    user_can_download_cover,
)
from app.services.cover_link_decisions import (
    create_cover_link_decision_for_ops,
    create_cover_link_decision_for_owner,
    get_cover_link_decision_for_ops,
    get_cover_link_decision_for_owner,
    list_cover_link_decisions_for_ops,
    list_cover_link_decisions_for_owner,
    revert_cover_link_decision_for_ops,
    revert_cover_link_decision_for_owner,
)
from app.services.cover_relationship_graph import (
    get_cover_relationship_graph_for_ops,
    get_cover_relationship_graph_for_owner,
)
from app.services.duplicate_candidate_reviews import (
    serialize_duplicate_candidate_review_read,
    upsert_duplicate_review_notes,
    upsert_mark_duplicate_review,
)
from app.services.duplicate_scan_intelligence import (
    duplicate_scan_candidates_for_cover_owner,
    duplicate_scan_candidates_for_ops,
    list_duplicate_scan_clusters_for_ops,
    list_duplicate_scan_clusters_for_owner,
)
from app.services.duplicate_ownership_intelligence import (
    get_duplicate_ownership_detail_ops,
    get_duplicate_ownership_detail_owner,
    list_duplicate_ownership_ops,
    list_duplicate_ownership_owner,
)
from app.services.run_detection import (
    get_run_detection_detail_ops,
    get_run_detection_detail_owner,
    list_missing_issues_ops,
    list_missing_issues_owner,
    list_run_detection_ops,
    list_run_detection_owner,
)
from app.services.scan_session_ingest import ParsedScanUploadSlot, ingest_uploaded_images_into_scan_session
from app.services.high_res_review_requests import (
    attach_high_res_review_scan_multipart,
    cancel_high_res_review_request,
    complete_high_res_review_request,
    create_high_res_review_request,
    get_high_res_review_request_detail,
    high_res_review_request_stats_ops,
    high_res_review_request_stats_owner,
    list_high_res_review_requests_ops,
    list_high_res_review_requests_owner,
)
from app.services.market_sales import (
    cancel_market_import_run_for_ops,
    complete_market_import_run_for_ops,
    create_market_import_run_for_ops,
    get_market_import_run_for_owner,
    get_market_source_read,
    list_market_import_runs_for_ops,
    list_market_import_runs_for_owner,
    list_market_sources,
    list_market_sales,
    start_market_import_run_for_ops,
    upsert_market_sale_record,
)
from app.services.market_ingestion import (
    get_ingestion_batch_ops,
    get_ingestion_batch_owner,
    ingest_market_acquisition_batch_for_owner,
    list_ingestion_batches_ops,
    list_ingestion_batches_owner,
    list_ingestion_raw_ops,
    list_ingestion_raw_owner,
)
from app.services.market_normalization import (
    execute_market_normalization_run_for_owner,
    get_normalization_run_ops,
    get_normalization_run_owner,
    list_normalized_candidates_ops,
    list_normalized_candidates_owner,
    list_normalization_issues_ops,
    list_normalization_issues_owner,
    list_normalization_runs_ops,
    list_normalization_runs_owner,
)
from app.services.market_scoring import (
    get_score_ops,
    get_score_owner,
    list_history_ops as list_market_scoring_history_ops,
    list_history_owner as list_market_scoring_history_owner,
    list_scores_ops,
    list_scores_owner,
    list_snapshots_ops,
    list_snapshots_owner,
    run_market_acquisition_scoring_for_owner,
)
from app.services.market_signal import (
    generate_market_signals_for_owner,
    get_signal_ops,
    get_signal_owner,
    list_evidence_ops as list_market_signal_evidence_ops,
    list_evidence_owner as list_market_signal_evidence_owner,
    list_history_ops as list_market_signal_history_ops,
    list_history_owner as list_market_signal_history_owner,
    list_signals_ops,
    list_signals_owner,
    list_snapshots_ops as list_market_signal_snapshots_ops,
    list_snapshots_owner as list_market_signal_snapshots_owner,
)
from app.services.market_opportunity import (
    generate_market_opportunities_for_owner,
    get_opportunity_detail_ops,
    get_opportunity_detail_owner,
    list_evidence_ops as list_market_opportunity_evidence_ops,
    list_evidence_owner as list_market_opportunity_evidence_owner,
    list_history_ops as list_market_opportunity_history_ops,
    list_history_owner as list_market_opportunity_history_owner,
    list_opportunity_items_ops,
    list_opportunity_items_owner,
    list_snapshots_ops as list_market_opportunity_snapshots_ops,
    list_snapshots_owner as list_market_opportunity_snapshots_owner,
)
from app.services.portfolio_market_coupling import (
    generate_coupling_for_owner,
    get_coupling_detail_ops,
    get_coupling_detail_owner,
    list_coupling_edges_ops,
    list_coupling_edges_owner,
    list_coupling_history_ops,
    list_coupling_history_owner,
    list_coupling_snapshots_ops,
    list_coupling_snapshots_owner,
)
from app.services.market_sale_review_queue import (
    flag_duplicate_market_sale_record,
    get_market_sale_review_detail,
    ignore_market_sale_record,
    list_market_sale_normalization_issues,
    list_market_sale_review_queue,
    market_sale_review_queue_summary,
    update_market_sale_normalization,
)
from app.services.market_sale_comp_eligibility import (
    get_market_comp_eligibility_for_ops,
    get_market_comp_eligibility_for_owner,
    list_market_comp_eligibility,
)
from app.services.market_sale_comps import get_market_fmv_snapshot_comps, list_market_comps
from app.services.market_sale_match_suggestions import (
    approve_market_sale_match_suggestion_for_ops,
    generate_market_sale_match_suggestions,
    get_market_sale_match_suggestion_for_ops,
    get_market_sale_match_suggestion_for_owner,
    ignore_market_sale_match_suggestion_for_ops,
    list_market_sale_match_suggestions,
    reject_market_sale_match_suggestion_for_ops,
)
from app.services.market_fmv import (
    generate_market_fmv_snapshots,
    get_market_fmv_snapshot,
    list_market_fmv_snapshots,
)
from app.services.market_trends import (
    generate_market_trend_snapshots,
    get_market_trend_snapshot,
    list_market_trends,
)
from app.services.scan_qa import (
    fleet_scan_qa_summary,
    get_scan_session_item_qa,
    get_scan_session_qa,
    inventory_cover_scan_qa,
    run_scan_session_qa,
)
from app.services.queue_routing import (
    acknowledge_queue_routing_recommendation,
    dismiss_queue_routing_recommendation,
    generate_scan_session_routing,
    get_scan_session_routing,
    list_queue_routing_recommendations_ops,
    list_queue_routing_recommendations_owner,
)
from app.services.scan_sessions import (
    append_scan_session_items,
    cancel_scan_session,
    complete_scan_session,
    create_scan_session,
    get_scan_session_detail,
    list_scan_session_items_read,
    list_scan_sessions,
    owner_scan_session_dashboard,
    pause_scan_session,
    patch_scan_session_item,
    start_scan_session,
)
from app.services.scanner_profiles import (
    create_scanner_profile,
    delete_scanner_profile_for_owner,
    get_scanner_profile_detail_for_owner,
    list_scanner_profiles_for_owner,
    list_scanner_profiles_ops,
    update_scanner_profile_for_owner,
)
from app.services.scan_pipeline_replays import (
    cancel_scan_pipeline_replay_run,
    create_scan_pipeline_replay_run,
    get_scan_pipeline_replay_run_for_owner,
    get_scan_pipeline_replay_run_ops,
    list_scan_pipeline_replay_runs_owner,
    list_scan_pipeline_replay_runs_ops,
    start_scan_pipeline_replay_run,
)
from app.services.scan_pipeline_dashboard import (
    scan_pipeline_dashboard,
    scan_pipeline_dashboard_summary,
)
from app.services.gmail_ingestion import (
    GmailIntegrationError,
    GmailIntegrationNotConfiguredError,
    GmailNotConnectedError,
    build_gmail_connect_authorization_url,
    connect_gmail_account_for_user,
    decode_gmail_connect_state,
    disconnect_gmail_for_user,
    get_gmail_status_for_user,
    get_gmail_sync_status_for_user,
    serialize_gmail_import_drafts,
    update_gmail_sync_settings_for_user,
)
from app.services.imports import (
    confirm_import_for_user,
    create_import_for_user,
    create_manual_import_for_user,
    discard_import_for_user,
    get_import_for_user,
    list_imports_for_user,
    update_import_for_user,
)
from app.services.inventory import (
    bulk_update_inventory,
    find_duplicate_inventory_candidates,
    get_inventory_copy_detail,
    get_inventory_fmv_history,
    inventory_summary,
    list_inventory,
    portfolio_performance,
    update_inventory_copy,
)
from app.services.inventory_arrival_tracking import build_inventory_arrival_tracking
from app.services.inventory_fmv import (
    inventory_fmv_detail_for_scope,
    inventory_fmv_inventory_response_for_scope,
    portfolio_value_summary_for_scope,
)
from app.services import dealer_dashboard as dealer_dashboard_service
from app.services import dealer_grading_dashboard as dealer_grading_dashboard_service
from app.services import grading_reporting as grading_reporting_service
from app.services import portfolio_strategy_dashboard as portfolio_strategy_dashboard_service
from app.services import portfolio_registry as portfolio_registry_service
from app.services import duplicate_consolidation as duplicate_consolidation_service
from app.services import portfolio_liquidity as portfolio_liquidity_service
from app.services import portfolio_recommendation as portfolio_recommendation_service
from app.services import acquisition_priority as acquisition_priority_service
from app.services import concentration_risk as concentration_risk_service
from app.services import grading_candidate_service
from app.services import grading_reconciliation as grading_reconciliation_service
from app.services import grading_recommendation as grading_recommendation_service
from app.services import grading_risk as grading_risk_service
from app.services import grading_spread as grading_spread_service
from app.services import grading_roi as grading_roi_service
from app.services import grading_submission as grading_submission_service
from app.services import operational_reporting as operational_reporting_service
from app.services import listing_export as listing_export_service
from app.services import listing_intelligence as listing_intelligence_service
from app.services import listing_registry as listing_registry_service
from app.services import convention_operations as convention_operations_service
from app.services import liquidity_engine as liquidity_engine_service
from app.services import sales_ledger as sales_ledger_service
from app.services.physical_intake import (
    build_physical_intake_summary,
    bulk_mark_physical_received,
    create_physical_intake_scan_session,
    list_physical_intake,
    mark_physical_received,
)
from app.services.inventory_risks import (
    get_inventory_risk_detail_ops,
    get_inventory_risk_detail_owner,
    get_inventory_risks_ops,
    get_inventory_risks_owner,
)
from app.services.inventory_action_center import get_inventory_action_center_response
from app.services.order_arrival_intelligence import (
    compute_order_arrival_intelligence,
    get_order_arrival_calendar,
    order_arrival_summary_only,
)
from app.services.collection_analytics import (
    analyze_collection_composition,
    analyze_collection_publishers,
    analyze_collection_quality,
    analyze_collection_summary,
    analyze_collection_timeline,
)
from app.services.collection_timeline import timeline_events_for_scope
from app.services.inventory_intelligence import compute_inventory_intelligence
from app.services.metadata_aliases import (
    create_metadata_alias,
    deactivate_metadata_alias,
    list_metadata_aliases,
    update_metadata_alias,
)
from app.services.metadata_audits import list_recent_metadata_audits
from app.services.ocr_batches import (
    cancel_ocr_batch_for_ops,
    cancel_ocr_batch_for_owner,
    create_ocr_batch_for_ops,
    create_ocr_batch_for_owner,
    enqueue_ocr_batch_for_ops,
    enqueue_ocr_batch_for_owner,
    get_ocr_batch_detail_for_ops,
    get_ocr_batch_detail_for_owner,
    list_ocr_batches_for_ops,
    list_ocr_batches_for_owner,
    retry_failed_ocr_batch_items_for_ops,
    retry_failed_ocr_batch_items_for_owner,
)
from app.services.ocr_pipeline_health import recover_ocr_pipeline
from app.services.ocr_replays import (
    cancel_ocr_replay_run_for_ops,
    cancel_ocr_replay_run_for_owner,
    create_ocr_replay_run_for_ops,
    create_ocr_replay_run_for_owner,
    get_ocr_replay_run_detail_for_ops,
    get_ocr_replay_run_detail_for_owner,
    list_ocr_replay_runs_for_ops,
    list_ocr_replay_runs_for_owner,
    start_ocr_replay_run_for_ops,
    start_ocr_replay_run_for_owner,
)
from app.services.ocr_review_queue import (
    build_filters_from_http,
    build_ocr_review_summary,
    bulk_ack_warnings_for_ops,
    bulk_ack_warnings_for_owner,
    bulk_approve_barcodes_for_ops,
    bulk_approve_barcodes_for_owner,
    bulk_dismiss_warnings_for_ops,
    bulk_dismiss_warnings_for_owner,
    bulk_reject_barcodes_for_ops,
    bulk_reject_barcodes_for_owner,
    list_ocr_review_queue,
)
from app.services.ops_admin import build_ops_dashboard, ensure_ops_admin_access
from app.services.ops_access import is_ops_admin_user
from app.services.reports_export import (
    ACTION_CENTER_CSV_COLUMNS,
    INVENTORY_OPS_CSV_COLUMNS,
    INVENTORY_OWNER_CSV_COLUMNS,
    ORDER_ARRIVAL_CSV_COLUMNS,
    RUN_DETECTION_SERIES_CSV_COLUMNS,
    TIMELINE_CSV_COLUMNS,
    InventoryExportFilters,
    action_center_export_rows,
    collection_summary_payload,
    dumps_report_json,
    inventory_export_json_document,
    inventory_export_rows_ops,
    inventory_export_rows_owner,
    order_arrival_export_rows,
    render_csv,
    run_detection_series_rows,
    sanitize_report_filename,
    timeline_export_rows,
)
from app.services.market_reporting import (
    dumps_market_deterministic_summary_bytes,
    dumps_no_market_data_inventory_json,
    render_low_confidence_inventory_csv,
    render_market_eligible_comps_csv,
    render_market_fmv_snapshots_csv,
    render_market_sales_csv,
    render_market_trends_csv,
    render_no_market_data_inventory_csv,
    render_normalization_issues_summary_csv,
    render_portfolio_value_summary_csv,
    render_stale_fmv_inventory_csv,
)
from app.services.orders import (
    create_order_for_user,
    get_order_detail_for_user,
    list_orders_for_user,
)
from app.services.relationship_conflicts import (
    acknowledge_relationship_conflict_for_ops,
    acknowledge_relationship_conflict_for_owner,
    detect_relationship_conflicts_for_ops,
    detect_relationship_conflicts_for_owner,
    dismiss_relationship_conflict_for_ops,
    dismiss_relationship_conflict_for_owner,
    list_relationship_conflicts_for_cover_ops,
    list_relationship_conflicts_for_cover_owner,
    list_relationship_conflicts_for_ops,
    list_relationship_conflicts_for_owner,
    resolve_relationship_conflict_for_ops,
    resolve_relationship_conflict_for_owner,
)
from app.services.relationship_replays import (
    cancel_relationship_replay_run_for_ops,
    cancel_relationship_replay_run_for_owner,
    create_relationship_replay_run_for_ops,
    create_relationship_replay_run_for_owner,
    get_relationship_replay_run_detail_for_ops,
    get_relationship_replay_run_detail_for_owner,
    list_relationship_replay_runs_for_ops,
    list_relationship_replay_runs_for_owner,
    start_relationship_replay_run_for_ops,
    start_relationship_replay_run_for_owner,
)
from app.services.runtime_debug import build_runtime_debug_response
from app.services.variant_family_intelligence import (
    list_variant_family_clusters_for_ops,
    list_variant_family_clusters_for_owner,
    variant_family_candidates_for_cover_owner,
    variant_family_candidates_for_ops,
)

from app.api.market_v1_layer import attach_market_v1_layer
from app.api.scan_ingestion import attach_scan_ingestion_layer
from app.api.scan_normalization import attach_scan_normalization_layer
from app.api.scan_boundary import attach_scan_boundary_layer
from app.api.scan_ocr import attach_scan_ocr_layer
from app.api.scan_reconciliation import attach_scan_reconciliation_layer
from app.api.scan_defects import attach_scan_defects_layer
from app.api.scan_spine_ticks import attach_scan_spine_ticks_layer
from app.api.scan_corner_edges import attach_scan_corner_edges_layer
from app.api.scan_surface_defects import attach_scan_surface_defects_layer
from app.api.scan_structural_damage import attach_scan_structural_damage_layer
from app.api.scan_defect_aggregation import attach_scan_defect_aggregation_layer
from app.api.scan_grading_assistance import attach_scan_grading_assistance_layer
from app.api.scan_visual_evidence import attach_scan_visual_evidence_layer
from app.api.scan_review import attach_scan_review_layer
from app.api.scan_historical_comparison import attach_scan_historical_comparison_layer
from app.api.scan_authentication import attach_scan_authentication_layer
from app.api.scan_intelligence_feed import attach_scan_intelligence_feed_layer
from app.api.automation_batch import attach_automation_batch_layer
from app.api.automation_notifications import attach_automation_notifications_layer
from app.api.automation_ops import attach_automation_ops_layer
from app.api.automation_analytics import attach_automation_analytics_layer
from app.api.automation_rules import attach_automation_rules_layer
from app.api.automation_jobs import attach_automation_jobs_layer
from app.api.automation_recovery import attach_automation_recovery_layer
from app.api.automation_scheduling import attach_automation_scheduling_layer
from app.api.automation_workers import attach_automation_workers_layer
from app.api.organization import attach_organization_layer
from app.api.whatnot import attach_whatnot_layer
from app.api.ebay_compliance import attach_ebay_compliance_layer
from app.api.shopify import attach_shopify_layer
from app.api.marketplace_dashboard import attach_marketplace_dashboard_layer
from app.api.marketplace_operations import attach_marketplace_operations_layer
from app.api.marketplace import attach_marketplace_layer
from app.api.marketplace_publish import attach_marketplace_publish_layer
from app.api.marketplace_sync import attach_marketplace_sync_layer
from app.api.marketplace_accounts import attach_marketplace_accounts_layer
from app.api.marketplace_events import attach_marketplace_events_layer
from app.api.marketplace_inventory_sync import attach_marketplace_inventory_sync_layer
from app.api.marketplace_listings import attach_marketplace_listings_layer
from app.api.marketplace_orders import attach_marketplace_order_layer
from app.api.marketplace_pricing import attach_marketplace_pricing_layer
from app.api.live_sales import attach_live_sales_layer
from app.api.marketplace_ops_dashboard import attach_marketplace_ops_dashboard_layer
from app.api.marketplace_analytics import attach_marketplace_analytics_layer
from app.api.market_intelligence import attach_market_intelligence_layer
from app.api.market_intelligence_platform import attach_market_intelligence_platform_layer
from app.api.collector_assistant_api import attach_collector_assistant_layer
from app.api.collector_experience_api import attach_collector_experience_layer
from app.api.variant_market_intelligence_api import attach_variant_market_intelligence_layer
from app.api.portfolio_analytics_api import attach_portfolio_analytics_layer
from app.api.market_pricing_engine_api import attach_market_pricing_engine_layer
from app.api.sell_intelligence_api import attach_sell_intelligence_layer
from app.api.market_forecast import attach_market_forecast_layer
from app.api.forecast_dashboard import attach_forecast_dashboard_layer
from app.api.forecast_validation import attach_forecast_validation_layer
from app.api.forecast_validation_dashboard import attach_forecast_validation_dashboard_layer
from app.api.forecast_platform import attach_forecast_platform_layer
from app.api.data_integrity import attach_data_integrity_layer
from app.api.operations_reliability import attach_operations_reliability_layer
from app.api.production_readiness import attach_production_readiness_layer
from app.api.condition_intelligence import attach_condition_intelligence_layer
from app.api.recommendation_feedback import attach_recommendation_feedback_layer
from app.api.grading_intelligence import attach_grading_intelligence_layer
from app.api.grading_validation import attach_grading_validation_layer
from app.api.grading_platform import attach_grading_platform_layer
from app.api.release_intelligence import attach_release_intelligence_layer
from app.api.release_monitoring import attach_release_monitoring_layer
from app.api.storage_foundation import attach_storage_foundation_layer
from app.api.release_watchlists import attach_release_watchlists_layer
from app.api.spec_intelligence import attach_spec_intelligence_layer
from app.api.release_imports import attach_release_imports_layer
from app.api.lunar_feed import attach_lunar_feed_layer
from app.api.lunar_scheduler import attach_lunar_scheduler_layer
from app.api.release_platform import attach_release_platform_layer
from app.api.release_platform_certification import attach_release_platform_certification_layer
from app.api.intelligence import attach_intelligence_layer
from app.api.key_issue_intelligence import attach_key_issue_intelligence_layer
from app.api.market_user_intelligence import attach_market_user_intelligence_layer
from app.api.recommendations_v2 import attach_recommendations_v2_layer
from app.api.pull_list_decisions import attach_pull_list_decisions_layer
from app.api.foc_dashboard import attach_foc_dashboard_layer
from app.api.pull_list_automation import attach_pull_list_automation_layer
from app.api.pull_list_certification import attach_pull_list_certification_layer
from app.api.purchase_profiles import attach_purchase_profile_layer
from app.api.purchase_quantity import attach_purchase_quantity_layer
from app.api.purchase_variant import attach_purchase_variant_layer
from app.api.purchase_budget import attach_purchase_budget_layer
from app.api.sell_candidate import attach_sell_candidate_layer
from app.api.portfolio_certification import attach_portfolio_certification_layer
from app.api.want_lists import attach_want_list_layer
from app.api.collection_gaps import attach_collection_gap_layer
from app.api.collected_runs import attach_collected_run_layer
from app.api.next_issues import attach_next_issue_layer
from app.api.future_release_matches import attach_future_release_match_layer
from app.api.future_release_actions import attach_future_release_action_layer
from app.api.future_release_dashboard import attach_future_release_dashboard_layer
from app.api.future_release_certification import attach_future_release_certification_layer
from app.api.external_catalog import attach_external_catalog_layer
from app.api.demand_intelligence_platform import attach_demand_intelligence_platform_layer
from app.api.recommendation_intelligence_platform import attach_recommendation_intelligence_platform_layer
from app.api.industry_publishers import attach_industry_publishers_layer
from app.api.industry_release_scan import attach_industry_release_scan_layer
from app.api.industry_release_signals import attach_industry_release_signal_layer
from app.api.industry_opportunities import attach_industry_opportunity_layer
from app.api.industry_scanner_dashboard import attach_industry_scanner_dashboard_layer
from app.api.industry_scanner_automation import attach_industry_scanner_automation_layer
from app.api.industry_scanner_certification import attach_industry_scanner_certification_layer
from app.api.spec_inputs import attach_spec_inputs_layer
from app.api.spec_baseline_scores import attach_spec_baseline_scores_layer
from app.api.ai_spec_evaluations import attach_ai_spec_evaluations_layer
from app.api.top_spec_picks import attach_top_spec_picks_layer
from app.api.weekly_spec_dashboard import attach_weekly_spec_dashboard_layer
from app.api.spec_automation import attach_spec_automation_layer
from app.api.ai_spec_certification import attach_ai_spec_certification_layer
from app.api.acquisition_opportunities import attach_acquisition_opportunity_layer
from app.api.marketplace_acquisitions import attach_marketplace_acquisition_layer
from app.api.acquisition_dashboard import attach_acquisition_dashboard_layer
from app.api.acquisition_certification import attach_acquisition_certification_layer
from app.api.exit_candidates import attach_exit_candidate_layer
from app.api.hold_sell_intelligence import attach_hold_sell_intelligence_layer
from app.api.grade_before_sell import attach_grade_before_sell_layer
from app.api.portfolio_rebalancing import attach_portfolio_rebalancing_layer
from app.api.exit_dashboard import attach_exit_dashboard_layer
from app.api.exit_certification import attach_exit_certification_layer
from app.api.unified_collector_intelligence import attach_unified_collector_intelligence_layer
from app.api.daily_action_engine import attach_daily_action_engine_layer
from app.api.cross_system_recommendation import attach_cross_system_recommendation_layer
from app.api.executive_dashboard import attach_executive_dashboard_layer
from app.api.final_platform_certification import attach_final_platform_certification_layer
from app.api.pull_list import attach_pull_list_layer
from app.api.recommendation_intelligence_certification import attach_recommendation_intelligence_certification_layer
from app.api.dealer_copilot import attach_dealer_copilot_layer
from app.api.shopify_sync import attach_shopify_sync_layer
from app.api.mobile_foundation import attach_mobile_foundation_layer
from app.api.offline_inventory import attach_offline_inventory_layer
from app.api.mobile_scanning import attach_mobile_scanning_layer
from app.api.convention_mode import attach_convention_mode_layer
from app.api.quick_sales import attach_quick_sales_layer
from app.api.mobile_ops_dashboard import attach_mobile_ops_dashboard_layer
from app.api.mobile_device_security import attach_mobile_device_security_layer
from app.api.mobile_analytics import attach_mobile_analytics_layer
from app.api.mobile_scan_platform import attach_mobile_scan_platform_layer
from app.api.mobile_operations import attach_mobile_operations_layer
from app.api.p80_collector_assistant import attach_p80_collector_assistant_layer
from app.api.agents import attach_agents_layer
from app.api.workflows import attach_workflows_layer
from app.api.research_agents import attach_research_agents_layer
from app.api.agent_dashboard import attach_agent_dashboard_layer
from app.api.agent_security import attach_agent_security_layer
from app.api.agent_analytics import attach_agent_analytics_layer
from app.api.agent_platform import attach_agent_platform_layer
from app.api.routes.auth_sessions import attach_auth_sessions_layer
from app.api.shared_inventory import attach_shared_inventory_layer
from app.api.reviews import attach_reviews_layer
from app.api.storefronts import attach_storefronts_layer
from app.api.activity import attach_activity_layer
from app.api.audit import attach_audit_layer
from app.api.dealer_dashboard import attach_dealer_dashboard_layer
from app.api.scan_replay import attach_scan_replay_layer
from app.security.session_manager import build_device_label, create_session, detect_device_type


settings = get_settings()
validate_production_settings(settings)

app = FastAPI(title="ComicOS API")

attach_market_v1_layer(app)
attach_scan_ingestion_layer(app)
attach_scan_normalization_layer(app)
attach_scan_boundary_layer(app)
attach_scan_ocr_layer(app)
attach_scan_reconciliation_layer(app)
attach_scan_defects_layer(app)
attach_scan_spine_ticks_layer(app)
attach_scan_corner_edges_layer(app)
attach_scan_surface_defects_layer(app)
attach_scan_structural_damage_layer(app)
attach_scan_defect_aggregation_layer(app)
attach_scan_grading_assistance_layer(app)
attach_scan_visual_evidence_layer(app)
attach_scan_review_layer(app)
attach_scan_historical_comparison_layer(app)
attach_scan_authentication_layer(app)
attach_scan_intelligence_feed_layer(app)
attach_automation_batch_layer(app)
attach_automation_notifications_layer(app)
attach_automation_ops_layer(app)
attach_automation_analytics_layer(app)
attach_automation_rules_layer(app)
attach_automation_jobs_layer(app)
attach_automation_recovery_layer(app)
attach_automation_scheduling_layer(app)
attach_automation_workers_layer(app)
attach_organization_layer(app)
attach_marketplace_layer(app)
attach_marketplace_publish_layer(app)
attach_marketplace_sync_layer(app)
attach_marketplace_operations_layer(app)
attach_whatnot_layer(app)
attach_shopify_layer(app)
attach_ebay_compliance_layer(app)
attach_marketplace_dashboard_layer(app)
attach_marketplace_accounts_layer(app)
attach_marketplace_events_layer(app)
attach_live_sales_layer(app)
attach_marketplace_ops_dashboard_layer(app)
attach_marketplace_analytics_layer(app)
attach_market_intelligence_layer(app)
attach_market_intelligence_platform_layer(app)
attach_collector_assistant_layer(app)
attach_collector_experience_layer(app)
attach_variant_market_intelligence_layer(app)
attach_portfolio_analytics_layer(app)
attach_market_pricing_engine_layer(app)
attach_sell_intelligence_layer(app)
attach_market_forecast_layer(app)
attach_forecast_dashboard_layer(app)
attach_forecast_validation_layer(app)
attach_forecast_validation_dashboard_layer(app)
attach_forecast_platform_layer(app)
attach_data_integrity_layer(app)
attach_operations_reliability_layer(app)
attach_production_readiness_layer(app)
attach_condition_intelligence_layer(app)
attach_recommendation_feedback_layer(app)
attach_grading_intelligence_layer(app)
attach_grading_validation_layer(app)
attach_grading_platform_layer(app)
attach_release_intelligence_layer(app)
attach_release_monitoring_layer(app)
attach_storage_foundation_layer(app)
attach_release_watchlists_layer(app)
attach_spec_intelligence_layer(app)
attach_release_platform_layer(app)
attach_release_platform_certification_layer(app)
attach_intelligence_layer(app)
attach_key_issue_intelligence_layer(app)
attach_market_user_intelligence_layer(app)
attach_recommendations_v2_layer(app)
attach_recommendation_intelligence_certification_layer(app)
attach_pull_list_layer(app)
attach_pull_list_decisions_layer(app)
attach_foc_dashboard_layer(app)
attach_pull_list_automation_layer(app)
attach_pull_list_certification_layer(app)
attach_purchase_profile_layer(app)
attach_purchase_quantity_layer(app)
attach_purchase_variant_layer(app)
attach_purchase_budget_layer(app)
attach_sell_candidate_layer(app)
attach_portfolio_certification_layer(app)
attach_want_list_layer(app)
attach_collection_gap_layer(app)
attach_collected_run_layer(app)
attach_next_issue_layer(app)
attach_future_release_match_layer(app)
attach_future_release_action_layer(app)
attach_future_release_dashboard_layer(app)
attach_future_release_certification_layer(app)
attach_external_catalog_layer(app)
attach_demand_intelligence_platform_layer(app)
attach_recommendation_intelligence_platform_layer(app)
attach_industry_publishers_layer(app)
attach_industry_release_scan_layer(app)
attach_industry_release_signal_layer(app)
attach_industry_opportunity_layer(app)
attach_industry_scanner_dashboard_layer(app)
attach_industry_scanner_automation_layer(app)
attach_industry_scanner_certification_layer(app)
attach_spec_inputs_layer(app)
attach_spec_baseline_scores_layer(app)
attach_ai_spec_evaluations_layer(app)
attach_top_spec_picks_layer(app)
attach_weekly_spec_dashboard_layer(app)
attach_spec_automation_layer(app)
attach_ai_spec_certification_layer(app)
attach_acquisition_opportunity_layer(app)
attach_marketplace_acquisition_layer(app)
attach_acquisition_dashboard_layer(app)
attach_acquisition_certification_layer(app)
attach_exit_candidate_layer(app)
attach_hold_sell_intelligence_layer(app)
attach_grade_before_sell_layer(app)
attach_portfolio_rebalancing_layer(app)
attach_exit_dashboard_layer(app)
attach_exit_certification_layer(app)
attach_unified_collector_intelligence_layer(app)
attach_daily_action_engine_layer(app)
attach_cross_system_recommendation_layer(app)
attach_executive_dashboard_layer(app)
attach_final_platform_certification_layer(app)
attach_release_imports_layer(app)
attach_lunar_feed_layer(app)
attach_lunar_scheduler_layer(app)
attach_dealer_copilot_layer(app)
attach_shopify_sync_layer(app)
attach_marketplace_inventory_sync_layer(app)
attach_marketplace_listings_layer(app)
attach_marketplace_order_layer(app)
attach_marketplace_pricing_layer(app)
attach_mobile_foundation_layer(app)
attach_offline_inventory_layer(app)
attach_mobile_scanning_layer(app)
attach_convention_mode_layer(app)
attach_quick_sales_layer(app)
attach_mobile_ops_dashboard_layer(app)
attach_mobile_device_security_layer(app)
attach_mobile_analytics_layer(app)
attach_mobile_scan_platform_layer(app)
attach_mobile_operations_layer(app)
attach_p80_collector_assistant_layer(app)
attach_agents_layer(app)
attach_workflows_layer(app)
attach_research_agents_layer(app)
attach_agent_dashboard_layer(app)
attach_agent_security_layer(app)
attach_agent_analytics_layer(app)
attach_agent_platform_layer(app)
attach_auth_sessions_layer(app)
attach_shared_inventory_layer(app)
attach_reviews_layer(app)
attach_storefronts_layer(app)
attach_activity_layer(app)
attach_audit_layer(app)
attach_dealer_dashboard_layer(app)
attach_scan_replay_layer(app)


@app.exception_handler(HTTPException)
async def _v1_http_exception_dispatcher(request: Request, exc: HTTPException):
    path = request.url.path
    if not (path.startswith("/api/v1/") or path.startswith("/ops/") or path.startswith("/market-")):
        return await default_http_exception_handler(request, exc)

    if isinstance(exc.detail, str):
        message = exc.detail
        details = None
    elif isinstance(exc.detail, dict):
        message = str(exc.detail.get("message") or exc.detail.get("msg") or "Request failed")
        details = exc.detail
    elif isinstance(exc.detail, list):
        message = "Request failed"
        details = exc.detail
    else:
        message = str(exc.detail)
        details = None

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": f"HTTP_{exc.status_code}", "message": message, "details": details}},
    )


@app.exception_handler(RequestValidationError)
async def _request_validation_exception_handler(request: Request, exc: RequestValidationError):
    return await default_request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import logging

    logging.getLogger(__name__).exception("Unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _reports_attachment_response(body: bytes | str, *, media_type: str, stem: str, extension: str) -> Response:
    iso = date.today().isoformat()
    base = sanitize_report_filename(f"{stem}-{iso}")
    filename = f"{base}.{extension}"
    blob = body.encode("utf-8") if isinstance(body, str) else body
    disp = (
        'attachment; filename="{fn}"; filename*=UTF-8\'\'{fn_star}'
    ).format(fn=filename, fn_star=quote(filename, safe=""))
    return Response(
        content=blob,
        media_type=media_type,
        headers={
            "Content-Disposition": disp,
        },
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/health/db")
def health_db(session: Session = Depends(get_session)) -> dict[str, bool | str]:
    try:
        session.exec(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database connection failed") from exc

    return {"ok": True, "database": "connected"}


@app.get("/health/auth-schema")
def health_auth_schema(session: Session = Depends(get_session)) -> dict[str, object]:
    """Public check: login requires auth session tables (P43+ migrations)."""
    required = ("user_auth_sessions", "user_auth_session_events", "organization_security_contexts")
    try:
        rows = session.exec(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('user_auth_sessions', 'user_auth_session_events', 'organization_security_contexts')
                """
            )
        ).all()
        present = {str(row[0]) for row in rows}
        missing = [name for name in required if name not in present]
        alembic_row = session.exec(text("SELECT version_num FROM alembic_version LIMIT 1")).first()
        alembic_version = str(alembic_row[0]) if alembic_row else None
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Auth schema check failed") from exc

    ok = not missing
    return {
        "ok": ok,
        "missing_tables": missing,
        "alembic_version": alembic_version,
        "login_ready": ok,
    }


@app.get("/health/redis")
def health_redis() -> dict[str, bool | str]:
    from redis.exceptions import RedisError

    from app.tasks.queue import get_redis_connection

    try:
        get_redis_connection().ping()
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Redis connection failed") from exc

    return {"ok": True, "redis": "connected"}


@app.get("/health/worker")
def health_worker() -> dict[str, object]:
    from redis.exceptions import RedisError
    from rq import Worker

    from app.tasks.queue import get_redis_connection, get_worker_queue_names

    try:
        connection = get_redis_connection()
        workers = Worker.all(connection=connection)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Worker visibility unavailable") from exc

    return {
        "ok": True,
        "worker_count": len(workers),
        "workers": [worker.name for worker in workers],
        "queues": get_worker_queue_names(),
    }


@app.get("/debug/runtime", response_model=RuntimeDebugResponse, include_in_schema=False)
def debug_runtime(settings: Settings = Depends(get_settings)) -> RuntimeDebugResponse:
    if not settings.debug_runtime:
        raise HTTPException(status_code=404, detail="Not Found")

    return build_runtime_debug_response(settings)


@app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, session: Session = Depends(get_session)) -> User:
    existing_user = session.exec(select(User).where(User.email == payload.email)).first()
    if existing_user is not None:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return user


@app.post("/auth/login", response_model=TokenResponse)
def login(request: Request, payload: UserLogin, session: Session = Depends(get_session)) -> TokenResponse:
    user = session.exec(select(User).where(User.email == payload.email)).first()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    assert user.id is not None
    access_token = create_access_token(subject=str(user.id))
    create_session(
        session,
        user_id=int(user.id),
        raw_token=access_token,
        expires_at=token_expiration_utc(access_token),
        device_label=build_device_label(request.headers.get("user-agent")),
        device_type=detect_device_type(request.headers.get("user-agent")),
        ip_address=request.client.host if request.client is not None else None,
        user_agent=request.headers.get("user-agent"),
    )
    return TokenResponse(access_token=access_token)


@app.get("/auth/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@app.get("/ops/dashboard", response_model=OpsDashboardResponse, include_in_schema=False)
def ops_dashboard(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OpsDashboardResponse:
    ensure_ops_admin_access(current_user, settings)
    return build_ops_dashboard(session, settings)


@app.get(
    "/ops/inventory-intelligence/summary",
    response_model=InventoryIntelligenceSummary,
    include_in_schema=False,
)
def ops_inventory_intelligence_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> InventoryIntelligenceSummary:
    ensure_ops_admin_access(current_user, settings)
    summary, _, _, _ = compute_inventory_intelligence(
        session,
        current_user=None,
        include_signals=False,
    )
    return summary


@app.get(
    "/ops/inventory-intelligence/health",
    response_model=InventoryIntelligenceHealthSummary,
    include_in_schema=False,
)
def ops_inventory_intelligence_health(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> InventoryIntelligenceHealthSummary:
    ensure_ops_admin_access(current_user, settings)
    _, health, _, _ = compute_inventory_intelligence(
        session,
        current_user=None,
        include_signals=False,
    )
    return health


@app.get(
    "/ops/inventory-intelligence/breakdown",
    response_model=InventoryIntelligenceBreakdown,
    include_in_schema=False,
)
def ops_inventory_intelligence_breakdown(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> InventoryIntelligenceBreakdown:
    ensure_ops_admin_access(current_user, settings)
    _, _, breakdown, _ = compute_inventory_intelligence(
        session,
        current_user=None,
        include_signals=False,
    )
    return breakdown


@app.get(
    "/ops/collection-analytics/summary",
    response_model=CollectionAnalyticsSummary,
    include_in_schema=False,
)
def ops_collection_analytics_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionAnalyticsSummary:
    ensure_ops_admin_access(current_user, settings)
    summary_bundle, _ = analyze_collection_summary(
        session,
        projection_user_filter=None,
        intel_user=None,
        as_of_date=as_of,
    )
    return summary_bundle


@app.get(
    "/ops/collection-analytics/publishers",
    response_model=CollectionPublisherAnalyticsResponse,
    include_in_schema=False,
)
def ops_collection_analytics_publishers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionPublisherAnalyticsResponse:
    ensure_ops_admin_access(current_user, settings)
    return analyze_collection_publishers(
        session,
        projection_user_filter=None,
        intel_user=None,
        as_of_date=as_of,
    )


@app.get(
    "/ops/collection-analytics/timeline",
    response_model=CollectionTimelineResponse,
    include_in_schema=False,
)
def ops_collection_analytics_timeline(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionTimelineResponse:
    ensure_ops_admin_access(current_user, settings)
    return analyze_collection_timeline(
        session,
        projection_user_filter=None,
        intel_user=None,
        as_of_date=as_of,
    )


@app.get(
    "/ops/collection-analytics/quality",
    response_model=CollectionQualityAnalyticsResponse,
    include_in_schema=False,
)
def ops_collection_analytics_quality(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionQualityAnalyticsResponse:
    ensure_ops_admin_access(current_user, settings)
    return analyze_collection_quality(
        session,
        projection_user_filter=None,
        intel_user=None,
        as_of_date=as_of,
    )


@app.get(
    "/ops/collection-analytics/composition",
    response_model=CollectionCompositionResponse,
    include_in_schema=False,
)
def ops_collection_analytics_composition(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionCompositionResponse:
    ensure_ops_admin_access(current_user, settings)
    return analyze_collection_composition(
        session,
        projection_user_filter=None,
        intel_user=None,
        as_of_date=as_of,
    )


@app.get(
    "/ops/collection-timeline",
    response_model=CollectionTimelineEventsResponse,
    include_in_schema=False,
)
def ops_collection_timeline_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    event_type: Annotated[
        CollectionTimelineEventType | None,
        Query(description="Filter by deterministic timeline event kind."),
    ] = None,
    publisher: Annotated[str | None, Query(description="Case-insensitive substring match on publisher label.")] = None,
    ownership_state: Annotated[
        CollectionTimelineOwnershipStateFilter | None,
        Query(description="Filter rows to copies whose current normalized ownership matches."),
    ] = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    preorder_only: bool = False,
    in_hand_only: bool = False,
    grouping: Annotated[CollectionTimelineGrouping, Query()] = "none",
    sort: Annotated[CollectionTimelineSort, Query()] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 280,
) -> CollectionTimelineEventsResponse:
    ensure_ops_admin_access(current_user, settings)
    return timeline_events_for_scope(
        session,
        scope_user_id=None,
        event_type_filter=event_type,
        publisher=publisher,
        ownership_filter=ownership_state,
        release_status=release_status,
        start_date=start_date,
        end_date=end_date,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
        inventory_copy_id=None,
        grouping=grouping,
        sort=sort,
        limit=limit,
        return_events=True,
    )


@app.get(
    "/ops/collection-timeline/summary",
    response_model=CollectionTimelineSummary,
    include_in_schema=False,
)
def ops_collection_timeline_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    event_type: Annotated[
        CollectionTimelineEventType | None,
        Query(description="Filter by deterministic timeline event kind."),
    ] = None,
    publisher: Annotated[str | None, Query(description="Case-insensitive substring match on publisher label.")] = None,
    ownership_state: Annotated[
        CollectionTimelineOwnershipStateFilter | None,
        Query(description="Filter rows to copies whose current normalized ownership matches."),
    ] = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    preorder_only: bool = False,
    in_hand_only: bool = False,
) -> CollectionTimelineSummary:
    ensure_ops_admin_access(current_user, settings)
    return timeline_events_for_scope(
        session,
        scope_user_id=None,
        event_type_filter=event_type,
        publisher=publisher,
        ownership_filter=ownership_state,
        release_status=release_status,
        start_date=start_date,
        end_date=end_date,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
        inventory_copy_id=None,
        grouping="none",
        sort="desc",
        limit=1,
        return_events=False,
    ).summary


@app.get(
    "/ops/inventory/{inventory_copy_id}/timeline",
    response_model=CollectionTimelineEventsResponse,
    include_in_schema=False,
)
def ops_inventory_copy_timeline(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    event_type: Annotated[
        CollectionTimelineEventType | None,
        Query(description="Filter by deterministic timeline event kind."),
    ] = None,
    grouping: Annotated[CollectionTimelineGrouping, Query()] = "none",
    sort: Annotated[CollectionTimelineSort, Query()] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 280,
) -> CollectionTimelineEventsResponse:
    ensure_ops_admin_access(current_user, settings)
    row = session.exec(select(InventoryCopy.id).where(InventoryCopy.id == inventory_copy_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    return timeline_events_for_scope(
        session,
        scope_user_id=None,
        event_type_filter=event_type,
        publisher=None,
        ownership_filter=None,
        release_status=None,
        start_date=None,
        end_date=None,
        preorder_only=False,
        in_hand_only=False,
        inventory_copy_id=inventory_copy_id,
        grouping=grouping,
        sort=sort,
        limit=limit,
        return_events=True,
    )


@app.get(
    "/ops/duplicate-ownership",
    response_model=DuplicateOwnershipListRead,
    include_in_schema=False,
)
def ops_list_duplicate_ownership_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    dup_scan_classification: Annotated[
        DuplicateScanClassificationFilter,
        Query(alias="dup_scan_classification"),
    ] = "all",
    classification: Annotated[
        DuplicateOwnershipClassification | None,
        Query(description="Filter groups by deterministic duplicate ownership classification."),
    ] = None,
) -> DuplicateOwnershipListRead:
    ensure_ops_admin_access(current_user, settings)
    return list_duplicate_ownership_ops(
        session,
        dup_scan_classification=dup_scan_classification,
        classification=classification,
    )


@app.get(
    "/ops/duplicate-ownership/{group_key}",
    response_model=DuplicateOwnershipGroupRead,
    include_in_schema=False,
)
def ops_get_duplicate_ownership_route(
    group_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DuplicateOwnershipGroupRead:
    ensure_ops_admin_access(current_user, settings)
    return get_duplicate_ownership_detail_ops(session, group_key=group_key)


@app.get(
    "/ops/run-detection",
    response_model=RunDetectionListRead,
    include_in_schema=False,
)
def ops_list_run_detection_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    series_status: Annotated[
        RunDetectionSeriesStatus | None,
        Query(description="Filter series groups by deterministic run-detection status."),
    ] = None,
) -> RunDetectionListRead:
    ensure_ops_admin_access(current_user, settings)
    return list_run_detection_ops(session, series_status=series_status)


@app.get(
    "/ops/run-detection/{series_key}",
    response_model=RunDetectionSeriesDetailRead,
    include_in_schema=False,
)
def ops_get_run_detection_detail_route(
    series_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RunDetectionSeriesDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return get_run_detection_detail_ops(session, series_key=series_key)


@app.get(
    "/ops/missing-issues",
    response_model=MissingIssueListRead,
    include_in_schema=False,
)
def ops_list_missing_issues_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    classification: Annotated[
        MissingIssueClassification | None,
        Query(description="Filter missing issue rows by deterministic classification."),
    ] = None,
) -> MissingIssueListRead:
    ensure_ops_admin_access(current_user, settings)
    return list_missing_issues_ops(session, classification=classification)


@app.post(
    "/ops/ocr-pipeline/recover",
    response_model=OpsOcrPipelineRecoverResponse,
    include_in_schema=False,
)
def ops_ocr_pipeline_recover_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OpsOcrPipelineRecoverResponse:
    ensure_ops_admin_access(current_user, settings)
    counts = recover_ocr_pipeline(
        session,
        settings=settings,
        actor_user_id=int(current_user.id) if current_user.id is not None else None,
    )
    return OpsOcrPipelineRecoverResponse(**counts)


@app.get(
    "/ops/inventory/duplicates",
    response_model=list[OpsInventoryDuplicateCandidateGroup],
    include_in_schema=False,
)
def get_inventory_duplicate_candidates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    publisher: str | None = None,
    series_title: str | None = None,
    min_count: Annotated[int, Query(ge=2)] = 2,
    review_status: Annotated[
        Literal["pending", "confirmed_duplicate", "not_duplicate"] | None,
        Query(description="Filter duplicate groups by review classification."),
    ] = None,
) -> list[OpsInventoryDuplicateCandidateGroup]:
    ensure_ops_admin_access(current_user, settings)
    return find_duplicate_inventory_candidates(
        session,
        publisher=publisher,
        series_title=series_title,
        min_count=min_count,
        review_status=review_status,
    )


@app.post(
    "/ops/inventory/duplicates/review",
    response_model=DuplicateCandidateReviewRead,
    include_in_schema=False,
)
def post_inventory_duplicate_review_decision(
    payload: DuplicateCandidateReviewCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DuplicateCandidateReviewRead:
    ensure_ops_admin_access(current_user, settings)
    dumped = payload.model_dump(exclude_unset=True)
    notes_provided = "notes" in dumped
    record = upsert_mark_duplicate_review(
        session,
        metadata_identity_key=payload.metadata_identity_key,
        review_status=payload.review_status,
        notes=payload.notes,
        notes_provided=notes_provided,
        reviewed_by_user=current_user,
    )
    return serialize_duplicate_candidate_review_read(session, record)


@app.patch(
    "/ops/inventory/duplicates/review/notes",
    response_model=DuplicateCandidateReviewRead,
    include_in_schema=False,
)
def patch_inventory_duplicate_review_notes_endpoint(
    payload: DuplicateCandidateNotesUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DuplicateCandidateReviewRead:
    ensure_ops_admin_access(current_user, settings)
    record = upsert_duplicate_review_notes(
        session,
        metadata_identity_key=payload.metadata_identity_key,
        notes=payload.notes,
        reviewer=current_user,
    )
    return serialize_duplicate_candidate_review_read(session, record)


@app.get(
    "/ops/canonical-creators",
    response_model=list[OpsCanonicalCreatorRow],
    include_in_schema=False,
)
def get_canonical_creators_registry(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    name: str | None = None,
    canonical_name: str | None = None,
    normalized_name: str | None = None,
    creator_key: str | None = None,
) -> list[OpsCanonicalCreatorRow]:
    ensure_ops_admin_access(current_user, settings)
    return list_canonical_creators_registry(
        session,
        name=name,
        canonical_name=canonical_name,
        normalized_name=normalized_name,
        creator_key=creator_key,
    )


@app.get(
    "/ops/canonical-series",
    response_model=list[OpsCanonicalSeriesRow],
    include_in_schema=False,
)
def get_canonical_series_registry(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    publisher: str | None = None,
    title: str | None = None,
    earliest_release_year_min: Annotated[int | None, Query(ge=1800, le=2999)] = None,
    earliest_release_year_max: Annotated[int | None, Query(ge=1800, le=2999)] = None,
    latest_release_year_min: Annotated[int | None, Query(ge=1800, le=2999)] = None,
    latest_release_year_max: Annotated[int | None, Query(ge=1800, le=2999)] = None,
) -> list[OpsCanonicalSeriesRow]:
    ensure_ops_admin_access(current_user, settings)
    return list_canonical_series_registry(
        session,
        publisher=publisher,
        title=title,
        earliest_release_year_min=earliest_release_year_min,
        earliest_release_year_max=earliest_release_year_max,
        latest_release_year_min=latest_release_year_min,
        latest_release_year_max=latest_release_year_max,
    )


@app.get("/ops/metadata-aliases", response_model=list[MetadataAliasRead], include_in_schema=False)
def get_metadata_aliases(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    alias_type: MetadataAliasType | None = None,
    is_active: bool | None = None,
) -> list[MetadataAliasRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_metadata_aliases(session, alias_type=alias_type, is_active=is_active)


@app.post(
    "/ops/metadata-aliases",
    response_model=MetadataAliasRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def post_metadata_alias(
    payload: MetadataAliasCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MetadataAliasRead:
    ensure_ops_admin_access(current_user, settings)
    return create_metadata_alias(session, payload=payload, actor_user_id=current_user.id)


@app.patch(
    "/ops/metadata-aliases/{alias_id}",
    response_model=MetadataAliasRead,
    include_in_schema=False,
)
def patch_metadata_alias(
    alias_id: int,
    payload: MetadataAliasUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MetadataAliasRead:
    ensure_ops_admin_access(current_user, settings)
    return update_metadata_alias(
        session,
        alias_id=alias_id,
        payload=payload,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/metadata-aliases/{alias_id}/deactivate",
    response_model=MetadataAliasRead,
    include_in_schema=False,
)
def post_deactivate_metadata_alias(
    alias_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MetadataAliasRead:
    ensure_ops_admin_access(current_user, settings)
    return deactivate_metadata_alias(session, alias_id=alias_id, actor_user_id=current_user.id)


@app.get(
    "/ops/metadata-audits",
    response_model=list[OpsMetadataAuditRow],
    include_in_schema=False,
)
def get_metadata_audits(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    entity_type: str | None = None,
    action: str | None = None,
) -> list[OpsMetadataAuditRow]:
    ensure_ops_admin_access(current_user, settings)
    return list_recent_metadata_audits(
        session,
        limit=limit,
        entity_type=entity_type,
        action=action,
    )


@app.get(
    "/ops/cover-images/recent",
    response_model=list[OpsCoverImageRecentRow],
    include_in_schema=False,
)
def get_ops_recent_cover_images(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    source_type: str | None = Query(None),
    linkage: Literal["inventory", "import"] | None = Query(None),
    matching_status: Literal["not_ready", "ready", "needs_review", "failed"] | None = Query(None),
) -> list[OpsCoverImageRecentRow]:
    ensure_ops_admin_access(current_user, settings)
    return list_recent_cover_uploads_for_ops(
        session,
        limit=limit,
        source_type=source_type,
        linkage=linkage,
        matching_status=matching_status,
    )


@app.get(
    "/ops/cover-images/duplicates",
    response_model=list[OpsCoverDuplicateGroup],
    include_in_schema=False,
)
def get_ops_cover_image_duplicates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    min_count: Annotated[int, Query(ge=2, le=500)] = 2,
    source_type: str | None = Query(None),
    linkage: Literal["inventory", "import", "unlinked"] | None = Query(None),
) -> list[OpsCoverDuplicateGroup]:
    ensure_ops_admin_access(current_user, settings)
    return list_duplicate_cover_image_groups_for_ops(
        session,
        min_count=min_count,
        limit=limit,
        source_type=source_type,
        linkage=linkage,
    )


@app.post(
    "/ops/imports/{import_id}/re-enrich",
    response_model=OpsMetadataReenrichmentEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def post_reenrich_import(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    reason: str | None = None,
) -> OpsMetadataReenrichmentEnqueueResponse:
    ensure_ops_admin_access(current_user, settings)
    return enqueue_metadata_reenrichment_for_draft_import(
        session,
        current_user=current_user,
        import_id=import_id,
        reason=reason,
    )


@app.post(
    "/ops/inventory/{inventory_copy_id}/re-enrich",
    response_model=OpsMetadataReenrichmentEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def post_reenrich_inventory_copy(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    reason: str | None = None,
) -> OpsMetadataReenrichmentEnqueueResponse:
    ensure_ops_admin_access(current_user, settings)
    return enqueue_metadata_reenrichment_for_inventory_copy(
        session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
        reason=reason,
    )


@app.get("/gmail/connect/start", response_model=GmailConnectStartResponse)
def gmail_connect_start(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> GmailConnectStartResponse:
    try:
        authorization_url = build_gmail_connect_authorization_url(
            current_user,
            redirect_origin=request.headers.get("origin"),
            redirect_path="/settings/integrations",
        )
    except GmailIntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return GmailConnectStartResponse(authorization_url=authorization_url)


@app.get("/gmail/connect/callback")
def gmail_connect_callback(
    code: str,
    state: str,
    session: Session = Depends(get_session),
):
    state_payload = decode_gmail_connect_state(state)
    user = session.get(User, state_payload["user_id"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        connect_gmail_account_for_user(session=session, current_user=user, code=code)
    except GmailIntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GmailIntegrationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    redirect_origin = state_payload.get("redirect_origin") or "http://127.0.0.1:5173"
    redirect_path = state_payload.get("redirect_path") or "/settings/integrations"
    redirect_url = f"{redirect_origin.rstrip('/')}{redirect_path}?gmail=connected"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)


@app.get("/gmail/status", response_model=GmailStatusResponse)
def gmail_status(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailStatusResponse:
    return get_gmail_status_for_user(session=session, current_user=current_user)


@app.post("/gmail/disconnect", response_model=GmailDisconnectResponse)
def gmail_disconnect(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailDisconnectResponse:
    disconnect_gmail_for_user(session=session, current_user=current_user)
    return GmailDisconnectResponse(disconnected=True)


@app.get("/gmail/sync/status", response_model=GmailSyncStatusResponse)
def gmail_sync_status_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailSyncStatusResponse:
    return get_gmail_sync_status_for_user(session=session, current_user=current_user)


@app.patch("/gmail/sync/settings", response_model=GmailSyncStatusResponse)
def gmail_sync_settings(
    payload: GmailSyncSettingsUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GmailSyncStatusResponse:
    try:
        return update_gmail_sync_settings_for_user(
            session=session,
            current_user=current_user,
            auto_sync_enabled=payload.auto_sync_enabled,
        )
    except GmailNotConnectedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/gmail/imports", response_model=list[GmailImportedDraftRead])
def gmail_imports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[GmailImportedDraftRead]:
    return serialize_gmail_import_drafts(
        session=session,
        current_user=current_user,
        limit=limit,
    )


@app.post(
    "/gmail/sync",
    response_model=GmailSyncEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def gmail_sync(current_user: User = Depends(get_current_user)) -> GmailSyncEnqueueResponse:
    try:
        return enqueue_gmail_sync_job_for_user(current_user=current_user)
    except GmailIntegrationNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GmailNotConnectedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/gmail/sync/{job_id}", response_model=ImportParseJobStatusResponse)
def gmail_sync_status(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImportParseJobStatusResponse:
    return get_gmail_sync_job_status_for_user(
        session=session,
        current_user=current_user,
        job_id=job_id,
    )


@app.post("/ai/parse-order", response_model=ParseOrderResponse)
def parse_order(
    payload: ParseOrderRequest,
    current_user: User = Depends(get_current_user),
) -> ParseOrderResponse:
    del current_user
    try:
        return parse_order_draft_from_text(payload.raw_text)
    except AiOrderParserNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AiOrderParserError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/imports", response_model=DraftImportListResponse)
def get_imports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status: DraftImportStatus | None = None,
    search: str | None = None,
    needs_metadata_review: bool | None = None,
    needs_release_date_review: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "desc",
) -> DraftImportListResponse:
    return list_imports_for_user(
        session=session,
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
        search=search,
        needs_metadata_review=needs_metadata_review,
        needs_release_date_review=needs_release_date_review,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.post("/imports", response_model=DraftImportRead, status_code=status.HTTP_201_CREATED)
def create_import(
    payload: DraftImportCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    try:
        return create_import_for_user(session=session, current_user=current_user, payload=payload)
    except AiOrderParserNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AiOrderParserError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/imports/manual", response_model=DraftImportRead, status_code=status.HTTP_201_CREATED)
def create_manual_import(
    payload: ManualDraftImportCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return create_manual_import_for_user(
        session=session,
        current_user=current_user,
        payload=payload,
    )


@app.post(
    "/imports/parse-jobs",
    response_model=ImportParseJobEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_import_parse_job(
    payload: DraftImportCreate,
    current_user: User = Depends(get_current_user),
) -> ImportParseJobEnqueueResponse:
    try:
        return enqueue_import_parse_job_for_user(current_user=current_user, payload=payload)
    except AiOrderParserNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/imports/parse-jobs/{job_id}", response_model=ImportParseJobStatusResponse)
def get_import_parse_job_status(
    job_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ImportParseJobStatusResponse:
    return get_import_parse_job_status_for_user(
        session=session,
        current_user=current_user,
        job_id=job_id,
    )


@app.get("/imports/{import_id}", response_model=DraftImportRead)
def get_import(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return get_import_for_user(session=session, current_user=current_user, import_id=import_id)


@app.patch("/imports/{import_id}", response_model=DraftImportRead)
def patch_import(
    import_id: int,
    payload: DraftImportUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return update_import_for_user(
        session=session,
        current_user=current_user,
        import_id=import_id,
        payload=payload,
    )


@app.post("/imports/{import_id}/confirm", response_model=DraftImportConfirmResponse)
def confirm_import(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportConfirmResponse:
    return confirm_import_for_user(session=session, current_user=current_user, import_id=import_id)


@app.post("/imports/{import_id}/discard", response_model=DraftImportRead)
def discard_import(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DraftImportRead:
    return discard_import_for_user(session=session, current_user=current_user, import_id=import_id)


COVER_IMAGE_SOURCE_TYPES = frozenset({"upload", "gmail_attachment", "import_image"})


def validated_cover_source_type(source_type: str) -> str:
    if source_type not in COVER_IMAGE_SOURCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail="source_type must be one of upload, gmail_attachment, import_image",
        )
    return source_type


@app.post("/inventory/{inventory_copy_id}/cover-images", response_model=CoverImageRead)
async def upload_inventory_cover_image(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file: UploadFile = File(...),
    source_type: Annotated[str, Form()] = "upload",
) -> CoverImageRead:
    validated = validated_cover_source_type(source_type)
    return await persist_cover_upload(
        session,
        settings=settings,
        file=file,
        inventory_copy_id=inventory_copy_id,
        draft_import_id=None,
        source_type=validated,
        current_user=current_user,
    )


@app.post("/imports/{import_id}/cover-images", response_model=CoverImageRead)
async def upload_import_cover_image(
    import_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file: UploadFile = File(...),
    source_type: Annotated[str, Form()] = "import_image",
) -> CoverImageRead:
    validated = validated_cover_source_type(source_type)
    return await persist_cover_upload(
        session,
        settings=settings,
        file=file,
        inventory_copy_id=None,
        draft_import_id=import_id,
        source_type=validated,
        current_user=current_user,
    )


@app.post(
    "/inventory/{inventory_copy_id}/cover-images/{cover_image_id}/primary",
    response_model=CoverImageRead,
)
def set_inventory_cover_image_primary(
    inventory_copy_id: int,
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageRead:
    return set_inventory_primary_cover_image(
        session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/imports/{import_id}/cover-images/{cover_image_id}/primary",
    response_model=CoverImageRead,
)
def set_import_cover_image_primary(
    import_id: int,
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageRead:
    return set_draft_import_primary_cover_image(
        session,
        current_user=current_user,
        draft_import_id=import_id,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/inventory/{inventory_copy_id}/cover-images/assign-existing",
    response_model=CoverImageRead,
)
def assign_inventory_cover_existing(
    inventory_copy_id: int,
    payload: CoverImageAssignExistingPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageRead:
    return assign_existing_cover_image_to_inventory_copy(
        session,
        settings=settings,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
        cover_image_id=payload.cover_image_id,
        set_primary=payload.set_primary,
    )


@app.post("/cover-images/{cover_image_id}/return-to-draft-import", response_model=CoverImageRead)
def return_cover_image_to_import_draft_route(
    cover_image_id: int,
    payload: CoverImageReturnToDraftPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageRead:
    return return_cover_image_to_draft_import(
        session,
        settings=settings,
        current_user=current_user,
        cover_image_id=cover_image_id,
        draft_import_id=payload.draft_import_id,
        set_primary=payload.set_primary,
    )


@app.post(
    "/cover-images/{cover_image_id}/process",
    response_model=CoverImageProcessingEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_cover_image_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageProcessingEnqueueResponse:
    return enqueue_cover_image_processing_for_user(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/cover-images/{cover_image_id}/run-ocr",
    response_model=CoverImageOcrEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_cover_image_ocr_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrEnqueueResponse:
    return enqueue_cover_image_ocr_for_user(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/cover-images/{cover_image_id}/retry-ocr",
    response_model=CoverImageOcrEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_cover_image_ocr_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrEnqueueResponse:
    """Alias of ``run-ocr`` for operational clarity; preserves OCR history rows."""
    return enqueue_cover_image_ocr_for_user(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.get(
    "/cover-images/{cover_image_id}/ocr-results",
    response_model=list[CoverImageOcrResultRead],
)
def get_cover_image_ocr_results_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageOcrResultRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_ocr_result_reads_for_cover(session, cover_image_id)


@app.get(
    "/cover-images/{cover_image_id}/ocr-candidates",
    response_model=list[CoverImageOcrCandidateRead],
)
def get_cover_image_ocr_candidates_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageOcrCandidateRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_ocr_candidate_reads_for_cover(session, cover_image_id)


@app.get(
    "/cover-images/{cover_image_id}/ocr-regions",
    response_model=list[CoverImageOcrRegionRead],
)
def get_cover_image_ocr_regions_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageOcrRegionRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_ocr_region_reads_for_cover(session, cover_image_id)


@app.post(
    "/cover-images/{cover_image_id}/extract-ocr-candidates",
    response_model=CoverImageOcrCandidateExtractResponse,
    status_code=status.HTTP_200_OK,
)
def extract_cover_image_ocr_candidates_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrCandidateExtractResponse:
    return extract_cover_image_ocr_candidates_for_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/ocr-candidates/{ocr_candidate_id}/approve",
    response_model=CoverImageOcrCandidateRead,
    status_code=status.HTTP_200_OK,
)
def approve_ocr_candidate_for_owner(
    ocr_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrCandidateRead:
    return approve_cover_image_ocr_candidate_for_owner(
        session,
        current_user=current_user,
        ocr_candidate_id=ocr_candidate_id,
    )


@app.post(
    "/ocr-candidates/{ocr_candidate_id}/reject",
    response_model=CoverImageOcrCandidateRead,
    status_code=status.HTTP_200_OK,
)
def reject_ocr_candidate_for_owner(
    ocr_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrCandidateRead:
    return reject_cover_image_ocr_candidate_for_owner(
        session,
        current_user=current_user,
        ocr_candidate_id=ocr_candidate_id,
    )


@app.patch(
    "/ocr-candidates/{ocr_candidate_id}/review-notes",
    response_model=CoverImageOcrCandidateRead,
    status_code=status.HTTP_200_OK,
)
def patch_ocr_candidate_review_notes_owner(
    ocr_candidate_id: int,
    payload: CoverImageOcrCandidateReviewNotesPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrCandidateRead:
    return patch_cover_image_ocr_candidate_review_notes_for_owner(
        session,
        current_user=current_user,
        ocr_candidate_id=ocr_candidate_id,
        review_notes=payload.review_notes,
    )


@app.get(
    "/cover-images/{cover_image_id}/barcode-candidates",
    response_model=list[CoverImageBarcodeCandidateRead],
)
def get_cover_image_barcode_candidates_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageBarcodeCandidateRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_barcode_candidate_reads_for_cover(session, cover_image_id)


@app.post(
    "/cover-images/{cover_image_id}/extract-barcodes",
    response_model=CoverImageBarcodeCandidateExtractResponse,
    status_code=status.HTTP_200_OK,
)
def extract_cover_image_barcode_candidates_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageBarcodeCandidateExtractResponse:
    return extract_cover_image_barcode_candidates_for_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.patch(
    "/barcode-candidates/{barcode_candidate_id}/approve",
    response_model=CoverImageBarcodeCandidateRead,
    status_code=status.HTTP_200_OK,
)
def approve_barcode_candidate_for_owner(
    barcode_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageBarcodeCandidateRead:
    return approve_cover_image_barcode_candidate_for_owner(
        session,
        current_user=current_user,
        barcode_candidate_id=barcode_candidate_id,
    )


@app.patch(
    "/barcode-candidates/{barcode_candidate_id}/reject",
    response_model=CoverImageBarcodeCandidateRead,
    status_code=status.HTTP_200_OK,
)
def reject_barcode_candidate_for_owner(
    barcode_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageBarcodeCandidateRead:
    return reject_cover_image_barcode_candidate_for_owner(
        session,
        current_user=current_user,
        barcode_candidate_id=barcode_candidate_id,
    )


@app.get(
    "/cover-images/{cover_image_id}/fingerprints",
    response_model=list[CoverImageFingerprintRead],
)
def get_cover_image_fingerprints_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageFingerprintRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_fingerprint_reads_for_cover(session, cover_image_id)


@app.post(
    "/cover-images/{cover_image_id}/generate-fingerprints",
    response_model=CoverImageFingerprintGenerateResponse,
    status_code=status.HTTP_200_OK,
)
def generate_cover_image_fingerprints_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageFingerprintGenerateResponse:
    return generate_cover_image_fingerprints_for_owner(
        session,
        settings=settings,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.get(
    "/cover-images/{cover_image_id}/ocr-quality-analysis",
    response_model=list[CoverImageOcrQualityAnalysisRead],
)
def get_cover_image_ocr_quality_analysis_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageOcrQualityAnalysisRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_ocr_quality_analysis_reads_for_cover(session, cover_image_id)


@app.post(
    "/cover-images/{cover_image_id}/analyze-ocr-quality",
    response_model=CoverImageOcrQualityAnalysisResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_cover_image_ocr_quality_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrQualityAnalysisResponse:
    return analyze_cover_image_ocr_quality_for_owner(
        session,
        settings=settings,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.get(
    "/cover-images/{cover_image_id}/match-candidates",
    response_model=list[CoverImageMatchCandidateRead],
)
def get_cover_image_match_candidates_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageMatchCandidateRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_match_candidate_reads_for_cover(session, cover_image_id)


@app.get(
    "/cover-images/{cover_image_id}/relationship-graph",
    response_model=CoverRelationshipGraphRead,
)
def get_cover_image_relationship_graph_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipGraphRead:
    return get_cover_relationship_graph_for_owner(
        session,
        center_cover_image_id=cover_image_id,
        current_user=current_user,
    )


@app.get(
    "/cover-images/{cover_image_id}/duplicate-scan-candidates",
    response_model=DuplicateScanCandidatesResponse,
)


def get_cover_image_duplicate_scan_candidates_owner(
    cover_image_id: int,

    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),

) -> DuplicateScanCandidatesResponse:


    return duplicate_scan_candidates_for_cover_owner(
        session,

        cover_image_id=cover_image_id,
        current_user=current_user,
    )



@app.get("/duplicate-scan-clusters", response_model=DuplicateScanClustersListResponse)


def list_duplicate_scan_clusters_owner_endpoint(
    classification_filter: Annotated[
        DuplicateScanClassificationFilter,
        Query(alias="classification_filter"),
    ] = "all",

    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DuplicateScanClustersListResponse:
    return list_duplicate_scan_clusters_for_owner(
        session,
        current_user=current_user,
        classification_filter=classification_filter,
    )


@app.get(
    "/cover-images/{cover_image_id}/variant-family-candidates",
    response_model=VariantFamilyCandidatesResponse,
)
def get_cover_image_variant_family_candidates_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> VariantFamilyCandidatesResponse:
    return variant_family_candidates_for_cover_owner(
        session,
        cover_image_id=cover_image_id,
        current_user=current_user,
    )


@app.get("/variant-family-clusters", response_model=VariantFamilyClustersListResponse)
def list_variant_family_clusters_owner_endpoint(
    classification_filter: Annotated[
        VariantFamilyClassificationFilter,
        Query(alias="classification_filter"),
    ] = "all",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> VariantFamilyClustersListResponse:
    return list_variant_family_clusters_for_owner(
        session,
        current_user=current_user,
        classification_filter=classification_filter,
    )


@app.post(
    "/cover-images/{cover_image_id}/generate-canonical-issue-suggestions",
    response_model=CanonicalIssueSuggestionGenerateResponse,
    status_code=status.HTTP_200_OK,
)
def generate_canonical_issue_suggestions_owner_endpoint(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CanonicalIssueSuggestionGenerateResponse:
    return generate_canonical_issue_suggestions_for_owner(
        session,
        cover_image_id=cover_image_id,
        current_user=current_user,
    )


@app.get(
    "/cover-images/{cover_image_id}/canonical-issue-suggestions",
    response_model=list[CanonicalIssueLinkSuggestionRead],
)
def list_canonical_issue_suggestions_owner_endpoint(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CanonicalIssueLinkSuggestionRead]:
    return list_canonical_issue_suggestions_for_cover_owner(
        session,
        cover_image_id=cover_image_id,
        current_user=current_user,
    )


@app.patch(
    "/canonical-issue-suggestions/{suggestion_id}/approve",
    response_model=CanonicalIssueSuggestionReviewActionResponse,
)
def approve_canonical_issue_suggestion_owner_endpoint(
    suggestion_id: int,
    payload: CanonicalIssueSuggestionReviewPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CanonicalIssueSuggestionReviewActionResponse:
    return approve_canonical_issue_suggestion_for_owner(
        session,
        suggestion_id=suggestion_id,
        current_user=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/canonical-issue-suggestions/{suggestion_id}/reject",
    response_model=CanonicalIssueSuggestionReviewActionResponse,
)
def reject_canonical_issue_suggestion_owner_endpoint(
    suggestion_id: int,
    payload: CanonicalIssueSuggestionReviewPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CanonicalIssueSuggestionReviewActionResponse:
    return reject_canonical_issue_suggestion_for_owner(
        session,
        suggestion_id=suggestion_id,
        current_user=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/canonical-issue-suggestions/{suggestion_id}/ignore",
    response_model=CanonicalIssueSuggestionReviewActionResponse,
)
def ignore_canonical_issue_suggestion_owner_endpoint(
    suggestion_id: int,
    payload: CanonicalIssueSuggestionReviewPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CanonicalIssueSuggestionReviewActionResponse:
    return ignore_canonical_issue_suggestion_for_owner(
        session,
        suggestion_id=suggestion_id,
        current_user=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.post(
    "/relationship-conflicts/detect",
    response_model=CoverRelationshipConflictDetectResponse,
    status_code=status.HTTP_200_OK,
)
def detect_relationship_conflicts_owner_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipConflictDetectResponse:
    return detect_relationship_conflicts_for_owner(session, current_user=current_user)


@app.get(
    "/relationship-conflicts",
    response_model=CoverRelationshipConflictListResponse,
)
def list_relationship_conflicts_owner_endpoint(
    severity: RelationshipConflictSeverity | Literal["all"] = "all",
    status: RelationshipConflictStatus | Literal["all"] = "all",
    conflict_type: RelationshipConflictType | Literal["all"] = "all",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipConflictListResponse:
    return list_relationship_conflicts_for_owner(
        session,
        current_user=current_user,
        severity=severity,
        status=status,
        conflict_type=conflict_type,
    )


@app.get(
    "/cover-images/{cover_image_id}/relationship-conflicts",
    response_model=CoverRelationshipConflictListResponse,
)
def list_relationship_conflicts_for_cover_owner_endpoint(
    cover_image_id: int,
    severity: RelationshipConflictSeverity | Literal["all"] = "all",
    status: RelationshipConflictStatus | Literal["all"] = "all",
    conflict_type: RelationshipConflictType | Literal["all"] = "all",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipConflictListResponse:
    return list_relationship_conflicts_for_cover_owner(
        session,
        cover_image_id=cover_image_id,
        current_user=current_user,
        severity=severity,
        status=status,
        conflict_type=conflict_type,
    )


@app.patch(
    "/relationship-conflicts/{conflict_id}/acknowledge",
    response_model=CoverRelationshipConflictActionResponse,
)
def acknowledge_relationship_conflict_owner_endpoint(
    conflict_id: int,
    payload: CoverRelationshipConflictStatusPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipConflictActionResponse:
    return acknowledge_relationship_conflict_for_owner(
        session,
        conflict_id=conflict_id,
        current_user=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/relationship-conflicts/{conflict_id}/dismiss",
    response_model=CoverRelationshipConflictActionResponse,
)
def dismiss_relationship_conflict_owner_endpoint(
    conflict_id: int,
    payload: CoverRelationshipConflictStatusPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipConflictActionResponse:
    return dismiss_relationship_conflict_for_owner(
        session,
        conflict_id=conflict_id,
        current_user=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/relationship-conflicts/{conflict_id}/resolve",
    response_model=CoverRelationshipConflictActionResponse,
)
def resolve_relationship_conflict_owner_endpoint(
    conflict_id: int,
    payload: CoverRelationshipConflictStatusPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipConflictActionResponse:
    return resolve_relationship_conflict_for_owner(
        session,
        conflict_id=conflict_id,
        current_user=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.get("/match-groups/{grouping_key}", response_model=CoverImageMatchGroupRead)
def get_match_group_for_owner(
    grouping_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageMatchGroupRead:
    return get_cover_match_group_for_owner(
        session,
        current_user=current_user,
        grouping_key=grouping_key,
    )


@app.get(
    "/cover-relationship-graph",
    response_model=CoverRelationshipGraphRead,
)
def get_cover_relationship_graph_query_owner(
    cover_image_id: Annotated[
        int,
        Query(ge=1, description="Focal cover for the human-decision subgraph."),
    ],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverRelationshipGraphRead:
    return get_cover_relationship_graph_for_owner(
        session,
        center_cover_image_id=cover_image_id,
        current_user=current_user,
    )


@app.post(
    "/cover-images/{cover_image_id}/generate-match-candidates",
    response_model=CoverImageMatchCandidateGenerateResponse,
    status_code=status.HTTP_200_OK,
)
def generate_cover_image_match_candidates_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageMatchCandidateGenerateResponse:
    return generate_cover_image_match_candidates_for_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/cover-images/{cover_image_id}/regenerate-match-confidence",
    response_model=CoverImageMatchCandidateGenerateResponse,
    status_code=status.HTTP_200_OK,
)
def regenerate_cover_image_match_confidence_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageMatchCandidateGenerateResponse:
    return generate_cover_image_match_candidates_for_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.patch(
    "/match-candidates/{match_candidate_id}/acknowledge",
    response_model=CoverImageMatchCandidateRead,
    status_code=status.HTTP_200_OK,
)
def acknowledge_cover_match_candidate_owner(
    match_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageMatchCandidateRead:
    return acknowledge_cover_match_candidate_for_owner(
        session,
        current_user=current_user,
        match_candidate_id=match_candidate_id,
    )


@app.patch(
    "/match-candidates/{match_candidate_id}/dismiss",
    response_model=CoverImageMatchCandidateRead,
    status_code=status.HTTP_200_OK,
)
def dismiss_cover_match_candidate_owner(
    match_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageMatchCandidateRead:
    return dismiss_cover_match_candidate_for_owner(
        session,
        current_user=current_user,
        match_candidate_id=match_candidate_id,
    )


@app.post(
    "/cover-link-decisions",
    response_model=CoverImageLinkDecisionRead,
    status_code=status.HTTP_200_OK,
)
def create_cover_link_decision_owner(
    payload: CoverImageLinkDecisionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageLinkDecisionRead:
    return create_cover_link_decision_for_owner(
        session,
        payload=payload,
        current_user=current_user,
    )


@app.get(
    "/cover-link-decisions",
    response_model=list[CoverImageLinkDecisionRead],
)
def list_cover_link_decisions_owner(
    cover_image_id: int | None = None,
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageLinkDecisionRead]:
    return list_cover_link_decisions_for_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
        include_inactive=include_inactive,
        limit=limit,
    )


@app.get(
    "/cover-link-decisions/recent",
    response_model=list[CoverImageLinkDecisionRead],
)
def list_recent_cover_link_decisions_owner(
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageLinkDecisionRead]:
    return list_cover_link_decisions_for_owner(
        session,
        current_user=current_user,
        cover_image_id=None,
        include_inactive=include_inactive,
        limit=limit,
    )


@app.get(
    "/cover-link-decisions/{decision_id}",
    response_model=CoverImageLinkDecisionRead,
)
def get_cover_link_decision_owner(
    decision_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageLinkDecisionRead:
    return get_cover_link_decision_for_owner(
        session,
        decision_id=decision_id,
        current_user=current_user,
    )


@app.post(
    "/cover-link-decisions/{decision_id}/revert",
    response_model=CoverImageLinkDecisionRead,
    status_code=status.HTTP_200_OK,
)
def revert_cover_link_decision_owner(
    decision_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageLinkDecisionRead:
    return revert_cover_link_decision_for_owner(
        session,
        decision_id=decision_id,
        current_user=current_user,
    )


@app.post(
    "/cover-images/{cover_image_id}/reconcile-ocr-metadata",
    response_model=CoverImageOcrReconciliationResponse,
    status_code=status.HTTP_200_OK,
)
def reconcile_cover_image_ocr_metadata_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrReconciliationResponse:
    return reconcile_cover_image_ocr_metadata_for_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.get(
    "/cover-images/{cover_image_id}/ocr-reconciliation-warnings",
    response_model=list[CoverImageOcrReconciliationWarningRead],
)
def get_cover_image_ocr_reconciliation_warnings_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[CoverImageOcrReconciliationWarningRead]:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    return list_cover_image_ocr_reconciliation_warnings(session, cover_image_id=cover_image_id)


@app.patch(
    "/ocr-reconciliation-warnings/{warning_id}/acknowledge",
    response_model=CoverImageOcrReconciliationWarningRead,
    status_code=status.HTTP_200_OK,
)
def acknowledge_ocr_reconciliation_warning_owner(
    warning_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrReconciliationWarningRead:
    return acknowledge_ocr_reconciliation_warning_for_owner(
        session,
        current_user=current_user,
        warning_id=warning_id,
    )


@app.patch(
    "/ocr-reconciliation-warnings/{warning_id}/dismiss",
    response_model=CoverImageOcrReconciliationWarningRead,
    status_code=status.HTTP_200_OK,
)
def dismiss_ocr_reconciliation_warning_owner(
    warning_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrReconciliationWarningRead:
    return dismiss_ocr_reconciliation_warning_for_owner(
        session,
        current_user=current_user,
        warning_id=warning_id,
    )


@app.post(
    "/cover-images/{cover_image_id}/extract-ocr-regions",
    response_model=CoverImageOcrRegionExtractResponse,
    status_code=status.HTTP_200_OK,
)
def extract_cover_image_ocr_regions_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrRegionExtractResponse:
    return extract_cover_image_ocr_regions_for_owner(
        session,
        settings=settings,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/cover-images/{cover_image_id}/replay-ocr",
    response_model=CoverImageOcrEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def replay_cover_image_ocr_for_owner(
    cover_image_id: int,
    payload: CoverImageOcrReplayPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CoverImageOcrEnqueueResponse:
    return enqueue_cover_image_ocr_replay_for_user(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
        replay_reason=payload.replay_reason if payload is not None else None,
    )


@app.post("/ocr-batches", response_model=OcrBatchRead, status_code=status.HTTP_201_CREATED)
def create_ocr_batch_owner(
    payload: OcrBatchCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrBatchRead:
    return create_ocr_batch_for_owner(session, current_user=current_user, payload=payload)


@app.get("/ocr-batches", response_model=list[OcrBatchRead])
def list_ocr_batches_owner(
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[OcrBatchRead]:
    return list_ocr_batches_for_owner(session, current_user=current_user, limit=limit)


@app.get("/ocr-batches/{batch_id}", response_model=OcrBatchRead)
def get_ocr_batch_owner(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrBatchRead:
    return get_ocr_batch_detail_for_owner(session, current_user=current_user, batch_id=batch_id)


@app.post("/ocr-batches/{batch_id}/enqueue", response_model=OcrBatchRead)
def enqueue_ocr_batch_owner(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrBatchRead:
    return enqueue_ocr_batch_for_owner(session, current_user=current_user, batch_id=batch_id)


@app.post("/ocr-batches/{batch_id}/retry-failed", response_model=OcrBatchRead)
def retry_failed_ocr_batch_items_owner(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrBatchRead:
    return retry_failed_ocr_batch_items_for_owner(
        session,
        current_user=current_user,
        batch_id=batch_id,
    )


@app.post("/ocr-batches/{batch_id}/cancel", response_model=OcrBatchRead)
def cancel_ocr_batch_owner(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrBatchRead:
    return cancel_ocr_batch_for_owner(session, current_user=current_user, batch_id=batch_id)


@app.post("/ocr-replays", response_model=OcrReplayRunRead, status_code=status.HTTP_201_CREATED)
def create_ocr_replay_owner(
    payload: OcrReplayCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrReplayRunRead:
    return create_ocr_replay_run_for_owner(
        session,
        settings=settings,
        current_user=current_user,
        payload=payload,
    )


@app.get("/ocr-replays", response_model=list[OcrReplayRunRead])
def list_ocr_replays_owner(
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[OcrReplayRunRead]:
    return list_ocr_replay_runs_for_owner(session, current_user=current_user, limit=limit)


@app.get("/ocr-replays/{replay_id}", response_model=OcrReplayRunRead)
def get_ocr_replay_owner(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrReplayRunRead:
    return get_ocr_replay_run_detail_for_owner(
        session,
        current_user=current_user,
        replay_id=replay_id,
    )


@app.post("/ocr-replays/{replay_id}/start", response_model=OcrReplayRunRead)
def start_ocr_replay_owner(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrReplayRunRead:
    return start_ocr_replay_run_for_owner(
        session,
        settings=settings,
        current_user=current_user,
        replay_id=replay_id,
    )


@app.post("/ocr-replays/{replay_id}/cancel", response_model=OcrReplayRunRead)
def cancel_ocr_replay_owner(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrReplayRunRead:
    return cancel_ocr_replay_run_for_owner(session, current_user=current_user, replay_id=replay_id)


@app.post(
    "/relationship-replays",
    response_model=RelationshipReplayRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship_replay_owner(
    payload: RelationshipReplayCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RelationshipReplayRunRead:
    return create_relationship_replay_run_for_owner(
        session,
        current_user=current_user,
        payload=payload,
    )


@app.get("/relationship-replays", response_model=list[RelationshipReplayRunRead])
def list_relationship_replays_owner(
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[RelationshipReplayRunRead]:
    return list_relationship_replay_runs_for_owner(session, current_user=current_user, limit=limit)


@app.get("/relationship-replays/{replay_id}", response_model=RelationshipReplayRunRead)
def get_relationship_replay_owner(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RelationshipReplayRunRead:
    return get_relationship_replay_run_detail_for_owner(
        session,
        current_user=current_user,
        replay_id=replay_id,
    )


@app.post("/relationship-replays/{replay_id}/start", response_model=RelationshipReplayRunRead)
def start_relationship_replay_owner(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RelationshipReplayRunRead:
    return start_relationship_replay_run_for_owner(
        session,
        current_user=current_user,
        replay_id=replay_id,
    )


@app.post("/relationship-replays/{replay_id}/cancel", response_model=RelationshipReplayRunRead)
def cancel_relationship_replay_owner(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RelationshipReplayRunRead:
    return cancel_relationship_replay_run_for_owner(
        session,
        current_user=current_user,
        replay_id=replay_id,
    )


@app.get("/ocr-review-queue", response_model=OcrReviewQueueResponse)
def get_ocr_review_queue_owner_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    queue_scope: Annotated[
        Literal["attention", "all"],
        Query(description="attention presets pending/open subsets per kind."),
    ] = "attention",
    item_kind: Annotated[list[str] | None, Query(description="repeat for multiple kinds")] = None,
    publisher_id: int | None = None,
    extraction_version: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    confidence_bucket: Literal["high", "medium", "low", "unknown"] | None = None,
    severity: Literal["critical", "warning", "info"] | None = None,
    candidate_type: str | None = None,
    warning_type: str | None = None,
    quality_type: str | None = None,
    ocr_candidate_review_status: Literal["pending", "approved", "rejected"] | None = None,
    reconciliation_warning_status: Literal["open", "acknowledged", "dismissed"] | None = None,
    barcode_review_state: Literal["pending", "approved", "rejected"] | None = None,
    match_review: Literal["pending", "acknowledged", "dismissed"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> OcrReviewQueueResponse:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    filters = build_filters_from_http(
        queue_scope=queue_scope,
        ops_mode=False,
        owner_user_id=current_user.id,
        item_kind=item_kind,
        publisher_id=publisher_id,
        extraction_version=extraction_version,
        created_after=created_after,
        created_before=created_before,
        confidence_bucket=confidence_bucket,
        severity=severity,
        candidate_type=candidate_type,
        warning_type=warning_type,
        quality_type=quality_type,
        ocr_candidate_review_status=ocr_candidate_review_status,
        reconciliation_warning_status=reconciliation_warning_status,
        barcode_review_state=barcode_review_state,
        match_review=match_review,
    )
    return list_ocr_review_queue(session, filters=filters, page=page, page_size=page_size)


@app.get("/ocr-review-summary", response_model=OcrReviewSummaryResponse)
def get_ocr_review_summary_owner_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OcrReviewSummaryResponse:
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return build_ocr_review_summary(session, ops_mode=False, owner_user_id=current_user.id)


@app.post(
    "/ocr-review/bulk/reconciliation-warnings/acknowledge",
    response_model=BulkMutationResult,
)
def bulk_ack_ocr_warnings_owner_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkMutationResult:
    return bulk_ack_warnings_for_owner(session, current_user=current_user, payload=payload)


@app.post(
    "/ocr-review/bulk/reconciliation-warnings/dismiss",
    response_model=BulkMutationResult,
)
def bulk_dismiss_ocr_warnings_owner_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkMutationResult:
    return bulk_dismiss_warnings_for_owner(session, current_user=current_user, payload=payload)


@app.post("/ocr-review/bulk/barcode-candidates/approve", response_model=BulkMutationResult)
def bulk_approve_barcode_candidates_owner_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkMutationResult:
    return bulk_approve_barcodes_for_owner(session, current_user=current_user, payload=payload)


@app.post("/ocr-review/bulk/barcode-candidates/reject", response_model=BulkMutationResult)
def bulk_reject_barcode_candidates_owner_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkMutationResult:
    return bulk_reject_barcodes_for_owner(session, current_user=current_user, payload=payload)


@app.post(
    "/ops/cover-images/{cover_image_id}/process",
    response_model=CoverImageProcessingEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def process_cover_image_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageProcessingEnqueueResponse:
    ensure_ops_admin_access(current_user, settings)
    return enqueue_cover_image_processing_for_ops(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/run-ocr",
    response_model=CoverImageOcrEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def run_cover_image_ocr_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrEnqueueResponse:
    ensure_ops_admin_access(current_user, settings)
    return enqueue_cover_image_ocr_for_ops(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/retry-ocr",
    response_model=CoverImageOcrEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def retry_cover_image_ocr_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrEnqueueResponse:
    """Alias of ``run-ocr`` for operations; preserves OCR history rows."""
    ensure_ops_admin_access(current_user, settings)
    return enqueue_cover_image_ocr_for_ops(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/replay-ocr",
    response_model=CoverImageOcrEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
def replay_cover_image_ocr_for_ops(
    cover_image_id: int,
    payload: CoverImageOcrReplayPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrEnqueueResponse:
    ensure_ops_admin_access(current_user, settings)
    return enqueue_cover_image_ocr_replay_for_ops(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
        replay_reason=payload.replay_reason if payload is not None else None,
    )


@app.post(
    "/ops/ocr-batches",
    response_model=OcrBatchRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_ocr_batch_ops(
    payload: OcrBatchCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrBatchRead:
    ensure_ops_admin_access(current_user, settings)
    return create_ocr_batch_for_ops(session, actor_user_id=current_user.id, payload=payload)


@app.get("/ops/ocr-batches", response_model=list[OcrBatchRead], include_in_schema=False)
def list_ocr_batches_ops(
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[OcrBatchRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_ocr_batches_for_ops(session, limit=limit)


@app.get("/ops/ocr-batches/{batch_id}", response_model=OcrBatchRead, include_in_schema=False)
def get_ocr_batch_ops(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrBatchRead:
    ensure_ops_admin_access(current_user, settings)
    return get_ocr_batch_detail_for_ops(session, batch_id=batch_id)


@app.post(
    "/ops/ocr-batches/{batch_id}/enqueue",
    response_model=OcrBatchRead,
    include_in_schema=False,
)
def enqueue_ocr_batch_ops(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrBatchRead:
    ensure_ops_admin_access(current_user, settings)
    return enqueue_ocr_batch_for_ops(session, batch_id=batch_id, actor_user_id=current_user.id)


@app.post(
    "/ops/ocr-batches/{batch_id}/retry-failed",
    response_model=OcrBatchRead,
    include_in_schema=False,
)
def retry_failed_ocr_batch_items_ops(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrBatchRead:
    ensure_ops_admin_access(current_user, settings)
    return retry_failed_ocr_batch_items_for_ops(
        session,
        batch_id=batch_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/ocr-batches/{batch_id}/cancel",
    response_model=OcrBatchRead,
    include_in_schema=False,
)
def cancel_ocr_batch_ops(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrBatchRead:
    ensure_ops_admin_access(current_user, settings)
    return cancel_ocr_batch_for_ops(session, batch_id=batch_id, actor_user_id=current_user.id)


@app.post(
    "/ops/ocr-replays",
    response_model=OcrReplayRunRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_ocr_replay_ops(
    payload: OcrReplayCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return create_ocr_replay_run_for_ops(
        session,
        settings=settings,
        actor_user_id=current_user.id,
        payload=payload,
    )


@app.get("/ops/ocr-replays", response_model=list[OcrReplayRunRead], include_in_schema=False)
def list_ocr_replays_ops(
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[OcrReplayRunRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_ocr_replay_runs_for_ops(session, limit=limit)


@app.get("/ops/ocr-replays/{replay_id}", response_model=OcrReplayRunRead, include_in_schema=False)
def get_ocr_replay_ops(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return get_ocr_replay_run_detail_for_ops(session, replay_id=replay_id)


@app.post(
    "/ops/ocr-replays/{replay_id}/start",
    response_model=OcrReplayRunRead,
    include_in_schema=False,
)
def start_ocr_replay_ops(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return start_ocr_replay_run_for_ops(
        session,
        settings=settings,
        replay_id=replay_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/ocr-replays/{replay_id}/cancel",
    response_model=OcrReplayRunRead,
    include_in_schema=False,
)
def cancel_ocr_replay_ops(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return cancel_ocr_replay_run_for_ops(
        session,
        replay_id=replay_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/relationship-replays",
    response_model=RelationshipReplayRunRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_relationship_replay_ops(
    payload: RelationshipReplayCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RelationshipReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return create_relationship_replay_run_for_ops(
        session,
        actor_user_id=current_user.id,
        payload=payload,
    )


@app.get(
    "/ops/relationship-replays",
    response_model=list[RelationshipReplayRunRead],
    include_in_schema=False,
)
def list_relationship_replays_ops(
    limit: int = Query(default=25, ge=1, le=100),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[RelationshipReplayRunRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_relationship_replay_runs_for_ops(session, limit=limit)


@app.get(
    "/ops/relationship-replays/{replay_id}",
    response_model=RelationshipReplayRunRead,
    include_in_schema=False,
)
def get_relationship_replay_ops(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RelationshipReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return get_relationship_replay_run_detail_for_ops(session, replay_id=replay_id)


@app.post(
    "/ops/relationship-replays/{replay_id}/start",
    response_model=RelationshipReplayRunRead,
    include_in_schema=False,
)
def start_relationship_replay_ops(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RelationshipReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return start_relationship_replay_run_for_ops(
        session,
        replay_id=replay_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/relationship-replays/{replay_id}/cancel",
    response_model=RelationshipReplayRunRead,
    include_in_schema=False,
)
def cancel_relationship_replay_ops(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> RelationshipReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return cancel_relationship_replay_run_for_ops(
        session,
        replay_id=replay_id,
        actor_user_id=current_user.id,
    )


@app.get("/ops/ocr-review-queue", response_model=OcrReviewQueueResponse, include_in_schema=False)
def get_ocr_review_queue_ops_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    queue_scope: Annotated[
        Literal["attention", "all"],
        Query(description="attention presets pending/open subsets per kind."),
    ] = "attention",
    item_kind: Annotated[list[str] | None, Query(description="repeat for multiple kinds")] = None,
    publisher_id: int | None = None,
    extraction_version: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    confidence_bucket: Literal["high", "medium", "low", "unknown"] | None = None,
    severity: Literal["critical", "warning", "info"] | None = None,
    candidate_type: str | None = None,
    warning_type: str | None = None,
    quality_type: str | None = None,
    ocr_candidate_review_status: Literal["pending", "approved", "rejected"] | None = None,
    reconciliation_warning_status: Literal["open", "acknowledged", "dismissed"] | None = None,
    barcode_review_state: Literal["pending", "approved", "rejected"] | None = None,
    match_review: Literal["pending", "acknowledged", "dismissed"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> OcrReviewQueueResponse:
    ensure_ops_admin_access(current_user, settings)
    filters = build_filters_from_http(
        queue_scope=queue_scope,
        ops_mode=True,
        owner_user_id=None,
        item_kind=item_kind,
        publisher_id=publisher_id,
        extraction_version=extraction_version,
        created_after=created_after,
        created_before=created_before,
        confidence_bucket=confidence_bucket,
        severity=severity,
        candidate_type=candidate_type,
        warning_type=warning_type,
        quality_type=quality_type,
        ocr_candidate_review_status=ocr_candidate_review_status,
        reconciliation_warning_status=reconciliation_warning_status,
        barcode_review_state=barcode_review_state,
        match_review=match_review,
    )
    return list_ocr_review_queue(session, filters=filters, page=page, page_size=page_size)


@app.get(
    "/ops/ocr-review-summary",
    response_model=OcrReviewSummaryResponse,
    include_in_schema=False,
)
def get_ocr_review_summary_ops_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OcrReviewSummaryResponse:
    ensure_ops_admin_access(current_user, settings)
    return build_ocr_review_summary(session, ops_mode=True, owner_user_id=None)


@app.post(
    "/ops/ocr-review/bulk/reconciliation-warnings/acknowledge",
    response_model=BulkMutationResult,
    include_in_schema=False,
)
def bulk_ack_ocr_warnings_ops_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> BulkMutationResult:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return bulk_ack_warnings_for_ops(session, actor_user_id=current_user.id, payload=payload)


@app.post(
    "/ops/ocr-review/bulk/reconciliation-warnings/dismiss",
    response_model=BulkMutationResult,
    include_in_schema=False,
)
def bulk_dismiss_ocr_warnings_ops_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> BulkMutationResult:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return bulk_dismiss_warnings_for_ops(session, actor_user_id=current_user.id, payload=payload)


@app.post(
    "/ops/ocr-review/bulk/barcode-candidates/approve",
    response_model=BulkMutationResult,
    include_in_schema=False,
)
def bulk_approve_barcode_candidates_ops_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> BulkMutationResult:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return bulk_approve_barcodes_for_ops(session, actor_user_id=current_user.id, payload=payload)


@app.post(
    "/ops/ocr-review/bulk/barcode-candidates/reject",
    response_model=BulkMutationResult,
    include_in_schema=False,
)
def bulk_reject_barcode_candidates_ops_route(
    payload: BulkIdsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> BulkMutationResult:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return bulk_reject_barcodes_for_ops(session, actor_user_id=current_user.id, payload=payload)


@app.post(
    "/ops/cover-images/{cover_image_id}/extract-ocr-regions",
    response_model=CoverImageOcrRegionExtractResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def extract_cover_image_ocr_regions_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrRegionExtractResponse:
    ensure_ops_admin_access(current_user, settings)
    return extract_cover_image_ocr_regions_for_ops(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/extract-ocr-candidates",
    response_model=CoverImageOcrCandidateExtractResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def extract_cover_image_ocr_candidates_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrCandidateExtractResponse:
    ensure_ops_admin_access(current_user, settings)
    return extract_cover_image_ocr_candidates_for_ops(
        session,
        cover_image_id=cover_image_id,
    )


@app.post(
    "/ops/ocr-candidates/{ocr_candidate_id}/approve",
    response_model=CoverImageOcrCandidateRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def approve_ocr_candidate_for_ops(
    ocr_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrCandidateRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return approve_cover_image_ocr_candidate_for_ops(
        session,
        ocr_candidate_id=ocr_candidate_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/ocr-candidates/{ocr_candidate_id}/reject",
    response_model=CoverImageOcrCandidateRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def reject_ocr_candidate_for_ops(
    ocr_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrCandidateRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return reject_cover_image_ocr_candidate_for_ops(
        session,
        ocr_candidate_id=ocr_candidate_id,
        actor_user_id=current_user.id,
    )


@app.patch(
    "/ops/ocr-candidates/{ocr_candidate_id}/review-notes",
    response_model=CoverImageOcrCandidateRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def patch_ocr_candidate_review_notes_ops(
    ocr_candidate_id: int,
    payload: CoverImageOcrCandidateReviewNotesPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrCandidateRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return patch_cover_image_ocr_candidate_review_notes_for_ops(
        session,
        ocr_candidate_id=ocr_candidate_id,
        review_notes=payload.review_notes,
        actor_user_id=current_user.id,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/barcode-candidates",
    response_model=list[CoverImageBarcodeCandidateRead],
    include_in_schema=False,
)
def get_cover_image_barcode_candidates_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageBarcodeCandidateRead]:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return list_cover_barcode_candidate_reads_for_cover(session, cover_image_id)


@app.post(
    "/ops/cover-images/{cover_image_id}/extract-barcodes",
    response_model=CoverImageBarcodeCandidateExtractResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def extract_cover_image_barcode_candidates_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageBarcodeCandidateExtractResponse:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return extract_cover_image_barcode_candidates_for_ops(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


@app.patch(
    "/ops/barcode-candidates/{barcode_candidate_id}/approve",
    response_model=CoverImageBarcodeCandidateRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def approve_barcode_candidate_for_ops(
    barcode_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageBarcodeCandidateRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return approve_cover_image_barcode_candidate_for_ops(
        session,
        barcode_candidate_id=barcode_candidate_id,
        actor_user_id=current_user.id,
    )


@app.patch(
    "/ops/barcode-candidates/{barcode_candidate_id}/reject",
    response_model=CoverImageBarcodeCandidateRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def reject_barcode_candidate_for_ops(
    barcode_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageBarcodeCandidateRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return reject_cover_image_barcode_candidate_for_ops(
        session,
        barcode_candidate_id=barcode_candidate_id,
        actor_user_id=current_user.id,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/ocr-results",
    response_model=list[CoverImageOcrResultRead],
    include_in_schema=False,
)
def get_cover_image_ocr_results_for_ops_route(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageOcrResultRead]:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return list_cover_ocr_result_reads_for_cover(session, cover_image_id)


@app.get(
    "/ops/cover-images/{cover_image_id}/ocr-candidates",
    response_model=list[CoverImageOcrCandidateRead],
    include_in_schema=False,
)
def get_cover_image_ocr_candidates_for_ops_route(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageOcrCandidateRead]:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return list_cover_ocr_candidate_reads_for_cover(session, cover_image_id)


@app.get(
    "/ops/cover-images/{cover_image_id}/fingerprints",
    response_model=list[CoverImageFingerprintRead],
    include_in_schema=False,
)
def get_cover_image_fingerprints_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageFingerprintRead]:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return list_cover_fingerprint_reads_for_cover(session, cover_image_id)


@app.post(
    "/ops/cover-images/{cover_image_id}/generate-fingerprints",
    response_model=CoverImageFingerprintGenerateResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def generate_cover_image_fingerprints_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageFingerprintGenerateResponse:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return generate_cover_image_fingerprints_for_ops(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/ocr-quality-analysis",
    response_model=list[CoverImageOcrQualityAnalysisRead],
    include_in_schema=False,
)
def get_cover_image_ocr_quality_analysis_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageOcrQualityAnalysisRead]:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return list_cover_ocr_quality_analysis_reads_for_cover(session, cover_image_id)


@app.post(
    "/ops/cover-images/{cover_image_id}/analyze-ocr-quality",
    response_model=CoverImageOcrQualityAnalysisResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def analyze_cover_image_ocr_quality_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrQualityAnalysisResponse:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return analyze_cover_image_ocr_quality_for_ops(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/match-candidates",
    response_model=list[CoverImageMatchCandidateRead],
    include_in_schema=False,
)
def get_cover_image_match_candidates_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageMatchCandidateRead]:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)


    return list_cover_match_candidate_reads_for_cover(session, cover_image_id)


@app.get(
    "/ops/cover-images/{cover_image_id}/relationship-graph",
    response_model=CoverRelationshipGraphRead,
    include_in_schema=False,
)
def get_cover_image_relationship_graph_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipGraphRead:
    ensure_ops_admin_access(current_user, settings)
    return get_cover_relationship_graph_for_ops(
        session,
        center_cover_image_id=cover_image_id,
    )


@app.get(
    "/ops/cover-relationship-graph",
    response_model=CoverRelationshipGraphRead,
    include_in_schema=False,
)
def get_cover_relationship_graph_query_ops(
    cover_image_id: Annotated[
        int,
        Query(ge=1, description="Focal cover for the human-decision subgraph."),
    ],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipGraphRead:
    ensure_ops_admin_access(current_user, settings)
    return get_cover_relationship_graph_for_ops(
        session,
        center_cover_image_id=cover_image_id,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/duplicate-scan-candidates",
    response_model=DuplicateScanCandidatesResponse,
    include_in_schema=False,
)


def get_cover_image_duplicate_scan_candidates_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DuplicateScanCandidatesResponse:
    ensure_ops_admin_access(current_user, settings)

    return duplicate_scan_candidates_for_ops(session, cover_image_id=cover_image_id)



@app.get(
    "/ops/duplicate-scan-clusters",

    response_model=DuplicateScanClustersListResponse,
    include_in_schema=False,
)



def list_duplicate_scan_clusters_ops_route(
    classification_filter: Annotated[
        DuplicateScanClassificationFilter,
        Query(alias="classification_filter"),

    ] = "all",

    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DuplicateScanClustersListResponse:
    ensure_ops_admin_access(current_user, settings)



    return list_duplicate_scan_clusters_for_ops(
        session,
        classification_filter=classification_filter,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/variant-family-candidates",
    response_model=VariantFamilyCandidatesResponse,
    include_in_schema=False,
)
def get_cover_image_variant_family_candidates_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> VariantFamilyCandidatesResponse:
    ensure_ops_admin_access(current_user, settings)
    return variant_family_candidates_for_ops(session, cover_image_id=cover_image_id)


@app.get(
    "/ops/variant-family-clusters",
    response_model=VariantFamilyClustersListResponse,
    include_in_schema=False,
)
def list_variant_family_clusters_ops_route(
    classification_filter: Annotated[
        VariantFamilyClassificationFilter,
        Query(alias="classification_filter"),
    ] = "all",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> VariantFamilyClustersListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_variant_family_clusters_for_ops(
        session,
        classification_filter=classification_filter,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/generate-canonical-issue-suggestions",
    response_model=CanonicalIssueSuggestionGenerateResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def generate_canonical_issue_suggestions_ops_endpoint(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CanonicalIssueSuggestionGenerateResponse:
    ensure_ops_admin_access(current_user, settings)
    return generate_canonical_issue_suggestions_for_ops(
        session,
        cover_image_id=cover_image_id,
        reviewer=current_user,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/canonical-issue-suggestions",
    response_model=list[CanonicalIssueLinkSuggestionRead],
    include_in_schema=False,
)
def list_canonical_issue_suggestions_ops_endpoint(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CanonicalIssueLinkSuggestionRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_canonical_issue_suggestions_for_cover_ops(session, cover_image_id=cover_image_id)


@app.post(
    "/ops/relationship-conflicts/detect",
    response_model=CoverRelationshipConflictDetectResponse,
    include_in_schema=False,
)
def detect_relationship_conflicts_ops_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipConflictDetectResponse:
    ensure_ops_admin_access(current_user, settings)
    return detect_relationship_conflicts_for_ops(session, actor_user_id=current_user.id)


@app.get(
    "/ops/relationship-conflicts",
    response_model=CoverRelationshipConflictListResponse,
    include_in_schema=False,
)
def list_relationship_conflicts_ops_endpoint(
    severity: RelationshipConflictSeverity | Literal["all"] = "all",
    status: RelationshipConflictStatus | Literal["all"] = "all",
    conflict_type: RelationshipConflictType | Literal["all"] = "all",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipConflictListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_relationship_conflicts_for_ops(
        session,
        severity=severity,
        status=status,
        conflict_type=conflict_type,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/relationship-conflicts",
    response_model=CoverRelationshipConflictListResponse,
    include_in_schema=False,
)
def list_relationship_conflicts_for_cover_ops_endpoint(
    cover_image_id: int,
    severity: RelationshipConflictSeverity | Literal["all"] = "all",
    status: RelationshipConflictStatus | Literal["all"] = "all",
    conflict_type: RelationshipConflictType | Literal["all"] = "all",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipConflictListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_relationship_conflicts_for_cover_ops(
        session,
        cover_image_id=cover_image_id,
        severity=severity,
        status=status,
        conflict_type=conflict_type,
    )


@app.patch(
    "/ops/relationship-conflicts/{conflict_id}/acknowledge",
    response_model=CoverRelationshipConflictActionResponse,
    include_in_schema=False,
)
def acknowledge_relationship_conflict_ops_endpoint(
    conflict_id: int,
    payload: CoverRelationshipConflictStatusPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipConflictActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return acknowledge_relationship_conflict_for_ops(
        session,
        conflict_id=conflict_id,
        actor_user_id=current_user.id,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/ops/relationship-conflicts/{conflict_id}/dismiss",
    response_model=CoverRelationshipConflictActionResponse,
    include_in_schema=False,
)
def dismiss_relationship_conflict_ops_endpoint(
    conflict_id: int,
    payload: CoverRelationshipConflictStatusPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipConflictActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return dismiss_relationship_conflict_for_ops(
        session,
        conflict_id=conflict_id,
        actor_user_id=current_user.id,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/ops/relationship-conflicts/{conflict_id}/resolve",
    response_model=CoverRelationshipConflictActionResponse,
    include_in_schema=False,
)
def resolve_relationship_conflict_ops_endpoint(
    conflict_id: int,
    payload: CoverRelationshipConflictStatusPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverRelationshipConflictActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return resolve_relationship_conflict_for_ops(
        session,
        conflict_id=conflict_id,
        actor_user_id=current_user.id,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/ops/canonical-issue-suggestions/{suggestion_id}/approve",
    response_model=CanonicalIssueSuggestionReviewActionResponse,
    include_in_schema=False,
)
def approve_canonical_issue_suggestion_ops_endpoint(
    suggestion_id: int,
    payload: CanonicalIssueSuggestionReviewPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CanonicalIssueSuggestionReviewActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return approve_canonical_issue_suggestion_for_ops(
        session,
        suggestion_id=suggestion_id,
        reviewer=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/ops/canonical-issue-suggestions/{suggestion_id}/reject",
    response_model=CanonicalIssueSuggestionReviewActionResponse,
    include_in_schema=False,
)
def reject_canonical_issue_suggestion_ops_endpoint(
    suggestion_id: int,
    payload: CanonicalIssueSuggestionReviewPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CanonicalIssueSuggestionReviewActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return reject_canonical_issue_suggestion_for_ops(
        session,
        suggestion_id=suggestion_id,
        reviewer=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.patch(
    "/ops/canonical-issue-suggestions/{suggestion_id}/ignore",
    response_model=CanonicalIssueSuggestionReviewActionResponse,
    include_in_schema=False,
)
def ignore_canonical_issue_suggestion_ops_endpoint(
    suggestion_id: int,
    payload: CanonicalIssueSuggestionReviewPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CanonicalIssueSuggestionReviewActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return ignore_canonical_issue_suggestion_for_ops(
        session,
        suggestion_id=suggestion_id,
        reviewer=current_user,
        reason=payload.reason if payload is not None else None,
    )


@app.get(
    "/ops/canonical-issue-suggestions",
    response_model=CanonicalIssueSuggestionOpsListResponse,
    include_in_schema=False,
)
def list_canonical_issue_suggestions_for_ops_endpoint(
    review_state: Annotated[str, Query(alias="review_state")] = "all",
    confidence_bucket: Annotated[str, Query(alias="confidence_bucket")] = "all",
    suggestion_type: Annotated[str, Query(alias="suggestion_type")] = "all",
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CanonicalIssueSuggestionOpsListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_canonical_issue_suggestions_for_ops(
        session,
        review_state=review_state,
        confidence_bucket=confidence_bucket,
        suggestion_type=suggestion_type,
    )


@app.get(
    "/ops/match-groups/{grouping_key}",
    response_model=CoverImageMatchGroupRead,
    include_in_schema=False,
)
def get_match_group_for_ops(
    grouping_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageMatchGroupRead:
    ensure_ops_admin_access(current_user, settings)
    return get_cover_match_group_for_ops(session, grouping_key=grouping_key)


@app.post(
    "/ops/cover-images/{cover_image_id}/generate-match-candidates",
    response_model=CoverImageMatchCandidateGenerateResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def generate_cover_image_match_candidates_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageMatchCandidateGenerateResponse:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return generate_cover_image_match_candidates_for_ops(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/regenerate-match-confidence",
    response_model=CoverImageMatchCandidateGenerateResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def regenerate_cover_image_match_confidence_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageMatchCandidateGenerateResponse:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return generate_cover_image_match_candidates_for_ops(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


@app.patch(
    "/ops/match-candidates/{match_candidate_id}/acknowledge",
    response_model=CoverImageMatchCandidateRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def acknowledge_cover_match_candidate_ops(
    match_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageMatchCandidateRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return acknowledge_cover_match_candidate_for_ops(
        session,
        match_candidate_id=match_candidate_id,
        actor_user_id=current_user.id,
    )


@app.patch(
    "/ops/match-candidates/{match_candidate_id}/dismiss",
    response_model=CoverImageMatchCandidateRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def dismiss_cover_match_candidate_ops(
    match_candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageMatchCandidateRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return dismiss_cover_match_candidate_for_ops(
        session,
        match_candidate_id=match_candidate_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/cover-link-decisions",
    response_model=CoverImageLinkDecisionRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def create_cover_link_decision_ops(
    payload: CoverImageLinkDecisionCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageLinkDecisionRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return create_cover_link_decision_for_ops(
        session,
        payload=payload,
        actor_user_id=current_user.id,
    )


@app.get(
    "/ops/cover-link-decisions",
    response_model=list[CoverImageLinkDecisionRead],
    include_in_schema=False,
)
def list_cover_link_decisions_ops(
    cover_image_id: int | None = None,
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageLinkDecisionRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_cover_link_decisions_for_ops(
        session,
        cover_image_id=cover_image_id,
        include_inactive=include_inactive,
        limit=limit,
    )


@app.get(
    "/ops/cover-link-decisions/recent",
    response_model=list[CoverImageLinkDecisionRead],
    include_in_schema=False,
)
def list_recent_cover_link_decisions_ops(
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageLinkDecisionRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_cover_link_decisions_for_ops(
        session,
        cover_image_id=None,
        include_inactive=include_inactive,
        limit=limit,
    )


@app.get(
    "/ops/cover-link-decisions/{decision_id}",
    response_model=CoverImageLinkDecisionRead,
    include_in_schema=False,
)
def get_cover_link_decision_ops(
    decision_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageLinkDecisionRead:
    ensure_ops_admin_access(current_user, settings)
    return get_cover_link_decision_for_ops(
        session,
        decision_id=decision_id,
    )


@app.post(
    "/ops/cover-link-decisions/{decision_id}/revert",
    response_model=CoverImageLinkDecisionRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def revert_cover_link_decision_ops(
    decision_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageLinkDecisionRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return revert_cover_link_decision_for_ops(
        session,
        decision_id=decision_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/reconcile-ocr-metadata",
    response_model=CoverImageOcrReconciliationResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def reconcile_cover_image_ocr_metadata_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrReconciliationResponse:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return reconcile_cover_image_ocr_metadata_for_ops(
        session,
        cover_image_id=cover_image_id,
        actor_user_id=current_user.id,
    )


@app.get(
    "/ops/cover-images/{cover_image_id}/ocr-reconciliation-warnings",
    response_model=list[CoverImageOcrReconciliationWarningRead],
    include_in_schema=False,
)
def get_cover_image_ocr_reconciliation_warnings_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverImageOcrReconciliationWarningRead]:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    return list_cover_image_ocr_reconciliation_warnings(session, cover_image_id=cover_image_id)


@app.patch(
    "/ops/ocr-reconciliation-warnings/{warning_id}/acknowledge",
    response_model=CoverImageOcrReconciliationWarningRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def acknowledge_ocr_reconciliation_warning_ops(
    warning_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrReconciliationWarningRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return acknowledge_ocr_reconciliation_warning_for_ops(
        session,
        warning_id=warning_id,
        actor_user_id=current_user.id,
    )


@app.patch(
    "/ops/ocr-reconciliation-warnings/{warning_id}/dismiss",
    response_model=CoverImageOcrReconciliationWarningRead,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def dismiss_ocr_reconciliation_warning_ops(
    warning_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageOcrReconciliationWarningRead:
    ensure_ops_admin_access(current_user, settings)
    if current_user.id is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return dismiss_ocr_reconciliation_warning_for_ops(
        session,
        warning_id=warning_id,
        actor_user_id=current_user.id,
    )


@app.post(
    "/cover-images/{cover_image_id}/evaluate-matching-readiness",
    response_model=CoverImageMatchingEvaluationResponse,
)
def evaluate_matching_readiness_for_owner(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageMatchingEvaluationResponse:
    get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    cover = evaluate_cover_image_matching_readiness(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
    )
    return CoverImageMatchingEvaluationResponse(
        cover_image_id=cover.id,
        matching_status=cover.matching_status,
        matching_notes=cover.matching_notes,
        ready_for_matching_at=cover.ready_for_matching_at,
    )


@app.post(
    "/ops/cover-images/{cover_image_id}/evaluate-matching-readiness",
    response_model=CoverImageMatchingEvaluationResponse,
    include_in_schema=False,
)
def evaluate_matching_readiness_for_ops(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> CoverImageMatchingEvaluationResponse:
    ensure_ops_admin_access(current_user, settings)
    get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    cover = evaluate_cover_image_matching_readiness(
        session,
        settings=settings,
        cover_image_id=cover_image_id,
    )
    return CoverImageMatchingEvaluationResponse(
        cover_image_id=cover.id,
        matching_status=cover.matching_status,
        matching_notes=cover.matching_notes,
        ready_for_matching_at=cover.ready_for_matching_at,
    )


@app.get("/files/cover-images/{cover_image_id}/derivatives/{derivative_type}")
def download_cover_image_derivative_file(
    cover_image_id: int,
    derivative_type: Literal["thumb", "medium"],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    cover = get_cover_entity_or_404(session, cover_image_id)
    if not user_can_download_cover(session, cover, current_user):
        ensure_ops_admin_access(current_user, settings)
    derivative = get_cover_derivative_or_404(
        session,
        cover_image_id=cover_image_id,
        derivative_type=derivative_type,
    )
    abs_path = resolve_filesystem_path(settings, derivative.storage_path)
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Cover image derivative file missing on disk")
    filename = f"cover-{cover_image_id}-{derivative_type}.{derivative.mime_type.split('/')[-1]}"
    return FileResponse(abs_path, media_type=derivative.mime_type, filename=filename)


@app.get("/files/cover-images/{cover_image_id}/ocr-regions/{region_type}")
def download_cover_image_ocr_region_file(
    cover_image_id: int,
    region_type: Literal[
        "full_cover",
        "title_region",
        "issue_region",
        "publisher_region",
        "barcode_region",
        "lower_text_region",
    ],
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    cover = get_cover_entity_or_404(session, cover_image_id)
    if not user_can_download_cover(session, cover, current_user):
        ensure_ops_admin_access(current_user, settings)
    region = get_cover_ocr_region_or_404(
        session,
        cover_image_id=cover_image_id,
        region_type=region_type,
    )
    abs_path = resolve_filesystem_path(settings, region.storage_path)
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Cover image OCR region file missing on disk")
    filename = f"cover-{cover_image_id}-{region_type}.{region.mime_type.split('/')[-1]}"
    return FileResponse(abs_path, media_type=region.mime_type, filename=filename)


@app.get("/files/cover-images/{cover_image_id}")
def download_cover_image_file(
    cover_image_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    cover = get_cover_entity_or_404(session, cover_image_id)
    if user_can_download_cover(session, cover, current_user):
        pass
    else:
        ensure_ops_admin_access(current_user, settings)
    abs_path = resolve_filesystem_path(settings, cover.storage_path)
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Cover image file missing on disk")
    filename = cover.original_filename or f"cover-{cover_image_id}.{cover.mime_type.split('/')[-1]}"
    return FileResponse(abs_path, media_type=cover.mime_type, filename=filename)


@app.post("/orders", response_model=OrderCreateResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OrderCreateResponse:
    return create_order_for_user(session=session, current_user=current_user, payload=payload)


@app.get("/orders", response_model=OrderListResponse)
def get_orders(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    retailer: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "desc",
) -> OrderListResponse:
    return list_orders_for_user(
        session=session,
        current_user=current_user,
        page=page,
        page_size=page_size,
        retailer=retailer,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@app.get("/orders/{order_id}", response_model=OrderDetailResponse)
def get_order(
    order_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OrderDetailResponse:
    return get_order_detail_for_user(session=session, current_user=current_user, order_id=order_id)


@app.get("/inventory", response_model=InventoryListResponse)
def get_inventory(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: str | None = None,
    publisher: str | None = None,
    hold_status: str | None = None,
    grade_status: str | None = None,
    release_year: Annotated[int | None, Query(ge=1800, le=2999)] = None,
    release_calendar: ReleaseCalendarPresence | None = None,
    asset_state: str | None = None,
    intelligence_health: Annotated[
        Literal["healthy", "needs_review", "incomplete", "blocked", "not_healthy"] | None,
        Query(description="Filter rows by deterministic computed inventory-health bucket."),
    ] = None,
    ownership_intel: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter rows by normalized ownership state."),
    ] = None,
    risk_priority: Annotated[
        InventoryRiskPriority | None,
        Query(description="Filter rows by matching inventory risk priority."),
    ] = None,
    risk_type: Annotated[
        InventoryRiskType | None,
        Query(description="Filter rows by matching inventory risk type."),
    ] = None,
    needs_attention: bool = False,
    action_attention: Annotated[
        bool,
        Query(description="When true, only copies that have workflow actions in critical/high lanes."),
    ] = False,
    action_center_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter rows requiring the given deterministic action-center category."),
    ] = None,
    arrival_classification: Annotated[
        OrderArrivalClassification | None,
        Query(description="Filter rows derived order/arrival classification."),
    ] = None,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "asc",
    organization_id: Annotated[int | None, Query(description="Organization scope for shared dealer inventory visibility.")] = None,
) -> InventoryListResponse:
    return list_inventory(
        session=session,
        current_user=current_user,
        page=page,
        page_size=page_size,
        search=search,
        publisher=publisher,
        hold_status=hold_status,
        grade_status=grade_status,
        release_year=release_year,
        release_calendar=release_calendar,
        asset_state=asset_state,
        intelligence_health=intelligence_health,
        ownership_intel=ownership_intel,
        risk_priority=risk_priority,
        risk_type=risk_type,
        needs_attention=needs_attention,
        action_attention=action_attention,
        action_center_category=action_center_category,
        arrival_classification=arrival_classification,
        sort_by=sort_by,
        sort_dir=sort_dir,
        organization_id=organization_id,
    )


@app.get("/reports/inventory.csv")
def export_owner_inventory_csv_report(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    filt: Annotated[InventoryExportFilters, Depends(parse_inventory_export_filters)],
) -> Response:
    assert current_user.id is not None
    rows, _as_of = inventory_export_rows_owner(session, owner=current_user, filt=filt)
    return _reports_attachment_response(
        render_csv(INVENTORY_OWNER_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="inventory",
        extension="csv",
    )


@app.get("/reports/inventory.json")
def export_owner_inventory_json_report(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    filt: Annotated[InventoryExportFilters, Depends(parse_inventory_export_filters)],
) -> Response:
    assert current_user.id is not None
    rows, as_of = inventory_export_rows_owner(session, owner=current_user, filt=filt)
    return _reports_attachment_response(
        inventory_export_json_document(rows, filt, INVENTORY_OWNER_CSV_COLUMNS, as_of),
        media_type="application/json; charset=utf-8",
        stem="inventory",
        extension="json",
    )


@app.get("/reports/action-center.csv")
def export_reports_action_center_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    priority: Annotated[
        InventoryRiskPriority | None,
        Query(description="Filter by deterministic workflow lane"),
    ] = None,
    action_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter by deterministic action-center category."),
    ] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    release_status: Annotated[
        InventoryReleaseStatusFilter | None,
        Query(description="Filter by raw release_status"),
    ] = None,
    in_hand_only: bool = False,
    inventory_copy_id: Annotated[
        int | None,
        Query(description="Restrict exported actions to a single inventory row."),
    ] = None,
) -> Response:
    rows, _as_of = action_center_export_rows(
        session,
        current_user=current_user,
        priority=priority,
        category=action_category,
        ownership_state_filter=ownership_state,
        publisher=publisher,
        release_status_filter=release_status,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id,
    )
    return _reports_attachment_response(
        render_csv(ACTION_CENTER_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="inventory-action-center",
        extension="csv",
    )


@app.get("/reports/order-arrival.csv")
def export_reports_order_arrival_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    params: Annotated[OrderArrivalExportParams, Depends(parse_order_arrival_export_params)],
) -> Response:
    rows, _as_of = order_arrival_export_rows(
        session,
        current_user=current_user,
        classification=params.classification,
        retailer=params.retailer,
        publisher=params.publisher,
        release_date_from=params.release_date_from,
        release_date_to=params.release_date_to,
        expected_ship_date_from=params.expected_ship_date_from,
        expected_ship_date_to=params.expected_ship_date_to,
        order_status=params.order_status,
        in_hand_only=params.in_hand_only,
    )
    return _reports_attachment_response(
        render_csv(ORDER_ARRIVAL_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="order-arrival-intelligence",
        extension="csv",
    )


@app.get("/reports/run-detection.csv")
def export_reports_run_detection_csv_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    series_status: Annotated[
        RunDetectionSeriesStatus | None,
        Query(description="Filter series groups by deterministic run-detection status."),
    ] = None,
) -> Response:
    rows, _as_of = run_detection_series_rows(
        session,
        current_user=current_user,
        ops_scope=False,
        series_status=series_status,
    )
    return _reports_attachment_response(
        render_csv(RUN_DETECTION_SERIES_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="run-detection-series",
        extension="csv",
    )


@app.get("/reports/timeline.csv")
def export_reports_timeline_csv_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    tl: Annotated[TimelineExportParams, Depends(parse_timeline_export_params)],
) -> Response:
    assert current_user.id is not None
    rows, _as_of = timeline_export_rows(
        session,
        ops_scope=False,
        scoped_user_id=int(current_user.id),
        event_type_filter=tl.event_type,
        publisher=tl.publisher,
        ownership_filter=tl.ownership_state,
        release_status_tl=tl.release_status,
        start_date_tl=tl.start_date,
        end_date_tl=tl.end_date,
        preorder_only=tl.preorder_only,
        in_hand_only=tl.in_hand_only,
    )
    return _reports_attachment_response(
        render_csv(TIMELINE_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="collection-timeline",
        extension="csv",
    )


@app.get("/reports/collection-summary.json")
def export_reports_collection_summary_json_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    payload = collection_summary_payload(
        session,
        projection_user_filter=int(current_user.id),
        intel_user=current_user,
        include_reconciliation=False,
    )
    return _reports_attachment_response(
        dumps_report_json(payload),
        media_type="application/json; charset=utf-8",
        stem="collection-summary",
        extension="json",
    )


@app.get("/inventory/summary", response_model=InventorySummaryResponse)
def get_inventory_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventorySummaryResponse:
    return inventory_summary(session=session, current_user=current_user)


@app.get("/inventory-arrival-tracking", response_model=InventoryArrivalTrackingResponse)
def get_inventory_arrival_tracking(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    not_released_limit: Annotated[int, Query(ge=1, le=200, description="Max not-released-yet rows.")] = 50,
) -> InventoryArrivalTrackingResponse:
    return build_inventory_arrival_tracking(
        session,
        current_user=current_user,
        not_released_limit=not_released_limit,
    )


@app.get("/inventory-intelligence/summary", response_model=InventoryIntelligenceSummary)
def get_inventory_intelligence_summary_for_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryIntelligenceSummary:
    summary, _, _, _ = compute_inventory_intelligence(
        session,
        current_user=current_user,
        include_signals=False,
    )
    return summary


@app.get("/inventory-intelligence/health", response_model=InventoryIntelligenceHealthSummary)
def get_inventory_intelligence_health_for_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryIntelligenceHealthSummary:
    _, health, _, _ = compute_inventory_intelligence(
        session,
        current_user=current_user,
        include_signals=False,
    )
    return health


@app.get("/inventory-intelligence/breakdown", response_model=InventoryIntelligenceBreakdown)
def get_inventory_intelligence_breakdown_for_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryIntelligenceBreakdown:
    _, _, breakdown, _ = compute_inventory_intelligence(
        session,
        current_user=current_user,
        include_signals=False,
    )
    return breakdown


@app.get("/inventory-risks", response_model=InventoryRiskListResponse)
def get_inventory_risks_for_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by priority.")] = None,
    risk_type: Annotated[InventoryRiskType | None, Query(description="Filter by risk type.")] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    in_hand_only: bool = False,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    return get_inventory_risks_owner(
        session,
        user=current_user,
        priority=priority,
        risk_type=risk_type,
        ownership_state=ownership_state,
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
    )


@app.get("/inventory-risks/summary", response_model=InventoryRiskSummary)
def get_inventory_risk_summary_for_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by priority.")] = None,
    risk_type: Annotated[InventoryRiskType | None, Query(description="Filter by risk type.")] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    in_hand_only: bool = False,
    open_only: bool = True,
) -> InventoryRiskSummary:
    summary = get_inventory_risks_owner(
        session,
        user=current_user,
        priority=priority,
        risk_type=risk_type,
        ownership_state=ownership_state,
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
    ).summary
    return summary


@app.get("/inventory/{inventory_copy_id}/risks", response_model=InventoryRiskListResponse)
def get_inventory_risk_detail_for_owner(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by priority.")] = None,
    risk_type: Annotated[InventoryRiskType | None, Query(description="Filter by risk type.")] = None,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    return get_inventory_risk_detail_owner(
        session,
        user=current_user,
        inventory_copy_id=inventory_copy_id,
        priority=priority,
        risk_type=risk_type,
        open_only=open_only,
    )


@app.get("/ops/inventory-risks", response_model=InventoryRiskListResponse, include_in_schema=False)
def get_ops_inventory_risks(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by priority.")] = None,
    risk_type: Annotated[InventoryRiskType | None, Query(description="Filter by risk type.")] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    in_hand_only: bool = False,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    ensure_ops_admin_access(current_user, settings)
    return get_inventory_risks_ops(
        session,
        priority=priority,
        risk_type=risk_type,
        ownership_state=ownership_state,
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
    )


@app.get("/ops/inventory-risks/summary", response_model=InventoryRiskSummary, include_in_schema=False)
def get_ops_inventory_risk_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by priority.")] = None,
    risk_type: Annotated[InventoryRiskType | None, Query(description="Filter by risk type.")] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    in_hand_only: bool = False,
    open_only: bool = True,
) -> InventoryRiskSummary:
    ensure_ops_admin_access(current_user, settings)
    return get_inventory_risks_ops(
        session,
        priority=priority,
        risk_type=risk_type,
        ownership_state=ownership_state,
        publisher=publisher,
        in_hand_only=in_hand_only,
        open_only=open_only,
    ).summary


@app.get("/ops/inventory/{inventory_copy_id}/risks", response_model=InventoryRiskListResponse, include_in_schema=False)
def get_ops_inventory_risk_detail(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by priority.")] = None,
    risk_type: Annotated[InventoryRiskType | None, Query(description="Filter by risk type.")] = None,
    open_only: bool = True,
) -> InventoryRiskListResponse:
    ensure_ops_admin_access(current_user, settings)
    return get_inventory_risk_detail_ops(
        session,
        inventory_copy_id=inventory_copy_id,
        priority=priority,
        risk_type=risk_type,
        open_only=open_only,
    )


@app.get("/inventory-action-center", response_model=InventoryActionCenterListResponse)
def get_inventory_action_center_for_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by deterministic workflow lane")] = None,
    action_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter by deterministic action-center category."),
    ] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query(description="Filter by raw release_status")] = None,
    unresolved_only: bool = True,
    in_hand_only: bool = False,
    inventory_copy_id: Annotated[
        int | None,
        Query(description="Restrict aggregated actions to a single inventory row (detail prefetch)."),
    ] = None,
) -> InventoryActionCenterListResponse:
    return get_inventory_action_center_response(
        session,
        current_user=current_user,
        priority=priority,
        action_category_str=action_category,
        ownership_state=ownership_state,
        publisher=publisher,
        release_status_filter=release_status,
        unresolved_only=unresolved_only,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id,
    )


@app.get("/inventory-action-center/summary", response_model=InventoryActionCenterSummary)
def get_inventory_action_center_summary_for_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by deterministic workflow lane")] = None,
    action_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter by deterministic action-center category."),
    ] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query(description="Filter by raw release_status")] = None,
    unresolved_only: bool = True,
    in_hand_only: bool = False,
    inventory_copy_id: Annotated[int | None, Query(description="Restrict summary to one inventory row.")] = None,
) -> InventoryActionCenterSummary:
    body = get_inventory_action_center_response(
        session,
        current_user=current_user,
        priority=priority,
        action_category_str=action_category,
        ownership_state=ownership_state,
        publisher=publisher,
        release_status_filter=release_status,
        unresolved_only=unresolved_only,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id,
    )
    return body.summary


@app.get("/ops/inventory-action-center", response_model=InventoryActionCenterListResponse, include_in_schema=False)
def get_ops_inventory_action_center(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by deterministic workflow lane")] = None,
    action_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter by deterministic action-center category."),
    ] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query(description="Filter by raw release_status")] = None,
    unresolved_only: bool = True,
    in_hand_only: bool = False,
    inventory_copy_id: Annotated[int | None, Query(description="Restrict aggregated actions to a single inventory row.")] = None,
) -> InventoryActionCenterListResponse:
    ensure_ops_admin_access(current_user, settings)
    return get_inventory_action_center_response(
        session,
        current_user=None,
        priority=priority,
        action_category_str=action_category,
        ownership_state=ownership_state,
        publisher=publisher,
        release_status_filter=release_status,
        unresolved_only=unresolved_only,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id,
    )


@app.get(
    "/ops/inventory-action-center/summary",
    response_model=InventoryActionCenterSummary,
    include_in_schema=False,
)
def get_ops_inventory_action_center_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    priority: Annotated[InventoryRiskPriority | None, Query(description="Filter by deterministic workflow lane")] = None,
    action_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter by deterministic action-center category."),
    ] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query(description="Filter by raw release_status")] = None,
    unresolved_only: bool = True,
    in_hand_only: bool = False,
    inventory_copy_id: Annotated[int | None, Query(description="Restrict summary to one inventory row.")] = None,
) -> InventoryActionCenterSummary:
    ensure_ops_admin_access(current_user, settings)
    return get_inventory_action_center_response(
        session,
        current_user=None,
        priority=priority,
        action_category_str=action_category,
        ownership_state=ownership_state,
        publisher=publisher,
        release_status_filter=release_status,
        unresolved_only=unresolved_only,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id,
    ).summary


@app.get("/ops/reports/inventory.csv", include_in_schema=False)
def export_ops_inventory_csv_report(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    filt: Annotated[InventoryExportFilters, Depends(parse_inventory_export_filters)],
    run_detection_series_status: Annotated[
        RunDetectionSeriesStatus | None,
        Query(description="Filter global run-detection overlay columns by deterministic series status."),
    ] = None,
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    rows, _ = inventory_export_rows_ops(session, filt=filt, series_status=run_detection_series_status)
    return _reports_attachment_response(
        render_csv(INVENTORY_OPS_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="ops-inventory-all-accounts",
        extension="csv",
    )


@app.get("/ops/reports/inventory.json", include_in_schema=False)
def export_ops_inventory_json_report(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    filt: Annotated[InventoryExportFilters, Depends(parse_inventory_export_filters)],
    run_detection_series_status: Annotated[
        RunDetectionSeriesStatus | None,
        Query(description="Filter global run-detection overlay columns by deterministic series status."),
    ] = None,
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    rows, as_of = inventory_export_rows_ops(session, filt=filt, series_status=run_detection_series_status)
    return _reports_attachment_response(
        inventory_export_json_document(rows, filt, INVENTORY_OPS_CSV_COLUMNS, as_of),
        media_type="application/json; charset=utf-8",
        stem="ops-inventory-all-accounts",
        extension="json",
    )


@app.get("/ops/reports/action-center.csv", include_in_schema=False)
def export_ops_action_center_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    priority: Annotated[
        InventoryRiskPriority | None,
        Query(description="Filter by deterministic workflow lane"),
    ] = None,
    action_category: Annotated[
        InventoryActionCenterCategory | None,
        Query(description="Filter by deterministic action-center category."),
    ] = None,
    ownership_state: Annotated[
        Literal["in_hand", "preorder", "ordered_not_received", "cancelled", "unknown_state"] | None,
        Query(description="Filter by normalized ownership state."),
    ] = None,
    publisher: str | None = None,
    release_status: Annotated[
        InventoryReleaseStatusFilter | None,
        Query(description="Filter by raw release_status"),
    ] = None,
    in_hand_only: bool = False,
    inventory_copy_id: Annotated[
        int | None,
        Query(description="Restrict exported actions to a single inventory row."),
    ] = None,
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    rows, _ = action_center_export_rows(
        session,
        current_user=None,
        priority=priority,
        category=action_category,
        ownership_state_filter=ownership_state,
        publisher=publisher,
        release_status_filter=release_status,
        in_hand_only=in_hand_only,
        inventory_copy_id_filter=inventory_copy_id,
    )
    return _reports_attachment_response(
        render_csv(ACTION_CENTER_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="ops-inventory-action-center",
        extension="csv",
    )


@app.get("/ops/reports/order-arrival.csv", include_in_schema=False)
def export_ops_order_arrival_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    params: Annotated[OrderArrivalExportParams, Depends(parse_order_arrival_export_params)],
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    rows, _ = order_arrival_export_rows(
        session,
        current_user=None,
        classification=params.classification,
        retailer=params.retailer,
        publisher=params.publisher,
        release_date_from=params.release_date_from,
        release_date_to=params.release_date_to,
        expected_ship_date_from=params.expected_ship_date_from,
        expected_ship_date_to=params.expected_ship_date_to,
        order_status=params.order_status,
        in_hand_only=params.in_hand_only,
    )
    return _reports_attachment_response(
        render_csv(ORDER_ARRIVAL_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="ops-order-arrival-intelligence",
        extension="csv",
    )


@app.get("/ops/reports/run-detection.csv", include_in_schema=False)
def export_ops_run_detection_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    series_status: Annotated[
        RunDetectionSeriesStatus | None,
        Query(description="Filter series groups by deterministic run-detection status."),
    ] = None,
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    rows, _ = run_detection_series_rows(
        session,
        current_user=None,
        ops_scope=True,
        series_status=series_status,
    )
    return _reports_attachment_response(
        render_csv(RUN_DETECTION_SERIES_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="ops-run-detection-series",
        extension="csv",
    )


@app.get("/ops/reports/timeline.csv", include_in_schema=False)
def export_ops_timeline_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    tl: Annotated[TimelineExportParams, Depends(parse_timeline_export_params)],
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    rows, _ = timeline_export_rows(
        session,
        ops_scope=True,
        scoped_user_id=None,
        event_type_filter=tl.event_type,
        publisher=tl.publisher,
        ownership_filter=tl.ownership_state,
        release_status_tl=tl.release_status,
        start_date_tl=tl.start_date,
        end_date_tl=tl.end_date,
        preorder_only=tl.preorder_only,
        in_hand_only=tl.in_hand_only,
    )
    return _reports_attachment_response(
        render_csv(TIMELINE_CSV_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        stem="ops-collection-timeline",
        extension="csv",
    )


@app.get("/ops/reports/collection-summary.json", include_in_schema=False)
def export_ops_collection_summary_json_report(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    payload = collection_summary_payload(
        session,
        projection_user_filter=None,
        intel_user=None,
        include_reconciliation=True,
    )
    return _reports_attachment_response(
        dumps_report_json(payload),
        media_type="application/json; charset=utf-8",
        stem="ops-collection-summary",
        extension="json",
    )


@app.get("/reports/market-sales.csv")
def export_reports_market_sales_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    publisher: Annotated[str | None, Query(description="Filter by normalized publisher.")] = None,
    normalized_title: Annotated[str | None, Query(description="Filter by normalized title.")] = None,
    normalized_issue: Annotated[str | None, Query(description="Filter by normalized issue.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter graded or raw sale records.")] = None,
    normalization_status: Annotated[str | None, Query(description="Filter by normalization status.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter records sold on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter records sold on or before this date.")] = None,
) -> Response:
    assert current_user.id is not None
    csv_text = render_market_sales_csv(
        session,
        source=source,
        publisher=publisher,
        normalized_title=normalized_title,
        normalized_issue=normalized_issue,
        grading_company=grading_company,
        is_graded=is_graded,
        normalization_status=normalization_status,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="market-sales",
        extension="csv",
    )


@app.get("/reports/market-eligible-comps.csv")
def export_reports_market_eligible_comps_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    csv_text = render_market_eligible_comps_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="market-eligible-comps",
        extension="csv",
    )


@app.get("/reports/market-fmv-snapshots.csv")
def export_reports_market_fmv_snapshots_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    csv_text = render_market_fmv_snapshots_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="market-fmv-snapshots",
        extension="csv",
    )


@app.get("/reports/market-trends.csv")
def export_reports_market_trends_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    csv_text = render_market_trends_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="market-trends",
        extension="csv",
    )


@app.get("/reports/market-normalization-issues-summary.csv")
def export_reports_market_normalization_issues_summary_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    csv_text = render_normalization_issues_summary_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="market-normalization-issues-summary",
        extension="csv",
    )


@app.get("/reports/portfolio-value-summary.csv")
def export_reports_portfolio_value_summary_csv_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
) -> Response:
    assert current_user.id is not None
    csv_text = render_portfolio_value_summary_csv(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        ownership_state=ownership_state,
    )
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="portfolio-value-summary",
        extension="csv",
    )


@app.get("/reports/inventory-no-market-data.csv")
def export_reports_inventory_no_market_data_csv_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    csv_text = render_no_market_data_inventory_csv(session, owner_user_id=int(current_user.id))
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="inventory-no-market-data",
        extension="csv",
    )


@app.get("/reports/inventory-no-market-data.json")
def export_reports_inventory_no_market_data_json_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    return _reports_attachment_response(
        dumps_no_market_data_inventory_json(session, owner_user_id=int(current_user.id)),
        media_type="application/json; charset=utf-8",
        stem="inventory-no-market-data",
        extension="json",
    )


@app.get("/reports/inventory-fmv-low-confidence.csv")
def export_reports_inventory_fmv_low_confidence_csv_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    csv_text = render_low_confidence_inventory_csv(session, owner_user_id=int(current_user.id))
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="inventory-fmv-low-confidence",
        extension="csv",
    )


@app.get("/reports/inventory-fmv-stale.csv")
def export_reports_inventory_fmv_stale_csv_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    csv_text = render_stale_fmv_inventory_csv(session, owner_user_id=int(current_user.id))
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="inventory-fmv-stale",
        extension="csv",
    )


@app.get("/reports/market-deterministic-summary.json")
def export_reports_market_deterministic_summary_json_owner(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
) -> Response:
    assert current_user.id is not None
    blob = dumps_market_deterministic_summary_bytes(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        ownership_state=ownership_state,
    )
    return _reports_attachment_response(
        blob,
        media_type="application/json; charset=utf-8",
        stem="market-deterministic-summary",
        extension="json",
    )


@app.get("/ops/reports/market-sales.csv", include_in_schema=False)
def export_ops_reports_market_sales_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    publisher: Annotated[str | None, Query(description="Filter by normalized publisher.")] = None,
    normalized_title: Annotated[str | None, Query(description="Filter by normalized title.")] = None,
    normalized_issue: Annotated[str | None, Query(description="Filter by normalized issue.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter graded or raw sale records.")] = None,
    normalization_status: Annotated[str | None, Query(description="Filter by normalization status.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter records sold on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter records sold on or before this date.")] = None,
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_market_sales_csv(
        session,
        source=source,
        publisher=publisher,
        normalized_title=normalized_title,
        normalized_issue=normalized_issue,
        grading_company=grading_company,
        is_graded=is_graded,
        normalization_status=normalization_status,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-market-sales",
        extension="csv",
    )


@app.get("/ops/reports/market-eligible-comps.csv", include_in_schema=False)
def export_ops_reports_market_eligible_comps_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_market_eligible_comps_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-market-eligible-comps",
        extension="csv",
    )


@app.get("/ops/reports/market-fmv-snapshots.csv", include_in_schema=False)
def export_ops_reports_market_fmv_snapshots_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_market_fmv_snapshots_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-market-fmv-snapshots",
        extension="csv",
    )


@app.get("/ops/reports/market-trends.csv", include_in_schema=False)
def export_ops_reports_market_trends_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_market_trends_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-market-trends",
        extension="csv",
    )


@app.get("/ops/reports/market-normalization-issues-summary.csv", include_in_schema=False)
def export_ops_reports_market_normalization_issues_summary_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_normalization_issues_summary_csv(session)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-market-normalization-issues-summary",
        extension="csv",
    )


@app.get("/ops/reports/portfolio-value-summary.csv", include_in_schema=False)
def export_ops_reports_portfolio_value_summary_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_portfolio_value_summary_csv(
        session,
        owner_user_id=None,
        publisher=publisher,
        ownership_state=ownership_state,
    )
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-portfolio-value-summary",
        extension="csv",
    )


@app.get("/ops/reports/inventory-no-market-data.csv", include_in_schema=False)
def export_ops_reports_inventory_no_market_data_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_no_market_data_inventory_csv(session, owner_user_id=None)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-inventory-no-market-data",
        extension="csv",
    )


@app.get("/ops/reports/inventory-no-market-data.json", include_in_schema=False)
def export_ops_reports_inventory_no_market_data_json(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    return _reports_attachment_response(
        dumps_no_market_data_inventory_json(session, owner_user_id=None),
        media_type="application/json; charset=utf-8",
        stem="ops-inventory-no-market-data",
        extension="json",
    )


@app.get("/ops/reports/inventory-fmv-low-confidence.csv", include_in_schema=False)
def export_ops_reports_inventory_fmv_low_confidence_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_low_confidence_inventory_csv(session, owner_user_id=None)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-inventory-fmv-low-confidence",
        extension="csv",
    )


@app.get("/ops/reports/inventory-fmv-stale.csv", include_in_schema=False)
def export_ops_reports_inventory_fmv_stale_csv(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    csv_text = render_stale_fmv_inventory_csv(session, owner_user_id=None)
    return _reports_attachment_response(
        csv_text,
        media_type="text/csv; charset=utf-8",
        stem="ops-inventory-fmv-stale",
        extension="csv",
    )


@app.get("/ops/reports/market-deterministic-summary.json", include_in_schema=False)
def export_ops_reports_market_deterministic_summary_json(
    *,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
) -> Response:
    ensure_ops_admin_access(current_user, settings)
    blob = dumps_market_deterministic_summary_bytes(
        session,
        owner_user_id=None,
        publisher=publisher,
        ownership_state=ownership_state,
    )
    return _reports_attachment_response(
        blob,
        media_type="application/json; charset=utf-8",
        stem="ops-market-deterministic-summary",
        extension="json",
    )


OrderArrivalOrderStatusLiteral = Literal["ordered", "preordered", "shipped", "received", "cancelled"]


@app.get("/order-arrival-intelligence", response_model=OrderArrivalIntelListResponse)
def get_order_arrival_intelligence_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    classification: Annotated[OrderArrivalClassification | None, Query(description="Filter by classification.")] = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: OrderArrivalOrderStatusLiteral | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelListResponse:
    resp, _ = compute_order_arrival_intelligence(
        session,
        current_user=current_user,
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )
    return resp


@app.get("/order-arrival-intelligence/summary", response_model=OrderArrivalIntelSummary)
def get_order_arrival_intelligence_summary_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    classification: Annotated[OrderArrivalClassification | None, Query(description="Filter by classification.")] = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: OrderArrivalOrderStatusLiteral | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelSummary:
    return order_arrival_summary_only(
        session,
        user=current_user,
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )


@app.get("/order-arrival-intelligence/calendar", response_model=OrderArrivalIntelCalendarResponse)
def get_order_arrival_calendar_owner(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    calendar_start: date | None = None,
    calendar_end: date | None = None,
    classification: Annotated[OrderArrivalClassification | None, Query(description="Filter by classification.")] = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: OrderArrivalOrderStatusLiteral | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelCalendarResponse:
    return get_order_arrival_calendar(
        session,
        current_user=current_user,
        calendar_start=calendar_start,
        calendar_end=calendar_end,
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )


@app.get("/ops/order-arrival-intelligence", response_model=OrderArrivalIntelListResponse, include_in_schema=False)
def get_ops_order_arrival_intelligence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    classification: Annotated[OrderArrivalClassification | None, Query(description="Filter by classification.")] = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: OrderArrivalOrderStatusLiteral | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelListResponse:
    ensure_ops_admin_access(current_user, settings)
    resp, _ = compute_order_arrival_intelligence(
        session,
        current_user=None,
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )
    return resp


@app.get("/ops/order-arrival-intelligence/summary", response_model=OrderArrivalIntelSummary, include_in_schema=False)
def get_ops_order_arrival_intelligence_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    classification: Annotated[OrderArrivalClassification | None, Query(description="Filter by classification.")] = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: OrderArrivalOrderStatusLiteral | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelSummary:
    ensure_ops_admin_access(current_user, settings)
    response, _ = compute_order_arrival_intelligence(
        session,
        current_user=None,
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )
    return response.summary


@app.get("/ops/order-arrival-intelligence/calendar", response_model=OrderArrivalIntelCalendarResponse, include_in_schema=False)
def get_ops_order_arrival_calendar(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    calendar_start: date | None = None,
    calendar_end: date | None = None,
    classification: Annotated[OrderArrivalClassification | None, Query(description="Filter by classification.")] = None,
    retailer: str | None = None,
    publisher: str | None = None,
    release_date_from: date | None = None,
    release_date_to: date | None = None,
    expected_ship_date_from: date | None = None,
    expected_ship_date_to: date | None = None,
    order_status: OrderArrivalOrderStatusLiteral | None = None,
    in_hand_only: bool = False,
) -> OrderArrivalIntelCalendarResponse:
    ensure_ops_admin_access(current_user, settings)
    return get_order_arrival_calendar(
        session,
        current_user=None,
        calendar_start=calendar_start,
        calendar_end=calendar_end,
        classification=classification,
        retailer=retailer,
        publisher=publisher,
        release_date_from=release_date_from,
        release_date_to=release_date_to,
        expected_ship_date_from=expected_ship_date_from,
        expected_ship_date_to=expected_ship_date_to,
        order_status=order_status,
        in_hand_only=in_hand_only,
    )


@app.get("/collection-analytics/summary", response_model=CollectionAnalyticsSummary)
def get_collection_analytics_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionAnalyticsSummary:
    assert current_user.id is not None
    summary_bundle, _ = analyze_collection_summary(
        session,
        projection_user_filter=int(current_user.id),
        intel_user=current_user,
        as_of_date=as_of,
    )
    return summary_bundle


@app.get("/collection-analytics/publishers", response_model=CollectionPublisherAnalyticsResponse)
def get_collection_analytics_publishers(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionPublisherAnalyticsResponse:
    assert current_user.id is not None
    return analyze_collection_publishers(
        session,
        projection_user_filter=int(current_user.id),
        intel_user=current_user,
        as_of_date=as_of,
    )


@app.get("/collection-analytics/timeline", response_model=CollectionTimelineResponse)
def get_collection_analytics_timeline(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionTimelineResponse:
    assert current_user.id is not None
    return analyze_collection_timeline(
        session,
        projection_user_filter=int(current_user.id),
        intel_user=current_user,
        as_of_date=as_of,
    )


@app.get("/collection-analytics/quality", response_model=CollectionQualityAnalyticsResponse)
def get_collection_analytics_quality(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionQualityAnalyticsResponse:
    assert current_user.id is not None
    return analyze_collection_quality(
        session,
        projection_user_filter=int(current_user.id),
        intel_user=current_user,
        as_of_date=as_of,
    )


@app.get("/collection-analytics/composition", response_model=CollectionCompositionResponse)
def get_collection_analytics_composition(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    as_of: Annotated[date | None, Query(alias="as_of")] = None,
) -> CollectionCompositionResponse:
    assert current_user.id is not None
    return analyze_collection_composition(
        session,
        projection_user_filter=int(current_user.id),
        intel_user=current_user,
        as_of_date=as_of,
    )


@app.get("/collection-timeline", response_model=CollectionTimelineEventsResponse)
def get_collection_timeline_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: Annotated[
        CollectionTimelineEventType | None,
        Query(description="Filter by deterministic timeline event kind."),
    ] = None,
    publisher: Annotated[str | None, Query(description="Case-insensitive substring match on publisher label.")] = None,
    ownership_state: Annotated[
        CollectionTimelineOwnershipStateFilter | None,
        Query(description="Filter rows to copies whose current normalized ownership matches."),
    ] = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    preorder_only: bool = False,
    in_hand_only: bool = False,
    grouping: Annotated[CollectionTimelineGrouping, Query()] = "none",
    sort: Annotated[CollectionTimelineSort, Query()] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 280,
) -> CollectionTimelineEventsResponse:
    assert current_user.id is not None
    return timeline_events_for_scope(
        session,
        scope_user_id=int(current_user.id),
        event_type_filter=event_type,
        publisher=publisher,
        ownership_filter=ownership_state,
        release_status=release_status,
        start_date=start_date,
        end_date=end_date,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
        inventory_copy_id=None,
        grouping=grouping,
        sort=sort,
        limit=limit,
        return_events=True,
    )


@app.get("/collection-timeline/summary", response_model=CollectionTimelineSummary)
def get_collection_timeline_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: Annotated[
        CollectionTimelineEventType | None,
        Query(description="Filter by deterministic timeline event kind."),
    ] = None,
    publisher: Annotated[str | None, Query(description="Case-insensitive substring match on publisher label.")] = None,
    ownership_state: Annotated[
        CollectionTimelineOwnershipStateFilter | None,
        Query(description="Filter rows to copies whose current normalized ownership matches."),
    ] = None,
    release_status: Annotated[InventoryReleaseStatusFilter | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    preorder_only: bool = False,
    in_hand_only: bool = False,
) -> CollectionTimelineSummary:
    assert current_user.id is not None
    return timeline_events_for_scope(
        session,
        scope_user_id=int(current_user.id),
        event_type_filter=event_type,
        publisher=publisher,
        ownership_filter=ownership_state,
        release_status=release_status,
        start_date=start_date,
        end_date=end_date,
        preorder_only=preorder_only,
        in_hand_only=in_hand_only,
        inventory_copy_id=None,
        grouping="none",
        sort="desc",
        limit=1,
        return_events=False,
    ).summary


@app.get("/duplicate-ownership", response_model=DuplicateOwnershipListRead)
def list_duplicate_ownership_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    dup_scan_classification: Annotated[
        DuplicateScanClassificationFilter,
        Query(alias="dup_scan_classification"),
    ] = "all",
    classification: Annotated[
        DuplicateOwnershipClassification | None,
        Query(description="Filter groups by deterministic duplicate ownership classification."),
    ] = None,
) -> DuplicateOwnershipListRead:
    return list_duplicate_ownership_owner(
        session,
        user=current_user,
        dup_scan_classification=dup_scan_classification,
        classification=classification,
    )


@app.get("/duplicate-ownership/{group_key}", response_model=DuplicateOwnershipGroupRead)
def get_duplicate_ownership_detail_endpoint(
    group_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DuplicateOwnershipGroupRead:
    return get_duplicate_ownership_detail_owner(session, user=current_user, group_key=group_key)


@app.get("/run-detection", response_model=RunDetectionListRead)
def list_run_detection_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    series_status: Annotated[
        RunDetectionSeriesStatus | None,
        Query(description="Filter series groups by deterministic run-detection status."),
    ] = None,
) -> RunDetectionListRead:
    return list_run_detection_owner(session, user=current_user, series_status=series_status)


@app.get("/run-detection/{series_key}", response_model=RunDetectionSeriesDetailRead)
def get_run_detection_detail_endpoint(
    series_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> RunDetectionSeriesDetailRead:
    return get_run_detection_detail_owner(session, user=current_user, series_key=series_key)


@app.post("/scanner-profiles", response_model=ScannerProfileRead, status_code=status.HTTP_201_CREATED)
def owner_create_scanner_profile(
    payload: ScannerProfileCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScannerProfileRead:
    assert current_user.id is not None
    return create_scanner_profile(session, owner_user_id=int(current_user.id), payload=payload)


@app.get("/scanner-profiles", response_model=ScannerProfileListResponse)
def owner_list_scanner_profiles_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScannerProfileListResponse:
    assert current_user.id is not None
    return list_scanner_profiles_for_owner(session, owner_user_id=int(current_user.id))


@app.get("/scanner-profiles/{profile_id}", response_model=ScannerProfileRead)
def owner_get_scanner_profile_endpoint(
    profile_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScannerProfileRead:
    assert current_user.id is not None
    return get_scanner_profile_detail_for_owner(session, owner_user_id=int(current_user.id), profile_id=profile_id)


@app.patch("/scanner-profiles/{profile_id}", response_model=ScannerProfileRead)
def owner_patch_scanner_profile_endpoint(
    profile_id: int,
    payload: ScannerProfileUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScannerProfileRead:
    assert current_user.id is not None
    return update_scanner_profile_for_owner(
        session, owner_user_id=int(current_user.id), profile_id=profile_id, payload=payload
    )


@app.delete("/scanner-profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def owner_delete_scanner_profile_endpoint(
    profile_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> Response:
    assert current_user.id is not None
    delete_scanner_profile_for_owner(session, owner_user_id=int(current_user.id), profile_id=profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/market-ingestion/batch", response_model=MarketAcquisitionIngestionBatchRead, status_code=status.HTTP_201_CREATED)
def owner_create_market_ingestion_batch_endpoint(
    payload: MarketAcquisitionIngestionBatchCreatePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionIngestionBatchRead:
    assert current_user.id is not None
    body, created = ingest_market_acquisition_batch_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/market-ingestion/batches", response_model=MarketAcquisitionIngestionBatchListResponse)
def owner_list_market_ingestion_batches_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionIngestionBatchListResponse:
    assert current_user.id is not None
    return list_ingestion_batches_owner(
        session,
        owner_user_id=int(current_user.id),
        limit=limit,
        offset=offset,
    )


@app.get("/market-ingestion/batches/{batch_id}", response_model=MarketAcquisitionIngestionBatchRead)
def owner_get_market_ingestion_batch_endpoint(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionIngestionBatchRead:
    assert current_user.id is not None
    return get_ingestion_batch_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)


@app.get("/market-ingestion/batches/{batch_id}/raw", response_model=MarketAcquisitionRawSourceListResponse)
def owner_list_market_ingestion_raw_endpoint(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionRawSourceListResponse:
    assert current_user.id is not None
    return list_ingestion_raw_owner(
        session,
        owner_user_id=int(current_user.id),
        batch_id=batch_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-ingestion/batches", response_model=MarketAcquisitionIngestionBatchListResponse)
def ops_list_market_ingestion_batches_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionIngestionBatchListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_ingestion_batches_ops(
        session,
        owner_user_id=owner_user_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-ingestion/batches/{batch_id}", response_model=MarketAcquisitionIngestionBatchRead)
def ops_get_market_ingestion_batch_endpoint(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketAcquisitionIngestionBatchRead:
    ensure_ops_admin_access(current_user, settings)
    return get_ingestion_batch_ops(session, batch_id=batch_id)


@app.get("/ops/market-ingestion/raw", response_model=MarketAcquisitionRawSourceListResponse)
def ops_list_market_ingestion_raw_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    processing_status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionRawSourceListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_ingestion_raw_ops(
        session,
        owner_user_id=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        processing_status=processing_status,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/market-normalization/run",
    response_model=MarketNormalizationRunDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def owner_create_market_normalization_run_endpoint(
    payload: MarketNormalizationRunCreatePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketNormalizationRunDetailRead:
    assert current_user.id is not None
    body, fresh = execute_market_normalization_run_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if not fresh:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/market-normalization/runs", response_model=MarketNormalizationRunListResponse)
def owner_list_market_normalization_runs_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    ingestion_batch_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketNormalizationRunListResponse:
    assert current_user.id is not None
    return list_normalization_runs_owner(
        session,
        owner_user_id=int(current_user.id),
        ingestion_batch_id=ingestion_batch_id,
        limit=limit,
        offset=offset,
    )


@app.get("/market-normalization/runs/{run_id}", response_model=MarketNormalizationRunDetailRead)
def owner_get_market_normalization_run_endpoint(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketNormalizationRunDetailRead:
    assert current_user.id is not None
    return get_normalization_run_owner(session, owner_user_id=int(current_user.id), run_id=run_id)


@app.get("/market-normalization/candidates", response_model=MarketAcquisitionNormalizedCandidateListResponse)
def owner_list_market_normalization_candidates_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    ingestion_batch_id: int | None = Query(default=None),
    normalization_status: str | None = Query(default=None),
    publisher: Annotated[
        str | None,
        Query(description="Canonical publisher exact match."),
    ] = None,
    condition_band: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionNormalizedCandidateListResponse:
    assert current_user.id is not None
    return list_normalized_candidates_owner(
        session,
        owner_user_id=int(current_user.id),
        ingestion_batch_id=ingestion_batch_id,
        normalization_status=normalization_status,
        canonical_publisher=publisher,
        condition_band=condition_band,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )


@app.get("/market-normalization/issues", response_model=MarketNormalizationIssueListResponse)
def owner_list_market_normalization_issues_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    ingestion_batch_id: int | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketNormalizationIssueListResponse:
    assert current_user.id is not None
    return list_normalization_issues_owner(
        session,
        owner_user_id=int(current_user.id),
        ingestion_batch_id=ingestion_batch_id,
        issue_type=issue_type,
        severity=severity,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-normalization/runs", response_model=MarketNormalizationRunListResponse)
def ops_list_market_normalization_runs_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketNormalizationRunListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_normalization_runs_ops(
        session,
        owner_user_id_filter=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-normalization/candidates", response_model=MarketAcquisitionNormalizedCandidateListResponse)
def ops_list_market_normalization_candidates_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    normalization_status: str | None = Query(default=None),
    publisher: Annotated[
        str | None,
        Query(description="Canonical publisher exact match."),
    ] = None,
    condition_band: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionNormalizedCandidateListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_normalized_candidates_ops(
        session,
        owner_user_id_filter=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        normalization_status=normalization_status,
        canonical_publisher=publisher,
        condition_band=condition_band,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-normalization/issues", response_model=MarketNormalizationIssueListResponse)
def ops_list_market_normalization_issues_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    ingestion_batch_id: int | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    created_since: datetime | None = Query(default=None),
    created_until: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketNormalizationIssueListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_normalization_issues_ops(
        session,
        owner_user_id_filter=owner_user_id,
        ingestion_batch_id=ingestion_batch_id,
        issue_type=issue_type,
        severity=severity,
        created_since=created_since,
        created_until=created_until,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-normalization/runs/{run_id}", response_model=MarketNormalizationRunDetailRead)
def ops_get_market_normalization_run_endpoint(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketNormalizationRunDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return get_normalization_run_ops(session, run_id=run_id)


@app.post("/market-scoring/run", response_model=MarketAcquisitionScoreRunResponse)
def owner_run_market_scoring_endpoint(
    payload: MarketAcquisitionScoreRunPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionScoreRunResponse:
    assert current_user.id is not None
    return run_market_acquisition_scoring_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/market-scoring/scores", response_model=MarketAcquisitionScoreListResponse)
def owner_list_market_scoring_scores_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    score_min: Decimal | None = Query(default=None),
    score_max: Decimal | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionScoreListResponse:
    assert current_user.id is not None
    return list_scores_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        score_min=score_min,
        score_max=score_max,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-scoring/scores/{score_id}", response_model=MarketAcquisitionScoreDetailRead)
def owner_get_market_scoring_score_endpoint(
    score_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionScoreDetailRead:
    assert current_user.id is not None
    return get_score_owner(session, owner_user_id=int(current_user.id), score_id=score_id)


@app.get("/market-scoring/snapshots", response_model=MarketAcquisitionScoreSnapshotListResponse)
def owner_list_market_scoring_snapshots_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionScoreSnapshotListResponse:
    assert current_user.id is not None
    return list_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-scoring/history", response_model=MarketAcquisitionScoreHistoryListResponse)
def owner_list_market_scoring_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionScoreHistoryListResponse:
    assert current_user.id is not None
    return list_market_scoring_history_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-scoring/scores", response_model=MarketAcquisitionScoreListResponse)
def ops_list_market_scoring_scores_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    score_min: Decimal | None = Query(default=None),
    score_max: Decimal | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionScoreListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_scores_ops(
        session,
        owner_user_id=owner_user_id,
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        score_min=score_min,
        score_max=score_max,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-scoring/scores/{score_id}", response_model=MarketAcquisitionScoreDetailRead)
def ops_get_market_scoring_score_endpoint(
    score_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketAcquisitionScoreDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return get_score_ops(session, score_id=score_id)


@app.get("/ops/market-scoring/snapshots", response_model=MarketAcquisitionScoreSnapshotListResponse)
def ops_list_market_scoring_snapshots_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionScoreSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-scoring/history", response_model=MarketAcquisitionScoreHistoryListResponse)
def ops_list_market_scoring_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    recommendation_label: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionScoreHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_scoring_history_ops(
        session,
        owner_user_id=owner_user_id,
        recommendation_label=recommendation_label,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.post("/market-signals/generate", response_model=MarketAcquisitionSignalGenerateResponse)
def owner_generate_market_signals_endpoint(
    payload: MarketAcquisitionSignalGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionSignalGenerateResponse:
    assert current_user.id is not None
    return generate_market_signals_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/market-signals", response_model=MarketAcquisitionSignalListResponse)
def owner_list_market_signals_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalListResponse:
    assert current_user.id is not None
    return list_signals_owner(
        session,
        owner_user_id=int(current_user.id),
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-signals/{signal_id}", response_model=MarketAcquisitionSignalDetailRead)
def owner_get_market_signal_endpoint(
    signal_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionSignalDetailRead:
    assert current_user.id is not None
    return get_signal_owner(session, owner_user_id=int(current_user.id), signal_id=signal_id)


@app.get("/market-signal-snapshots", response_model=MarketAcquisitionSignalSnapshotListResponse)
def owner_list_market_signal_snapshots_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalSnapshotListResponse:
    assert current_user.id is not None
    return list_market_signal_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-signal-evidence", response_model=MarketAcquisitionSignalEvidenceListResponse)
def owner_list_market_signal_evidence_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    signal_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalEvidenceListResponse:
    assert current_user.id is not None
    return list_market_signal_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        signal_id=signal_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-signal-history", response_model=MarketAcquisitionSignalHistoryListResponse)
def owner_list_market_signal_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalHistoryListResponse:
    assert current_user.id is not None
    return list_market_signal_history_owner(
        session,
        owner_user_id=int(current_user.id),
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-signals", response_model=MarketAcquisitionSignalListResponse)
def ops_list_market_signals_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_signals_ops(
        session,
        owner_user_id=owner_user_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-signals/{signal_id}", response_model=MarketAcquisitionSignalDetailRead)
def ops_get_market_signal_endpoint(
    signal_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketAcquisitionSignalDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return get_signal_ops(session, signal_id=signal_id)


@app.get("/ops/market-signal-snapshots", response_model=MarketAcquisitionSignalSnapshotListResponse)
def ops_list_market_signal_snapshots_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_signal_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-signal-evidence", response_model=MarketAcquisitionSignalEvidenceListResponse)
def ops_list_market_signal_evidence_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    signal_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_signal_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        signal_id=signal_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-signal-history", response_model=MarketAcquisitionSignalHistoryListResponse)
def ops_list_market_signal_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionSignalHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_signal_history_ops(
        session,
        owner_user_id=owner_user_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.post("/market-opportunities/generate", response_model=MarketAcquisitionOpportunityGenerateResponse)
def owner_generate_market_opportunities_endpoint(
    payload: MarketAcquisitionOpportunityGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionOpportunityGenerateResponse:
    assert current_user.id is not None
    return generate_market_opportunities_for_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/market-opportunities/snapshots", response_model=MarketAcquisitionOpportunitySnapshotListResponse)
def owner_list_market_opportunity_snapshots_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunitySnapshotListResponse:
    assert current_user.id is not None
    return list_market_opportunity_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-opportunities/evidence", response_model=MarketAcquisitionOpportunityEvidenceListResponse)
def owner_list_market_opportunity_evidence_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunityEvidenceListResponse:
    assert current_user.id is not None
    return list_market_opportunity_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-opportunities/history", response_model=MarketAcquisitionOpportunityHistoryListResponse)
def owner_list_market_opportunity_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunityHistoryListResponse:
    assert current_user.id is not None
    return list_market_opportunity_history_owner(
        session,
        owner_user_id=int(current_user.id),
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-opportunities", response_model=MarketAcquisitionOpportunityItemListResponse)
def owner_list_market_opportunity_items_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunityItemListResponse:
    assert current_user.id is not None
    return list_opportunity_items_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=opportunity_snapshot_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/market-opportunities/{snapshot_id}", response_model=MarketAcquisitionOpportunityDetailRead)
def owner_get_market_opportunity_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketAcquisitionOpportunityDetailRead:
    assert current_user.id is not None
    return get_opportunity_detail_owner(
        session,
        owner_user_id=int(current_user.id),
        opportunity_snapshot_id=snapshot_id,
    )


@app.get("/ops/market-opportunities/snapshots", response_model=MarketAcquisitionOpportunitySnapshotListResponse)
def ops_list_market_opportunity_snapshots_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunitySnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_opportunity_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-opportunities/evidence", response_model=MarketAcquisitionOpportunityEvidenceListResponse)
def ops_list_market_opportunity_evidence_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunityEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_opportunity_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-opportunities/history", response_model=MarketAcquisitionOpportunityHistoryListResponse)
def ops_list_market_opportunity_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunityHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_opportunity_history_ops(
        session,
        owner_user_id=owner_user_id,
        opportunity_snapshot_id=opportunity_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-opportunities", response_model=MarketAcquisitionOpportunityItemListResponse)
def ops_list_market_opportunity_items_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    opportunity_snapshot_id: int | None = Query(default=None, ge=1),
    signal_type: str | None = Query(default=None),
    signal_strength: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> MarketAcquisitionOpportunityItemListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_opportunity_items_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_id=opportunity_snapshot_id,
        signal_type=signal_type,
        signal_strength=signal_strength,
        risk_level=risk_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-opportunities/{snapshot_id}", response_model=MarketAcquisitionOpportunityDetailRead)
def ops_get_market_opportunity_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketAcquisitionOpportunityDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return get_opportunity_detail_ops(session, opportunity_snapshot_id=snapshot_id)


@app.post("/market-portfolio-coupling/generate", response_model=PortfolioMarketCouplingGenerateResponse)
def owner_generate_portfolio_market_coupling_endpoint(
    payload: PortfolioMarketCouplingGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioMarketCouplingGenerateResponse:
    assert current_user.id is not None
    return generate_coupling_for_owner(session, owner_user_id=int(current_user.id), payload=payload)


@app.get("/market-portfolio-coupling/snapshots", response_model=PortfolioMarketCouplingSnapshotListResponse)
def owner_list_portfolio_market_coupling_snapshots_alias_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingSnapshotListResponse:
    assert current_user.id is not None
    return list_coupling_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )


@app.get("/market-portfolio-coupling", response_model=PortfolioMarketCouplingSnapshotListResponse)
def owner_list_portfolio_market_coupling_root_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingSnapshotListResponse:
    assert current_user.id is not None
    return list_coupling_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )


@app.get("/market-portfolio-coupling/edges", response_model=PortfolioMarketCouplingEdgeListResponse)
def owner_list_portfolio_market_coupling_edges_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    coupling_type: str | None = Query(default=None),
    coupling_strength: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_coupling_score: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingEdgeListResponse:
    assert current_user.id is not None
    return list_coupling_edges_owner(
        session,
        owner_user_id=int(current_user.id),
        coupling_snapshot_id=coupling_snapshot_id,
        coupling_type=coupling_type,
        coupling_strength=coupling_strength,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_coupling_score=min_coupling_score,
        limit=limit,
        offset=offset,
    )


@app.get("/market-portfolio-coupling/history", response_model=PortfolioMarketCouplingHistoryListResponse)
def owner_list_portfolio_market_coupling_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingHistoryListResponse:
    assert current_user.id is not None
    return list_coupling_history_owner(
        session,
        owner_user_id=int(current_user.id),
        coupling_snapshot_id=coupling_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )


@app.get("/market-portfolio-coupling/{snapshot_id}", response_model=PortfolioMarketCouplingDetailRead)
def owner_get_portfolio_market_coupling_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioMarketCouplingDetailRead:
    assert current_user.id is not None
    return get_coupling_detail_owner(session, owner_user_id=int(current_user.id), snapshot_id=snapshot_id)


@app.get("/ops/market-portfolio-coupling/snapshots", response_model=PortfolioMarketCouplingSnapshotListResponse)
def ops_list_portfolio_market_coupling_snapshots_alias_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_coupling_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-portfolio-coupling", response_model=PortfolioMarketCouplingSnapshotListResponse)
def ops_list_portfolio_market_coupling_root_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_coupling_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-portfolio-coupling/edges", response_model=PortfolioMarketCouplingEdgeListResponse)
def ops_list_portfolio_market_coupling_edges_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    coupling_type: str | None = Query(default=None),
    coupling_strength: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_coupling_score: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingEdgeListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_coupling_edges_ops(
        session,
        owner_user_id=owner_user_id,
        coupling_snapshot_id=coupling_snapshot_id,
        coupling_type=coupling_type,
        coupling_strength=coupling_strength,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_coupling_score=min_coupling_score,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-portfolio-coupling/history", response_model=PortfolioMarketCouplingHistoryListResponse)
def ops_list_portfolio_market_coupling_history_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    coupling_snapshot_id: int | None = Query(default=None, ge=1),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    min_alignment_score: Decimal | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioMarketCouplingHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_coupling_history_ops(
        session,
        owner_user_id=owner_user_id,
        coupling_snapshot_id=coupling_snapshot_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        min_alignment_score=min_alignment_score,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/market-portfolio-coupling/{snapshot_id}", response_model=PortfolioMarketCouplingDetailRead)
def ops_get_portfolio_market_coupling_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> PortfolioMarketCouplingDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return get_coupling_detail_ops(session, snapshot_id=snapshot_id, owner_filter=owner_user_id)


@app.get("/market-sales", response_model=MarketSaleListResponse)
def owner_list_market_sales_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    publisher: Annotated[str | None, Query(description="Filter by normalized publisher.")] = None,
    normalized_title: Annotated[str | None, Query(description="Filter by normalized title.")] = None,
    normalized_issue: Annotated[str | None, Query(description="Filter by normalized issue.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter graded or raw sale records.")] = None,
    normalization_status: Annotated[str | None, Query(description="Filter by normalization status.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter records sold on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter records sold on or before this date.")] = None,
) -> MarketSaleListResponse:
    del current_user
    return list_market_sales(
        session,
        source=source,
        publisher=publisher,
        normalized_title=normalized_title,
        normalized_issue=normalized_issue,
        grading_company=grading_company,
        is_graded=is_graded,
        normalization_status=normalization_status,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )


@app.get("/market-sales/{market_sale_record_id}", response_model=MarketSaleRead)
def owner_get_market_sale_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketSaleRead:
    assert current_user.id is not None
    return get_market_sale_review_detail(
        session,
        market_sale_record_id=market_sale_record_id,
        ops_mode=False,
        owner_user_id=int(current_user.id),
    )


@app.get("/ops/market-sales", response_model=MarketSaleListResponse)
def ops_list_market_sales_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    publisher: Annotated[str | None, Query(description="Filter by normalized publisher.")] = None,
    normalized_title: Annotated[str | None, Query(description="Filter by normalized title.")] = None,
    normalized_issue: Annotated[str | None, Query(description="Filter by normalized issue.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter graded or raw sale records.")] = None,
    normalization_status: Annotated[str | None, Query(description="Filter by normalization status.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter records sold on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter records sold on or before this date.")] = None,
) -> MarketSaleListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_sales(
        session,
        source=source,
        publisher=publisher,
        normalized_title=normalized_title,
        normalized_issue=normalized_issue,
        grading_company=grading_company,
        is_graded=is_graded,
        normalization_status=normalization_status,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )


@app.get("/ops/market-sales/{market_sale_record_id}", response_model=MarketSaleRead)
def ops_get_market_sale_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleRead:
    ensure_ops_admin_access(current_user, settings)
    return get_market_sale_review_detail(
        session,
        market_sale_record_id=market_sale_record_id,
        ops_mode=True,
        owner_user_id=None,
    )


@app.post("/ops/market-sales", response_model=MarketSaleRead, status_code=status.HTTP_201_CREATED)
def ops_upsert_market_sale_endpoint(
    payload: MarketSaleUpsertPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleRead:
    ensure_ops_admin_access(current_user, settings)
    return upsert_market_sale_record(session, payload=payload)


@app.get("/market-sale-review-queue", response_model=MarketSaleReviewQueueResponse)
def owner_list_market_sale_review_queue_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    classification: Annotated[
        str | None,
        Query(description="Filter by deterministic review classification."),
    ] = None,
    priority: Annotated[str | None, Query(description="Filter by static priority lane.")] = None,
    review_status: Annotated[str | None, Query(description="Filter by record review status.")] = None,
    source: Annotated[str | None, Query(description="Filter by source name or type.")] = None,
    source_type: Annotated[str | None, Query(description="Filter by source type.")] = None,
    issue_type: Annotated[str | None, Query(description="Filter by normalization issue type.")] = None,
) -> MarketSaleReviewQueueResponse:
    assert current_user.id is not None
    return list_market_sale_review_queue(
        session,
        ops_mode=False,
        owner_user_id=int(current_user.id),
        classification=classification,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        review_status=review_status,  # type: ignore[arg-type]
        source=source,
        source_type=source_type,
        issue_type=issue_type,  # type: ignore[arg-type]
    )


@app.get("/market-sale-review-queue/summary", response_model=MarketSaleReviewQueueSummaryRead)
def owner_market_sale_review_queue_summary_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    classification: Annotated[
        str | None,
        Query(description="Filter by deterministic review classification."),
    ] = None,
    priority: Annotated[str | None, Query(description="Filter by static priority lane.")] = None,
    review_status: Annotated[str | None, Query(description="Filter by record review status.")] = None,
    source: Annotated[str | None, Query(description="Filter by source name or type.")] = None,
    source_type: Annotated[str | None, Query(description="Filter by source type.")] = None,
    issue_type: Annotated[str | None, Query(description="Filter by normalization issue type.")] = None,
) -> MarketSaleReviewQueueSummaryRead:
    assert current_user.id is not None
    return market_sale_review_queue_summary(
        session,
        ops_mode=False,
        owner_user_id=int(current_user.id),
        classification=classification,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        review_status=review_status,  # type: ignore[arg-type]
        source=source,
        source_type=source_type,
        issue_type=issue_type,  # type: ignore[arg-type]
    )


@app.get("/market-sales/{market_sale_record_id}/normalization-issues", response_model=list[MarketSaleNormalizationIssueRead])
def owner_get_market_sale_normalization_issues_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[MarketSaleNormalizationIssueRead]:
    assert current_user.id is not None
    return list_market_sale_normalization_issues(
        session,
        market_sale_record_id=market_sale_record_id,
        ops_mode=False,
        owner_user_id=int(current_user.id),
    )


@app.get("/ops/market-sale-review-queue", response_model=MarketSaleReviewQueueResponse)
def ops_list_market_sale_review_queue_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    classification: Annotated[
        str | None,
        Query(description="Filter by deterministic review classification."),
    ] = None,
    priority: Annotated[str | None, Query(description="Filter by static priority lane.")] = None,
    review_status: Annotated[str | None, Query(description="Filter by record review status.")] = None,
    source: Annotated[str | None, Query(description="Filter by source name or type.")] = None,
    source_type: Annotated[str | None, Query(description="Filter by source type.")] = None,
    issue_type: Annotated[str | None, Query(description="Filter by normalization issue type.")] = None,
) -> MarketSaleReviewQueueResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_sale_review_queue(
        session,
        ops_mode=True,
        owner_user_id=None,
        classification=classification,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        review_status=review_status,  # type: ignore[arg-type]
        source=source,
        source_type=source_type,
        issue_type=issue_type,  # type: ignore[arg-type]
    )


@app.get("/ops/market-sale-review-queue/summary", response_model=MarketSaleReviewQueueSummaryRead)
def ops_market_sale_review_queue_summary_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    classification: Annotated[
        str | None,
        Query(description="Filter by deterministic review classification."),
    ] = None,
    priority: Annotated[str | None, Query(description="Filter by static priority lane.")] = None,
    review_status: Annotated[str | None, Query(description="Filter by record review status.")] = None,
    source: Annotated[str | None, Query(description="Filter by source name or type.")] = None,
    source_type: Annotated[str | None, Query(description="Filter by source type.")] = None,
    issue_type: Annotated[str | None, Query(description="Filter by normalization issue type.")] = None,
) -> MarketSaleReviewQueueSummaryRead:
    ensure_ops_admin_access(current_user, settings)
    return market_sale_review_queue_summary(
        session,
        ops_mode=True,
        owner_user_id=None,
        classification=classification,  # type: ignore[arg-type]
        priority=priority,  # type: ignore[arg-type]
        review_status=review_status,  # type: ignore[arg-type]
        source=source,
        source_type=source_type,
        issue_type=issue_type,  # type: ignore[arg-type]
    )


@app.get("/market-comp-eligibility", response_model=MarketSaleCompEligibilityListResponse)
def owner_list_market_comp_eligibility_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    eligibility_status: Annotated[
        MarketCompEligibilityStatus | None,
        Query(description="Filter by overall eligibility status."),
    ] = None,
    eligibility_classification: Annotated[
        MarketCompEligibilityClassification | None,
        Query(description="Filter by deterministic eligibility classification."),
    ] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter graded or raw sale records.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter records sold on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter records sold on or before this date.")] = None,
) -> MarketSaleCompEligibilityListResponse:
    assert current_user.id is not None
    return list_market_comp_eligibility(
        session,
        source=source,
        eligibility_status=eligibility_status,
        eligibility_classification=eligibility_classification,
        grading_company=grading_company,
        is_graded=is_graded,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )


@app.get("/market-sales/{market_sale_record_id}/comp-eligibility", response_model=MarketSaleCompEligibilityRead)
def owner_get_market_comp_eligibility_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketSaleCompEligibilityRead:
    assert current_user.id is not None
    return get_market_comp_eligibility_for_owner(
        session,
        market_sale_record_id=market_sale_record_id,
        owner_user_id=int(current_user.id),
    )


@app.get("/ops/market-comp-eligibility", response_model=MarketSaleCompEligibilityListResponse)
def ops_list_market_comp_eligibility_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    eligibility_status: Annotated[
        MarketCompEligibilityStatus | None,
        Query(description="Filter by overall eligibility status."),
    ] = None,
    eligibility_classification: Annotated[
        MarketCompEligibilityClassification | None,
        Query(description="Filter by deterministic eligibility classification."),
    ] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter graded or raw sale records.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter records sold on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter records sold on or before this date.")] = None,
) -> MarketSaleCompEligibilityListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_comp_eligibility(
        session,
        source=source,
        eligibility_status=eligibility_status,
        eligibility_classification=eligibility_classification,
        grading_company=grading_company,
        is_graded=is_graded,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )


@app.get("/ops/market-sales/{market_sale_record_id}/comp-eligibility", response_model=MarketSaleCompEligibilityRead)
def ops_get_market_comp_eligibility_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleCompEligibilityRead:
    ensure_ops_admin_access(current_user, settings)
    return get_market_comp_eligibility_for_ops(session, market_sale_record_id=market_sale_record_id)


@app.get("/market-comps", response_model=MarketComparableListResponse)
def owner_list_market_comps_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    metadata_identity_key: Annotated[str | None, Query(description="Filter by metadata identity key.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter raw or graded sale records.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    normalized_grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter comps on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter comps on or before this date.")] = None,
    include_excluded: Annotated[bool, Query(description="Include excluded comps in grouped results.")] = False,
) -> MarketComparableListResponse:
    assert current_user.id is not None
    return list_market_comps(
        session,
        source=source,
        metadata_identity_key=metadata_identity_key,
        is_graded=is_graded,
        grading_company=grading_company,
        normalized_grade=normalized_grade,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
        include_excluded=include_excluded,
    )


@app.get("/market-comps/by-identity/{metadata_identity_key}", response_model=MarketComparableListResponse)
def owner_list_market_comps_by_identity_endpoint(
    metadata_identity_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter raw or graded sale records.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    normalized_grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter comps on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter comps on or before this date.")] = None,
    include_excluded: Annotated[bool, Query(description="Include excluded comps in grouped results.")] = False,
) -> MarketComparableListResponse:
    assert current_user.id is not None
    return list_market_comps(
        session,
        source=source,
        metadata_identity_key=metadata_identity_key,
        is_graded=is_graded,
        grading_company=grading_company,
        normalized_grade=normalized_grade,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
        include_excluded=include_excluded,
    )


@app.get("/ops/market-comps", response_model=MarketComparableListResponse)
def ops_list_market_comps_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    metadata_identity_key: Annotated[str | None, Query(description="Filter by metadata identity key.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter raw or graded sale records.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    normalized_grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter comps on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter comps on or before this date.")] = None,
    include_excluded: Annotated[bool, Query(description="Include excluded comps in grouped results.")] = False,
) -> MarketComparableListResponse:
    if not is_ops_admin_user(current_user, Settings()):
        raise HTTPException(status_code=403, detail="Operations dashboard access denied")
    return list_market_comps(
        session,
        source=source,
        metadata_identity_key=metadata_identity_key,
        is_graded=is_graded,
        grading_company=grading_company,
        normalized_grade=normalized_grade,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
        include_excluded=include_excluded,
    )


@app.get("/ops/market-comps/by-identity/{metadata_identity_key}", response_model=MarketComparableListResponse)
def ops_list_market_comps_by_identity_endpoint(
    metadata_identity_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    is_graded: Annotated[bool | None, Query(description="Filter raw or graded sale records.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    normalized_grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    sale_date_from: Annotated[date | None, Query(description="Filter comps on or after this date.")] = None,
    sale_date_to: Annotated[date | None, Query(description="Filter comps on or before this date.")] = None,
    include_excluded: Annotated[bool, Query(description="Include excluded comps in grouped results.")] = False,
) -> MarketComparableListResponse:
    if not is_ops_admin_user(current_user, Settings()):
        raise HTTPException(status_code=403, detail="Operations dashboard access denied")
    return list_market_comps(
        session,
        source=source,
        metadata_identity_key=metadata_identity_key,
        is_graded=is_graded,
        grading_company=grading_company,
        normalized_grade=normalized_grade,
        currency=currency,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
        include_excluded=include_excluded,
    )


@app.get("/market-fmv", response_model=MarketFmvSnapshotListResponse)
def owner_list_market_fmv_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_scope: Annotated[MarketFmvSnapshotScope | None, Query(description="Filter by FMV snapshot scope.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    normalized_grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
    confidence_bucket: Annotated[
        MarketFmvConfidenceBucket | None,
        Query(description="Filter by deterministic confidence bucket."),
    ] = None,
    liquidity_bucket: Annotated[
        MarketFmvLiquidityBucket | None,
        Query(description="Filter by deterministic liquidity bucket."),
    ] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale snapshot rows.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    snapshot_date_from: Annotated[date | None, Query(description="Filter snapshots on or after this date.")] = None,
    snapshot_date_to: Annotated[date | None, Query(description="Filter snapshots on or before this date.")] = None,
) -> MarketFmvSnapshotListResponse:
    assert current_user.id is not None
    return list_market_fmv_snapshots(
        session,
        snapshot_scope=snapshot_scope,
        grading_company=grading_company,
        normalized_grade=normalized_grade,
        confidence_bucket=confidence_bucket,
        liquidity_bucket=liquidity_bucket,
        stale_data=stale_data,
        currency=currency,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )


@app.get("/market-fmv/{snapshot_id}", response_model=MarketFmvSnapshotRead)
def owner_get_market_fmv_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketFmvSnapshotRead:
    assert current_user.id is not None
    return get_market_fmv_snapshot(session, snapshot_id=snapshot_id)


@app.get("/market-fmv/by-identity/{metadata_identity_key}", response_model=MarketFmvSnapshotListResponse)
def owner_get_market_fmv_by_identity_endpoint(
    metadata_identity_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketFmvSnapshotListResponse:
    assert current_user.id is not None
    return list_market_fmv_snapshots(session, metadata_identity_key=metadata_identity_key)


@app.get("/market-fmv/{snapshot_id}/comps", response_model=MarketComparableSnapshotCompsResponse)
def owner_get_market_fmv_snapshot_comps_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    include_excluded: Annotated[bool, Query(description="Include excluded comps in grouped results.")] = False,
) -> MarketComparableSnapshotCompsResponse:
    assert current_user.id is not None
    return get_market_fmv_snapshot_comps(session, snapshot_id=snapshot_id, include_excluded=include_excluded)


@app.post("/ops/market-fmv/generate", response_model=MarketFmvGenerateResponse)
def ops_generate_market_fmv_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketFmvGenerateResponse:
    ensure_ops_admin_access(current_user, settings)
    return generate_market_fmv_snapshots(session)


@app.get("/ops/market-fmv", response_model=MarketFmvSnapshotListResponse)
def ops_list_market_fmv_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    snapshot_scope: Annotated[MarketFmvSnapshotScope | None, Query(description="Filter by FMV snapshot scope.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    normalized_grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
    confidence_bucket: Annotated[
        MarketFmvConfidenceBucket | None,
        Query(description="Filter by deterministic confidence bucket."),
    ] = None,
    liquidity_bucket: Annotated[
        MarketFmvLiquidityBucket | None,
        Query(description="Filter by deterministic liquidity bucket."),
    ] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale snapshot rows.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    snapshot_date_from: Annotated[date | None, Query(description="Filter snapshots on or after this date.")] = None,
    snapshot_date_to: Annotated[date | None, Query(description="Filter snapshots on or before this date.")] = None,
) -> MarketFmvSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_fmv_snapshots(
        session,
        snapshot_scope=snapshot_scope,
        grading_company=grading_company,
        normalized_grade=normalized_grade,
        confidence_bucket=confidence_bucket,
        liquidity_bucket=liquidity_bucket,
        stale_data=stale_data,
        currency=currency,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
    )


@app.get("/ops/market-fmv/{snapshot_id}", response_model=MarketFmvSnapshotRead)
def ops_get_market_fmv_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketFmvSnapshotRead:
    ensure_ops_admin_access(current_user, settings)
    return get_market_fmv_snapshot(session, snapshot_id=snapshot_id)


@app.get("/ops/market-fmv/{snapshot_id}/comps", response_model=MarketComparableSnapshotCompsResponse, include_in_schema=False)
def ops_get_market_fmv_snapshot_comps_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    include_excluded: Annotated[bool, Query(description="Include excluded comps in grouped results.")] = False,
) -> MarketComparableSnapshotCompsResponse:
    ensure_ops_admin_access(current_user, settings)
    return get_market_fmv_snapshot_comps(session, snapshot_id=snapshot_id, include_excluded=include_excluded)


@app.get("/market-trends", response_model=MarketTrendSnapshotListResponse)
def owner_list_market_trends_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_scope: Annotated[MarketTrendSnapshotScope | None, Query(description="Filter by trend snapshot scope.")] = None,
    trend_direction: Annotated[MarketTrendDirection | None, Query(description="Filter by trend direction.")] = None,
    trend_strength: Annotated[MarketTrendStrength | None, Query(description="Filter by trend strength.")] = None,
    liquidity_direction: Annotated[
        MarketTrendLiquidityDirection | None,
        Query(description="Filter by liquidity direction."),
    ] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale trend rows.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    trend_window: Annotated[MarketTrendWindow | None, Query(description="Filter by trend window.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
) -> MarketTrendSnapshotListResponse:
    assert current_user.id is not None
    return list_market_trends(
        session,
        snapshot_scope=snapshot_scope,
        grading_company=grading_company,
        grade=grade,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        liquidity_direction=liquidity_direction,
        stale_data=stale_data,
        currency=currency,
        trend_window=trend_window,
    )


@app.get("/market-trends/by-identity/{metadata_identity_key}", response_model=MarketTrendSnapshotListResponse)
def owner_list_market_trends_by_identity_endpoint(
    metadata_identity_key: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_scope: Annotated[MarketTrendSnapshotScope | None, Query(description="Filter by trend snapshot scope.")] = None,
    trend_direction: Annotated[MarketTrendDirection | None, Query(description="Filter by trend direction.")] = None,
    trend_strength: Annotated[MarketTrendStrength | None, Query(description="Filter by trend strength.")] = None,
    liquidity_direction: Annotated[
        MarketTrendLiquidityDirection | None,
        Query(description="Filter by liquidity direction."),
    ] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale trend rows.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    trend_window: Annotated[MarketTrendWindow | None, Query(description="Filter by trend window.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
) -> MarketTrendSnapshotListResponse:
    assert current_user.id is not None
    return list_market_trends(
        session,
        snapshot_scope=snapshot_scope,
        grading_company=grading_company,
        grade=grade,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        liquidity_direction=liquidity_direction,
        stale_data=stale_data,
        currency=currency,
        trend_window=trend_window,
        metadata_identity_key=metadata_identity_key,
    )


@app.get("/market-trends/{snapshot_id}", response_model=MarketTrendSnapshotRead)
def owner_get_market_trend_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketTrendSnapshotRead:
    assert current_user.id is not None
    return get_market_trend_snapshot(session, snapshot_id=snapshot_id)


@app.post("/ops/market-trends/generate", response_model=MarketTrendGenerateResponse)
def ops_generate_market_trends_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketTrendGenerateResponse:
    ensure_ops_admin_access(current_user, settings)
    return generate_market_trend_snapshots(session)


@app.get("/ops/market-trends", response_model=MarketTrendSnapshotListResponse)
def ops_list_market_trends_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    snapshot_scope: Annotated[MarketTrendSnapshotScope | None, Query(description="Filter by trend snapshot scope.")] = None,
    trend_direction: Annotated[MarketTrendDirection | None, Query(description="Filter by trend direction.")] = None,
    trend_strength: Annotated[MarketTrendStrength | None, Query(description="Filter by trend strength.")] = None,
    liquidity_direction: Annotated[
        MarketTrendLiquidityDirection | None,
        Query(description="Filter by liquidity direction."),
    ] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale trend rows.")] = None,
    currency: Annotated[str | None, Query(description="Filter by currency code.")] = None,
    trend_window: Annotated[MarketTrendWindow | None, Query(description="Filter by trend window.")] = None,
    grading_company: Annotated[str | None, Query(description="Filter by grading company.")] = None,
    grade: Annotated[str | None, Query(description="Filter by normalized grade.")] = None,
) -> MarketTrendSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_trends(
        session,
        snapshot_scope=snapshot_scope,
        grading_company=grading_company,
        grade=grade,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        liquidity_direction=liquidity_direction,
        stale_data=stale_data,
        currency=currency,
        trend_window=trend_window,
    )


@app.get("/ops/market-trends/{snapshot_id}", response_model=MarketTrendSnapshotRead)
def ops_get_market_trend_snapshot_endpoint(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketTrendSnapshotRead:
    ensure_ops_admin_access(current_user, settings)
    return get_market_trend_snapshot(session, snapshot_id=snapshot_id)


@app.get("/ops/market-sales/{market_sale_record_id}/normalization-issues", response_model=list[MarketSaleNormalizationIssueRead])
def ops_get_market_sale_normalization_issues_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[MarketSaleNormalizationIssueRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_market_sale_normalization_issues(
        session,
        market_sale_record_id=market_sale_record_id,
        ops_mode=True,
        owner_user_id=None,
    )


@app.patch("/ops/market-sales/{market_sale_record_id}/normalization", response_model=MarketSaleRead)
def ops_patch_market_sale_normalization_endpoint(
    market_sale_record_id: int,
    payload: MarketSaleNormalizationUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleRead:
    ensure_ops_admin_access(current_user, settings)
    return update_market_sale_normalization(
        session,
        market_sale_record_id=market_sale_record_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@app.post("/ops/market-sales/{market_sale_record_id}/ignore", response_model=MarketSaleRead)
def ops_ignore_market_sale_record_endpoint(
    market_sale_record_id: int,
    payload: MarketSaleReviewActionPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleRead:
    ensure_ops_admin_access(current_user, settings)
    return ignore_market_sale_record(
        session,
        market_sale_record_id=market_sale_record_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@app.post("/ops/market-sales/{market_sale_record_id}/flag-duplicate", response_model=MarketSaleRead)
def ops_flag_duplicate_market_sale_record_endpoint(
    market_sale_record_id: int,
    payload: MarketSaleReviewActionPayload | None = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleRead:
    ensure_ops_admin_access(current_user, settings)
    return flag_duplicate_market_sale_record(
        session,
        market_sale_record_id=market_sale_record_id,
        actor_user_id=current_user.id,
        payload=payload,
    )


@app.get("/market-sales/{market_sale_record_id}/match-suggestions", response_model=list[MarketSaleMatchSuggestionRead])
def owner_get_market_sale_match_suggestions_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[MarketSaleMatchSuggestionRead]:
    assert current_user.id is not None
    return get_market_sale_match_suggestion_for_owner(
        session,
        market_sale_record_id=market_sale_record_id,
        owner_user_id=int(current_user.id),
    )


@app.get("/market-match-suggestions", response_model=MarketSaleMatchSuggestionOpsListResponse)
def owner_list_market_sale_match_suggestions_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    confidence_bucket: Annotated[
        MarketSaleMatchSuggestionConfidenceBucket | None,
        Query(description="Filter by confidence bucket."),
    ] = None,
    review_state: Annotated[
        MarketSaleMatchSuggestionReviewState | None,
        Query(description="Filter by suggestion review state."),
    ] = None,
    suggestion_type: Annotated[
        MarketSaleMatchSuggestionType | None,
        Query(description="Filter by suggestion type."),
    ] = None,
) -> MarketSaleMatchSuggestionOpsListResponse:
    assert current_user.id is not None
    return list_market_sale_match_suggestions(
        session,
        ops_mode=False,
        owner_user_id=int(current_user.id),
        source=source,
        confidence_bucket=confidence_bucket,
        review_state=review_state,
        suggestion_type=suggestion_type,
    )


@app.get("/ops/market-sales/{market_sale_record_id}/match-suggestions", response_model=list[MarketSaleMatchSuggestionRead])
def ops_get_market_sale_match_suggestions_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[MarketSaleMatchSuggestionRead]:
    ensure_ops_admin_access(current_user, settings)
    return get_market_sale_match_suggestion_for_ops(session, market_sale_record_id=market_sale_record_id)


@app.post("/ops/market-sales/{market_sale_record_id}/generate-match-suggestions", response_model=MarketSaleMatchSuggestionGenerateResponse)
def ops_generate_market_sale_match_suggestions_endpoint(
    market_sale_record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleMatchSuggestionGenerateResponse:
    ensure_ops_admin_access(current_user, settings)
    return generate_market_sale_match_suggestions(
        session,
        market_sale_record_id=market_sale_record_id,
        actor_user_id=current_user.id,
    )


@app.get("/ops/market-match-suggestions", response_model=MarketSaleMatchSuggestionOpsListResponse)
def ops_list_market_sale_match_suggestions_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    source: Annotated[str | None, Query(description="Filter by market source name or type.")] = None,
    confidence_bucket: Annotated[
        MarketSaleMatchSuggestionConfidenceBucket | None,
        Query(description="Filter by confidence bucket."),
    ] = None,
    review_state: Annotated[
        MarketSaleMatchSuggestionReviewState | None,
        Query(description="Filter by suggestion review state."),
    ] = None,
    suggestion_type: Annotated[
        MarketSaleMatchSuggestionType | None,
        Query(description="Filter by suggestion type."),
    ] = None,
) -> MarketSaleMatchSuggestionOpsListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_sale_match_suggestions(
        session,
        ops_mode=True,
        owner_user_id=None,
        source=source,
        confidence_bucket=confidence_bucket,
        review_state=review_state,
        suggestion_type=suggestion_type,
    )


@app.patch("/ops/market-match-suggestions/{suggestion_id}/approve", response_model=MarketSaleMatchSuggestionReviewActionResponse)
def ops_approve_market_sale_match_suggestion_endpoint(
    suggestion_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleMatchSuggestionReviewActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return approve_market_sale_match_suggestion_for_ops(session, suggestion_id=suggestion_id, actor_user_id=current_user.id)


@app.patch("/ops/market-match-suggestions/{suggestion_id}/reject", response_model=MarketSaleMatchSuggestionReviewActionResponse)
def ops_reject_market_sale_match_suggestion_endpoint(
    suggestion_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleMatchSuggestionReviewActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return reject_market_sale_match_suggestion_for_ops(session, suggestion_id=suggestion_id, actor_user_id=current_user.id)


@app.patch("/ops/market-match-suggestions/{suggestion_id}/ignore", response_model=MarketSaleMatchSuggestionReviewActionResponse)
def ops_ignore_market_sale_match_suggestion_endpoint(
    suggestion_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSaleMatchSuggestionReviewActionResponse:
    ensure_ops_admin_access(current_user, settings)
    return ignore_market_sale_match_suggestion_for_ops(session, suggestion_id=suggestion_id, actor_user_id=current_user.id)


@app.get("/market-sources", response_model=list[MarketSourceRead])
def owner_list_market_sources_endpoint(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)) -> list[MarketSourceRead]:
    del current_user
    return list_market_sources(session)


@app.get("/market-sources/{market_source_id}", response_model=MarketSourceRead)
def owner_get_market_source_endpoint(
    market_source_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketSourceRead:
    del current_user
    return get_market_source_read(session, market_source_id=market_source_id)


@app.get("/market-import-runs", response_model=MarketSourceImportRunListResponse)
def owner_list_market_import_runs_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketSourceImportRunListResponse:
    assert current_user.id is not None
    return list_market_import_runs_for_owner(session, current_user_id=int(current_user.id))


@app.get("/market-import-runs/{run_id}", response_model=MarketSourceImportRunRead)
def owner_get_market_import_run_endpoint(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MarketSourceImportRunRead:
    assert current_user.id is not None
    return get_market_import_run_for_owner(session, current_user_id=int(current_user.id), run_id=run_id)


@app.get("/ops/market-sources", response_model=list[MarketSourceRead], include_in_schema=False)
def ops_list_market_sources_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> list[MarketSourceRead]:
    ensure_ops_admin_access(current_user, settings)
    return list_market_sources(session)


@app.get("/ops/market-import-runs", response_model=MarketSourceImportRunListResponse, include_in_schema=False)
def ops_list_market_import_runs_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSourceImportRunListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_market_import_runs_for_ops(session)


@app.post("/ops/market-import-runs", response_model=MarketSourceImportRunRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def ops_create_market_import_run_endpoint(
    payload: MarketSourceImportRunCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSourceImportRunRead:
    ensure_ops_admin_access(current_user, settings)
    return create_market_import_run_for_ops(session, actor_user_id=current_user.id, payload=payload)


@app.post("/ops/market-import-runs/{run_id}/start", response_model=MarketSourceImportRunRead, include_in_schema=False)
def ops_start_market_import_run_endpoint(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSourceImportRunRead:
    ensure_ops_admin_access(current_user, settings)
    return start_market_import_run_for_ops(session, run_id=run_id, actor_user_id=current_user.id)


@app.post("/ops/market-import-runs/{run_id}/cancel", response_model=MarketSourceImportRunRead, include_in_schema=False)
def ops_cancel_market_import_run_endpoint(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSourceImportRunRead:
    ensure_ops_admin_access(current_user, settings)
    return cancel_market_import_run_for_ops(session, run_id=run_id, actor_user_id=current_user.id)


@app.post("/ops/market-import-runs/{run_id}/complete", response_model=MarketSourceImportRunRead, include_in_schema=False)
def ops_complete_market_import_run_endpoint(
    run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> MarketSourceImportRunRead:
    ensure_ops_admin_access(current_user, settings)
    return complete_market_import_run_for_ops(session, run_id=run_id, actor_user_id=current_user.id)


@app.post("/scan-pipeline-replays", response_model=ScanPipelineReplayRunRead, status_code=status.HTTP_201_CREATED)
def owner_create_scan_pipeline_replay_endpoint(
    payload: ScanPipelineReplayCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanPipelineReplayRunRead:
    assert current_user.id is not None
    return create_scan_pipeline_replay_run(session, owner_user_id=int(current_user.id), payload=payload)


@app.get("/scan-pipeline-replays", response_model=ScanPipelineReplayListRead)
def owner_list_scan_pipeline_replays_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    scan_session_id: Annotated[int | None, Query(description="Filter runs for a scan session.")] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanPipelineReplayListRead:
    assert current_user.id is not None
    return list_scan_pipeline_replay_runs_owner(
        session, owner_user_id=int(current_user.id), scan_session_id=scan_session_id, limit=limit, offset=offset
    )


@app.get("/scan-pipeline-replays/{replay_id}", response_model=ScanPipelineReplayRunRead)
def owner_get_scan_pipeline_replay_endpoint(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanPipelineReplayRunRead:
    assert current_user.id is not None
    return get_scan_pipeline_replay_run_for_owner(session, owner_user_id=int(current_user.id), replay_id=replay_id)


@app.post("/scan-pipeline-replays/{replay_id}/start", response_model=ScanPipelineReplayRunRead)
def owner_start_scan_pipeline_replay_endpoint(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanPipelineReplayRunRead:
    assert current_user.id is not None
    return start_scan_pipeline_replay_run(session, owner_user_id=int(current_user.id), replay_id=replay_id)


@app.post("/scan-pipeline-replays/{replay_id}/cancel", response_model=ScanPipelineReplayRunRead)
def owner_cancel_scan_pipeline_replay_endpoint(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanPipelineReplayRunRead:
    assert current_user.id is not None
    return cancel_scan_pipeline_replay_run(session, owner_user_id=int(current_user.id), replay_id=replay_id)


@app.post("/scan-sessions", response_model=ScanSessionSummaryRead, status_code=status.HTTP_201_CREATED)
def owner_create_scan_session(
    payload: ScanSessionCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionSummaryRead:
    assert current_user.id is not None
    return create_scan_session(session, owner_user_id=int(current_user.id), payload=payload)


@app.get("/scan-sessions/dashboard", response_model=ScanSessionDashboardResponse)
def owner_scan_sessions_dashboard_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionDashboardResponse:
    assert current_user.id is not None
    active_trim, recent_trim = owner_scan_session_dashboard(session, owner_user_id=int(current_user.id))
    return ScanSessionDashboardResponse(active_sessions=active_trim, recent_sessions=recent_trim)


@app.get("/scan-pipeline-dashboard/summary", response_model=ScanPipelineDashboardSummaryRead)
def owner_scan_pipeline_dashboard_summary_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanPipelineDashboardSummaryRead:
    assert current_user.id is not None
    return scan_pipeline_dashboard_summary(session, owner_user_id=int(current_user.id))


@app.get("/scan-pipeline-dashboard", response_model=ScanPipelineDashboardRead)
def owner_scan_pipeline_dashboard_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanPipelineDashboardRead:
    assert current_user.id is not None
    return scan_pipeline_dashboard(session, owner_user_id=int(current_user.id))


@app.get("/scan-sessions", response_model=ScanSessionListResponse)
def owner_list_scan_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status_filter: Annotated[ScanSessionStatus | None, Query(alias="status")] = None,
    session_type: Annotated[ScanSessionType | None, Query(alias="session_type")] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanSessionListResponse:
    assert current_user.id is not None
    rows = list_scan_sessions(
        session,
        owner_user_id=int(current_user.id),
        status=status_filter,
        session_type=session_type,
        limit=limit,
        offset=offset,
    )
    return ScanSessionListResponse(sessions=rows)


@app.get("/scan-sessions/{session_id}", response_model=ScanSessionDetailRead)
def owner_get_scan_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionDetailRead:
    assert current_user.id is not None
    return get_scan_session_detail(session, owner_user_id=int(current_user.id), session_id=session_id)


@app.get("/scan-sessions/{session_id}/items", response_model=ScanSessionItemsListRead)
def owner_list_scan_session_items_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: Annotated[int, Query(ge=1, le=2500)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanSessionItemsListRead:
    assert current_user.id is not None
    return list_scan_session_items_read(
        session,
        owner_user_id=int(current_user.id),
        session_id=session_id,
        limit=int(limit),
        offset=int(offset),
    )


@app.get("/scan-sessions/{session_id}/qa", response_model=ScanSessionQaSummaryRead)
def owner_get_scan_session_qa_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionQaSummaryRead:
    assert current_user.id is not None
    return get_scan_session_qa(session, owner_user_id=int(current_user.id), scan_session_id=session_id)


@app.get("/scan-sessions/{session_id}/items/{item_id}/qa", response_model=ScanQaItemRead)
def owner_get_scan_session_item_qa_endpoint(
    session_id: int,
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanQaItemRead:
    assert current_user.id is not None
    return get_scan_session_item_qa(session, owner_user_id=int(current_user.id), scan_session_id=session_id, item_id=item_id)


@app.post("/scan-sessions/{session_id}/run-qa", response_model=ScanSessionQaSummaryRead)
def owner_run_scan_session_qa_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionQaSummaryRead:
    assert current_user.id is not None
    return run_scan_session_qa(session, owner_user_id=int(current_user.id), scan_session_id=session_id)


@app.get("/scan-routing-recommendations", response_model=QueueRoutingListResponse)
def owner_list_queue_routing_recommendations_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> QueueRoutingListResponse:
    assert current_user.id is not None
    return list_queue_routing_recommendations_owner(session, owner_user_id=int(current_user.id))


@app.get("/scan-sessions/{session_id}/routing", response_model=ScanSessionRoutingRead)
def owner_get_scan_session_routing_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionRoutingRead:
    assert current_user.id is not None
    return get_scan_session_routing(session, owner_user_id=int(current_user.id), scan_session_id=session_id)


@app.post("/scan-sessions/{session_id}/generate-routing", response_model=ScanSessionRoutingRead)
def owner_generate_scan_session_routing_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionRoutingRead:
    assert current_user.id is not None
    return generate_scan_session_routing(session, owner_user_id=int(current_user.id), scan_session_id=session_id)


@app.post("/scan-routing-recommendations/{recommendation_id}/acknowledge", response_model=QueueRoutingRecommendationRead)
def owner_acknowledge_queue_routing_recommendation_endpoint(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> QueueRoutingRecommendationRead:
    assert current_user.id is not None
    return acknowledge_queue_routing_recommendation(
        session,
        recommendation_id=recommendation_id,
        owner_user_id=int(current_user.id),
    )


@app.post("/scan-routing-recommendations/{recommendation_id}/dismiss", response_model=QueueRoutingRecommendationRead)
def owner_dismiss_queue_routing_recommendation_endpoint(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> QueueRoutingRecommendationRead:
    assert current_user.id is not None
    return dismiss_queue_routing_recommendation(
        session,
        recommendation_id=recommendation_id,
        owner_user_id=int(current_user.id),
    )


@app.post("/scan-sessions/{session_id}/ingest-files", response_model=ScanSessionDetailRead)
async def owner_ingest_scan_session_files_endpoint(
    session_id: int,
    files: Annotated[list[UploadFile], File()],
    manifest: Annotated[str, Form()] = '{"items":[]}',
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanSessionDetailRead:
    assert current_user.id is not None
    if not files:
        raise HTTPException(status_code=422, detail="At least one upload file is required.")
    try:
        manifest_payload = ScanSessionIngestManifest.model_validate_json(manifest)
    except (ValueError, TypeError, ValidationError):
        raise HTTPException(status_code=422, detail="manifest must be JSON matching ScanSessionIngestManifest")

    slots: list[ParsedScanUploadSlot] = []
    for idx, upload in enumerate(files):
        blob = await upload.read()
        row = manifest_payload.items[idx] if idx < len(manifest_payload.items) else ScanSessionIngestManifestRow()
        slots.append(
            ParsedScanUploadSlot(
                body=blob,
                declared_content_type=upload.content_type,
                upload_filename=upload.filename,
                manifest_row=row,
            ),
        )

    return ingest_uploaded_images_into_scan_session(
        session,
        settings,
        owner_user_id=int(current_user.id),
        scan_session_id=session_id,
        slots=slots,
    )


@app.post("/scan-sessions/{session_id}/items", response_model=ScanSessionDetailRead)
def owner_append_scan_session_items(
    session_id: int,
    payload: ScanSessionItemsAppendPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionDetailRead:
    assert current_user.id is not None
    return append_scan_session_items(
        session,
        owner_user_id=int(current_user.id),
        session_id=session_id,
        payload=payload,
    )


@app.patch("/scan-sessions/{session_id}/items/{item_id}", response_model=ScanSessionDetailRead)
def owner_patch_scan_session_item(
    session_id: int,
    item_id: int,
    payload: ScanSessionItemUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionDetailRead:
    assert current_user.id is not None
    return patch_scan_session_item(
        session,
        owner_user_id=int(current_user.id),
        session_id=session_id,
        item_id=item_id,
        payload=payload,
    )


@app.post("/scan-sessions/{session_id}/start", response_model=ScanSessionSummaryRead)
def owner_start_scan_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionSummaryRead:
    assert current_user.id is not None
    return start_scan_session(session, owner_user_id=int(current_user.id), session_id=session_id)


@app.post("/scan-sessions/{session_id}/pause", response_model=ScanSessionSummaryRead)
def owner_pause_scan_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionSummaryRead:
    assert current_user.id is not None
    return pause_scan_session(session, owner_user_id=int(current_user.id), session_id=session_id)


@app.post("/scan-sessions/{session_id}/cancel", response_model=ScanSessionSummaryRead)
def owner_cancel_scan_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionSummaryRead:
    assert current_user.id is not None
    return cancel_scan_session(session, owner_user_id=int(current_user.id), session_id=session_id)


@app.post("/scan-sessions/{session_id}/complete", response_model=ScanSessionSummaryRead)
def owner_complete_scan_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionSummaryRead:
    assert current_user.id is not None
    return complete_scan_session(session, owner_user_id=int(current_user.id), session_id=session_id)


@app.post("/high-res-review-requests", response_model=HighResReviewRequestRead)
def owner_create_high_res_review_request(
    payload: HighResReviewRequestCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HighResReviewRequestRead:
    assert current_user.id is not None
    return create_high_res_review_request(session, owner_user_id=int(current_user.id), payload=payload)


@app.get("/high-res-review-requests/stats", response_model=HighResReviewRequestStatsRead)
def owner_high_res_review_requests_stats_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HighResReviewRequestStatsRead:
    assert current_user.id is not None
    return high_res_review_request_stats_owner(session, owner_user_id=int(current_user.id))


@app.get("/high-res-review-requests", response_model=HighResReviewRequestListResponse)
def owner_list_high_res_review_requests_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    inventory_copy_id: Annotated[int | None, Query(ge=1)] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    priority: Annotated[str | None, Query()] = None,
    reason: Annotated[str | None, Query(alias="reason")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HighResReviewRequestListResponse:
    assert current_user.id is not None
    return list_high_res_review_requests_owner(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
        status_filter=status_filter,
        priority_filter=priority,
        reason_filter=reason,
        limit=int(limit),
        offset=int(offset),
    )


@app.get("/high-res-review-requests/{request_id}", response_model=HighResReviewRequestRead)
def owner_get_high_res_review_request_endpoint(
    request_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HighResReviewRequestRead:
    assert current_user.id is not None
    return get_high_res_review_request_detail(session, owner_user_id=int(current_user.id), request_id=request_id)


@app.post("/high-res-review-requests/{request_id}/attach-scan", response_model=HighResReviewRequestRead)
async def owner_attach_high_res_review_scan_endpoint(
    request_id: int,
    file: Annotated[UploadFile, File(description="Deterministic Epson/flatbed high-resolution scan.")],
    source_filename: Annotated[str | None, Form()] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> HighResReviewRequestRead:
    assert current_user.id is not None
    body = await file.read()
    return attach_high_res_review_scan_multipart(
        session,
        settings,
        owner_user_id=int(current_user.id),
        request_id=request_id,
        body=body,
        declared_content_type=file.content_type,
        source_filename=source_filename if source_filename else file.filename,
    )


@app.post("/high-res-review-requests/{request_id}/cancel", response_model=HighResReviewRequestRead)
def owner_cancel_high_res_review_request_endpoint(
    request_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HighResReviewRequestRead:
    assert current_user.id is not None
    return cancel_high_res_review_request(session, owner_user_id=int(current_user.id), request_id=request_id)


@app.post("/high-res-review-requests/{request_id}/complete", response_model=HighResReviewRequestRead)
def owner_complete_high_res_review_request_endpoint(
    request_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> HighResReviewRequestRead:
    assert current_user.id is not None
    return complete_high_res_review_request(session, owner_user_id=int(current_user.id), request_id=request_id)


@app.get("/ops/scanner-profiles", response_model=ScannerProfileListResponse, include_in_schema=False)
def ops_list_scanner_profiles_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScannerProfileListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_scanner_profiles_ops(session)


@app.get("/ops/scan-pipeline-replays", response_model=ScanPipelineReplayListRead, include_in_schema=False)
def ops_list_scan_pipeline_replays_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    scan_session_id: Annotated[int | None, Query(description="Filter runs for a scan session.")] = None,
    owner_user_id: Annotated[int | None, Query(description="Filter runs by deterministic owner user id.")] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanPipelineReplayListRead:
    ensure_ops_admin_access(current_user, settings)
    return list_scan_pipeline_replay_runs_ops(
        session,
        scan_session_id=scan_session_id,
        owner_user_id=owner_user_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/scan-pipeline-replays/{replay_id}", response_model=ScanPipelineReplayRunRead, include_in_schema=False)
def ops_get_scan_pipeline_replay_endpoint(
    replay_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanPipelineReplayRunRead:
    ensure_ops_admin_access(current_user, settings)
    return get_scan_pipeline_replay_run_ops(session, replay_id=replay_id)


@app.get("/ops/scan-pipeline-dashboard/summary", response_model=ScanPipelineDashboardSummaryRead, include_in_schema=False)
def ops_scan_pipeline_dashboard_summary_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanPipelineDashboardSummaryRead:
    ensure_ops_admin_access(current_user, settings)
    return scan_pipeline_dashboard_summary(session, owner_user_id=None)


@app.get("/ops/scan-pipeline-dashboard", response_model=ScanPipelineDashboardRead, include_in_schema=False)
def ops_scan_pipeline_dashboard_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanPipelineDashboardRead:
    ensure_ops_admin_access(current_user, settings)
    return scan_pipeline_dashboard(session, owner_user_id=None)


@app.get("/ops/scan-sessions", response_model=ScanSessionListResponse, include_in_schema=False)
def ops_list_scan_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: Annotated[int | None, Query(description="Filter sessions by deterministic owner user id.")] = None,
    status_filter: Annotated[ScanSessionStatus | None, Query(alias="status")] = None,
    session_type: Annotated[ScanSessionType | None, Query(alias="session_type")] = None,
    limit: Annotated[int, Query(ge=1, le=250)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanSessionListResponse:
    ensure_ops_admin_access(current_user, settings)
    rows = list_scan_sessions(
        session,
        owner_user_id=owner_user_id,
        status=status_filter,
        session_type=session_type,
        limit=limit,
        offset=offset,
    )
    return ScanSessionListResponse(sessions=rows)


@app.get("/ops/scan-sessions/{session_id}", response_model=ScanSessionDetailRead, include_in_schema=False)
def ops_get_scan_session(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanSessionDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return get_scan_session_detail(session, owner_user_id=None, session_id=session_id)


@app.get("/ops/scan-sessions/{session_id}/items", response_model=ScanSessionItemsListRead, include_in_schema=False)
def ops_list_scan_session_items_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    limit: Annotated[int, Query(ge=1, le=2500)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ScanSessionItemsListRead:
    ensure_ops_admin_access(current_user, settings)
    return list_scan_session_items_read(
        session,
        owner_user_id=None,
        session_id=session_id,
        limit=int(limit),
        offset=int(offset),
    )


@app.get("/ops/scan-sessions/{session_id}/qa", response_model=ScanSessionQaSummaryRead, include_in_schema=False)
def ops_get_scan_session_qa_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanSessionQaSummaryRead:
    ensure_ops_admin_access(current_user, settings)
    return get_scan_session_qa(session, owner_user_id=None, scan_session_id=session_id)


@app.get("/ops/scan-sessions/{session_id}/items/{item_id}/qa", response_model=ScanQaItemRead, include_in_schema=False)
def ops_get_scan_session_item_qa_endpoint(
    session_id: int,
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanQaItemRead:
    ensure_ops_admin_access(current_user, settings)
    return get_scan_session_item_qa(session, owner_user_id=None, scan_session_id=session_id, item_id=item_id)


@app.get("/ops/scan-qa/summary", response_model=OpsScanQaFleetSummaryRead, include_in_schema=False)
def ops_scan_qa_fleet_summary_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OpsScanQaFleetSummaryRead:
    ensure_ops_admin_access(current_user, settings)
    return fleet_scan_qa_summary(session)


@app.get("/ops/scan-routing-recommendations", response_model=QueueRoutingListResponse, include_in_schema=False)
def ops_list_queue_routing_recommendations_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> QueueRoutingListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_queue_routing_recommendations_ops(session)


@app.get("/ops/scan-sessions/{session_id}/routing", response_model=ScanSessionRoutingRead, include_in_schema=False)
def ops_get_scan_session_routing_endpoint(
    session_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ScanSessionRoutingRead:
    ensure_ops_admin_access(current_user, settings)
    return get_scan_session_routing(session, owner_user_id=None, scan_session_id=session_id)


@app.get("/ops/high-res-review-requests/stats", response_model=HighResReviewRequestStatsRead, include_in_schema=False)
def ops_high_res_review_requests_stats_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> HighResReviewRequestStatsRead:
    ensure_ops_admin_access(current_user, settings)
    return high_res_review_request_stats_ops(session)


@app.get("/ops/high-res-review-requests", response_model=HighResReviewRequestListResponse, include_in_schema=False)
def ops_list_high_res_review_requests_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: Annotated[int | None, Query(description="Filter by deterministic owning user id.")] = None,
    inventory_copy_id: Annotated[int | None, Query(ge=1)] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    priority: Annotated[str | None, Query()] = None,
    reason: Annotated[str | None, Query(alias="reason")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 250,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HighResReviewRequestListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_high_res_review_requests_ops(
        session,
        owner_user_id_filter=owner_user_id,
        inventory_copy_id=inventory_copy_id,
        status_filter=status_filter,
        priority_filter=priority,
        reason_filter=reason,
        limit=int(limit),
        offset=int(offset),
    )


@app.get("/ops/high-res-review-requests/{request_id}", response_model=HighResReviewRequestRead, include_in_schema=False)
def ops_get_high_res_review_request_endpoint(
    request_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> HighResReviewRequestRead:
    ensure_ops_admin_access(current_user, settings)
    return get_high_res_review_request_detail(session, owner_user_id=None, request_id=request_id)


@app.get("/missing-issues", response_model=MissingIssueListRead)
def list_missing_issues_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    classification: Annotated[
        MissingIssueClassification | None,
        Query(description="Filter missing issue rows by deterministic classification."),
    ] = None,
) -> MissingIssueListRead:
    return list_missing_issues_owner(session, user=current_user, classification=classification)


@app.get("/inventory/{inventory_copy_id}", response_model=InventoryDetailResponse)
def get_inventory_copy(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryDetailResponse:
    return get_inventory_copy_detail(
        session=session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
    )


@app.get("/inventory-fmv", response_model=InventoryListResponse)
def get_inventory_fmv(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=250)] = 25,
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
    valuation_scope: Annotated[InventoryValuationScope | None, Query(description="Filter by FMV valuation scope.")] = None,
    confidence_bucket: Annotated[str | None, Query(description="Filter by FMV confidence bucket.")] = None,
    liquidity_bucket: Annotated[str | None, Query(description="Filter by FMV liquidity bucket.")] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale FMV rows.")] = None,
    currency_code: Annotated[str | None, Query(description="Filter by FMV currency code.")] = None,
) -> InventoryListResponse:
    assert current_user.id is not None
    return list_inventory(
        session=session,
        current_user=current_user,
        page=page,
        page_size=page_size,
        search=None,
        publisher=publisher,
        hold_status=None,
        grade_status=None,
        release_year=None,
        release_calendar=None,
        asset_state=None,
        intelligence_health=None,
        ownership_intel=None,
        valuation_scope=valuation_scope,
        fmv_confidence_bucket=confidence_bucket,
        fmv_liquidity_bucket=liquidity_bucket,
        fmv_stale_data=stale_data,
        fmv_currency_code=currency_code,
        ownership_state=ownership_state,
        risk_priority=None,
        risk_type=None,
        needs_attention=False,
        action_attention=False,
        action_center_category=None,
        arrival_classification=None,
        sort_by="purchase_date",
        sort_dir="asc",
    )


@app.get("/inventory/{inventory_copy_id}/fmv", response_model=InventoryFmvAttachmentRead)
def get_inventory_copy_fmv(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryFmvAttachmentRead:
    assert current_user.id is not None
    return inventory_fmv_detail_for_scope(
        session,
        owner_user_id=int(current_user.id),
        inventory_copy_id=inventory_copy_id,
        include_detail=True,
    )


@app.get("/ops/inventory-fmv", response_model=InventoryListResponse, include_in_schema=False)
def ops_get_inventory_fmv(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=250)] = 25,
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
    valuation_scope: Annotated[InventoryValuationScope | None, Query(description="Filter by FMV valuation scope.")] = None,
    confidence_bucket: Annotated[str | None, Query(description="Filter by FMV confidence bucket.")] = None,
    liquidity_bucket: Annotated[str | None, Query(description="Filter by FMV liquidity bucket.")] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale FMV rows.")] = None,
    currency_code: Annotated[str | None, Query(description="Filter by FMV currency code.")] = None,
) -> InventoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    return inventory_fmv_inventory_response_for_scope(
        session,
        owner_user_id=None,
        page=page,
        page_size=page_size,
        publisher=publisher,
        ownership_state=ownership_state,
        valuation_scope=valuation_scope,
        confidence_bucket=confidence_bucket,
        liquidity_bucket=liquidity_bucket,
        stale_data=stale_data,
        currency_code=currency_code,
    )


@app.get("/ops/inventory/{inventory_copy_id}/fmv", response_model=InventoryFmvAttachmentRead, include_in_schema=False)
def ops_get_inventory_copy_fmv(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> InventoryFmvAttachmentRead:
    ensure_ops_admin_access(current_user, settings)
    return inventory_fmv_detail_for_scope(
        session,
        owner_user_id=None,
        inventory_copy_id=inventory_copy_id,
        include_detail=True,
    )


@app.get("/portfolio-value/summary", response_model=PortfolioValueSummaryResponse)
def get_portfolio_value_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
    valuation_scope: Annotated[InventoryValuationScope | None, Query(description="Filter by FMV valuation scope.")] = None,
    confidence_bucket: Annotated[str | None, Query(description="Filter by FMV confidence bucket.")] = None,
    liquidity_bucket: Annotated[str | None, Query(description="Filter by FMV liquidity bucket.")] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale FMV rows.")] = None,
    currency_code: Annotated[str | None, Query(description="Filter by FMV currency code.")] = None,
) -> PortfolioValueSummaryResponse:
    assert current_user.id is not None
    return portfolio_value_summary_for_scope(
        session,
        owner_user_id=int(current_user.id),
        publisher=publisher,
        ownership_state=ownership_state,
        valuation_scope=valuation_scope,
        confidence_bucket=confidence_bucket,
        liquidity_bucket=liquidity_bucket,
        stale_data=stale_data,
        currency_code=currency_code,
    )


@app.get("/ops/portfolio-value/summary", response_model=PortfolioValueSummaryResponse, include_in_schema=False)
def ops_get_portfolio_value_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    publisher: Annotated[str | None, Query(description="Filter by publisher name.")] = None,
    ownership_state: Annotated[str | None, Query(description="Filter by normalized ownership state.")] = None,
    valuation_scope: Annotated[InventoryValuationScope | None, Query(description="Filter by FMV valuation scope.")] = None,
    confidence_bucket: Annotated[str | None, Query(description="Filter by FMV confidence bucket.")] = None,
    liquidity_bucket: Annotated[str | None, Query(description="Filter by FMV liquidity bucket.")] = None,
    stale_data: Annotated[bool | None, Query(description="Filter stale FMV rows.")] = None,
    currency_code: Annotated[str | None, Query(description="Filter by FMV currency code.")] = None,
) -> PortfolioValueSummaryResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_value_summary_for_scope(
        session,
        owner_user_id=None,
        publisher=publisher,
        ownership_state=ownership_state,
        valuation_scope=valuation_scope,
        confidence_bucket=confidence_bucket,
        liquidity_bucket=liquidity_bucket,
        stale_data=stale_data,
        currency_code=currency_code,
    )


@app.get("/inventory/{inventory_copy_id}/scan-qa", response_model=InventoryScanQaPanelRead)
def get_inventory_cover_scan_qa_endpoint(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryScanQaPanelRead:
    assert current_user.id is not None
    return inventory_cover_scan_qa(session, owner_user_id=int(current_user.id), inventory_copy_id=inventory_copy_id)


@app.get("/inventory/{inventory_copy_id}/timeline", response_model=CollectionTimelineEventsResponse)
def get_inventory_copy_timeline(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: Annotated[
        CollectionTimelineEventType | None,
        Query(description="Filter by deterministic timeline event kind."),
    ] = None,
    grouping: Annotated[CollectionTimelineGrouping, Query()] = "none",
    sort: Annotated[CollectionTimelineSort, Query()] = "desc",
    limit: Annotated[int, Query(ge=1, le=500)] = 280,
) -> CollectionTimelineEventsResponse:
    assert current_user.id is not None
    row = session.exec(
        select(InventoryCopy.id).where(
            InventoryCopy.id == inventory_copy_id,
            InventoryCopy.user_id == current_user.id,
        ),
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Inventory copy not found")
    return timeline_events_for_scope(
        session,
        scope_user_id=int(current_user.id),
        event_type_filter=event_type,
        publisher=None,
        ownership_filter=None,
        release_status=None,
        start_date=None,
        end_date=None,
        preorder_only=False,
        in_hand_only=False,
        inventory_copy_id=inventory_copy_id,
        grouping=grouping,
        sort=sort,
        limit=limit,
        return_events=True,
    )


@app.get(
    "/inventory/{inventory_copy_id}/fmv-history",
    response_model=list[InventoryFmvSnapshotResponse],
)
def get_inventory_copy_fmv_history(
    inventory_copy_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[InventoryFmvSnapshotResponse]:
    return get_inventory_fmv_history(
        session=session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
    )


@app.get("/portfolio/performance", response_model=PortfolioPerformanceResponse)
def get_portfolio_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioPerformanceResponse:
    return portfolio_performance(session=session, current_user=current_user)


@app.get("/physical-intake/summary", response_model=PhysicalIntakeSummaryResponse)
def get_physical_intake_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PhysicalIntakeSummaryResponse:
    assert current_user.id is not None
    return build_physical_intake_summary(session, owner_user_id=int(current_user.id))


@app.get("/physical-intake", response_model=PhysicalIntakeListResponse)
def get_physical_intake_list(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    intake_state: PhysicalIntakeState | None = Query(default=None),
) -> PhysicalIntakeListResponse:
    assert current_user.id is not None
    return list_physical_intake(
        session,
        owner_user_id=int(current_user.id),
        intake_state_filter=intake_state,
    )


@app.post("/physical-intake/create-scan-session", response_model=ScanSessionDetailRead)
def post_physical_intake_create_scan_session(
    payload: CreatePhysicalIntakeScanSessionPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ScanSessionDetailRead:
    return create_physical_intake_scan_session(session, current_user, payload)


@app.get("/ops/physical-intake/summary", response_model=PhysicalIntakeSummaryResponse)
def ops_physical_intake_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PhysicalIntakeSummaryResponse:
    ensure_ops_admin_access(current_user, settings)
    return build_physical_intake_summary(session, owner_user_id=None)


@app.get("/ops/physical-intake", response_model=PhysicalIntakeListResponse)
def ops_physical_intake_list(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    intake_state: PhysicalIntakeState | None = Query(default=None),
) -> PhysicalIntakeListResponse:
    ensure_ops_admin_access(current_user, settings)
    return list_physical_intake(session, owner_user_id=None, intake_state_filter=intake_state)


@app.patch("/inventory/bulk", response_model=BulkInventoryUpdateResponse)
def patch_inventory_bulk(
    payload: BulkInventoryUpdateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkInventoryUpdateResponse:
    return bulk_update_inventory(session=session, current_user=current_user, payload=payload)


@app.patch("/inventory/{inventory_copy_id}", response_model=InventoryRow)
def patch_inventory_copy(
    inventory_copy_id: int,
    payload: InventoryUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryRow:
    return update_inventory_copy(
        session=session,
        current_user=current_user,
        inventory_copy_id=inventory_copy_id,
        updates=payload,
    )


@app.post("/inventory/{inventory_copy_id}/mark-received", response_model=InventoryRow)
def post_inventory_mark_received(
    inventory_copy_id: int,
    payload: MarkInventoryReceivedPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryRow:
    return mark_physical_received(
        session,
        current_user,
        inventory_copy_id=inventory_copy_id,
        payload=payload,
    )


@app.post("/inventory/bulk-mark-received", response_model=BulkMarkInventoryReceivedResponse)
def post_inventory_bulk_mark_received(
    payload: BulkMarkInventoryReceivedRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> BulkMarkInventoryReceivedResponse:
    return bulk_mark_physical_received(session, current_user, payload=payload)


# --- Listing registry foundation (P36-01) ------------------------------------


@app.get("/listings/summary", response_model=ListingDashboardSummary)
def get_listing_registry_owner_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingDashboardSummary:
    drafts, active, sold, recent = listing_registry_service.owner_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
    )
    return ListingDashboardSummary(
        draft_count=drafts,
        active_count=active,
        sold_count=sold,
        recent_events=[listing_registry_service.coerce_lifecycle_read(evt) for evt in recent],
    )


@app.get("/listings", response_model=ListingListResponse)
def list_owner_listings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    inventory_copy_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingListResponse:
    lim, off = listing_registry_service.clamp_list_pagination(limit=limit, offset=offset)
    rows, total = listing_registry_service.list_listings_owner(
        session,
        owner_user_id=int(current_user.id),
        limit=lim,
        offset=off,
        status=status_filter,
        inventory_copy_id=inventory_copy_id,
    )
    return ListingListResponse(
        items=[listing_registry_service.coerce_listing_read(r) for r in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.post("/listings", response_model=ListingRead, status_code=status.HTTP_201_CREATED)
def post_owner_listing(
    payload: ListingCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingRead:
    row, created = listing_registry_service.create_listing(
        session, owner_user_id=int(current_user.id), payload=payload
    )
    if not created:
        response.status_code = status.HTTP_200_OK
    return listing_registry_service.coerce_listing_read(row)


@app.get("/listings/{listing_id}", response_model=ListingDetailRead)
def get_owner_listing_detail(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingDetailRead:
    listing = listing_registry_service.get_listing_owner(
        session,
        listing_id=listing_id,
        owner_user_id=int(current_user.id),
    )
    return listing_registry_service.assemble_listing_detail(session, listing)


@app.patch("/listings/{listing_id}", response_model=ListingRead)
def patch_owner_listing(
    listing_id: int,
    payload: ListingUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingRead:
    row = listing_registry_service.patch_listing(
        session,
        listing_id=listing_id,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    return listing_registry_service.coerce_listing_read(row)


@app.post("/listings/{listing_id}/activate", response_model=ListingRead)
def post_owner_listing_activate(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    body: ListingReplayBody | None = Body(default=None),
) -> ListingRead:
    replay = body.replay_key if body else None
    row = listing_registry_service.activate_listing(
        session,
        listing_id=listing_id,
        owner_user_id=int(current_user.id),
        replay_key=replay,
    )
    return listing_registry_service.coerce_listing_read(row)


@app.post("/listings/{listing_id}/cancel", response_model=ListingRead)
def post_owner_listing_cancel(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    body: ListingReplayBody | None = Body(default=None),
) -> ListingRead:
    replay = body.replay_key if body else None
    row = listing_registry_service.cancel_listing(
        session,
        listing_id=listing_id,
        owner_user_id=int(current_user.id),
        replay_key=replay,
    )
    return listing_registry_service.coerce_listing_read(row)


@app.post("/listings/{listing_id}/archive", response_model=ListingRead)
def post_owner_listing_archive(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    body: ListingReplayBody | None = Body(default=None),
) -> ListingRead:
    replay = body.replay_key if body else None
    row = listing_registry_service.archive_listing(
        session,
        listing_id=listing_id,
        owner_user_id=int(current_user.id),
        replay_key=replay,
    )
    return listing_registry_service.coerce_listing_read(row)


@app.get("/ops/listings", response_model=ListingListResponse)
def ops_list_listings(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_registry_service.clamp_list_pagination(limit=limit, offset=offset)
    rows, total = listing_registry_service.list_listings_ops(
        session,
        limit=lim,
        offset=off,
        owner_user_id=owner_user_id,
        status_filter=status_filter,
    )
    return ListingListResponse(
        items=[listing_registry_service.coerce_listing_read(r) for r in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listings/status-distribution", response_model=ListingOpsStatusDistribution)
def ops_listings_status_distribution_endpoint(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ListingOpsStatusDistribution:
    ensure_ops_admin_access(current_user, settings)
    rows = listing_registry_service.ops_status_distribution(session)
    return ListingOpsStatusDistribution(
        rows=[ListingOpsStatusCountRow(status=st, count=cnt) for st, cnt in rows],
    )


@app.get("/ops/listings/{listing_id}", response_model=ListingDetailRead)
def ops_get_listing_detail(
    listing_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ListingDetailRead:
    ensure_ops_admin_access(current_user, settings)
    listing = listing_registry_service.get_listing_ops(session, listing_id=listing_id)
    return listing_registry_service.assemble_listing_detail(session, listing)


@app.get("/ops/listing-events", response_model=OpsListingLifecycleEventListResponse)
def ops_list_listing_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    listing_id: int | None = Query(default=None),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> OpsListingLifecycleEventListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_registry_service.clamp_list_pagination(limit=limit, offset=offset)
    items, total = listing_registry_service.list_events_ops(
        session,
        limit=lim,
        offset=off,
        listing_id=listing_id,
        owner_user_id_filter=owner_user_id,
    )
    return OpsListingLifecycleEventListResponse(
        items=[listing_registry_service.coerce_lifecycle_read(evt) for evt in items],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-price-history", response_model=OpsListingPriceHistoryListResponse)
def ops_list_listing_price_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    listing_id: int | None = Query(default=None),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> OpsListingPriceHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_registry_service.clamp_list_pagination(limit=limit, offset=offset)
    items, total = listing_registry_service.list_price_hist_ops(
        session,
        limit=lim,
        offset=off,
        listing_id=listing_id,
        owner_user_id_filter=owner_user_id,
    )
    return OpsListingPriceHistoryListResponse(
        items=[listing_registry_service.coerce_price_history_read(row) for row in items],
        total_items=total,
        limit=lim,
        offset=off,
    )


# --- Listing export engine (P36-02: deterministic CSV; no marketplace APIs) -------------
@app.get("/listing-export-runs/dashboard-summary", response_model=ListingExportDashboardSummary)
def listing_export_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingExportDashboardSummary:
    return listing_export_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get("/listing-export-templates", response_model=list[ListingExportTemplateRead])
def list_owner_listing_export_templates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[ListingExportTemplateRead]:
    return listing_export_service.list_templates_owner(session, owner_user_id=int(current_user.id))


@app.post(
    "/listing-export-runs",
    response_model=ListingExportRunDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def post_listing_export_run(
    payload: ListingExportRunCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ListingExportRunDetailRead:
    detail, replayed = listing_export_service.execute_export_run(
        session,
        owner_user_id=int(current_user.id),
        settings=settings,
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/listing-export-runs", response_model=ListingExportRunListResponse)
def list_owner_listing_export_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingExportRunListResponse:
    lim, off = listing_export_service.clamp_list_export_pagination(limit=limit, offset=offset)
    rows, total = listing_export_service.list_runs_owner(
        session,
        owner_user_id=int(current_user.id),
        limit=lim,
        offset=off,
    )
    return ListingExportRunListResponse(
        items=[listing_export_service.coerce_run_summary(r) for r in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/listing-export-runs/{export_run_id}/download")
def download_owner_listing_export_csv(
    export_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file_id: int | None = Query(default=None),
) -> FileResponse:
    abs_path, frow = listing_export_service.resolve_export_download_path_session(
        session,
        settings,
        owner_user_id=int(current_user.id),
        export_run_id=export_run_id,
        file_id=file_id,
        allow_ops_any_owner=False,
    )
    return FileResponse(
        path=str(abs_path),
        media_type="text/csv; charset=utf-8",
        filename=frow.file_name,
    )


@app.get("/listing-export-runs/{export_run_id}", response_model=ListingExportRunDetailRead)
def get_owner_listing_export_run(
    export_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingExportRunDetailRead:
    return listing_export_service.build_run_detail(
        session,
        owner_user_id=int(current_user.id),
        export_run_id=export_run_id,
    )


@app.get("/ops/listing-export-runs", response_model=ListingExportRunListResponse)
def ops_list_listing_export_runs(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingExportRunListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_export_service.clamp_list_export_pagination(limit=limit, offset=offset)
    rows, total = listing_export_service.list_runs_ops(
        session,
        owner_user_id=owner_user_id,
        limit=lim,
        offset=off,
    )
    return ListingExportRunListResponse(
        items=[listing_export_service.coerce_run_summary(r) for r in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-export-runs/{export_run_id}/download")
def ops_download_listing_export_csv(
    export_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file_id: int | None = Query(default=None),
) -> FileResponse:
    ensure_ops_admin_access(current_user, settings)
    abs_path, frow = listing_export_service.resolve_export_download_path_session(
        session,
        settings,
        owner_user_id=0,
        export_run_id=export_run_id,
        file_id=file_id,
        allow_ops_any_owner=True,
    )
    return FileResponse(
        path=str(abs_path),
        media_type="text/csv; charset=utf-8",
        filename=frow.file_name,
    )


@app.get("/ops/listing-export-runs/{export_run_id}", response_model=ListingExportRunDetailRead)
def ops_detail_listing_export_run(
    export_run_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ListingExportRunDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return listing_export_service.build_run_detail(
        session,
        owner_user_id=0,
        export_run_id=export_run_id,
        allow_cross_owner_ops=True,
    )


@app.get("/ops/listing-export-files", response_model=OpsListingExportFileListResponse)
def ops_list_listing_export_files(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    export_run_id: int | None = Query(default=None),
    owner_user_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> OpsListingExportFileListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_export_service.clamp_list_export_pagination(limit=limit, offset=offset)
    rows, total = listing_export_service.list_export_files_ops(
        session,
        export_run_id=export_run_id,
        owner_user_id=owner_user_id,
        limit=lim,
        offset=off,
    )
    return OpsListingExportFileListResponse(
        items=[listing_export_service.coerce_file(r) for r in rows],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/listing-intelligence/dashboard-summary", response_model=ListingIntelligenceDashboardSummary)
def owner_listing_intelligence_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingIntelligenceDashboardSummary:
    return listing_intelligence_service.build_listing_intelligence_dashboard_summary(
        session,
        owner_user_id=int(current_user.id),
    )


@app.post("/listing-intelligence/generate", response_model=ListingIntelligenceGenerateResponse, status_code=status.HTTP_201_CREATED)
def owner_generate_listing_intelligence(
    payload: ListingIntelligenceGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingIntelligenceGenerateResponse:
    return listing_intelligence_service.generate_listing_intelligence(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/listing-intelligence", response_model=ListingIntelligenceSnapshotListResponse)
def owner_list_listing_intelligence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    listing_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    intelligence_status: str | None = Query(default=None),
    stale_risk_flag: bool | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingIntelligenceSnapshotListResponse:
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_intelligence_owner(
        session,
        owner_user_id=int(current_user.id),
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        stale_risk_flag=stale_risk_flag,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return ListingIntelligenceSnapshotListResponse(
        items=[listing_intelligence_service._snapshot_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/listing-intelligence/evidence", response_model=ListingIntelligenceEvidenceListResponse)
def owner_list_listing_intelligence_evidence_pre(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    listing_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    intelligence_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingIntelligenceEvidenceListResponse:
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_intelligence_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return ListingIntelligenceEvidenceListResponse(
        items=[listing_intelligence_service._evidence_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/listing-intelligence/{snapshot_id}", response_model=ListingIntelligenceSnapshotRead)
def owner_get_listing_intelligence(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ListingIntelligenceSnapshotRead:
    row = listing_intelligence_service.get_listing_intelligence_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
    )
    return listing_intelligence_service._snapshot_read(row)  # noqa: SLF001


@app.get("/listing-completeness-checks", response_model=ListingCompletenessCheckListResponse)
def owner_list_listing_completeness_checks(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    listing_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    check_status: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingCompletenessCheckListResponse:
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_completeness_checks_owner(
        session,
        owner_user_id=int(current_user.id),
        listing_id=listing_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        check_status=check_status,
        severity=severity,
        limit=lim,
        offset=off,
    )
    return ListingCompletenessCheckListResponse(
        items=[listing_intelligence_service._check_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/listing-channel-performance", response_model=ListingChannelPerformanceListResponse)
def owner_list_listing_channel_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingChannelPerformanceListResponse:
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_channel_performance_owner(
        session,
        owner_user_id=int(current_user.id),
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return ListingChannelPerformanceListResponse(
        items=[listing_intelligence_service._channel_perf_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-intelligence-evidence", response_model=ListingIntelligenceEvidenceListResponse)
def ops_list_listing_intelligence_evidence_pre(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    listing_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    intelligence_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingIntelligenceEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_intelligence_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return ListingIntelligenceEvidenceListResponse(
        items=[listing_intelligence_service._evidence_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-intelligence/dashboard-summary", response_model=ListingIntelligenceDashboardSummary)
def ops_listing_intelligence_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> ListingIntelligenceDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return listing_intelligence_service.build_listing_intelligence_dashboard_summary(
        session,
        owner_user_id=owner_user_id,
    )


@app.get("/ops/listing-intelligence", response_model=ListingIntelligenceSnapshotListResponse)
def ops_list_listing_intelligence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    listing_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    intelligence_status: str | None = Query(default=None),
    stale_risk_flag: bool | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingIntelligenceSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_intelligence_ops(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        stale_risk_flag=stale_risk_flag,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return ListingIntelligenceSnapshotListResponse(
        items=[listing_intelligence_service._snapshot_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-intelligence/{snapshot_id}", response_model=ListingIntelligenceSnapshotRead)
def ops_get_listing_intelligence(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ListingIntelligenceSnapshotRead:
    ensure_ops_admin_access(current_user, settings)
    row = listing_intelligence_service.get_listing_intelligence_ops(session, snapshot_id=snapshot_id)
    return listing_intelligence_service._snapshot_read(row)  # noqa: SLF001


@app.get("/ops/listing-intelligence-evidence", response_model=ListingIntelligenceEvidenceListResponse)
def ops_list_listing_intelligence_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    listing_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    intelligence_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingIntelligenceEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_intelligence_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        channel=channel,
        intelligence_status=intelligence_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return ListingIntelligenceEvidenceListResponse(
        items=[listing_intelligence_service._evidence_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-completeness-checks", response_model=ListingCompletenessCheckListResponse)
def ops_list_listing_completeness_checks(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    listing_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    check_status: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingCompletenessCheckListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_completeness_checks_ops(
        session,
        owner_user_id=owner_user_id,
        listing_id=listing_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        check_status=check_status,
        severity=severity,
        limit=lim,
        offset=off,
    )
    return ListingCompletenessCheckListResponse(
        items=[listing_intelligence_service._check_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-channel-performance", response_model=ListingChannelPerformanceListResponse)
def ops_list_listing_channel_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingChannelPerformanceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = listing_intelligence_service.clamp_listing_intelligence_pagination(limit=limit, offset=offset)
    rows, total = listing_intelligence_service.list_listing_channel_performance_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return ListingChannelPerformanceListResponse(
        items=[listing_intelligence_service._channel_perf_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/dealer-dashboard", response_model=DealerDashboardGetResponse)
def owner_dealer_dashboard_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DealerDashboardGetResponse:
    return dealer_dashboard_service.get_dashboard_owner(session, owner_user_id=int(current_user.id))


@app.post("/dealer-dashboard/generate", response_model=DealerDashboardGenerateResponse, status_code=status.HTTP_201_CREATED)
def owner_dealer_dashboard_generate(
    payload: DealerDashboardGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DealerDashboardGenerateResponse:
    return dealer_dashboard_service.generate_dealer_dashboard(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/dealer-dashboard/metrics", response_model=DealerDashboardMetricListResponse)
def owner_list_dealer_dashboard_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    dashboard_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerDashboardMetricListResponse:
    return dealer_dashboard_service.list_metrics_owner(
        session,
        owner_user_id=int(current_user.id),
        dashboard_snapshot_id=dashboard_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/dealer-dashboard/alerts", response_model=DealerDashboardAlertListResponse)
def owner_list_dealer_dashboard_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    severity: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerDashboardAlertListResponse:
    return dealer_dashboard_service.list_alerts_owner(
        session,
        owner_user_id=int(current_user.id),
        severity=severity,
        alert_type=alert_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/dealer-dashboard/feed", response_model=DealerDashboardFeedListResponse)
def owner_list_dealer_dashboard_feed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerDashboardFeedListResponse:
    return dealer_dashboard_service.list_feed_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/dealer-dashboard", response_model=DealerDashboardGetResponse)
def ops_dealer_dashboard_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> DealerDashboardGetResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_dashboard_service.get_dashboard_ops(session, owner_user_id=owner_user_id)


@app.get("/ops/dealer-dashboard/metrics", response_model=DealerDashboardMetricListResponse)
def ops_list_dealer_dashboard_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    dashboard_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerDashboardMetricListResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_dashboard_service.list_metrics_ops(
        session,
        owner_user_id=owner_user_id,
        dashboard_snapshot_id=dashboard_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/dealer-dashboard/alerts", response_model=DealerDashboardAlertListResponse)
def ops_list_dealer_dashboard_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    severity: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerDashboardAlertListResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_dashboard_service.list_alerts_ops(
        session,
        owner_user_id=owner_user_id,
        severity=severity,
        alert_type=alert_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/dealer-dashboard/feed", response_model=DealerDashboardFeedListResponse)
def ops_list_dealer_dashboard_feed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerDashboardFeedListResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_dashboard_service.list_feed_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/dealer-grading-dashboard", response_model=DealerGradingDashboardGetResponse)
def owner_dealer_grading_dashboard_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DealerGradingDashboardGetResponse:
    return dealer_grading_dashboard_service.get_dashboard_owner(session, owner_user_id=int(current_user.id))


@app.post(
    "/dealer-grading-dashboard/generate",
    response_model=DealerGradingDashboardGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def owner_dealer_grading_dashboard_generate(
    payload: DealerGradingDashboardGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DealerGradingDashboardGenerateResponse:
    return dealer_grading_dashboard_service.generate_dealer_grading_dashboard(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/dealer-grading-dashboard/metrics", response_model=DealerGradingDashboardMetricListResponse)
def owner_list_dealer_grading_dashboard_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    dashboard_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerGradingDashboardMetricListResponse:
    return dealer_grading_dashboard_service.list_metrics_owner(
        session,
        owner_user_id=int(current_user.id),
        dashboard_snapshot_id=dashboard_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/dealer-grading-dashboard/alerts", response_model=DealerGradingDashboardAlertListResponse)
def owner_list_dealer_grading_dashboard_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    severity: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerGradingDashboardAlertListResponse:
    return dealer_grading_dashboard_service.list_alerts_owner(
        session,
        owner_user_id=int(current_user.id),
        severity=severity,
        alert_type=alert_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/dealer-grading-dashboard/feed", response_model=DealerGradingDashboardFeedListResponse)
def owner_list_dealer_grading_dashboard_feed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerGradingDashboardFeedListResponse:
    return dealer_grading_dashboard_service.list_feed_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/dealer-grading-dashboard", response_model=DealerGradingDashboardGetResponse)
def ops_dealer_grading_dashboard_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> DealerGradingDashboardGetResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_grading_dashboard_service.get_dashboard_ops(session, owner_user_id=owner_user_id)


@app.get("/ops/dealer-grading-dashboard/metrics", response_model=DealerGradingDashboardMetricListResponse)
def ops_list_dealer_grading_dashboard_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    dashboard_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerGradingDashboardMetricListResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_grading_dashboard_service.list_metrics_ops(
        session,
        owner_user_id=owner_user_id,
        dashboard_snapshot_id=dashboard_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/dealer-grading-dashboard/alerts", response_model=DealerGradingDashboardAlertListResponse)
def ops_list_dealer_grading_dashboard_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    severity: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerGradingDashboardAlertListResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_grading_dashboard_service.list_alerts_ops(
        session,
        owner_user_id=owner_user_id,
        severity=severity,
        alert_type=alert_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/dealer-grading-dashboard/feed", response_model=DealerGradingDashboardFeedListResponse)
def ops_list_dealer_grading_dashboard_feed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DealerGradingDashboardFeedListResponse:
    ensure_ops_admin_access(current_user, settings)
    return dealer_grading_dashboard_service.list_feed_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/portfolio-strategy-dashboard", response_model=PortfolioStrategyDashboardGetResponse)
def owner_portfolio_strategy_dashboard_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioStrategyDashboardGetResponse:
    return portfolio_strategy_dashboard_service.get_dashboard_owner(session, owner_user_id=int(current_user.id))


@app.post(
    "/portfolio-strategy-dashboard/generate",
    response_model=PortfolioStrategyDashboardGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def owner_portfolio_strategy_dashboard_generate(
    payload: PortfolioStrategyDashboardGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioStrategyDashboardGenerateResponse:
    existing = None
    if payload.replay_key:
        existing = session.exec(
            select(PortfolioStrategyDashboardSnapshot).where(
                PortfolioStrategyDashboardSnapshot.owner_user_id == int(current_user.id),
                PortfolioStrategyDashboardSnapshot.replay_key == payload.replay_key,
            )
        ).first()
    body = portfolio_strategy_dashboard_service.generate_dashboard(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if existing is not None:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/portfolio-strategy-dashboard/metrics", response_model=PortfolioStrategyDashboardMetricListResponse)
def owner_list_portfolio_strategy_dashboard_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    dashboard_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioStrategyDashboardMetricListResponse:
    return portfolio_strategy_dashboard_service.list_metrics_owner(
        session,
        owner_user_id=int(current_user.id),
        dashboard_snapshot_id=dashboard_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/portfolio-strategy-dashboard/alerts", response_model=PortfolioStrategyDashboardAlertListResponse)
def owner_list_portfolio_strategy_dashboard_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    severity: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioStrategyDashboardAlertListResponse:
    return portfolio_strategy_dashboard_service.list_alerts_owner(
        session,
        owner_user_id=int(current_user.id),
        severity=severity,
        alert_type=alert_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/portfolio-strategy-dashboard/feed", response_model=PortfolioStrategyDashboardFeedListResponse)
def owner_list_portfolio_strategy_dashboard_feed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioStrategyDashboardFeedListResponse:
    return portfolio_strategy_dashboard_service.list_feed_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolio-strategy-dashboard", response_model=PortfolioStrategyDashboardGetResponse)
def ops_portfolio_strategy_dashboard_get(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> PortfolioStrategyDashboardGetResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_strategy_dashboard_service.get_dashboard_ops(session, owner_user_id=owner_user_id)


@app.get("/ops/portfolio-strategy-dashboard/metrics", response_model=PortfolioStrategyDashboardMetricListResponse)
def ops_list_portfolio_strategy_dashboard_metrics(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    dashboard_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioStrategyDashboardMetricListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_strategy_dashboard_service.list_metrics_ops(
        session,
        owner_user_id=owner_user_id,
        dashboard_snapshot_id=dashboard_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolio-strategy-dashboard/alerts", response_model=PortfolioStrategyDashboardAlertListResponse)
def ops_list_portfolio_strategy_dashboard_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    severity: str | None = Query(default=None),
    alert_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioStrategyDashboardAlertListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_strategy_dashboard_service.list_alerts_ops(
        session,
        owner_user_id=owner_user_id,
        severity=severity,
        alert_type=alert_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolio-strategy-dashboard/feed", response_model=PortfolioStrategyDashboardFeedListResponse)
def ops_list_portfolio_strategy_dashboard_feed(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioStrategyDashboardFeedListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_strategy_dashboard_service.list_feed_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )


# ——— P38-01 portfolio registry & exposure ———


@app.get("/portfolios", response_model=PortfolioListResponse)
def owner_list_portfolios(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioListResponse:
    return portfolio_registry_service.list_portfolios_owner(
        session,
        owner_user_id=int(current_user.id),
        status_filter=status_filter.upper() if status_filter else None,
        limit=limit,
        offset=offset,
    )


@app.post("/portfolios", response_model=PortfolioRead, status_code=status.HTTP_201_CREATED)
def owner_create_portfolio(
    payload: PortfolioCreatePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioRead:
    detail, replayed = portfolio_registry_service.create_portfolio(
        session, owner_user_id=int(current_user.id), payload=payload
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/portfolios/{portfolio_id}", response_model=PortfolioRead)
def owner_get_portfolio(
    portfolio_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioRead:
    return portfolio_registry_service.get_portfolio_owner(
        session, owner_user_id=int(current_user.id), portfolio_id=portfolio_id
    )


@app.patch("/portfolios/{portfolio_id}", response_model=PortfolioRead)
def owner_patch_portfolio(
    portfolio_id: int,
    payload: PortfolioUpdatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioRead:
    return portfolio_registry_service.update_portfolio_owner(
        session, owner_user_id=int(current_user.id), portfolio_id=portfolio_id, payload=payload
    )


@app.post("/portfolios/{portfolio_id}/archive", response_model=PortfolioRead)
def owner_archive_portfolio(
    portfolio_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioRead:
    return portfolio_registry_service.archive_portfolio_owner(
        session, owner_user_id=int(current_user.id), portfolio_id=portfolio_id
    )


@app.get("/portfolios/{portfolio_id}/items", response_model=PortfolioItemListResponse)
def owner_list_portfolio_items(
    portfolio_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    include_removed: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioItemListResponse:
    return portfolio_registry_service.list_portfolio_items_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        include_removed=include_removed,
        limit=limit,
        offset=offset,
    )


@app.post("/portfolios/{portfolio_id}/items", response_model=PortfolioItemRead, status_code=status.HTTP_201_CREATED)
def owner_add_portfolio_item(
    portfolio_id: int,
    payload: PortfolioItemCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioItemRead:
    return portfolio_registry_service.add_portfolio_item(
        session, owner_user_id=int(current_user.id), portfolio_id=portfolio_id, payload=payload
    )


@app.post("/portfolios/{portfolio_id}/items/{portfolio_item_id}/remove", response_model=PortfolioItemRead)
def owner_remove_portfolio_item(
    portfolio_id: int,
    portfolio_item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioItemRead:
    return portfolio_registry_service.remove_portfolio_item(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        portfolio_item_id=portfolio_item_id,
    )


@app.get("/portfolio-intelligence/summary", response_model=PortfolioIntelligenceSummary)
def owner_portfolio_intelligence_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioIntelligenceSummary:
    return portfolio_registry_service.portfolio_intelligence_summary(session, owner_user_id=int(current_user.id))


@app.get("/portfolio-exposures", response_model=PortfolioExposureSnapshotListResponse)
def owner_list_portfolio_exposures(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    generation_batch_checksum: str | None = Query(default=None),
    latest_batch: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioExposureSnapshotListResponse:
    return portfolio_registry_service.list_exposure_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        generation_batch_checksum=generation_batch_checksum,
        latest_batch=latest_batch,
        limit=limit,
        offset=offset,
    )


@app.get("/portfolio-exposure-evidence", response_model=PortfolioExposureEvidenceListResponse)
def owner_list_portfolio_exposure_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_exposure_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioExposureEvidenceListResponse:
    return portfolio_registry_service.list_exposure_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_exposure_snapshot_id=portfolio_exposure_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/portfolio-exposures/generate",
    response_model=PortfolioExposureGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def owner_generate_portfolio_exposures(
    payload: PortfolioGenerateScopePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioExposureGenerateResponse:
    body = portfolio_registry_service.generate_exposure_snapshots(session, owner_user_id=int(current_user.id), payload=payload)
    if body.replayed:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/portfolio-allocations", response_model=PortfolioAllocationSnapshotListResponse)
def owner_list_portfolio_allocations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    latest_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioAllocationSnapshotListResponse:
    return portfolio_registry_service.list_allocation_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/portfolio-allocations/generate",
    response_model=PortfolioAllocationGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def owner_generate_portfolio_allocations(
    payload: PortfolioGenerateScopePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioAllocationGenerateResponse:
    body = portfolio_registry_service.generate_allocation_snapshot(session, owner_user_id=int(current_user.id), payload=payload)
    if body.replayed:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/ops/portfolios", response_model=PortfolioListResponse)
def ops_list_portfolios(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_registry_service.list_portfolios_ops(
        session,
        owner_user_id=owner_user_id,
        status_filter=status_filter.upper() if status_filter else None,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolios/{portfolio_id}", response_model=PortfolioRead)
def ops_get_portfolio_detail(
    portfolio_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> PortfolioRead:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_registry_service.get_portfolio_ops(session, portfolio_id=portfolio_id, owner_user_id=owner_user_id)


@app.get("/ops/portfolio-items", response_model=PortfolioItemListResponse)
def ops_list_portfolio_items(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    include_removed: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioItemListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_registry_service.list_portfolio_items_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        include_removed=include_removed,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolio-exposures", response_model=PortfolioExposureSnapshotListResponse)
def ops_list_portfolio_exposures_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    generation_batch_checksum: str | None = Query(default=None),
    latest_batch: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioExposureSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_registry_service.list_exposure_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        generation_batch_checksum=generation_batch_checksum,
        latest_batch=latest_batch,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolio-exposure-evidence", response_model=PortfolioExposureEvidenceListResponse)
def ops_list_portfolio_exposure_evidence_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_exposure_snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioExposureEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_registry_service.list_exposure_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_exposure_snapshot_id=portfolio_exposure_snapshot_id,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolio-allocations", response_model=PortfolioAllocationSnapshotListResponse)
def ops_list_portfolio_allocations_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioAllocationSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_registry_service.list_allocation_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        limit=limit,
        offset=offset,
    )


@app.get("/duplicate-intelligence/summary", response_model=DuplicateIntelligenceSummary)
def owner_duplicate_intelligence_summary_route(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DuplicateIntelligenceSummary:
    return duplicate_consolidation_service.duplicate_intelligence_summary(session, owner_user_id=int(current_user.id))


@app.get("/duplicate-clusters", response_model=DuplicateClusterListResponse)
def owner_list_duplicate_clusters(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    canonical_comic_issue_id: int | None = Query(default=None),
    cluster_type: str | None = Query(default=None),
    duplication_status: str | None = Query(default=None),
    liquidity_profile: str | None = Query(default=None),
    recommendation_action: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateClusterListResponse:
    return duplicate_consolidation_service.list_clusters_owner(
        session,
        owner_user_id=int(current_user.id),
        canonical_comic_issue_id=canonical_comic_issue_id,
        cluster_type=cluster_type,
        duplication_status=duplication_status,
        liquidity_profile=liquidity_profile,
        recommendation_action=recommendation_action,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.get("/duplicate-clusters/{cluster_id}", response_model=DuplicateClusterRead)
def owner_get_duplicate_cluster(
    cluster_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DuplicateClusterRead:
    return duplicate_consolidation_service.get_cluster_owner(
        session, owner_user_id=int(current_user.id), cluster_id=cluster_id
    )


@app.get("/duplicate-cluster-items", response_model=DuplicateClusterItemListResponse)
def owner_list_duplicate_cluster_items(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    duplicate_cluster_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateClusterItemListResponse:
    return duplicate_consolidation_service.list_cluster_items_owner(
        session,
        owner_user_id=int(current_user.id),
        duplicate_cluster_id=duplicate_cluster_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        inventory_item_id=inventory_item_id,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/duplicate-consolidation-recommendations",
    response_model=DuplicateConsolidationRecommendationListResponse,
)
def owner_list_duplicate_consolidation_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_action: str | None = Query(default=None),
    recommendation_status: str | None = Query(default=None, alias="status"),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateConsolidationRecommendationListResponse:
    return duplicate_consolidation_service.list_consolidation_recommendations_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_action=recommendation_action,
        recommendation_status=recommendation_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.get("/duplicate-history", response_model=DuplicateHistoryListResponse)
def owner_duplicate_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    cluster_key_prefix: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateHistoryListResponse:
    return duplicate_consolidation_service.list_duplicate_history_owner(
        session,
        owner_user_id=int(current_user.id),
        cluster_key_prefix=cluster_key_prefix,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/duplicate-clusters/generate",
    response_model=DuplicateClusterGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def owner_generate_duplicate_clusters(
    payload: DuplicateClusterGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DuplicateClusterGenerateResponse:
    body = duplicate_consolidation_service.generate_duplicate_clusters(
        session, owner_user_id=int(current_user.id), payload=payload
    )
    if body.replayed:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/portfolio-liquidity", response_model=PortfolioLiquiditySnapshotListResponse)
def owner_list_portfolio_liquidity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    liquidity_balance_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioLiquiditySnapshotListResponse:
    return portfolio_liquidity_service.list_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        liquidity_balance_status=liquidity_balance_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.get("/portfolio-liquidity/{snapshot_id}", response_model=PortfolioLiquiditySnapshotDetailResponse)
def owner_get_portfolio_liquidity_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioLiquiditySnapshotDetailResponse:
    snap, buckets = portfolio_liquidity_service.get_snapshot_detail_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
    )
    return PortfolioLiquiditySnapshotDetailResponse(snapshot=snap, buckets=buckets)


@app.get("/portfolio-liquidity-evidence", response_model=PortfolioLiquidityEvidenceListResponse)
def owner_list_portfolio_liquidity_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_liquidity_snapshot_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioLiquidityEvidenceListResponse:
    return portfolio_liquidity_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_liquidity_snapshot_id=portfolio_liquidity_snapshot_id,
        evidence_type=evidence_type,
        limit=limit,
        offset=offset,
    )


@app.get("/portfolio-liquidity-history", response_model=PortfolioLiquidityHistoryListResponse)
def owner_portfolio_liquidity_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    liquidity_balance_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioLiquidityHistoryListResponse:
    return portfolio_liquidity_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        liquidity_balance_status=liquidity_balance_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.post(
    "/portfolio-liquidity/generate",
    response_model=PortfolioLiquidityGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def owner_generate_portfolio_liquidity(
    payload: PortfolioLiquidityGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioLiquidityGenerateResponse:
    body = portfolio_liquidity_service.generate_portfolio_liquidity(
        session, owner_user_id=int(current_user.id), payload=payload
    )
    if body.replayed:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/ops/duplicate-clusters", response_model=DuplicateClusterListResponse, include_in_schema=False)
def ops_list_duplicate_clusters(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    cluster_type: str | None = Query(default=None),
    duplication_status: str | None = Query(default=None),
    liquidity_profile: str | None = Query(default=None),
    recommendation_action: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=True),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateClusterListResponse:
    ensure_ops_admin_access(current_user, settings)
    return duplicate_consolidation_service.list_clusters_ops(
        session,
        owner_user_id=owner_user_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        cluster_type=cluster_type,
        duplication_status=duplication_status,
        liquidity_profile=liquidity_profile,
        recommendation_action=recommendation_action,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/duplicate-clusters/{cluster_id}", response_model=DuplicateClusterRead, include_in_schema=False)
def ops_get_duplicate_cluster(
    cluster_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> DuplicateClusterRead:
    ensure_ops_admin_access(current_user, settings)
    return duplicate_consolidation_service.get_cluster_ops(
        session, owner_user_id=owner_user_id, cluster_id=cluster_id
    )


@app.get("/ops/duplicate-cluster-items", response_model=DuplicateClusterItemListResponse, include_in_schema=False)
def ops_list_duplicate_cluster_items(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    duplicate_cluster_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateClusterItemListResponse:
    ensure_ops_admin_access(current_user, settings)
    return duplicate_consolidation_service.list_cluster_items_ops(
        session,
        owner_user_id=owner_user_id,
        duplicate_cluster_id=duplicate_cluster_id,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        inventory_item_id=inventory_item_id,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/ops/duplicate-consolidation-recommendations",
    response_model=DuplicateConsolidationRecommendationListResponse,
    include_in_schema=False,
)
def ops_duplicate_consolidation_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    recommendation_action: str | None = Query(default=None),
    recommendation_status: str | None = Query(default=None, alias="status"),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateConsolidationRecommendationListResponse:
    ensure_ops_admin_access(current_user, settings)
    return duplicate_consolidation_service.list_consolidation_recommendations_ops(
        session,
        owner_user_id=owner_user_id,
        recommendation_action=recommendation_action,
        recommendation_status=recommendation_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/duplicate-history", response_model=DuplicateHistoryListResponse, include_in_schema=False)
def ops_duplicate_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    cluster_key_prefix: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> DuplicateHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    return duplicate_consolidation_service.list_duplicate_history_ops(
        session,
        owner_user_id=owner_user_id,
        cluster_key_prefix=cluster_key_prefix,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.get("/ops/portfolio-liquidity", response_model=PortfolioLiquiditySnapshotListResponse, include_in_schema=False)
def ops_list_portfolio_liquidity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    liquidity_balance_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    latest_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioLiquiditySnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_liquidity_service.list_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        liquidity_balance_status=liquidity_balance_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/ops/portfolio-liquidity/{snapshot_id}",
    response_model=PortfolioLiquiditySnapshotDetailResponse,
    include_in_schema=False,
)
def ops_get_portfolio_liquidity_snapshot(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> PortfolioLiquiditySnapshotDetailResponse:
    ensure_ops_admin_access(current_user, settings)
    snap, buckets = portfolio_liquidity_service.get_snapshot_detail_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_id=snapshot_id,
    )
    return PortfolioLiquiditySnapshotDetailResponse(snapshot=snap, buckets=buckets)


@app.get(
    "/ops/portfolio-liquidity-evidence",
    response_model=PortfolioLiquidityEvidenceListResponse,
    include_in_schema=False,
)
def ops_list_portfolio_liquidity_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_liquidity_snapshot_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioLiquidityEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_liquidity_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_liquidity_snapshot_id=portfolio_liquidity_snapshot_id,
        evidence_type=evidence_type,
        limit=limit,
        offset=offset,
    )


@app.get(
    "/ops/portfolio-liquidity-history",
    response_model=PortfolioLiquidityHistoryListResponse,
    include_in_schema=False,
)
def ops_portfolio_liquidity_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    liquidity_balance_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioLiquidityHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    return portfolio_liquidity_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        liquidity_balance_status=liquidity_balance_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=limit,
        offset=offset,
    )


@app.get("/reports/dashboard-rollups", response_model=OperationalReportingDashboardRollup)
def owner_operational_reports_dashboard_rollups(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OperationalReportingDashboardRollup:
    return operational_reporting_service.dashboard_rollup_owner(session, owner_user_id=int(current_user.id))


@app.post(
    "/reports/generate",
    response_model=OperationalReportRunDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def owner_generate_operational_report(
    payload: OperationalReportGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OperationalReportRunDetailRead:
    detail, replayed = operational_reporting_service.generate_operational_report(
        session,
        settings,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/reports", response_model=OperationalReportRunListResponse)
def owner_list_operational_reports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    report_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> OperationalReportRunListResponse:
    lim, off = operational_reporting_service.clamp_report_pagination(limit=limit, offset=offset)
    rows, total = operational_reporting_service.list_runs_owner(
        session,
        owner_user_id=int(current_user.id),
        report_type=report_type,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
        limit=lim,
        offset=off,
    )
    return operational_reporting_service.list_response_from_rows(rows, total=total, limit=lim, offset=off)


@app.get("/reports/{report_id}/download")
def download_owner_operational_report_csv(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file_id: int | None = Query(default=None),
) -> FileResponse:
    run_row = session.get(OperationalReportRun, report_id)

    if run_row is None or int(run_row.owner_user_id) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report run not found")
    if str(run_row.status) != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="report not ready for download")

    abs_path, frow = operational_reporting_service.resolve_operational_report_download_path(
        session,
        settings,
        owner_user_id=int(current_user.id),
        operational_report_run_id=report_id,
        operational_report_file_id=file_id,
        allow_ops_any_owner=False,
    )
    return FileResponse(
        path=str(abs_path),
        media_type="text/csv; charset=utf-8",
        filename=frow.file_name,
    )


@app.get("/reports/{report_id}", response_model=OperationalReportRunDetailRead)
def owner_get_operational_report(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> OperationalReportRunDetailRead:
    return operational_reporting_service.build_run_detail(
        session,
        owner_user_id=int(current_user.id),
        operational_report_run_id=report_id,
    )


@app.post(
    "/grading-reports/generate",
    response_model=GradingOperationalReportRunDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def owner_generate_grading_report(
    payload: GradingOperationalReportGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingOperationalReportRunDetailRead:
    detail, replayed = grading_reporting_service.generate_grading_report(
        session,
        settings,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/grading-reports", response_model=GradingOperationalReportRunListResponse)
def owner_list_grading_reports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    report_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingOperationalReportRunListResponse:
    lim, off = grading_reporting_service.clamp_grading_report_pagination(limit=limit, offset=offset)
    rows, total = grading_reporting_service.list_runs_owner(
        session,
        owner_user_id=int(current_user.id),
        report_type=report_type,
        status_filter=status_filter,
        created_from=created_from,
        created_to=created_to,
        limit=lim,
        offset=off,
    )
    return grading_reporting_service.list_response_from_rows(rows, total=total, limit=lim, offset=off)


@app.get("/grading-reports/{report_id}/download")
def download_owner_grading_report_csv(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file_id: int | None = Query(default=None),
) -> FileResponse:
    row = session.get(GradingOperationalReportRun, report_id)
    if row is None or int(row.owner_user_id) != int(current_user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report run not found")
    if str(row.status) != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="grading report not ready for download")
    abs_path, frow = grading_reporting_service.resolve_grading_report_download_path(
        session,
        settings,
        owner_user_id=int(current_user.id),
        grading_operational_report_run_id=report_id,
        grading_operational_report_file_id=file_id,
        allow_ops_any_owner=False,
    )
    return FileResponse(path=str(abs_path), media_type="text/csv; charset=utf-8", filename=frow.file_name)


@app.get("/grading-reports/{report_id}", response_model=GradingOperationalReportRunDetailRead)
def owner_get_grading_report(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingOperationalReportRunDetailRead:
    return grading_reporting_service.build_run_detail(
        session,
        owner_user_id=int(current_user.id),
        grading_operational_report_run_id=report_id,
    )


@app.get("/ops/reports/dashboard-rollups", response_model=OperationalReportingDashboardRollup, include_in_schema=False)
def ops_operational_reports_dashboard_rollups(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> OperationalReportingDashboardRollup:
    ensure_ops_admin_access(current_user, settings)
    if owner_user_id is None:
        return OperationalReportingDashboardRollup(recent_runs=[], failed_runs=[])
    return operational_reporting_service.dashboard_rollup_owner(session, owner_user_id=int(owner_user_id))


@app.get("/ops/reports", response_model=OperationalReportRunListResponse, include_in_schema=False)
def ops_list_operational_reports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    report_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> OperationalReportRunListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = operational_reporting_service.clamp_report_pagination(limit=limit, offset=offset)
    rows, total = operational_reporting_service.list_runs_ops(
        session,
        owner_user_id=owner_user_id,
        report_type=report_type,
        status=status_filter,
        created_from=created_from,
        created_to=created_to,
        limit=lim,
        offset=off,
    )
    return operational_reporting_service.list_response_from_rows(rows, total=total, limit=lim, offset=off)


@app.get("/ops/reports/{report_id}", response_model=OperationalReportRunDetailRead, include_in_schema=False)
def ops_get_operational_report(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> OperationalReportRunDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = session.get(OperationalReportRun, report_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report run not found")

    uid = int(row.owner_user_id)
    return operational_reporting_service.build_run_detail(
        session,
        owner_user_id=uid,
        operational_report_run_id=report_id,
        allow_cross_owner_ops=True,
    )


@app.get("/ops/grading-reports", response_model=GradingOperationalReportRunListResponse, include_in_schema=False)
def ops_list_grading_reports(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    report_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingOperationalReportRunListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_reporting_service.clamp_grading_report_pagination(limit=limit, offset=offset)
    rows, total = grading_reporting_service.list_runs_ops(
        session,
        owner_user_id=owner_user_id,
        report_type=report_type,
        status_filter=status_filter,
        created_from=created_from,
        created_to=created_to,
        limit=lim,
        offset=off,
    )
    return grading_reporting_service.list_response_from_rows(rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-reports/{report_id}", response_model=GradingOperationalReportRunDetailRead, include_in_schema=False)
def ops_get_grading_report(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingOperationalReportRunDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = session.get(GradingOperationalReportRun, report_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report run not found")
    return grading_reporting_service.build_run_detail(
        session,
        owner_user_id=int(row.owner_user_id),
        grading_operational_report_run_id=report_id,
        allow_cross_owner_ops=True,
    )


@app.get("/ops/grading-reports/{report_id}/download", include_in_schema=False)
def ops_download_grading_report_csv(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file_id: int | None = Query(default=None),
) -> FileResponse:
    ensure_ops_admin_access(current_user, settings)
    row = session.get(GradingOperationalReportRun, report_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="grading report run not found")
    if str(row.status) != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="grading report not ready for download")
    abs_path, frow = grading_reporting_service.resolve_grading_report_download_path(
        session,
        settings,
        owner_user_id=int(row.owner_user_id),
        grading_operational_report_run_id=report_id,
        grading_operational_report_file_id=file_id,
        allow_ops_any_owner=True,
    )
    return FileResponse(path=str(abs_path), media_type="text/csv; charset=utf-8", filename=frow.file_name)


@app.get("/ops/reports/{report_id}/download", include_in_schema=False)
def ops_download_operational_report_csv(
    report_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    file_id: int | None = Query(default=None),
) -> FileResponse:
    ensure_ops_admin_access(current_user, settings)
    row = session.get(OperationalReportRun, report_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report run not found")
    uid = int(row.owner_user_id)
    if str(row.status) != "COMPLETED":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="report not ready for download")

    abs_path, frow = operational_reporting_service.resolve_operational_report_download_path(
        session,
        settings,
        owner_user_id=uid,
        operational_report_run_id=report_id,
        operational_report_file_id=file_id,
        allow_ops_any_owner=True,
    )

    return FileResponse(
        path=str(abs_path),
        media_type="text/csv; charset=utf-8",
        filename=frow.file_name,
    )


@app.get("/grading-candidates/dashboard-summary", response_model=GradingCandidateDashboardSummary)
def owner_grading_candidates_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDashboardSummary:
    return grading_candidate_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.post(
    "/grading-candidates",
    response_model=GradingCandidateDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def owner_create_grading_candidate(
    payload: GradingCandidateCreatePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    detail, replayed = grading_candidate_service.create_candidate(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/grading-candidates", response_model=GradingCandidateListResponse)
def owner_list_grading_candidates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    status_filter: str | None = Query(default=None, alias="status"),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingCandidateListResponse:
    lim, off = grading_candidate_service.clamp_grading_list_pagination(limit, offset)
    rows, total = grading_candidate_service.list_candidates_owner(
        session,
        owner_user_id=int(current_user.id),
        status=status_filter,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return grading_candidate_service.list_response_from_rows(
        session,
        rows=rows,
        total=total,
        limit=lim,
        offset=off,
    )


@app.get("/grading-candidates/{candidate_id}", response_model=GradingCandidateDetailRead)
def owner_get_grading_candidate(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    row = grading_candidate_service.get_owner_candidate(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
    )
    return grading_candidate_service.build_detail_read(session, row)


@app.patch("/grading-candidates/{candidate_id}", response_model=GradingCandidateDetailRead)
def owner_patch_grading_candidate(
    candidate_id: int,
    payload: GradingCandidatePatchPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    return grading_candidate_service.patch_candidate(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
        payload=payload,
    )


@app.post("/grading-candidates/{candidate_id}/evidence", response_model=GradingCandidateDetailRead)
def owner_append_grading_candidate_evidence(
    candidate_id: int,
    payload: GradingCandidateEvidenceCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    return grading_candidate_service.append_evidence_row(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
        payload=payload,
    )


@app.post("/grading-candidates/{candidate_id}/review", response_model=GradingCandidateDetailRead)
def owner_grading_candidate_review(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    return grading_candidate_service.transition_review(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
    )


@app.post("/grading-candidates/{candidate_id}/ready", response_model=GradingCandidateDetailRead)
def owner_grading_candidate_ready(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    return grading_candidate_service.transition_ready(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
    )


@app.post("/grading-candidates/{candidate_id}/submit", response_model=GradingCandidateDetailRead)
def owner_grading_candidate_submit(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    return grading_candidate_service.transition_submit(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
    )


@app.post("/grading-candidates/{candidate_id}/grade", response_model=GradingCandidateDetailRead)
def owner_grading_candidate_grade(
    candidate_id: int,
    payload: GradingCandidateGradePayload | None = Body(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    body = payload or GradingCandidateGradePayload()
    return grading_candidate_service.transition_grade(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
        payload=body,
    )


@app.post("/grading-candidates/{candidate_id}/reject", response_model=GradingCandidateDetailRead)
def owner_grading_candidate_reject(
    candidate_id: int,
    payload: GradingCandidateRejectPayload | None = Body(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    body = payload or GradingCandidateRejectPayload()
    return grading_candidate_service.transition_reject(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
        payload=body,
    )


@app.post("/grading-candidates/{candidate_id}/archive", response_model=GradingCandidateDetailRead)
def owner_grading_candidate_archive(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingCandidateDetailRead:
    return grading_candidate_service.transition_archive(
        session,
        owner_user_id=int(current_user.id),
        candidate_id=candidate_id,
    )


@app.get("/ops/grading-candidates", response_model=GradingCandidateListResponse, include_in_schema=False)
def ops_list_grading_candidates(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingCandidateListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_candidate_service.clamp_grading_list_pagination(limit, offset)
    rows, total = grading_candidate_service.list_candidates_ops(
        session,
        owner_user_id=owner_user_id,
        status=status_filter,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return grading_candidate_service.list_response_from_rows(session, rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-candidates/{candidate_id}", response_model=GradingCandidateDetailRead, include_in_schema=False)
def ops_get_grading_candidate(
    candidate_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingCandidateDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = grading_candidate_service.get_ops_candidate(session, candidate_id=candidate_id)
    return grading_candidate_service.build_detail_read(session, row)


@app.get(
    "/ops/grading-candidate-events",
    response_model=GradingCandidateLifecycleEventListResponse,
    include_in_schema=False,
)
def ops_list_grading_candidate_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingCandidateLifecycleEventListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_candidate_service.clamp_grading_list_pagination(limit, offset)
    return grading_candidate_service.list_lifecycle_events_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        limit=lim,
        offset=off,
    )


@app.get(
    "/ops/grading-candidate-evidence",
    response_model=GradingCandidateEvidenceListResponse,
    include_in_schema=False,
)
def ops_list_grading_candidate_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingCandidateEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_candidate_service.clamp_grading_list_pagination(limit, offset)
    return grading_candidate_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        limit=lim,
        offset=off,
    )


@app.get("/grading-spreads/dashboard-summary", response_model=GradingSpreadDashboardSummary)
def owner_grading_spreads_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSpreadDashboardSummary:
    return grading_spread_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get("/ops/grading-spreads/dashboard-summary", response_model=GradingSpreadDashboardSummary, include_in_schema=False)
def ops_grading_spreads_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> GradingSpreadDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return grading_spread_service.dashboard_summary_ops(session, owner_user_id=owner_user_id)


@app.post(
    "/grading-spreads/generate",
    response_model=GradingSpreadDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def owner_generate_grading_spread(
    payload: GradingSpreadGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSpreadDetailRead:
    detail, replayed = grading_spread_service.generate_grading_spread(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/grading-spreads", response_model=GradingSpreadListResponse)
def owner_list_grading_spreads(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    spread_status: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSpreadListResponse:
    lim, off = grading_spread_service.clamp_grading_spread_pagination(limit, offset)
    rows, total = grading_spread_service.list_spreads_owner(
        session,
        owner_user_id=int(current_user.id),
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        target_grade=target_grade,
        spread_status=spread_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_spread_service.list_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-spreads/{spread_id}", response_model=GradingSpreadDetailRead)
def owner_get_grading_spread(
    spread_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSpreadDetailRead:
    row = grading_spread_service.get_spread_owner(session, owner_user_id=int(current_user.id), spread_id=spread_id)
    return grading_spread_service._detail_read(session, row)


@app.get("/grading-spreads/evidence", response_model=GradingSpreadEvidenceListResponse)
def owner_list_grading_spread_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    spread_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSpreadEvidenceListResponse:
    lim, off = grading_spread_service.clamp_grading_spread_pagination(limit, offset)
    rows, total = grading_spread_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        spread_id=spread_id,
        limit=lim,
        offset=off,
    )
    return grading_spread_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-spread-history", response_model=GradingSpreadHistoryListResponse)
def owner_list_grading_spread_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    canonical_comic_issue_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSpreadHistoryListResponse:
    lim, off = grading_spread_service.clamp_grading_spread_pagination(limit, offset)
    rows, total = grading_spread_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_spread_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-spreads", response_model=GradingSpreadListResponse, include_in_schema=False)
def ops_list_grading_spreads(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    spread_status: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSpreadListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_spread_service.clamp_grading_spread_pagination(limit, offset)
    rows, total = grading_spread_service.list_spreads_ops(
        session,
        owner_user_id=owner_user_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        target_grade=target_grade,
        spread_status=spread_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_spread_service.list_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-spreads/{spread_id}", response_model=GradingSpreadDetailRead, include_in_schema=False)
def ops_get_grading_spread(
    spread_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingSpreadDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = grading_spread_service.get_spread_ops(session, spread_id=spread_id)
    return grading_spread_service._detail_read(session, row)


@app.get("/ops/grading-spread-evidence", response_model=GradingSpreadEvidenceListResponse, include_in_schema=False)
def ops_list_grading_spread_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    spread_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSpreadEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_spread_service.clamp_grading_spread_pagination(limit, offset)
    rows, total = grading_spread_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        spread_id=spread_id,
        limit=lim,
        offset=off,
    )
    return grading_spread_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-spread-history", response_model=GradingSpreadHistoryListResponse, include_in_schema=False)
def ops_list_grading_spread_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSpreadHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_spread_service.clamp_grading_spread_pagination(limit, offset)
    rows, total = grading_spread_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_spread_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-roi/dashboard-summary", response_model=GradingRoiDashboardSummary)
def owner_grading_roi_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRoiDashboardSummary:
    return grading_roi_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get("/ops/grading-roi/dashboard-summary", response_model=GradingRoiDashboardSummary, include_in_schema=False)
def ops_grading_roi_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> GradingRoiDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return grading_roi_service.dashboard_summary_ops(session, owner_user_id=owner_user_id)


@app.post("/grading-roi/generate", response_model=GradingRoiDetailRead, status_code=status.HTTP_201_CREATED)
def owner_generate_grading_roi(
    payload: GradingRoiGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRoiDetailRead:
    detail, replayed = grading_roi_service.generate_grading_roi(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/grading-roi", response_model=GradingRoiListResponse)
def owner_list_grading_roi(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    roi_status: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRoiListResponse:
    lim, off = grading_roi_service.clamp_grading_roi_pagination(limit, offset)
    rows, total = grading_roi_service.list_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        roi_status=roi_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_roi_service.list_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-roi/{roi_id}", response_model=GradingRoiDetailRead)
def owner_get_grading_roi(
    roi_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRoiDetailRead:
    row = grading_roi_service.get_snapshot_owner(session, owner_user_id=int(current_user.id), roi_id=roi_id)
    return grading_roi_service._detail_read(session, row)


@app.get("/grading-roi/evidence", response_model=GradingRoiEvidenceListResponse)
def owner_list_grading_roi_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    roi_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRoiEvidenceListResponse:
    lim, off = grading_roi_service.clamp_grading_roi_pagination(limit, offset)
    rows, total = grading_roi_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        roi_id=roi_id,
        limit=lim,
        offset=off,
    )
    return grading_roi_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-roi/history", response_model=GradingRoiHistoryListResponse)
def owner_list_grading_roi_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRoiHistoryListResponse:
    lim, off = grading_roi_service.clamp_grading_roi_pagination(limit, offset)
    rows, total = grading_roi_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_roi_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-roi", response_model=GradingRoiListResponse, include_in_schema=False)
def ops_list_grading_roi(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    roi_status: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRoiListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_roi_service.clamp_grading_roi_pagination(limit, offset)
    rows, total = grading_roi_service.list_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        roi_status=roi_status,
        confidence_level=confidence_level,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_roi_service.list_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-roi/{roi_id}", response_model=GradingRoiDetailRead, include_in_schema=False)
def ops_get_grading_roi(
    roi_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingRoiDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = grading_roi_service.get_snapshot_ops(session, roi_id=roi_id)
    return grading_roi_service._detail_read(session, row)


@app.get("/ops/grading-roi/evidence", response_model=GradingRoiEvidenceListResponse, include_in_schema=False)
def ops_list_grading_roi_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    roi_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRoiEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_roi_service.clamp_grading_roi_pagination(limit, offset)
    rows, total = grading_roi_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        roi_id=roi_id,
        limit=lim,
        offset=off,
    )
    return grading_roi_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-roi/history", response_model=GradingRoiHistoryListResponse, include_in_schema=False)
def ops_list_grading_roi_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    target_grade: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRoiHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_roi_service.clamp_grading_roi_pagination(limit, offset)
    rows, total = grading_roi_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        canonical_comic_issue_id=canonical_comic_issue_id,
        target_grader=target_grader,
        target_grade=target_grade,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        limit=lim,
        offset=off,
    )
    return grading_roi_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-submission-batches/dashboard-summary", response_model=GradingSubmissionDashboardSummary)
def owner_grading_submission_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDashboardSummary:
    return grading_submission_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get(
    "/ops/grading-submission-batches/dashboard-summary",
    response_model=GradingSubmissionDashboardSummary,
    include_in_schema=False,
)
def ops_grading_submission_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> GradingSubmissionDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return grading_submission_service.dashboard_summary_ops(session, owner_user_id=owner_user_id)


@app.post("/grading-submission-batches", response_model=GradingSubmissionDetailRead, status_code=status.HTTP_201_CREATED)
def owner_create_grading_submission_batch(
    payload: GradingSubmissionCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.create_batch_owner(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/grading-submission-batches", response_model=GradingSubmissionListResponse)
def owner_list_grading_submission_batches(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    target_grader: str | None = Query(default=None),
    status: str | None = Query(default=None),
    submission_date_from: date | None = Query(default=None),
    submission_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSubmissionListResponse:
    lim, off = grading_submission_service.clamp_grading_submission_pagination(limit, offset)
    rows, total = grading_submission_service.list_batches_owner(
        session,
        owner_user_id=int(current_user.id),
        target_grader=target_grader,
        status=status,
        submission_date_from=submission_date_from,
        submission_date_to=submission_date_to,
        limit=lim,
        offset=off,
    )
    return grading_submission_service.batch_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-submission-batches/{batch_id}", response_model=GradingSubmissionDetailRead)
def owner_get_grading_submission_batch(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    batch = grading_submission_service.get_batch_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)
    return grading_submission_service._detail_read(session, batch)


@app.patch("/grading-submission-batches/{batch_id}", response_model=GradingSubmissionDetailRead)
def owner_patch_grading_submission_batch(
    batch_id: int,
    payload: GradingSubmissionPatchPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.patch_batch_owner(
        session,
        owner_user_id=int(current_user.id),
        batch_id=batch_id,
        payload=payload,
    )


@app.post("/grading-submission-batches/{batch_id}/ready", response_model=GradingSubmissionDetailRead)
def owner_mark_grading_submission_ready(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.mark_ready_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)


@app.post("/grading-submission-batches/{batch_id}/ship", response_model=GradingSubmissionDetailRead)
def owner_mark_grading_submission_shipped(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.mark_shipped_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)


@app.post("/grading-submission-batches/{batch_id}/receive", response_model=GradingSubmissionDetailRead)
def owner_mark_grading_submission_received(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.mark_received_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)


@app.post("/grading-submission-batches/{batch_id}/grading", response_model=GradingSubmissionDetailRead)
def owner_mark_grading_submission_grading(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.mark_grading_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)


@app.post("/grading-submission-batches/{batch_id}/return-ship", response_model=GradingSubmissionDetailRead)
def owner_mark_grading_submission_return_shipped(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.mark_return_shipped_owner(
        session,
        owner_user_id=int(current_user.id),
        batch_id=batch_id,
    )


@app.post("/grading-submission-batches/{batch_id}/complete", response_model=GradingSubmissionDetailRead)
def owner_mark_grading_submission_completed(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.mark_complete_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)


@app.post("/grading-submission-batches/{batch_id}/cancel", response_model=GradingSubmissionDetailRead)
def owner_mark_grading_submission_cancelled(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.mark_cancelled_owner(session, owner_user_id=int(current_user.id), batch_id=batch_id)


@app.post("/grading-submission-batches/{batch_id}/shipments", response_model=GradingSubmissionDetailRead)
def owner_add_grading_submission_shipment(
    batch_id: int,
    payload: GradingSubmissionShipmentCreatePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingSubmissionDetailRead:
    return grading_submission_service.add_shipment_owner(
        session,
        owner_user_id=int(current_user.id),
        batch_id=batch_id,
        payload=payload,
    )


@app.get("/ops/grading-submission-batches", response_model=GradingSubmissionListResponse, include_in_schema=False)
def ops_list_grading_submission_batches(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    status: str | None = Query(default=None),
    submission_date_from: date | None = Query(default=None),
    submission_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSubmissionListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_submission_service.clamp_grading_submission_pagination(limit, offset)
    rows, total = grading_submission_service.list_batches_ops(
        session,
        owner_user_id=owner_user_id,
        target_grader=target_grader,
        status=status,
        submission_date_from=submission_date_from,
        submission_date_to=submission_date_to,
        limit=lim,
        offset=off,
    )
    return grading_submission_service.batch_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-submission-batches/{batch_id}", response_model=GradingSubmissionDetailRead, include_in_schema=False)
def ops_get_grading_submission_batch(
    batch_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingSubmissionDetailRead:
    ensure_ops_admin_access(current_user, settings)
    batch = grading_submission_service.get_batch_ops(session, batch_id=batch_id)
    return grading_submission_service._detail_read(session, batch)


@app.get("/ops/grading-submission-events", response_model=GradingSubmissionEventListResponse, include_in_schema=False)
def ops_list_grading_submission_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    batch_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSubmissionEventListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_submission_service.clamp_grading_submission_pagination(limit, offset)
    rows, total = grading_submission_service.list_events_ops(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        limit=lim,
        offset=off,
    )
    return grading_submission_service.event_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-submission-shipments", response_model=GradingSubmissionShipmentListResponse, include_in_schema=False)
def ops_list_grading_submission_shipments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    batch_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingSubmissionShipmentListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_submission_service.clamp_grading_submission_pagination(limit, offset)
    rows, total = grading_submission_service.list_shipments_ops(
        session,
        owner_user_id=owner_user_id,
        batch_id=batch_id,
        limit=lim,
        offset=off,
    )
    return grading_submission_service.shipment_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-reconciliation/dashboard-summary", response_model=GradingReconciliationDashboardSummary)
def owner_grading_reconciliation_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingReconciliationDashboardSummary:
    return grading_reconciliation_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get(
    "/ops/grading-reconciliation/dashboard-summary",
    response_model=GradingReconciliationDashboardSummary,
    include_in_schema=False,
)
def ops_grading_reconciliation_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> GradingReconciliationDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return grading_reconciliation_service.dashboard_summary_ops(session, owner_user_id=owner_user_id)


@app.post("/grading-reconciliation/reconcile", response_model=GradingReconciliationDetailRead, status_code=status.HTTP_201_CREATED)
def owner_reconcile_grading_result(
    payload: GradingReconciliationReconcilePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingReconciliationDetailRead:
    return grading_reconciliation_service.reconcile_grading_result(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/grading-reconciliation", response_model=GradingReconciliationListResponse)
def owner_list_grading_reconciliation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    reconciliation_status: str | None = Query(default=None),
    grading_accuracy_status: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingReconciliationListResponse:
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_records_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        reconciliation_status=reconciliation_status,
        grading_accuracy_status=grading_accuracy_status,
        confidence_level=confidence_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.records_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-reconciliation/{record_id}", response_model=GradingReconciliationDetailRead)
def owner_get_grading_reconciliation(
    record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingReconciliationDetailRead:
    row = grading_reconciliation_service.get_record_owner(session, owner_user_id=int(current_user.id), record_id=record_id)
    return grading_reconciliation_service._detail_read(session, row)


@app.get("/grading-reconciliation/evidence", response_model=GradingReconciliationEvidenceListResponse)
def owner_list_grading_reconciliation_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    record_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingReconciliationEvidenceListResponse:
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        record_id=record_id,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-reconciliation/history", response_model=GradingReconciliationHistoryListResponse)
def owner_list_grading_reconciliation_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingReconciliationHistoryListResponse:
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grader-performance", response_model=GraderPerformanceSnapshotListResponse)
def owner_list_grader_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GraderPerformanceSnapshotListResponse:
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_performance_owner(
        session,
        owner_user_id=int(current_user.id),
        grader=grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.performance_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-reconciliation", response_model=GradingReconciliationListResponse, include_in_schema=False)
def ops_list_grading_reconciliation(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    reconciliation_status: str | None = Query(default=None),
    grading_accuracy_status: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingReconciliationListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_records_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        reconciliation_status=reconciliation_status,
        grading_accuracy_status=grading_accuracy_status,
        confidence_level=confidence_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.records_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-reconciliation/{record_id}", response_model=GradingReconciliationDetailRead, include_in_schema=False)
def ops_get_grading_reconciliation(
    record_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingReconciliationDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = grading_reconciliation_service.get_record_ops(session, record_id=record_id)
    return grading_reconciliation_service._detail_read(session, row)


@app.get("/ops/grading-reconciliation-evidence", response_model=GradingReconciliationEvidenceListResponse, include_in_schema=False)
def ops_list_grading_reconciliation_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    record_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingReconciliationEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        record_id=record_id,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-reconciliation-history", response_model=GradingReconciliationHistoryListResponse, include_in_schema=False)
def ops_list_grading_reconciliation_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    target_grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingReconciliationHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        target_grader=target_grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grader-performance", response_model=GraderPerformanceSnapshotListResponse, include_in_schema=False)
def ops_list_grader_performance(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GraderPerformanceSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_reconciliation_service.clamp_grading_reconciliation_pagination(limit, offset)
    rows, total = grading_reconciliation_service.list_performance_ops(
        session,
        owner_user_id=owner_user_id,
        grader=grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_reconciliation_service.performance_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-recommendations/dashboard-summary", response_model=GradingRecommendationDashboardSummary)
def owner_grading_recommendation_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRecommendationDashboardSummary:
    return grading_recommendation_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get(
    "/ops/grading-recommendations/dashboard-summary",
    response_model=GradingRecommendationDashboardSummary,
    include_in_schema=False,
)
def ops_grading_recommendation_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> GradingRecommendationDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return grading_recommendation_service.dashboard_summary_ops(session, owner_user_id=owner_user_id)


@app.get("/grading-risk/dashboard-summary", response_model=GradingRiskDashboardSummary)
def owner_grading_risk_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRiskDashboardSummary:
    return grading_risk_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get("/ops/grading-risk/dashboard-summary", response_model=GradingRiskDashboardSummary, include_in_schema=False)
def ops_grading_risk_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> GradingRiskDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return grading_risk_service.dashboard_summary_ops(session, owner_user_id=owner_user_id)


@app.post("/grading-recommendations/generate", response_model=GradingRecommendationDetailRead, status_code=status.HTTP_201_CREATED)
def owner_generate_grading_recommendation(
    payload: GradingRecommendationGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRecommendationDetailRead:
    return grading_recommendation_service.generate_grading_recommendation(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.post("/grading-risk/generate", response_model=GradingRiskDetailRead, status_code=status.HTTP_201_CREATED)
def owner_generate_grading_risk(
    payload: GradingRiskGeneratePayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRiskDetailRead:
    return grading_risk_service.generate_grading_risk(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )


@app.get("/grading-recommendations", response_model=GradingRecommendationListResponse)
def owner_list_grading_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommended_action: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_score: Decimal | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    recommended_grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRecommendationListResponse:
    lim, off = grading_recommendation_service.clamp_grading_recommendation_pagination(limit, offset)
    rows, total = grading_recommendation_service.list_recommendations_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommendation_strength=recommendation_strength,
        confidence_score=confidence_score,
        risk_level=risk_level,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_recommendation_service.recommendations_response_from_rows_with_risk(
        session,
        rows=rows,
        total=total,
        limit=lim,
        offset=off,
    )


@app.get("/grading-recommendations/evidence", response_model=GradingRecommendationEvidenceListResponse)
def owner_list_grading_recommendation_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRecommendationEvidenceListResponse:
    lim, off = grading_recommendation_service.clamp_grading_recommendation_pagination(limit, offset)
    rows, total = grading_recommendation_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        limit=lim,
        offset=off,
    )
    return grading_recommendation_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-risk", response_model=GradingRiskListResponse)
def owner_list_grading_risk(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    overall_risk_level: str | None = Query(default=None),
    overall_confidence_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRiskListResponse:
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_risk_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.risk_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-risk/evidence", response_model=GradingRiskEvidenceListResponse)
def owner_list_grading_risk_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRiskEvidenceListResponse:
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-confidence-factors", response_model=ConfidenceFactorSnapshotListResponse)
def owner_list_grading_confidence_factors(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConfidenceFactorSnapshotListResponse:
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_factors_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.factor_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-risk/history", response_model=RiskHistoryListResponse)
def owner_list_grading_risk_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    overall_risk_level: str | None = Query(default=None),
    overall_confidence_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RiskHistoryListResponse:
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-recommendations/history", response_model=GradingRecommendationHistoryListResponse)
def owner_list_grading_recommendation_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommended_action: str | None = Query(default=None),
    recommended_grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRecommendationHistoryListResponse:
    lim, off = grading_recommendation_service.clamp_grading_recommendation_pagination(limit, offset)
    rows, total = grading_recommendation_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_recommendation_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/grading-risk/{snapshot_id}", response_model=GradingRiskDetailRead)
def owner_get_grading_risk(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRiskDetailRead:
    row = grading_risk_service.get_risk_owner(session, owner_user_id=int(current_user.id), snapshot_id=snapshot_id)
    return grading_risk_service._detail_read(session, row)


@app.get("/grading-recommendations/{recommendation_id}", response_model=GradingRecommendationDetailRead)
def owner_get_grading_recommendation(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> GradingRecommendationDetailRead:
    row = grading_recommendation_service.get_recommendation_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
    )
    return grading_recommendation_service._detail_read(session, row)


@app.get("/ops/grading-recommendations", response_model=GradingRecommendationListResponse, include_in_schema=False)
def ops_list_grading_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommended_action: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_score: Decimal | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    recommended_grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRecommendationListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_recommendation_service.clamp_grading_recommendation_pagination(limit, offset)
    rows, total = grading_recommendation_service.list_recommendations_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommendation_strength=recommendation_strength,
        confidence_score=confidence_score,
        risk_level=risk_level,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_recommendation_service.recommendations_response_from_rows_with_risk(
        session,
        rows=rows,
        total=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/grading-recommendation-evidence", response_model=GradingRecommendationEvidenceListResponse, include_in_schema=False)
def ops_list_grading_recommendation_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    recommendation_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRecommendationEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_recommendation_service.clamp_grading_recommendation_pagination(limit, offset)
    rows, total = grading_recommendation_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        limit=lim,
        offset=off,
    )
    return grading_recommendation_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-risk", response_model=GradingRiskListResponse, include_in_schema=False)
def ops_list_grading_risk(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    overall_risk_level: str | None = Query(default=None),
    overall_confidence_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRiskListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_risk_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.risk_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-risk-evidence", response_model=GradingRiskEvidenceListResponse, include_in_schema=False)
def ops_list_grading_risk_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRiskEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_id=snapshot_id,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.evidence_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-confidence-factors", response_model=ConfidenceFactorSnapshotListResponse, include_in_schema=False)
def ops_list_grading_confidence_factors(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConfidenceFactorSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_factors_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_id=snapshot_id,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.factor_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-risk-history", response_model=RiskHistoryListResponse, include_in_schema=False)
def ops_list_grading_risk_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    overall_risk_level: str | None = Query(default=None),
    overall_confidence_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> RiskHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_risk_service.clamp_grading_risk_pagination(limit, offset)
    rows, total = grading_risk_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        overall_risk_level=overall_risk_level,
        overall_confidence_level=overall_confidence_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_risk_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-recommendation-history", response_model=GradingRecommendationHistoryListResponse, include_in_schema=False)
def ops_list_grading_recommendation_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    grading_candidate_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommended_action: str | None = Query(default=None),
    recommended_grader: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> GradingRecommendationHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = grading_recommendation_service.clamp_grading_recommendation_pagination(limit, offset)
    rows, total = grading_recommendation_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        grading_candidate_id=grading_candidate_id,
        inventory_item_id=inventory_item_id,
        recommended_action=recommended_action,
        recommended_grader=recommended_grader,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )
    return grading_recommendation_service.history_response_from_rows(rows=rows, total=total, limit=lim, offset=off)


@app.get("/ops/grading-risk/{snapshot_id}", response_model=GradingRiskDetailRead, include_in_schema=False)
def ops_get_grading_risk(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingRiskDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = grading_risk_service.get_risk_ops(session, snapshot_id=snapshot_id)
    return grading_risk_service._detail_read(session, row)


@app.get("/ops/grading-recommendations/{recommendation_id}", response_model=GradingRecommendationDetailRead, include_in_schema=False)
def ops_get_grading_recommendation(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> GradingRecommendationDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = grading_recommendation_service.get_recommendation_ops(session, recommendation_id=recommendation_id)
    return grading_recommendation_service._detail_read(session, row)


@app.post("/portfolio-recommendations/generate", response_model=PortfolioRecommendationGenerateResponse, status_code=status.HTTP_201_CREATED)
def owner_generate_portfolio_recommendations(
    payload: PortfolioRecommendationGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioRecommendationGenerateResponse:
    body = portfolio_recommendation_service.generate_portfolio_recommendations(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if body.replayed:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/portfolio-recommendations", response_model=PortfolioRecommendationListResponse)
def owner_list_portfolio_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommendation_action: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioRecommendationListResponse:
    lim, off = portfolio_recommendation_service.clamp_pagination(limit=limit, offset=offset)
    return portfolio_recommendation_service.list_recommendations_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/portfolio-recommendations/{recommendation_id}", response_model=PortfolioRecommendationDetailRead)
def owner_get_portfolio_recommendation(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> PortfolioRecommendationDetailRead:
    row = portfolio_recommendation_service.get_recommendation_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
    )
    return portfolio_recommendation_service._detail_read(session, row)


@app.get("/portfolio-recommendation-evidence", response_model=PortfolioRecommendationEvidenceListResponse)
def owner_list_portfolio_recommendation_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    recommendation_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioRecommendationEvidenceListResponse:
    lim, off = portfolio_recommendation_service.clamp_pagination(limit=limit, offset=offset)
    return portfolio_recommendation_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        recommendation_id=recommendation_id,
        evidence_type=evidence_type,
        limit=lim,
        offset=off,
    )


@app.get("/portfolio-recommendation-history", response_model=PortfolioRecommendationHistoryListResponse)
def owner_list_portfolio_recommendation_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommendation_action: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioRecommendationHistoryListResponse:
    lim, off = portfolio_recommendation_service.clamp_pagination(limit=limit, offset=offset)
    return portfolio_recommendation_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/ops/portfolio-recommendations", response_model=PortfolioRecommendationListResponse, include_in_schema=False)
def ops_list_portfolio_recommendations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommendation_action: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioRecommendationListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = portfolio_recommendation_service.clamp_pagination(limit=limit, offset=offset)
    return portfolio_recommendation_service.list_recommendations_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/ops/portfolio-recommendations/{recommendation_id}", response_model=PortfolioRecommendationDetailRead, include_in_schema=False)
def ops_get_portfolio_recommendation(
    recommendation_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> PortfolioRecommendationDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = portfolio_recommendation_service.get_recommendation_ops(session, recommendation_id=recommendation_id)
    return portfolio_recommendation_service._detail_read(session, row)


@app.get("/ops/portfolio-recommendation-evidence", response_model=PortfolioRecommendationEvidenceListResponse, include_in_schema=False)
def ops_list_portfolio_recommendation_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    recommendation_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioRecommendationEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = portfolio_recommendation_service.clamp_pagination(limit=limit, offset=offset)
    return portfolio_recommendation_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        recommendation_id=recommendation_id,
        evidence_type=evidence_type,
        limit=lim,
        offset=off,
    )


@app.get("/ops/portfolio-recommendation-history", response_model=PortfolioRecommendationHistoryListResponse, include_in_schema=False)
def ops_list_portfolio_recommendation_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    recommendation_action: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PortfolioRecommendationHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = portfolio_recommendation_service.clamp_pagination(limit=limit, offset=offset)
    return portfolio_recommendation_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        inventory_item_id=inventory_item_id,
        recommendation_action=recommendation_action,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.post("/acquisition-priorities/generate", response_model=AcquisitionPriorityGenerateResponse, status_code=status.HTTP_201_CREATED)
def owner_generate_acquisition_priorities(
    payload: AcquisitionPriorityGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionPriorityGenerateResponse:
    body = acquisition_priority_service.generate_acquisition_priorities(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if body.replayed:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/acquisition-priorities", response_model=AcquisitionPriorityListResponse)
def owner_list_acquisition_priorities(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    acquisition_category: str | None = Query(default=None),
    acquisition_priority: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AcquisitionPriorityListResponse:
    lim, off = acquisition_priority_service.clamp_pagination(limit=limit, offset=offset)
    return acquisition_priority_service.list_priorities_owner(
        session,
        owner_user_id=int(current_user.id),
        acquisition_category=acquisition_category,
        acquisition_priority=acquisition_priority,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/acquisition-priorities/{snapshot_id}", response_model=AcquisitionPriorityDetailRead)
def owner_get_acquisition_priority(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> AcquisitionPriorityDetailRead:
    row = acquisition_priority_service.get_priority_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
    )
    return acquisition_priority_service._detail_read(session, row)


@app.get("/acquisition-priority-evidence", response_model=AcquisitionPriorityEvidenceListResponse)
def owner_list_acquisition_priority_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    acquisition_priority_snapshot_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AcquisitionPriorityEvidenceListResponse:
    lim, off = acquisition_priority_service.clamp_pagination(limit=limit, offset=offset)
    return acquisition_priority_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        acquisition_priority_snapshot_id=acquisition_priority_snapshot_id,
        evidence_type=evidence_type,
        limit=lim,
        offset=off,
    )


@app.get("/acquisition-priority-history", response_model=AcquisitionPriorityHistoryListResponse)
def owner_list_acquisition_priority_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    acquisition_category: str | None = Query(default=None),
    acquisition_priority: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AcquisitionPriorityHistoryListResponse:
    lim, off = acquisition_priority_service.clamp_pagination(limit=limit, offset=offset)
    return acquisition_priority_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        acquisition_category=acquisition_category,
        acquisition_priority=acquisition_priority,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/ops/acquisition-priorities", response_model=AcquisitionPriorityListResponse, include_in_schema=False)
def ops_list_acquisition_priorities(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    acquisition_category: str | None = Query(default=None),
    acquisition_priority: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AcquisitionPriorityListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = acquisition_priority_service.clamp_pagination(limit=limit, offset=offset)
    return acquisition_priority_service.list_priorities_ops(
        session,
        owner_user_id=owner_user_id,
        acquisition_category=acquisition_category,
        acquisition_priority=acquisition_priority,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/ops/acquisition-priorities/{snapshot_id}", response_model=AcquisitionPriorityDetailRead, include_in_schema=False)
def ops_get_acquisition_priority(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> AcquisitionPriorityDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = acquisition_priority_service.get_priority_ops(session, snapshot_id=snapshot_id)
    return acquisition_priority_service._detail_read(session, row)


@app.get("/ops/acquisition-priority-evidence", response_model=AcquisitionPriorityEvidenceListResponse, include_in_schema=False)
def ops_list_acquisition_priority_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    acquisition_priority_snapshot_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AcquisitionPriorityEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = acquisition_priority_service.clamp_pagination(limit=limit, offset=offset)
    return acquisition_priority_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        acquisition_priority_snapshot_id=acquisition_priority_snapshot_id,
        evidence_type=evidence_type,
        limit=lim,
        offset=off,
    )


@app.get("/ops/acquisition-priority-history", response_model=AcquisitionPriorityHistoryListResponse, include_in_schema=False)
def ops_list_acquisition_priority_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    acquisition_category: str | None = Query(default=None),
    acquisition_priority: str | None = Query(default=None),
    recommendation_strength: str | None = Query(default=None),
    confidence_level: str | None = Query(default=None),
    risk_level: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> AcquisitionPriorityHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = acquisition_priority_service.clamp_pagination(limit=limit, offset=offset)
    return acquisition_priority_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        acquisition_category=acquisition_category,
        acquisition_priority=acquisition_priority,
        recommendation_strength=recommendation_strength,
        confidence_level=confidence_level,
        risk_level=risk_level,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.post("/concentration-risk/generate", response_model=ConcentrationRiskGenerateResponse, status_code=status.HTTP_201_CREATED)
def owner_generate_concentration_risk(
    payload: ConcentrationRiskGeneratePayload,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConcentrationRiskGenerateResponse:
    body = concentration_risk_service.generate_concentration_risk(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if body.replayed:
        response.status_code = status.HTTP_200_OK
    return body


@app.get("/concentration-risk", response_model=ConcentrationRiskListResponse)
def owner_list_concentration_risk(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    concentration_type: str | None = Query(default=None),
    concentration_key: str | None = Query(default=None),
    exposure_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskListResponse:
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_concentration_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        concentration_type=concentration_type,
        concentration_key=concentration_key,
        exposure_status=exposure_status,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/concentration-risk/{snapshot_id}", response_model=ConcentrationRiskDetailRead)
def owner_get_concentration_risk(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConcentrationRiskDetailRead:
    row = concentration_risk_service.get_concentration_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
    )
    return concentration_risk_service._detail_read(session, row)


@app.get("/concentration-risk-evidence", response_model=ConcentrationRiskEvidenceListResponse)
def owner_list_concentration_risk_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    concentration_risk_snapshot_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskEvidenceListResponse:
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        concentration_risk_snapshot_id=concentration_risk_snapshot_id,
        evidence_type=evidence_type,
        limit=lim,
        offset=off,
    )


@app.get("/concentration-risk-factors", response_model=ConcentrationRiskFactorListResponse)
def owner_list_concentration_risk_factors(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    concentration_risk_snapshot_id: int | None = Query(default=None),
    factor_key: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskFactorListResponse:
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_factors_owner(
        session,
        owner_user_id=int(current_user.id),
        concentration_risk_snapshot_id=concentration_risk_snapshot_id,
        factor_key=factor_key,
        limit=lim,
        offset=off,
    )


@app.get("/concentration-risk-history", response_model=ConcentrationRiskHistoryListResponse)
def owner_list_concentration_risk_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    portfolio_id: int | None = Query(default=None),
    concentration_type: str | None = Query(default=None),
    concentration_key: str | None = Query(default=None),
    exposure_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskHistoryListResponse:
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_history_owner(
        session,
        owner_user_id=int(current_user.id),
        portfolio_id=portfolio_id,
        concentration_type=concentration_type,
        concentration_key=concentration_key,
        exposure_status=exposure_status,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/ops/concentration-risk", response_model=ConcentrationRiskListResponse, include_in_schema=False)
def ops_list_concentration_risk(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    concentration_type: str | None = Query(default=None),
    concentration_key: str | None = Query(default=None),
    exposure_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_concentration_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        concentration_type=concentration_type,
        concentration_key=concentration_key,
        exposure_status=exposure_status,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/ops/concentration-risk/{snapshot_id}", response_model=ConcentrationRiskDetailRead, include_in_schema=False)
def ops_get_concentration_risk(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ConcentrationRiskDetailRead:
    ensure_ops_admin_access(current_user, settings)
    row = concentration_risk_service.get_concentration_ops(session, snapshot_id=snapshot_id)
    return concentration_risk_service._detail_read(session, row)


@app.get("/ops/concentration-risk-evidence", response_model=ConcentrationRiskEvidenceListResponse, include_in_schema=False)
def ops_list_concentration_risk_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    concentration_risk_snapshot_id: int | None = Query(default=None),
    evidence_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        concentration_risk_snapshot_id=concentration_risk_snapshot_id,
        evidence_type=evidence_type,
        limit=lim,
        offset=off,
    )


@app.get("/ops/concentration-risk-factors", response_model=ConcentrationRiskFactorListResponse, include_in_schema=False)
def ops_list_concentration_risk_factors(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    concentration_risk_snapshot_id: int | None = Query(default=None),
    factor_key: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskFactorListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_factors_ops(
        session,
        owner_user_id=owner_user_id,
        concentration_risk_snapshot_id=concentration_risk_snapshot_id,
        factor_key=factor_key,
        limit=lim,
        offset=off,
    )


@app.get("/ops/concentration-risk-history", response_model=ConcentrationRiskHistoryListResponse, include_in_schema=False)
def ops_list_concentration_risk_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    portfolio_id: int | None = Query(default=None),
    concentration_type: str | None = Query(default=None),
    concentration_key: str | None = Query(default=None),
    exposure_status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConcentrationRiskHistoryListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = concentration_risk_service.clamp_pagination(limit=limit, offset=offset)
    return concentration_risk_service.list_history_ops(
        session,
        owner_user_id=owner_user_id,
        portfolio_id=portfolio_id,
        concentration_type=concentration_type,
        concentration_key=concentration_key,
        exposure_status=exposure_status,
        date_from=date_from,
        date_to=date_to,
        limit=lim,
        offset=off,
    )


@app.get("/sales/dashboard-summary", response_model=SalesDashboardSummary)
def owner_sales_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SalesDashboardSummary:
    return sales_ledger_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get("/sales", response_model=SaleRecordListResponse)
def owner_list_sales(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    channel: str | None = Query(default=None),
    status: str | None = Query(default=None),
    sale_date_from: date | None = Query(default=None),
    sale_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SaleRecordListResponse:
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = sales_ledger_service.list_sales_owner(
        session,
        owner_user_id=int(current_user.id),
        limit=lim,
        offset=off,
        channel=channel,
        status=status,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    counts = sales_ledger_service._load_sale_counts(session, [int(row.id) for row in rows])  # noqa: SLF001
    return SaleRecordListResponse(
        items=[
            sales_ledger_service._sale_read(  # noqa: SLF001
                row,
                event_count=counts.get(int(row.id), {}).get("event_count", 0),
                line_item_count=counts.get(int(row.id), {}).get("line_item_count", 0),
                adjustment_count=counts.get(int(row.id), {}).get("adjustment_count", 0),
            )
            for row in rows
        ],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.post("/sales", response_model=SaleRecordDetailRead, status_code=status.HTTP_201_CREATED)
def owner_create_sale(
    payload: SaleRecordCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SaleRecordDetailRead:
    detail, replayed = sales_ledger_service.create_sale(session, owner_user_id=int(current_user.id), payload=payload)
    if replayed:
        response.status_code = status.HTTP_200_OK
    return detail


@app.get("/sales/{sale_id}", response_model=SaleRecordDetailRead)
def owner_get_sale(
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SaleRecordDetailRead:
    return sales_ledger_service.build_sale_detail(session, owner_user_id=int(current_user.id), sale_id=sale_id)


@app.patch("/sales/{sale_id}", response_model=SaleRecordDetailRead)
def owner_patch_sale(
    sale_id: int,
    payload: SaleRecordPatch,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SaleRecordDetailRead:
    return sales_ledger_service.update_sale(session, owner_user_id=int(current_user.id), sale_id=sale_id, payload=payload)


@app.post("/sales/{sale_id}/record", response_model=SaleRecordDetailRead)
def owner_record_sale(
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SaleRecordDetailRead:
    return sales_ledger_service.record_sale(session, owner_user_id=int(current_user.id), sale_id=sale_id)


@app.post("/sales/{sale_id}/void", response_model=SaleRecordDetailRead)
def owner_void_sale(
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SaleRecordDetailRead:
    return sales_ledger_service.void_sale(session, owner_user_id=int(current_user.id), sale_id=sale_id)


@app.get("/sales/{sale_id}/events", response_model=SaleLifecycleEventListResponse)
def owner_list_sale_events(
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> SaleLifecycleEventListResponse:
    detail = sales_ledger_service.build_sale_detail(session, owner_user_id=int(current_user.id), sale_id=sale_id)
    return SaleLifecycleEventListResponse(
        items=detail.events,
        total_items=len(detail.events),
        limit=len(detail.events),
        offset=0,
    )


@app.get("/ops/sales", response_model=SaleRecordListResponse)
def ops_list_sales(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sale_date_from: date | None = Query(default=None),
    sale_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SaleRecordListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = sales_ledger_service.list_sales_ops(
        session,
        owner_user_id=owner_user_id,
        limit=lim,
        offset=off,
        channel=channel,
        status=status_filter,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    counts = sales_ledger_service._load_sale_counts(session, [int(row.id) for row in rows])  # noqa: SLF001
    return SaleRecordListResponse(
        items=[
            sales_ledger_service._sale_read(  # noqa: SLF001
                row,
                event_count=counts.get(int(row.id), {}).get("event_count", 0),
                line_item_count=counts.get(int(row.id), {}).get("line_item_count", 0),
                adjustment_count=counts.get(int(row.id), {}).get("adjustment_count", 0),
            )
            for row in rows
        ],
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/sales/{sale_id}", response_model=SaleRecordDetailRead)
def ops_get_sale(
    sale_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> SaleRecordDetailRead:
    ensure_ops_admin_access(current_user, settings)
    return sales_ledger_service.build_sale_detail(
        session,
        owner_user_id=0,
        sale_id=sale_id,
        allow_cross_owner_ops=True,
    )


@app.get("/ops/sale-events", response_model=SaleLifecycleEventListResponse)
def ops_list_sale_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sale_date_from: date | None = Query(default=None),
    sale_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SaleLifecycleEventListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = sales_ledger_service.list_sale_events_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        status=status_filter,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
        limit=lim,
        offset=off,
    )
    return SaleLifecycleEventListResponse(
        items=[sales_ledger_service._event_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/sale-financial-adjustments", response_model=SaleFinancialAdjustmentListResponse)
def ops_list_sale_financial_adjustments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    sale_date_from: date | None = Query(default=None),
    sale_date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> SaleFinancialAdjustmentListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = sales_ledger_service.list_sale_adjustments_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        status=status_filter,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
        limit=lim,
        offset=off,
    )
    return SaleFinancialAdjustmentListResponse(
        items=[sales_ledger_service._adjustment_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/liquidity/dashboard-summary", response_model=LiquidityDashboardSummary)
def owner_liquidity_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    snapshot_date: date | None = Query(default=None),
) -> LiquidityDashboardSummary:
    return liquidity_engine_service.dashboard_summary_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_date=snapshot_date,
    )


@app.get("/liquidity", response_model=InventoryLiquidityListResponse)
def owner_list_liquidity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    channel: str | None = Query(default=None),
    liquidity_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    snapshot_date: date | None = Query(default=None),
    evaluation_window_days: int = Query(default=365, ge=1, le=3650),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> InventoryLiquidityListResponse:
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_liquidity_owner(
        session,
        owner_user_id=int(current_user.id),
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
        snapshot_date=snapshot_date,
        evaluation_window_days=evaluation_window_days,
    )
    return InventoryLiquidityListResponse(
        items=[liquidity_engine_service._snapshot_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/liquidity/evidence", response_model=InventoryLiquidityEvidenceListResponse)
def owner_list_liquidity_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    channel: str | None = Query(default=None),
    liquidity_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    snapshot_date: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> InventoryLiquidityEvidenceListResponse:
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_liquidity_evidence_owner(
        session,
        owner_user_id=int(current_user.id),
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
        snapshot_date=snapshot_date,
    )
    return InventoryLiquidityEvidenceListResponse(
        items=[liquidity_engine_service._evidence_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/listing-velocity", response_model=ListingVelocityListResponse)
def owner_list_listing_velocity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingVelocityListResponse:
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_velocity_owner(
        session,
        owner_user_id=int(current_user.id),
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return ListingVelocityListResponse(
        items=[liquidity_engine_service._velocity_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/listing-staleness-events", response_model=ListingStalenessEventListResponse)
def owner_list_listing_staleness_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingStalenessEventListResponse:
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_staleness_owner(
        session,
        owner_user_id=int(current_user.id),
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return ListingStalenessEventListResponse(
        items=[liquidity_engine_service._staleness_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/liquidity/{snapshot_id}", response_model=InventoryLiquiditySnapshotRead)
def owner_get_liquidity(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> InventoryLiquiditySnapshotRead:
    row = liquidity_engine_service.build_snapshot_detail_owner(
        session,
        owner_user_id=int(current_user.id),
        snapshot_id=snapshot_id,
    )
    return liquidity_engine_service._snapshot_read(row)  # noqa: SLF001


@app.get("/ops/liquidity/dashboard-summary", response_model=LiquidityDashboardSummary)
def ops_liquidity_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    snapshot_date: date | None = Query(default=None),
) -> LiquidityDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return liquidity_engine_service.dashboard_summary_ops(
        session,
        owner_user_id=owner_user_id,
        snapshot_date=snapshot_date,
    )


@app.get("/ops/liquidity", response_model=InventoryLiquidityListResponse)
def ops_list_liquidity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    liquidity_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> InventoryLiquidityListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_liquidity_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return InventoryLiquidityListResponse(
        items=[liquidity_engine_service._snapshot_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/liquidity/{snapshot_id}", response_model=InventoryLiquiditySnapshotRead)
def ops_get_liquidity(
    snapshot_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> InventoryLiquiditySnapshotRead:
    ensure_ops_admin_access(current_user, settings)
    row = liquidity_engine_service.build_snapshot_detail_ops(session, snapshot_id=snapshot_id)
    return liquidity_engine_service._snapshot_read(row)  # noqa: SLF001


@app.get("/ops/liquidity-evidence", response_model=InventoryLiquidityEvidenceListResponse)
def ops_list_liquidity_evidence(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    liquidity_status: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> InventoryLiquidityEvidenceListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_liquidity_evidence_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        liquidity_status=liquidity_status,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return InventoryLiquidityEvidenceListResponse(
        items=[liquidity_engine_service._evidence_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/convention/dashboard-summary", response_model=ConventionDashboardSummary)
def owner_convention_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionDashboardSummary:
    return convention_operations_service.dashboard_summary_owner(session, owner_user_id=int(current_user.id))


@app.get("/convention-events", response_model=ConventionEventListResponse)
def owner_list_convention_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionEventListResponse:
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_events_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return ConventionEventListResponse(
        items=[convention_operations_service._event_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.post("/convention-events", response_model=ConventionEventRead, status_code=status.HTTP_201_CREATED)
def owner_create_convention_event(
    payload: ConventionEventCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionEventRead:
    row, replayed = convention_operations_service.create_convention_event(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return convention_operations_service._event_read(row)  # noqa: SLF001


@app.get("/convention-events/{convention_event_id}", response_model=ConventionEventRead)
def owner_get_convention_event(
    convention_event_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionEventRead:
    row = convention_operations_service.get_convention_event_owner(
        session,
        owner_user_id=int(current_user.id),
        convention_event_id=convention_event_id,
    )
    return convention_operations_service._event_read(row)  # noqa: SLF001


@app.patch("/convention-events/{convention_event_id}", response_model=ConventionEventRead)
def owner_patch_convention_event(
    convention_event_id: int,
    payload: ConventionEventPatch,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionEventRead:
    row = convention_operations_service.patch_convention_event(
        session,
        owner_user_id=int(current_user.id),
        convention_event_id=convention_event_id,
        payload=payload,
    )
    return convention_operations_service._event_read(row)  # noqa: SLF001


@app.post("/convention-events/{convention_event_id}/activate", response_model=ConventionEventRead)
def owner_activate_convention_event(
    convention_event_id: int,
    payload: ConventionReplayBody | None = Body(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionEventRead:
    row = convention_operations_service.activate_convention_event(
        session,
        owner_user_id=int(current_user.id),
        convention_event_id=convention_event_id,
        replay_key=payload.replay_key if payload else None,
    )
    return convention_operations_service._event_read(row)  # noqa: SLF001


@app.post("/convention-events/{convention_event_id}/complete", response_model=ConventionEventRead)
def owner_complete_convention_event(
    convention_event_id: int,
    payload: ConventionReplayBody | None = Body(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionEventRead:
    row = convention_operations_service.complete_convention_event(
        session,
        owner_user_id=int(current_user.id),
        convention_event_id=convention_event_id,
        replay_key=payload.replay_key if payload else None,
    )
    return convention_operations_service._event_read(row)  # noqa: SLF001


@app.get("/convention-assignments", response_model=ConventionAssignmentListResponse)
def owner_list_convention_assignments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionAssignmentListResponse:
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_assignments_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionAssignmentListResponse(
        items=[convention_operations_service._assignment_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.post("/convention-assignments", response_model=ConventionAssignmentRead, status_code=status.HTTP_201_CREATED)
def owner_create_convention_assignment(
    payload: ConventionAssignmentCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionAssignmentRead:
    row, replayed = convention_operations_service.create_convention_assignment(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return convention_operations_service._assignment_read(row)  # noqa: SLF001


@app.get("/convention-movements", response_model=ConventionMovementListResponse)
def owner_list_convention_movements(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionMovementListResponse:
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_movements_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionMovementListResponse(
        items=[convention_operations_service._movement_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.post("/convention-movements", response_model=ConventionMovementRead, status_code=status.HTTP_201_CREATED)
def owner_create_convention_movement(
    payload: ConventionMovementCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionMovementRead:
    row, replayed = convention_operations_service.create_convention_movement(
        session,
        owner_user_id=int(current_user.id),
        created_by_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return convention_operations_service._movement_read(row)  # noqa: SLF001


@app.get("/convention-price-snapshots", response_model=ConventionPriceSnapshotListResponse)
def owner_list_convention_price_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionPriceSnapshotListResponse:
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_price_snapshots_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionPriceSnapshotListResponse(
        items=[convention_operations_service._price_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.post("/convention-price-snapshots", response_model=ConventionPriceSnapshotRead, status_code=status.HTTP_201_CREATED)
def owner_create_convention_price_snapshot(
    payload: ConventionPriceSnapshotCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionPriceSnapshotRead:
    row, replayed = convention_operations_service.create_convention_price_snapshot(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return convention_operations_service._price_read(row)  # noqa: SLF001


@app.get("/convention-sale-sessions", response_model=ConventionSaleSessionListResponse)
def owner_list_convention_sale_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionSaleSessionListResponse:
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_sale_sessions_owner(
        session,
        owner_user_id=int(current_user.id),
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionSaleSessionListResponse(
        items=[convention_operations_service._session_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.post("/convention-sale-sessions", response_model=ConventionSaleSessionRead, status_code=status.HTTP_201_CREATED)
def owner_create_convention_sale_session(
    payload: ConventionSaleSessionCreate,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionSaleSessionRead:
    row, replayed = convention_operations_service.create_convention_sale_session(
        session,
        owner_user_id=int(current_user.id),
        payload=payload,
    )
    if replayed:
        response.status_code = status.HTTP_200_OK
    return convention_operations_service._session_read(row)  # noqa: SLF001


@app.post("/convention-sale-sessions/{convention_sale_session_id}/close", response_model=ConventionSaleSessionRead)
def owner_close_convention_sale_session(
    convention_sale_session_id: int,
    payload: ConventionReplayBody | None = Body(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ConventionSaleSessionRead:
    row = convention_operations_service.close_convention_sale_session(
        session,
        owner_user_id=int(current_user.id),
        convention_sale_session_id=convention_sale_session_id,
        replay_key=payload.replay_key if payload else None,
    )
    return convention_operations_service._session_read(row)  # noqa: SLF001


@app.get("/ops/convention/dashboard-summary", response_model=ConventionDashboardSummary)
def ops_convention_dashboard_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
) -> ConventionDashboardSummary:
    ensure_ops_admin_access(current_user, settings)
    return convention_operations_service.dashboard_summary_ops(session, owner_user_id=owner_user_id)


@app.get("/ops/convention-events", response_model=ConventionEventListResponse)
def ops_list_convention_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionEventListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_events_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return ConventionEventListResponse(
        items=[convention_operations_service._event_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/convention-assignments", response_model=ConventionAssignmentListResponse)
def ops_list_convention_assignments(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionAssignmentListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_assignments_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionAssignmentListResponse(
        items=[convention_operations_service._assignment_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/convention-movements", response_model=ConventionMovementListResponse)
def ops_list_convention_movements(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionMovementListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_movements_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionMovementListResponse(
        items=[convention_operations_service._movement_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/convention-price-snapshots", response_model=ConventionPriceSnapshotListResponse)
def ops_list_convention_price_snapshots(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionPriceSnapshotListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_price_snapshots_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionPriceSnapshotListResponse(
        items=[convention_operations_service._price_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/convention-sale-sessions", response_model=ConventionSaleSessionListResponse)
def ops_list_convention_sale_sessions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    event_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    convention_event_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ConventionSaleSessionListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = convention_operations_service.clamp_convention_pagination(limit=limit, offset=offset)
    rows, total = convention_operations_service.list_convention_sale_sessions_ops(
        session,
        owner_user_id=owner_user_id,
        event_type=event_type,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        inventory_item_id=inventory_item_id,
        convention_event_id=convention_event_id,
        limit=lim,
        offset=off,
    )
    return ConventionSaleSessionListResponse(
        items=[convention_operations_service._session_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-velocity", response_model=ListingVelocityListResponse)
def ops_list_listing_velocity(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingVelocityListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_velocity_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return ListingVelocityListResponse(
        items=[liquidity_engine_service._velocity_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


@app.get("/ops/listing-staleness-events", response_model=ListingStalenessEventListResponse)
def ops_list_listing_staleness_events(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    owner_user_id: int | None = Query(default=None),
    channel: str | None = Query(default=None),
    snapshot_date_from: date | None = Query(default=None),
    snapshot_date_to: date | None = Query(default=None),
    canonical_comic_issue_id: int | None = Query(default=None),
    inventory_item_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> ListingStalenessEventListResponse:
    ensure_ops_admin_access(current_user, settings)
    lim, off = sales_ledger_service.clamp_sale_pagination(limit=limit, offset=offset)
    rows, total = liquidity_engine_service.list_staleness_ops(
        session,
        owner_user_id=owner_user_id,
        channel=channel,
        snapshot_date_from=snapshot_date_from,
        snapshot_date_to=snapshot_date_to,
        canonical_comic_issue_id=canonical_comic_issue_id,
        inventory_item_id=inventory_item_id,
        limit=lim,
        offset=off,
    )
    return ListingStalenessEventListResponse(
        items=[liquidity_engine_service._staleness_read(row) for row in rows],  # noqa: SLF001
        total_items=total,
        limit=lim,
        offset=off,
    )


register_cors_middleware(app, settings)
