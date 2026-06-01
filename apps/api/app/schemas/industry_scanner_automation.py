from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IndustryScannerAutomationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    scan_run_id: int | None
    trigger_type: str
    status: str
    catalog_fingerprint: str
    releases_scanned: int
    candidates_created: int
    signals_upserted: int
    scores_updated: int
    scan_skipped: bool
    runtime_ms: int
    error_message: str = ""
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime


class IndustryScannerAutomationRunListRead(BaseModel):
    items: list[IndustryScannerAutomationRunRead] = Field(default_factory=list)
    total_items: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)


class IndustryScannerAutomationRunTriggerResponse(BaseModel):
    run: IndustryScannerAutomationRunRead


class IndustryScannerAutomationOpsPanelRead(BaseModel):
    last_run: datetime | None = None
    status: str = "NEVER_RUN"
    trigger_type: str | None = None
    runtime_ms: int = 0
    releases_scanned: int = 0
    candidates_created: int = 0
    signals_upserted: int = 0
    scores_updated: int = 0
    scan_skipped: bool = False
