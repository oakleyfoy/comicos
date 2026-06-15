from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VolumeYieldRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    volume_id: int
    series_name: str | None = None
    publisher: str | None = None
    status: str
    issues_created: int = 0
    issues_updated: int = 0
    api_requests_used: int = 0
    issues_per_request: float = 0.0
    created_at: datetime | None = None
    completed_at: datetime | None = None


class PublisherYieldRow(BaseModel):
    publisher: str
    volume_count: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    avg_issues_per_volume: float = 0.0
    avg_created_per_volume: float = Field(
        0.0,
        description="Alias of avg_issues_per_volume (issues created per imported volume).",
    )
    avg_requests_per_volume: float = 0.0
    avg_issues_per_request: float = 0.0


class QueueForecastRow(BaseModel):
    volume_id: int
    series_name: str | None = None
    publisher: str | None = None
    status: str
    estimated_remaining_issues: int = 0


class VolumeAnalyticsSummary(BaseModel):
    total_volumes: int = 0
    imported_volumes: int = 0
    pending_volumes: int = 0
    failed_volumes: int = 0

    issues_created: int = 0
    issues_updated: int = 0

    avg_issues_per_volume: float = 0.0
    avg_issues_per_request: float = 0.0

    current_catalog_size: int = 0
    projected_remaining_issues: int = 0
    projected_final_catalog_size: int = 0


class FinalCatalogProjection(BaseModel):
    current_catalog_size: int = 0
    projected_remaining_issues: int = 0
    projected_final_catalog_size: int = 0
