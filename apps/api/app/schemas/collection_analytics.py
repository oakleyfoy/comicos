"""Deterministic collection analytics payloads (read-only rollups).

No pricing/value fields. Percent metrics use integer numerator/denominator plus a rounded percent.
"""

from __future__ import annotations

from datetime import date as date_type

from pydantic import BaseModel, Field

from app.schemas.inventory_intelligence import KeyedCount


class PercentRollup(BaseModel):
    numerator: int = Field(default=0, ge=0)
    denominator: int = Field(default=0, ge=0)
    percent: float = Field(
        default=0.0,
        description=("Rounded percentage = round(10000 * numerator / denominator) / 100 when denominator > 0; else 0.0."),
    )


class PublisherAnalyticsRow(BaseModel):
    """Per-publisher rollup in stable publisher-name order."""

    publisher_name: str
    total_copies: int = Field(ge=0)
    in_hand_copies: int = Field(ge=0)
    preorder_copies: int = Field(ge=0)
    unresolved_review_copies: int = Field(ge=0)
    canonical_linked_copies: int = Field(ge=0)


class TimelineYearBucket(BaseModel):
    """Generic year bucket label (digits or sentinel for unknown)."""

    year_key: str
    copies: int = Field(ge=0)


class PreorderPipelineBucket(BaseModel):
    """Preorder copies grouped by expected release timeline bucket."""

    release_bucket_key: str
    preorder_copies: int = Field(ge=0)


class UpcomingPreorderBucket(BaseModel):
    preorder_copies: int = Field(ge=0)
    first_release_bucket: str = Field(
        description=(
            "'YYYY-MM' when release_date is known; "
            "'YYYY-only' fallback when release_year only; '__unknown_calendar__' when neither."
        ),
    )


class CollectionTimelineAnalytics(BaseModel):
    generated_as_of_date: date_type
    by_purchase_year: list[TimelineYearBucket]
    by_release_year: list[TimelineYearBucket]
    by_received_year: list[TimelineYearBucket]
    preorder_pipeline: list[PreorderPipelineBucket]
    upcoming_preorder_calendar: list[UpcomingPreorderBucket]


class InventoryQualityAnalytics(BaseModel):
    """Portfolio quality signals as stable percentages."""

    scope_active_copies_ex_cancelled: int = Field(
        ge=0,
        description="Denominator baseline for percentages that intentionally exclude cancelled lines.",
    )
    ocr_complete: PercentRollup
    canonical_linked: PercentRollup
    unresolved_open_conflict_copies: PercentRollup
    duplicate_ownership_exposure_copies: PercentRollup
    missing_primary_scan: PercentRollup
    primary_cover_failed_processing: PercentRollup
    primary_cover_failed_ocr: PercentRollup


class PublisherConcentration(BaseModel):
    top_publisher_share: PercentRollup
    publishers_represented: int = Field(ge=0)


class CompositionSeriesSignals(BaseModel):
    """Reuse deterministic run-detection classification counts (already portfolio-scoped)."""

    mini_series_limited_denominator_groups: int = Field(
        default=0,
        ge=0,
        description="Groups labeled complete OR incomplete limited series.",
    )
    mini_series_completed_groups: int = Field(default=0, ge=0)
    mini_series_completion_percent: float = Field(
        default=0.0,
        description=(
            "100 * completed_groups / limited_denominator_groups when denominator > 0; deterministic rounding applied."
        ),
    )
    probable_ongoing_series_groups: int = Field(default=0, ge=0)
    probable_ongoing_series_copy_touch_count: int = Field(
        default=0,
        ge=0,
        description="Distinct active copies attributed to probable ongoing runs.",
    )
    ongoing_series_participation_percent: float = Field(
        default=0.0,
        description=(
            "Touch count / scope_active copies (ex cancelled) rounded like other percentages."
        ),
    )


class CollectionCompositionAnalytics(BaseModel):
    graded_copies: int = Field(ge=0)
    raw_copies: int = Field(ge=0)
    preorder_active_copies: int = Field(ge=0)
    in_hand_active_copies: int = Field(ge=0)
    cancelled_copies: int = Field(ge=0)
    owned_active_copies: int = Field(ge=0, description="Everything that is not cancelled.")

    preorder_vs_in_hand: PercentRollup = Field(description="Preorder share among active-only copies.")

    graded_vs_raw: PercentRollup = Field(
        description="Graded copies among graded+raw totals (excluding unknown grade labels treated as graded if != raw)."
    )

    cancelled_vs_owned: PercentRollup = Field(
        description="Cancelled share among cancelled + owned_active counts."
    )

    publisher_concentration: PublisherConcentration = Field(default_factory=PublisherConcentration)
    series_signals: CompositionSeriesSignals = Field(default_factory=CompositionSeriesSignals)


class CollectionAnalyticsSummary(BaseModel):
    """High-level rollup suitable for dashboards."""

    scope_user_id: int | None = None
    scope: str = Field(description='"owner" or "ops_global".')
    generated_as_of_date: date_type

    total_copies: int = Field(ge=0)

    preorder_copies: int = Field(ge=0)
    in_hand_copies: int = Field(ge=0)
    preorder_missing_calendar_copies: int = Field(ge=0)

    unscanned_primary_copies: int = Field(
        ge=0,
        description="Copies with no attached cover scans (deterministic heuristic reuses intelligence scan detection).",
    )
    unresolved_review_copies: int = Field(
        ge=0,
        description="Copies whose deterministic health rollup is needs_review.",
    )

    graded_copies: int = Field(ge=0)
    raw_copies: int = Field(ge=0)

    released_status_breakdown: list[KeyedCount] = Field(default_factory=list)
    order_status_breakdown: list[KeyedCount] = Field(default_factory=list)
    ownership_breakdown: list[KeyedCount] = Field(default_factory=list)
    canonical_linked_copies: int = Field(ge=0)


class CollectionPublisherAnalyticsResponse(BaseModel):
    scope_user_id: int | None = None
    scope: str = "owner"
    generated_as_of_date: date_type
    publishers: list[PublisherAnalyticsRow] = Field(default_factory=list)


class CollectionQualityAnalyticsResponse(BaseModel):
    scope_user_id: int | None = None
    scope: str = "owner"
    generated_as_of_date: date_type
    inventory_quality: InventoryQualityAnalytics


class CollectionTimelineResponse(BaseModel):
    scope_user_id: int | None = None
    scope: str = "owner"
    timeline: CollectionTimelineAnalytics


class CollectionCompositionResponse(BaseModel):
    scope_user_id: int | None = None
    scope: str = "owner"
    generated_as_of_date: date_type
    composition: CollectionCompositionAnalytics
