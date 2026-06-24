"""Response schema for standalone GPT Comic Read (GPT + barcode verification)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class GptComicReadGptFields(BaseModel):
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


class GptComicReadBarcodeRead(BaseModel):
    barcode: str | None
    barcode_type: str | None
    confidence: float
    method: Literal["local_decode", "gpt_barcode_read", "none"]
    crop_used: str | None
    error: str | None


class GptComicReadCatalogMatch(BaseModel):
    matched: bool
    catalog_issue_id: int | None = None
    method: str = "none"
    confidence: float | None = None
    series: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    cover_image_url: str | None = None
    alternates: list[dict[str, Any]] = []


class GptComicReadComicvineBarcodeMatch(BaseModel):
    matched: bool
    source: str = "comicvine"
    comicvine_issue_id: str | None = None
    series: str | None = None
    issue_number: str | None = None
    publisher: str | None = None
    cover_date: str | None = None
    name: str | None = None
    image_url: str | None = None
    raw: dict[str, Any] | None = None


class GptComicReadResponse(BaseModel):
    gpt_read: GptComicReadGptFields
    catalog_match: GptComicReadCatalogMatch
    barcode_read: GptComicReadBarcodeRead
    comicvine_barcode_match: GptComicReadComicvineBarcodeMatch
    final_match_source: Literal["comicvine_barcode", "catalog", "gpt_only"]
