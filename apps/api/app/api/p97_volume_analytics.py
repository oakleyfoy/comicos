from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.p97_volume_analytics import (
    FinalCatalogProjection,
    PublisherYieldRow,
    QueueForecastRow,
    VolumeAnalyticsSummary,
    VolumeYieldRow,
)
from app.services import p97_volume_analytics_service as analytics

p97_volume_analytics_router = APIRouter(
    prefix="/p97/volume-analytics",
    tags=["P97 Volume Yield Analytics (P97-22)"],
)


def attach_p97_volume_analytics_layer(app: FastAPI) -> None:
    app.include_router(p97_volume_analytics_router)


@p97_volume_analytics_router.get("/summary", response_model=VolumeAnalyticsSummary)
def volume_analytics_summary(session: Session = Depends(get_session)) -> VolumeAnalyticsSummary:
    return analytics.get_volume_summary(session)


@p97_volume_analytics_router.get("/top-created", response_model=list[VolumeYieldRow])
def volume_analytics_top_created(
    session: Session = Depends(get_session),
    limit: int = Query(100, ge=1, le=500),
) -> list[VolumeYieldRow]:
    return analytics.get_top_created_volumes(session, limit=limit)


@p97_volume_analytics_router.get("/top-updated", response_model=list[VolumeYieldRow])
def volume_analytics_top_updated(
    session: Session = Depends(get_session),
    limit: int = Query(100, ge=1, le=500),
) -> list[VolumeYieldRow]:
    return analytics.get_top_updated_volumes(session, limit=limit)


@p97_volume_analytics_router.get("/publishers", response_model=list[PublisherYieldRow])
def volume_analytics_publishers(session: Session = Depends(get_session)) -> list[PublisherYieldRow]:
    return analytics.get_publisher_yields(session)


@p97_volume_analytics_router.get("/remaining-forecast", response_model=list[QueueForecastRow])
def volume_analytics_remaining_forecast(
    session: Session = Depends(get_session),
) -> list[QueueForecastRow]:
    return analytics.get_remaining_queue_forecast(session)


@p97_volume_analytics_router.get("/final-projection", response_model=FinalCatalogProjection)
def volume_analytics_final_projection(
    session: Session = Depends(get_session),
) -> FinalCatalogProjection:
    return analytics.get_projected_final_catalog_size(session)
