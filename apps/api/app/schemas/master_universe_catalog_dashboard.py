"""Master Universe catalog coverage dashboard (local catalog + inventory + reference tree)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MasterUniverseCatalogSourceCounts(BaseModel):
    comicvine: int = 0
    gcd: int = 0
    other: int = 0
    unknown: int = 0


class MasterUniverseCatalogDashboardSummary(BaseModel):
    total_publishers: int
    universe_volume_count: int = Field(description="ComicVine volume rows in comicvine_volume_universe")
    universe_issue_ceiling: int = Field(description="Sum of count_of_issues on discovered volumes")
    catalog_series_count: int
    catalog_issue_count: int
    missing_catalog_issues: int = Field(description="Rough gap: universe ceiling minus cataloged issues")
    reference_tree_publishers: int = Field(description="P98 universe_publisher rows (reference shells)")
    reference_tree_issues: int = Field(description="P98 universe_issue shell count")
    reference_tree_variants: int = 0
    inventory_copy_count: int
    inventory_linked_to_catalog: int
    inventory_unlinked: int
    catalog_source_counts: MasterUniverseCatalogSourceCounts


class MasterUniverseCatalogPublisherRow(BaseModel):
    publisher: str
    universe_volume_count: int = 0
    universe_issue_ceiling: int = 0
    catalog_series_count: int = 0
    catalog_issue_count: int = 0
    missing_catalog_issues: int = 0
    inventory_copy_count: int = 0
    primary_catalog_source: str | None = Field(
        default=None,
        description="Dominant _primary_source or inferred source for catalog issues in this publisher",
    )


class MasterUniverseCatalogDashboardResponse(BaseModel):
    summary: MasterUniverseCatalogDashboardSummary
    rows: list[MasterUniverseCatalogPublisherRow]
    total_count: int
    limit: int
    offset: int
