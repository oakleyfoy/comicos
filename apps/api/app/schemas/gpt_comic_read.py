"""Response schema for the standalone GPT Comic Read tool (GPT fields only, no catalog)."""

from __future__ import annotations

from pydantic import BaseModel


class GptComicReadResponse(BaseModel):
    publisher: str
    series: str
    issue_number: str | None
    issue_title: str
    year: str
    cover_date: str
    variant_description: str
    barcode: str
    confidence: float
    reasoning: str
    possible_alternates: list[str]
    raw_response: dict
    model: str
    image_width: int
    image_height: int
