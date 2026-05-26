"""P36-08 operational reporting registry schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


OPERATIONAL_REPORT_TYPES: frozenset[str] = frozenset(
    {
        "listing_summary",
        "sales_summary",
        "liquidity_summary",
        "convention_summary",
        "export_summary",
        "dealer_dashboard_summary",
        "inventory_health_summary",
    }
)

OperationalReportStatus = Literal["DRAFT", "RUNNING", "COMPLETED", "FAILED"]

OperationalReportTypeLiterals = Literal[
    "listing_summary",
    "sales_summary",
    "liquidity_summary",
    "convention_summary",
    "export_summary",
    "dealer_dashboard_summary",
    "inventory_health_summary",
]


class OperationalReportGenerationParams(BaseModel):
    """Optional deterministic filters mirrored into generation_params_json."""

    model_config = ConfigDict(extra="forbid")

    sale_date_from: date | None = None
    sale_date_to: date | None = None


class OperationalReportGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_type: OperationalReportTypeLiterals
    replay_key: str | None = Field(default=None, max_length=128)
    generation_params: OperationalReportGenerationParams = Field(default_factory=OperationalReportGenerationParams)


class OperationalReportFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    operational_report_run_id: int
    file_name: str
    file_type: str
    storage_path: str
    checksum: str
    row_count: int
    created_at: datetime


class OperationalReportItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    operational_report_run_id: int
    row_number: int
    lineage_domain: str
    lineage_key: str
    lineage_json: dict[str, Any]
    row_checksum: str | None
    created_at: datetime


class OperationalReportRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    owner_user_id: int
    report_type: str
    status: str
    replay_key: str | None
    generation_params_json: dict[str, Any]
    checksum: str | None
    csv_row_count: int
    failure_reason: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class OperationalReportRunDetailRead(OperationalReportRunRead):
    items: list[OperationalReportItemRead] = Field(default_factory=list)
    files: list[OperationalReportFileRead] = Field(default_factory=list)


class OperationalReportRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[OperationalReportRunRead]
    total_items: int
    limit: int
    offset: int




class OperationalReportingDashboardRollup(BaseModel):
    """Lightweight owner dashboard slice (recent + failed fingerprints)."""

    model_config = ConfigDict(extra="forbid")

    recent_runs: list[OperationalReportRunRead]
    failed_runs: list[OperationalReportRunRead]
