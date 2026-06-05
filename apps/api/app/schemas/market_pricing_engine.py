from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class P68ProviderRead(_Orm):
    id: int
    provider_type: str
    enabled: bool
    health_status: str
    last_ingest_at: datetime | None = None


class P68ObservationRead(_Orm):
    id: int
    provider: str
    title: str
    publisher: str
    issue_number: str
    total_price: float
    raw_or_graded: str
    confidence: float
    sale_date: date | None = None
    inventory_copy_id: int | None = None
    metadata_json: dict = Field(default_factory=dict)


class P68SnapshotRead(_Orm):
    id: int
    title: str
    publisher: str
    issue_number: str
    inventory_copy_id: int | None = None
    blended_fmv: float | None = None
    raw_fmv: float | None = None
    graded_fmv: float | None = None
    low_sale: float | None = None
    high_sale: float | None = None
    median_sale: float | None = None
    sales_count: int
    liquidity_score: float
    confidence: float
    price_trend_30d: str
    primary_provider: str
    metadata_json: dict = Field(default_factory=dict)


class P68ManualObservationWrite(BaseModel):
    title: str
    publisher: str
    issue_number: str
    total_price: float
    raw_or_graded: str = "raw"
    variant_label: str | None = None
    inventory_copy_id: int | None = None


class P68CertificationRead(BaseModel):
    owner_user_id: int
    certified: bool
    checks: list[dict]
    platform: str


class P68ProvidersListRead(BaseModel):
    providers: list[P68ProviderRead]


class P68ObservationsListRead(BaseModel):
    items: list[P68ObservationRead]
    total: int


class P68SnapshotsListRead(BaseModel):
    items: list[P68SnapshotRead]
    total: int


class P68SnapshotsBuildRead(BaseModel):
    built: int
    items: list[P68SnapshotRead]
