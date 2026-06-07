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
    metadata_json: dict = Field(default_factory=dict)


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
    provider_breakdown: dict[str, int] = Field(default_factory=dict)
    last_comp_date: date | None = None
    metadata_json: dict = Field(default_factory=dict)


class P70MarketRefreshRunRead(_Orm):
    id: int
    trigger_type: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    target_copy_count: int
    books_refreshed: int
    comps_fetched: int
    fmv_snapshots_generated: int
    failure_count: int
    error_message: str | None = None
    metadata_json: dict = Field(default_factory=dict)


class P70MarketRefreshHistoryRead(BaseModel):
    items: list[P70MarketRefreshRunRead] = Field(default_factory=list)
    total: int = 0


class P70MarketTrendPointRead(_Orm):
    id: int
    inventory_copy_id: int
    recorded_on: date
    blended_fmv: float | None = None
    confidence: float
    liquidity_score: float
    sales_count: int
    price_trend_7d: str
    price_trend_30d: str
    price_trend_90d: str
    provider_breakdown_json: dict[str, int] = Field(default_factory=dict)


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
    status: str = "OK"
    message: str = ""
    items: list[P68SnapshotRead]
    total: int


class P68SnapshotsBuildRead(BaseModel):
    status: str = "OK"
    message: str = ""
    built: int
    items: list[P68SnapshotRead]
