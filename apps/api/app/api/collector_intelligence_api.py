"""P62-03/04/05 Collector Intelligence API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.collector_intelligence import (
    AutoWatchlistBuildResultRead,
    AutoWatchlistBundleRead,
    AutoWatchlistItemRead,
    AutoWatchlistRead,
    CollectorComponentCertificationRead,
    CollectorPipelineRead,
    CollectorPlatformCertificationRead,
    FOCAlertItemRead,
    FOCAlertListRead,
    FOCBuildResultRead,
    PullForecastBuildResultRead,
    PullForecastItemRead,
    PullForecastListRead,
)
from app.schemas.scan_api_v1 import ScanApiV1Envelope, wrap_object
from app.services.auto_watchlist_service import (
    build_auto_watchlists,
    get_latest_watchlists,
    list_watchlist_items,
    refresh_auto_watchlists,
)
from app.services.collector_intelligence_automation import run_collector_intelligence_pipeline
from app.services.collector_intelligence_certification import (
    certify_auto_watchlists,
    certify_foc_intelligence,
    certify_pull_forecast,
    get_collector_platform_certification,
)
from app.services.foc_intelligence_service import (
    generate_foc_alerts,
    get_latest_foc_snapshot,
    list_foc_items,
    update_foc_item_status,
)
from app.services.future_pull_forecast_service import (
    generate_future_pull_forecast,
    get_latest_pull_forecast,
    list_forecast_items,
)
from app.services.p62_feature_flags import p62_auto_watchlist_enabled, p62_foc_enabled, p62_pull_forecast_enabled


def _display_title(session: Session, *, release_issue_id: int | None, title: str, issue_number: str, publisher: str) -> str:
    from app.services.collector_display_identity import resolve_collector_display_title

    return resolve_collector_display_title(
        session,
        release_issue_id=release_issue_id,
        title=title,
        issue_number=issue_number,
        publisher=publisher,
    )


def _foc_alert_list_read(session: Session, *, owner_user_id: int) -> FOCAlertListRead:
    snap = get_latest_foc_snapshot(session, owner_user_id=owner_user_id)
    if snap is None:
        return FOCAlertListRead()
    items, total = list_foc_items(session, snapshot_id=int(snap.id or 0))
    return FOCAlertListRead(
        snapshot_id=int(snap.id or 0),
        total_items=total,
        items=[
            FOCAlertItemRead(
                id=int(i.id or 0),
                owner_id=int(i.owner_user_id),
                release_issue_id=int(i.release_issue_id),
                title=_display_title(
                    session,
                    release_issue_id=int(i.release_issue_id),
                    title=i.title,
                    issue_number="",
                    publisher=i.publisher,
                ),
                publisher=i.publisher,
                foc_date=i.foc_date,
                release_date=i.release_date,
                recommendation_score=i.recommendation_score,
                demand_score=i.demand_score,
                velocity_score=i.velocity_score,
                spec_score=i.spec_score,
                urgency_score=i.urgency_score,
                alert_reason=i.alert_reason,
                suggested_quantity=i.suggested_quantity,
                status=i.status,
            )
            for i in items
        ],
    )


def _auto_watchlist_bundle_read(session: Session, *, owner_user_id: int) -> AutoWatchlistBundleRead:
    latest = get_latest_watchlists(session, owner_user_id=owner_user_id)
    wls = []
    for wl in latest:
        items = list_watchlist_items(session, watchlist_id=int(wl.id or 0))
        wls.append(
            AutoWatchlistRead(
                id=int(wl.id or 0),
                watchlist_type=wl.watchlist_type,
                generated_at=wl.generated_at,
                item_count=wl.item_count,
                items=[
                    AutoWatchlistItemRead(
                        id=int(i.id or 0),
                        title=_display_title(
                            session,
                            release_issue_id=int(i.release_issue_id) if i.release_issue_id else None,
                            title=i.title,
                            issue_number="",
                            publisher="",
                        ),
                        release_issue_id=i.release_issue_id,
                        inclusion_reason=i.inclusion_reason,
                    )
                    for i in items
                ],
            )
        )
    return AutoWatchlistBundleRead(watchlists=wls)


def register_collector_intelligence_routes(router: APIRouter) -> None:
    def _foc_latest_response(
        session: Session,
        current_user: User,
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        if not p62_foc_enabled():
            raise HTTPException(status_code=403, detail="P62_FOC_DISABLED")
        body = _foc_alert_list_read(session, owner_user_id=int(current_user.id))
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.get("/foc/alerts", response_model=ScanApiV1Envelope)
    def v1_foc_alerts(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        return _foc_latest_response(session, current_user)

    @router.get("/foc/latest", response_model=ScanApiV1Envelope)
    def v1_foc_latest(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        return _foc_latest_response(session, current_user)

    @router.post("/foc/build", response_model=ScanApiV1Envelope)
    def v1_foc_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        snap = generate_foc_alerts(session, owner_user_id=int(current_user.id))
        body = FOCBuildResultRead(snapshot_id=int(snap.id or 0), total_items=snap.total_items)
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.get("/foc/certification", response_model=ScanApiV1Envelope)
    def v1_foc_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        cert = certify_foc_intelligence(session, owner_user_id=int(current_user.id))
        return wrap_object(CollectorComponentCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.get("/pull-forecast/latest", response_model=ScanApiV1Envelope)
    def v1_pull_forecast_latest(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        if not p62_pull_forecast_enabled():
            raise HTTPException(status_code=403, detail="P62_PULL_FORECAST_DISABLED")
        fc = get_latest_pull_forecast(session, owner_user_id=int(current_user.id))
        if fc is None:
            return wrap_object(PullForecastListRead(), owner_user_id=int(current_user.id))
        items, total = list_forecast_items(session, forecast_id=int(fc.id or 0))
        body = PullForecastListRead(
            forecast_id=int(fc.id or 0),
            total_items=total,
            items=[
                PullForecastItemRead(
                    id=int(i.id or 0),
                    series_name=i.series_name,
                    title=i.title,
                    release_issue_id=i.release_issue_id,
                    confidence=i.confidence,
                    explanation=i.explanation,
                    reasons_json=i.reasons_json or {},
                )
                for i in items
            ],
        )
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.post("/pull-forecast/build", response_model=ScanApiV1Envelope)
    def v1_pull_forecast_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        fc = generate_future_pull_forecast(session, owner_user_id=int(current_user.id))
        body = PullForecastBuildResultRead(forecast_id=int(fc.id or 0), total_items=fc.total_items)
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.get("/pull-forecast/certification", response_model=ScanApiV1Envelope)
    def v1_pull_forecast_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        cert = certify_pull_forecast(session, owner_user_id=int(current_user.id))
        return wrap_object(CollectorComponentCertificationRead(**cert), owner_user_id=int(current_user.id))

    def _watchlists_latest_response(
        session: Session,
        current_user: User,
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        if not p62_auto_watchlist_enabled():
            raise HTTPException(status_code=403, detail="P62_AUTO_WATCHLIST_DISABLED")
        body = _auto_watchlist_bundle_read(session, owner_user_id=int(current_user.id))
        return wrap_object(body, owner_user_id=int(current_user.id))

    @router.get("/watchlists/auto", response_model=ScanApiV1Envelope)
    def v1_auto_watchlists(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        return _watchlists_latest_response(session, current_user)

    @router.get("/watchlists/latest", response_model=ScanApiV1Envelope)
    def v1_watchlists_latest(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        return _watchlists_latest_response(session, current_user)

    @router.post("/watchlists/auto/build", response_model=ScanApiV1Envelope)
    def v1_auto_watchlists_build(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        built = build_auto_watchlists(session, owner_user_id=int(current_user.id))
        return wrap_object(AutoWatchlistBuildResultRead(watchlist_count=len(built)), owner_user_id=int(current_user.id))

    @router.post("/watchlists/auto/refresh", response_model=ScanApiV1Envelope)
    def v1_auto_watchlists_refresh(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        built = refresh_auto_watchlists(session, owner_user_id=int(current_user.id))
        return wrap_object(AutoWatchlistBuildResultRead(watchlist_count=len(built)), owner_user_id=int(current_user.id))

    @router.get("/watchlists/auto/certification", response_model=ScanApiV1Envelope)
    def v1_auto_watchlists_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        cert = certify_auto_watchlists(session, owner_user_id=int(current_user.id))
        return wrap_object(CollectorComponentCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.get("/platform/certification", response_model=ScanApiV1Envelope)
    def v1_collector_platform_certification(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        cert = get_collector_platform_certification(session, owner_user_id=int(current_user.id))
        return wrap_object(CollectorPlatformCertificationRead(**cert), owner_user_id=int(current_user.id))

    @router.post("/platform/refresh", response_model=ScanApiV1Envelope)
    def v1_collector_platform_refresh(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user),
    ) -> ScanApiV1Envelope:
        assert current_user.id is not None
        raw = run_collector_intelligence_pipeline(session, owner_user_id=int(current_user.id))
        body = CollectorPipelineRead(
            steps=raw["steps"],
            certification=CollectorPlatformCertificationRead(**raw["certification"]),
        )
        return wrap_object(body, owner_user_id=int(current_user.id))
