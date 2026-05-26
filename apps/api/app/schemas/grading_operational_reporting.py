"""P37-09 grading operational reporting registry schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


GRADING_OPERATIONAL_REPORT_TYPES: frozenset[str] = frozenset(
    {
        "grading_candidate_summary",
        "grading_roi_summary",
        "grading_submission_summary",
        "grading_reconciliation_summary",
        "grading_recommendation_summary",
        "grading_risk_summary",
        "grading_dashboard_summary",
        "grader_performance_summary",
    }
)

GradingOperationalReportStatus = Literal["DRAFT", "RUNNING", "COMPLETED", "FAILED"]

GradingOperationalReportTypeLiterals = Literal[
    "grading_candidate_summary",
    "grading_roi_summary",
    "grading_submission_summary",
    "grading_reconciliation_summary",
    "grading_recommendation_summary",
    "grading_risk_summary",
    "grading_dashboard_summary",
    "grader_performance_summary",
]


class GradingOperationalReportGenerationParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GradingOperationalReportGeneratePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_type: GradingOperationalReportTypeLiterals
    replay_key: str | None = Field(default=None, max_length=128)
    generation_params: GradingOperationalReportGenerationParams = Field(
        default_factory=GradingOperationalReportGenerationParams
    )


class GradingOperationalReportFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    grading_operational_report_run_id: int
    file_name: str
    file_type: str
    storage_path: str
    checksum: str
    row_count: int
    created_at: datetime


class GradingOperationalReportItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    grading_operational_report_run_id: int
    row_number: int
    lineage_domain: str
    lineage_key: str
    lineage_json: dict[str, Any]
    row_checksum: str | None
    created_at: datetime


class GradingOperationalReportRunRead(BaseModel):
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


class GradingOperationalReportRunDetailRead(GradingOperationalReportRunRead):
    items: list[GradingOperationalReportItemRead] = Field(default_factory=list)
    files: list[GradingOperationalReportFileRead] = Field(default_factory=list)


class GradingOperationalReportRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[GradingOperationalReportRunRead]
    total_items: int
    limit: int
    offset: int
