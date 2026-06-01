from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.research_agent import ResearchSnapshotRead


class CharacterProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    character_name: str
    publisher: str
    franchise_id: int | None
    status: str
    created_at: datetime


class CharacterPopularityScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    popularity_score: float
    demand_score: float
    collector_score: float
    confidence_score: float
    source_version: str


class CharacterIntelligenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: CharacterProfileRead
    latest_score: CharacterPopularityScoreRead | None = None


class FranchiseProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    franchise_name: str
    primary_publisher: str
    status: str
    created_at: datetime


class FranchisePopularityScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    popularity_score: float
    demand_score: float
    longevity_score: float
    collector_strength_score: float
    confidence_score: float
    source_version: str


class FranchiseIntelligenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: FranchiseProfileRead
    latest_score: FranchisePopularityScoreRead | None = None


class CreatorProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    creator_name: str
    creator_role: str
    status: str
    created_at: datetime


class CreatorPopularityScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    popularity_score: float
    demand_score: float
    collector_score: float
    confidence_score: float
    source_version: str


class CreatorIntelligenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile: CreatorProfileRead
    latest_score: CreatorPopularityScoreRead | None = None


class IntelligenceEntityRankRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: int
    entity_name: str
    entity_type: str
    popularity_score: float
    demand_score: float
    collector_score: float


class IntelligenceUpcomingReleaseRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    release_issue_id: int
    title: str
    series_name: str
    publisher: str
    release_date: date | None
    combined_popularity_score: float
    matched_entity_count: int


class IntelligencePopularityBucketRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bucket_label: str
    entity_count: int


class IntelligenceDashboardRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_characters: list[IntelligenceEntityRankRead] = Field(default_factory=list)
    top_franchises: list[IntelligenceEntityRankRead] = Field(default_factory=list)
    top_creators: list[IntelligenceEntityRankRead] = Field(default_factory=list)
    upcoming_releases_by_popularity: list[IntelligenceUpcomingReleaseRead] = Field(default_factory=list)
    popularity_distribution: list[IntelligencePopularityBucketRead] = Field(default_factory=list)
    character_count: int
    franchise_count: int
    creator_count: int


class IntelligenceCharacterListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CharacterIntelligenceRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class IntelligenceFranchiseListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[FranchiseIntelligenceRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class IntelligenceCreatorListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CreatorIntelligenceRead] = Field(default_factory=list)
    total_items: int
    limit: int
    offset: int


class IntelligenceSeedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    franchise_count: int
    character_count: int
    creator_count: int
    scores_created: int


# Agent platform (recommendations / catalog & pricing intelligence agents)


class IntelligenceEvidenceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_id: int
    evidence_type: str
    evidence_source: str
    evidence_payload_json: dict[str, object]
    evidence_score: float = Field(ge=0.0)
    created_at: datetime


class IntelligenceRecommendationReviewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_id: int
    review_status: str
    reviewed_by: str
    reviewed_at: datetime
    review_notes: str | None = None


class IntelligenceRecommendationRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    recommendation_uuid: str
    agent_execution_id: int
    recommendation_type: str
    title: str
    description: str
    confidence_score: float = Field(ge=0.0)
    opportunity_score: float = Field(ge=0.0)
    priority_score: float = Field(ge=0.0)
    inventory_copy_id: int | None = None
    inventory_title: str
    status: str
    recommendation_payload_json: dict[str, object]
    created_at: datetime
    latest_review: IntelligenceRecommendationReviewRead | None = None


class IntelligenceRecommendationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation: IntelligenceRecommendationRead
    evidence: list[IntelligenceEvidenceRead] = Field(default_factory=list)
    reviews: list[IntelligenceRecommendationReviewRead] = Field(default_factory=list)


class IntelligenceRecommendationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[IntelligenceRecommendationRead]
    total_items: int
    limit: int
    offset: int


class IntelligenceRecommendationTypeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[str]


class IntelligenceRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: ResearchSnapshotRead
    recommendations: list[IntelligenceRecommendationRead] = Field(default_factory=list)
