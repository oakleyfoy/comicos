from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.cover_link_decisions import CoverLinkDecisionType, CoverLinkRelationshipType

CoverRelationshipGraphEdgeLane = Literal["strong", "related", "blocked", "needs_review"]


class CoverRelationshipGraphInventoryMetadata(BaseModel):
    inventory_copy_id: int
    title: str
    publisher: str
    issue_number: str
    cover_name: str | None = None


class CoverRelationshipGraphNodeDecisionSummary(BaseModel):
    """Counts of incident graph edges grouped for display (1-hop subgraph only)."""

    incident_strong_edges: int = Field(ge=0, default=0)
    incident_related_edges: int = Field(ge=0, default=0)
    incident_blocked_edges: int = Field(ge=0, default=0)
    incident_needs_review_edges: int = Field(ge=0, default=0)


class CoverRelationshipGraphNode(BaseModel):
    cover_image_id: int
    inventory: CoverRelationshipGraphInventoryMetadata | None = None
    primary_fetch_path: str = Field(
        description=(
            "Example: `/files/cover-images/{id}` — authorize with Bearer token on GET requests."
        ),
    )
    thumbnail_fetch_path: str | None = None
    medium_fetch_path: str | None = None
    decision_summary: CoverRelationshipGraphNodeDecisionSummary


class CoverRelationshipGraphEdge(BaseModel):
    source_cover_image_id: int
    candidate_cover_image_id: int
    relationship_type: CoverLinkRelationshipType
    decision_type: CoverLinkDecisionType
    decision_id: int = Field(ge=1)
    created_at: datetime
    reviewer_user_id: int | None = None
    decision_reason: str | None = None
    display_lane: CoverRelationshipGraphEdgeLane = Field(
        description=(
            "Deterministic grouping hint from persisted decision fields only: "
            "`strong` (approved same_cover/duplicate_scan), "
            "`related` (approved same_issue/variant_family), "
            "`blocked` (rejected), `needs_review`."
        ),
    )


class CoverRelationshipGraphRead(BaseModel):
    center_cover_image_id: int
    nodes: list[CoverRelationshipGraphNode]
    edges: list[CoverRelationshipGraphEdge]
