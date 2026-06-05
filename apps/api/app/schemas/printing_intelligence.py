from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PrintingBadgeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = ""
    kind: str = "FIRST_PRINT"
    printing_number: int | None = None


class PrintingScheduleRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    printing_badge: PrintingBadgeRead | None = None
    original_foc_date: date | None = None
    original_release_date: date | None = None
    printing_foc_date: date | None = None
    printing_release_date: date | None = None
