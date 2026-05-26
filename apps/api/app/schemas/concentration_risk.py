"""P38-05 concentration-risk API shapes."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


ConcentrationType = Literal[
    "publisher",
    "character",
    "title",
    "creator",
    "era",
    "variant_family",
    "grading_status",
    "liquidity_status",
    "acquisition_source",
]
ConcentrationExposureStatus = Literal["HEALTHY", "WATCH", "CONCENTRATED", "OVEREXPOSED", "CRITICAL"]
ConcentrationEvidenceType = Literal[
    "PORTFOLIO_REGISTRY",
    "PORTFOLIO_LIQUIDITY",
    "DUPLICATE_INTELLIGENCE",
    "SALES_LEDGER",
    "LIQUIDITY_ENGINE",
    "GRADING_ENGINE",
    "LISTING_INTELLIGENCE",
]
ConcentrationFactorKey = Literal[
    "liquidity_fragility",
    "duplicate_overlap",
    "grading_overlap",
    "sales_dependence",
    "fmv_dependence",
    "category_fragility",
]


class ConcentrationRiskGeneratePayload(BaseModel):
    model_config = {"extra": "forbid"}

    portfolio_id: int | None = Field(default=None, ge=1)
    snapshot_date: date | None = None
    replay_key: str | None = Field(default=None, min_length=1, max_length=128)


class ConcentrationRiskSnapshotRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    owner_user_id: int
    portfolio_id: int | None
    concentration_type: str
    concentration_key: str
    total_item_count: int
    total_fmv_amount: Decimal | None
    percentage_of_portfolio: Decimal | None
    concentration_score: Decimal | None
    liquidity_weighted_concentration: Decimal | None
    exposure_status: str
    diversification_score: Decimal | None
    checksum: str
    replay_key: str | None
    snapshot_date: date
    created_at: datetime


class ConcentrationRiskEvidenceRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    concentration_risk_snapshot_id: int
    evidence_type: str
    source_id: int | None
    source_table: str | None
    evidence_value_json: dict[str, object]
    created_at: datetime


class ConcentrationRiskFactorRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    concentration_risk_snapshot_id: int
    factor_key: str
    factor_score: Decimal | None
    weighting: Decimal | None
    created_at: datetime


class ConcentrationRiskHistoryRead(BaseModel):
    model_config = {"extra": "forbid"}

    id: int
    owner_user_id: int
    portfolio_id: int | None
    concentration_type: str
    concentration_key: str
    exposure_status: str
    concentration_score: Decimal | None
    diversification_score: Decimal | None
    checksum: str
    snapshot_date: date
    created_at: datetime


class ConcentrationRiskDetailRead(BaseModel):
    model_config = {"extra": "forbid"}

    snapshot: ConcentrationRiskSnapshotRead
    evidence: list[ConcentrationRiskEvidenceRead]
    factors: list[ConcentrationRiskFactorRead]
    history: list[ConcentrationRiskHistoryRead]


class ConcentrationRiskListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[ConcentrationRiskSnapshotRead]
    total: int


class ConcentrationRiskGenerateResponse(BaseModel):
    model_config = {"extra": "forbid"}

    replayed: bool
    items: list[ConcentrationRiskSnapshotRead]
    total: int
    history_appended_count: int


class ConcentrationRiskEvidenceListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[ConcentrationRiskEvidenceRead]
    total: int


class ConcentrationRiskFactorListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[ConcentrationRiskFactorRead]
    total: int


class ConcentrationRiskHistoryListResponse(BaseModel):
    model_config = {"extra": "forbid"}

    items: list[ConcentrationRiskHistoryRead]
    total: int


class InventoryConcentrationRiskTeaser(BaseModel):
    model_config = {"extra": "forbid"}

    concentration_type: str
    concentration_key: str
    exposure_status: str
    concentration_score: str | None = None
    diversification_score: str | None = None
    percentage_of_portfolio: str | None = None
