"""Deterministic run-detection and missing-issue API schemas."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

MissingIssueClassification = Literal[
    "confirmed_missing",
    "likely_missing",
    "unreleased_future_issue",
    "preorder_pending",
    "unresolved_identity_gap",
]

RunDetectionSeriesStatus = Literal[
    "partial_run",
    "complete_limited_series",
    "incomplete_limited_series",
    "probable_ongoing_series",
    "isolated_special_annual",
]


class RunDetectionSignals(BaseModel):
    has_confirmed_gaps: bool = False
    has_likely_gaps: bool = False
    has_unreleased_future_issues: bool = False
    has_preorder_pending_issues: bool = False
    has_unresolved_identity_gaps: bool = False
    has_isolated_special_or_annual_issues: bool = False
    variant_aware_issue_ownership: bool = False
    uses_canonical_series_identity: bool = False


class MissingIssueRead(BaseModel):
    series_key: str
    owner_user_id: int | None = None
    publisher: str
    title: str
    issue_number: str | None = None
    classification: MissingIssueClassification
    issue_release_date: date | None = None
    related_inventory_copy_ids: list[int] = Field(default_factory=list)
    related_owned_issue_numbers: list[str] = Field(default_factory=list)
    reason: str | None = None


class RunDetectionSeriesRead(BaseModel):
    series_key: str
    owner_user_id: int | None = None
    publisher: str
    title: str
    canonical_series_id: int | None = None
    series_status: RunDetectionSeriesStatus
    owned_issue_numbers: list[str] = Field(default_factory=list)
    isolated_issue_numbers: list[str] = Field(default_factory=list)
    inventory_copy_ids: list[int] = Field(default_factory=list)
    distinct_issue_count: int = Field(default=0, ge=0)
    known_issue_count: int = Field(default=0, ge=0)
    missing_issues: list[MissingIssueRead] = Field(default_factory=list)
    signal_flags: RunDetectionSignals = Field(default_factory=RunDetectionSignals)


class RunDetectionSummary(BaseModel):
    total_series_groups: int = Field(default=0, ge=0)
    partial_run_groups: int = Field(default=0, ge=0)
    complete_limited_series_groups: int = Field(default=0, ge=0)
    incomplete_limited_series_groups: int = Field(default=0, ge=0)
    probable_ongoing_series_groups: int = Field(default=0, ge=0)
    isolated_special_annual_groups: int = Field(default=0, ge=0)
    total_missing_issue_rows: int = Field(default=0, ge=0)
    confirmed_missing_rows: int = Field(default=0, ge=0)
    likely_missing_rows: int = Field(default=0, ge=0)
    unreleased_future_issue_rows: int = Field(default=0, ge=0)
    preorder_pending_rows: int = Field(default=0, ge=0)
    unresolved_identity_gap_rows: int = Field(default=0, ge=0)


class RunDetectionListRead(BaseModel):
    summary: RunDetectionSummary = Field(default_factory=RunDetectionSummary)
    series_groups: list[RunDetectionSeriesRead] = Field(default_factory=list)


class MissingIssueListRead(BaseModel):
    summary: RunDetectionSummary = Field(default_factory=RunDetectionSummary)
    items: list[MissingIssueRead] = Field(default_factory=list)


class RunDetectionSeriesDetailRead(BaseModel):
    series_key: str
    publisher: str
    title: str
    owner_groups: list[RunDetectionSeriesRead] = Field(default_factory=list)
    missing_issues: list[MissingIssueRead] = Field(default_factory=list)


class RunDetectionCopyAttachment(BaseModel):
    series_key: str
    series_status: RunDetectionSeriesStatus
    missing_issue_numbers: list[str] = Field(default_factory=list)
    pending_issue_numbers: list[str] = Field(default_factory=list)
    owned_issue_numbers: list[str] = Field(default_factory=list)
