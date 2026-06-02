from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.models.industry_release_scan import IndustryReleaseScanRun
from app.models.industry_scanner_automation import IndustryScannerAutomationRun
from app.schemas.industry_scanner_automation import IndustryScannerAutomationOpsPanelRead, IndustryScannerAutomationRunRead
from app.services.industry_opportunities import synchronize_industry_opportunity_scores
from app.services.industry_release_scanner import (
    IndustryScanOptions,
    load_lunar_catalog_releases,
    scan_industry_releases,
)
from app.services.industry_release_signals import synchronize_industry_release_signals

logger = logging.getLogger(__name__)

STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_NO_CHANGE = "NO_CHANGE"
SLOW_STEP_SECONDS = 60.0


@dataclass(frozen=True)
class IndustryScannerRefreshOptions:
    forward_window_only: bool = True
    progress_callback: Callable[[str], None] | None = None
    run_downstream_spec_refresh: bool | None = None


def _log(options: IndustryScannerRefreshOptions, message: str) -> None:
    if options.progress_callback is not None:
        options.progress_callback(message)
    else:
        print(f"run_industry_scanner_refresh: {message}", file=sys.stderr, flush=True)


def _timed(options: IndustryScannerRefreshOptions, label: str, fn: Callable[[], object]) -> object:
    started = time.monotonic()
    _log(options, f"step={label} start")
    result = fn()
    elapsed = time.monotonic() - started
    _log(options, f"step={label} done secs={elapsed:.1f}")
    if elapsed >= SLOW_STEP_SECONDS:
        _log(options, f"SLOW STEP (>{int(SLOW_STEP_SECONDS)}s): {label} took {elapsed:.1f}s")
    return result


def _catalog_fingerprint(catalog: list) -> str:
    payload = sorted(
        (
            row.release_id,
            row.publisher,
            row.series_name,
            row.issue_number,
            str(row.foc_date),
            str(row.release_date),
            row.variant_count,
        )
        for row in catalog
    )
    encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _to_read(row: IndustryScannerAutomationRun) -> IndustryScannerAutomationRunRead:
    return IndustryScannerAutomationRunRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        scan_run_id=int(row.scan_run_id) if row.scan_run_id is not None else None,
        trigger_type=row.trigger_type,
        status=row.status,
        catalog_fingerprint=row.catalog_fingerprint,
        releases_scanned=int(row.releases_scanned),
        candidates_created=int(row.candidates_created),
        signals_upserted=int(row.signals_upserted),
        scores_updated=int(row.scores_updated),
        scan_skipped=bool(row.scan_skipped),
        runtime_ms=int(row.runtime_ms),
        error_message=row.error_message or "",
        started_at=row.started_at,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def _latest_automation_run(session: Session, *, owner_user_id: int) -> IndustryScannerAutomationRun | None:
    return session.exec(
        select(IndustryScannerAutomationRun)
        .where(IndustryScannerAutomationRun.owner_user_id == owner_user_id)
        .order_by(IndustryScannerAutomationRun.started_at.desc(), IndustryScannerAutomationRun.id.desc())
    ).first()


def run_industry_scanner_refresh(
    session: Session,
    *,
    owner_user_id: int,
    trigger_type: str = "MANUAL",
    options: IndustryScannerRefreshOptions | None = None,
) -> IndustryScannerAutomationRun:
    opts = options or IndustryScannerRefreshOptions()
    if opts.run_downstream_spec_refresh is None:
        run_downstream = trigger_type != "LUNAR_REFRESH"
    else:
        run_downstream = opts.run_downstream_spec_refresh

    started = datetime.now(timezone.utc)
    automation = IndustryScannerAutomationRun(
        owner_user_id=owner_user_id,
        trigger_type=trigger_type,
        status=STATUS_SUCCESS,
        started_at=started,
    )
    session.add(automation)
    session.commit()
    session.refresh(automation)

    scan_opts = IndustryScanOptions(
        forward_window_only=opts.forward_window_only,
        progress_callback=opts.progress_callback,
    )

    try:
        catalog = _timed(
            opts,
            "load_forward_catalog",
            lambda: load_lunar_catalog_releases(
                session,
                owner_user_id=owner_user_id,
                forward_window_only=opts.forward_window_only,
            ),
        )
        assert isinstance(catalog, list)
        fingerprint = _catalog_fingerprint(catalog)
        automation.catalog_fingerprint = fingerprint
        automation.releases_scanned = len(catalog)
        _log(opts, f"forward_catalog_rows={len(catalog)} forward_window={opts.forward_window_only}")

        prior = session.exec(
            select(IndustryScannerAutomationRun)
            .where(IndustryScannerAutomationRun.owner_user_id == owner_user_id)
            .where(IndustryScannerAutomationRun.status.in_([STATUS_SUCCESS, STATUS_NO_CHANGE]))
            .where(IndustryScannerAutomationRun.id != int(automation.id or 0))
            .order_by(IndustryScannerAutomationRun.started_at.desc(), IndustryScannerAutomationRun.id.desc())
        ).first()

        scan_run_id: int | None = None
        candidates_created = 0
        scan_skipped = False
        if prior and prior.catalog_fingerprint == fingerprint and prior.scan_run_id is not None:
            scan_run_id = int(prior.scan_run_id)
            scan_skipped = True
            _log(opts, f"step=scan_industry_releases skipped idempotent scan_run_id={scan_run_id}")
        else:
            scan_read = _timed(
                opts,
                "scan_industry_releases",
                lambda: scan_industry_releases(
                    session,
                    owner_user_id=owner_user_id,
                    options=scan_opts,
                    catalog=catalog,
                ),
            )
            scan_run_id = int(scan_read.id)
            candidates_created = int(scan_read.candidates_created)

        automation.scan_run_id = scan_run_id
        automation.scan_skipped = scan_skipped
        automation.candidates_created = candidates_created

        signals_upserted = 0
        scores_updated = 0
        if scan_run_id is not None:
            signals_upserted = _timed(
                opts,
                "synchronize_industry_release_signals",
                lambda: synchronize_industry_release_signals(
                    session,
                    owner_user_id=owner_user_id,
                    scan_run_id=scan_run_id,
                    progress_callback=opts.progress_callback,
                ),
            )
            assert isinstance(signals_upserted, int)
            scores_updated = _timed(
                opts,
                "synchronize_industry_opportunity_scores",
                lambda: synchronize_industry_opportunity_scores(
                    session,
                    owner_user_id=owner_user_id,
                    scan_run_id=scan_run_id,
                    progress_callback=opts.progress_callback,
                ),
            )
            assert isinstance(scores_updated, int)

        automation.signals_upserted = signals_upserted
        automation.scores_updated = scores_updated
        if scan_skipped and candidates_created == 0 and signals_upserted == 0 and scores_updated == 0:
            automation.status = STATUS_NO_CHANGE
        else:
            automation.status = STATUS_SUCCESS
    except Exception as exc:  # noqa: BLE001
        logger.exception("Industry scanner refresh failed for owner %s", owner_user_id)
        session.rollback()
        automation = session.get(IndustryScannerAutomationRun, automation.id)
        assert automation is not None
        automation.status = STATUS_FAILED
        automation.error_message = str(exc)[:2000]
        session.add(automation)
        session.commit()
        session.refresh(automation)
        completed = datetime.now(timezone.utc)
        automation.completed_at = completed
        automation.runtime_ms = int((completed - started).total_seconds() * 1000)
        session.add(automation)
        session.commit()
        session.refresh(automation)
        return automation

    completed = datetime.now(timezone.utc)
    automation.completed_at = completed
    automation.runtime_ms = int((completed - started).total_seconds() * 1000)
    session.add(automation)
    session.commit()
    session.refresh(automation)

    if automation.status in (STATUS_SUCCESS, STATUS_NO_CHANGE):
        if run_downstream:
            _timed(
                opts,
                "downstream_spec_refresh",
                lambda: _run_downstream_spec(session, owner_user_id=owner_user_id),
            )
        else:
            _log(opts, "step=downstream_spec_refresh skipped (LUNAR_REFRESH pipeline already ran spec agents)")

    _log(
        opts,
        f"step=complete status={automation.status} releases_scanned={automation.releases_scanned} "
        f"signals_upserted={automation.signals_upserted} scores_updated={automation.scores_updated}",
    )
    return automation


def _run_downstream_spec(session: Session, *, owner_user_id: int) -> None:
    from app.services.spec_automation import trigger_spec_refresh_after_upstream

    trigger_spec_refresh_after_upstream(session, owner_user_id=owner_user_id)


def list_industry_scanner_automation_runs(
    session: Session,
    *,
    owner_user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[IndustryScannerAutomationRunRead], int]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(IndustryScannerAutomationRun)
        .where(IndustryScannerAutomationRun.owner_user_id == owner_user_id)
        .order_by(IndustryScannerAutomationRun.started_at.desc(), IndustryScannerAutomationRun.id.desc())
    ).all()
    total = len(rows)
    page = rows[offset : offset + limit]
    return [_to_read(row) for row in page], total


def get_latest_industry_scanner_automation_run(
    session: Session,
    *,
    owner_user_id: int,
) -> IndustryScannerAutomationRunRead | None:
    row = _latest_automation_run(session, owner_user_id=owner_user_id)
    if row is None:
        return None
    return _to_read(row)


def build_industry_scanner_automation_ops_panel(
    session: Session,
    *,
    owner_user_id: int,
) -> IndustryScannerAutomationOpsPanelRead:
    row = _latest_automation_run(session, owner_user_id=owner_user_id)
    if row is None:
        return IndustryScannerAutomationOpsPanelRead()
    return IndustryScannerAutomationOpsPanelRead(
        last_run=row.completed_at or row.started_at,
        status=row.status,
        trigger_type=row.trigger_type,
        runtime_ms=int(row.runtime_ms),
        releases_scanned=int(row.releases_scanned),
        candidates_created=int(row.candidates_created),
        signals_upserted=int(row.signals_upserted),
        scores_updated=int(row.scores_updated),
        scan_skipped=bool(row.scan_skipped),
    )
