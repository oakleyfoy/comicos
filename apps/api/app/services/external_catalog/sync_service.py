from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.external_catalog import (
    ExternalCatalogCharacter,
    ExternalCatalogCreator,
    ExternalCatalogIssue,
    ExternalCatalogSource,
    ExternalCatalogSyncRun,
    ExternalCatalogVariant,
)
from app.services.external_catalog.league_of_comic_geeks import (
    LOCG_MAX_DETAIL_PAGES_PER_RUN,
    LOCG_SOURCE_NAME,
    LocgAccessBlockedError,
    LocgHttpClient,
    LocgHttpError,
    calendar_url_for_date,
    discover_available_release_dates,
    fetch_issue_detail_page,
    fetch_release_date_page,
    merge_detail_into_seed,
    parse_issue_detail_page,
    parse_release_date_page,
    stub_to_detail_seed,
)
from app.services.external_catalog.normalization import NormalizedLocgIssue, normalize_locg_issue

SYNC_RUNNING = "RUNNING"
SYNC_COMPLETED = "COMPLETED"
SYNC_PARTIAL = "PARTIAL"
SYNC_FAILED = "FAILED"
SYNC_COMPLETE_WITH_WARNINGS = "COMPLETE_WITH_WARNINGS"

SYNC_BACKFILL = "BACKFILL"
SYNC_INCREMENTAL = "INCREMENTAL"
SYNC_REFRESH = "REFRESH"
SYNC_BROWSER = "BROWSER"


def _safe_session_rollback(session: Session) -> None:
    try:
        session.rollback()
    except Exception:
        pass


def format_db_exception(exc: BaseException) -> dict[str, Any]:
    """Extract type, message, SQL statement, and parameters from DB/SQLAlchemy errors."""
    details: dict[str, Any] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    orig = getattr(exc, "orig", None)
    if orig is not None:
        details["orig_type"] = type(orig).__name__
        details["orig_message"] = str(orig)
        if getattr(orig, "pgcode", None):
            details["pgcode"] = orig.pgcode
    stmt = getattr(exc, "statement", None)
    if stmt:
        details["statement"] = stmt
    params = getattr(exc, "params", None)
    if params is not None:
        details["parameters"] = params
    return details


@dataclass
class SyncCounters:
    pages_scanned: int = 0
    issues_created: int = 0
    issues_updated: int = 0
    variants_created: int = 0
    creators_created: int = 0
    characters_created: int = 0
    errors_count: int = 0
    error_sample: list[str] = field(default_factory=list)


def ensure_locg_source(session: Session) -> ExternalCatalogSource:
    row = session.exec(
        select(ExternalCatalogSource).where(ExternalCatalogSource.source_name == LOCG_SOURCE_NAME)
    ).first()
    if row:
        return row
    row = ExternalCatalogSource(
        source_name=LOCG_SOURCE_NAME,
        source_type="DISCOVERY",
        base_url="https://leagueofcomicgeeks.com",
        is_active=True,
    )
    session.add(row)
    try:
        session.commit()
        session.refresh(row)
    except Exception:
        _safe_session_rollback(session)
        raise
    return row


def create_sync_run(
    session: Session,
    *,
    source_name: str,
    sync_type: str,
    start_date: date | None,
    end_date: date | None,
) -> ExternalCatalogSyncRun:
    run = ExternalCatalogSyncRun(
        source_name=source_name,
        sync_type=sync_type,
        start_date=start_date,
        end_date=end_date,
        status=SYNC_RUNNING,
    )
    session.add(run)
    try:
        session.commit()
        session.refresh(run)
    except Exception:
        _safe_session_rollback(session)
        raise
    return run


def _sync_run_error_sample(
    counters: SyncCounters,
    *,
    warnings: list[str] | None = None,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {}
    if counters.error_sample:
        payload["messages"] = counters.error_sample[:20]
    if warnings:
        payload["warnings"] = warnings[:30]
    return payload or None


def complete_sync_run(
    session: Session,
    *,
    run: ExternalCatalogSyncRun,
    counters: SyncCounters,
    status: str,
    warnings: list[str] | None = None,
) -> None:
    run.status = status
    run.pages_scanned = counters.pages_scanned
    run.issues_created = counters.issues_created
    run.issues_updated = counters.issues_updated
    run.variants_created = counters.variants_created
    run.creators_created = counters.creators_created
    run.errors_count = counters.errors_count
    run.error_sample = _sync_run_error_sample(counters, warnings=warnings)
    from app.models.external_catalog import utc_now

    run.completed_at = utc_now()
    session.add(run)
    try:
        session.commit()
    except Exception:
        _safe_session_rollback(session)
        raise


def fail_sync_run(session: Session, *, run: ExternalCatalogSyncRun, message: str) -> None:
    counters = SyncCounters(errors_count=1, error_sample=[message])
    complete_sync_run(session, run=run, counters=counters, status=SYNC_FAILED)


def fail_sync_run_preserving_counters(
    session: Session,
    *,
    run: ExternalCatalogSyncRun,
    counters: SyncCounters,
    message: str,
    warnings: list[str] | None = None,
) -> None:
    counters.errors_count += 1
    if len(counters.error_sample) < 20:
        counters.error_sample.append(message)
    complete_sync_run(
        session,
        run=run,
        counters=counters,
        status=SYNC_FAILED,
        warnings=warnings,
    )


def count_locg_release_date_persistence(
    session: Session,
    *,
    release_date: date,
) -> dict[str, int]:
    from sqlalchemy import func

    issue_count = session.exec(
        select(func.count())
        .select_from(ExternalCatalogIssue)
        .where(
            ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
            ExternalCatalogIssue.release_date == release_date,
        )
    ).one()
    if hasattr(issue_count, "__getitem__"):
        issue_count = issue_count[0]
    variant_count = session.exec(
        select(func.count())
        .select_from(ExternalCatalogVariant)
        .join(ExternalCatalogIssue, ExternalCatalogVariant.external_issue_id == ExternalCatalogIssue.id)
        .where(
            ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
            ExternalCatalogIssue.release_date == release_date,
        )
    ).one()
    if hasattr(variant_count, "__getitem__"):
        variant_count = variant_count[0]
    return {"issues": int(issue_count or 0), "variants": int(variant_count or 0)}


def parent_browser_capture_complete(
    *,
    list_page_loaded: bool,
    list_issues_found: int,
    detail_pages_succeeded: int,
    max_issues: int | None,
) -> bool:
    if not list_page_loaded or list_issues_found <= 0:
        return False
    expected = list_issues_found if max_issues is None else min(list_issues_found, max_issues)
    return detail_pages_succeeded >= expected


def _find_issue(
    session: Session,
    *,
    source_name: str,
    source_url: str | None,
    source_issue_id: str | None,
) -> ExternalCatalogIssue | None:
    if source_url:
        row = session.exec(
            select(ExternalCatalogIssue).where(
                ExternalCatalogIssue.source_name == source_name,
                ExternalCatalogIssue.source_url == source_url,
            )
        ).first()
        if row:
            return row
    if source_issue_id:
        return session.exec(
            select(ExternalCatalogIssue).where(
                ExternalCatalogIssue.source_name == source_name,
                ExternalCatalogIssue.source_issue_id == source_issue_id,
            )
        ).first()
    return None


def _apply_mutable_fields(
    row: ExternalCatalogIssue,
    norm: NormalizedLocgIssue,
    *,
    overwrite_nulls_only: bool,
) -> bool:
    from app.models.external_catalog import utc_now

    changed = False

    def set_field(attr: str, value: Any) -> None:
        nonlocal changed
        current = getattr(row, attr)
        if value is None and overwrite_nulls_only:
            return
        if value is None:
            return
        if current != value:
            setattr(row, attr, value)
            changed = True

    for attr in (
        "title",
        "publisher",
        "series_name",
        "issue_number",
        "issue_title",
        "release_date",
        "foc_date",
        "cover_date",
        "price",
        "description",
        "story_summary",
        "imprint",
        "universe",
        "is_first_issue",
        "is_milestone_issue",
        "milestone_issue_number",
        "importance_signals_json",
        "decision_signals_json",
        "pull_count",
        "want_count",
        "variant_count",
        "cover_image_url",
        "thumbnail_url",
        "high_resolution_image_url",
        "product_url",
        "normalized_title_key",
        "source_issue_id",
    ):
        set_field(attr, getattr(norm, attr))
    row.last_seen_at = utc_now()
    row.updated_at = utc_now()
    return changed


def upsert_external_issue(
    session: Session,
    norm: NormalizedLocgIssue,
    *,
    overwrite_nulls_only: bool = True,
) -> tuple[ExternalCatalogIssue, bool, bool]:
    """Returns (row, created, updated)."""
    from app.models.external_catalog import utc_now

    existing = _find_issue(
        session,
        source_name=norm.source_name,
        source_url=norm.source_url,
        source_issue_id=norm.source_issue_id,
    )
    if existing is None:
        row = ExternalCatalogIssue(
            source_name=norm.source_name,
            source_issue_id=norm.source_issue_id,
            source_url=norm.source_url,
            title=norm.title,
            publisher=norm.publisher,
            series_name=norm.series_name,
            issue_number=norm.issue_number,
            issue_title=norm.issue_title,
            release_date=norm.release_date,
            foc_date=norm.foc_date,
            cover_date=norm.cover_date,
            price=norm.price,
            description=norm.description,
            story_summary=norm.story_summary,
            imprint=norm.imprint,
            universe=norm.universe,
            is_first_issue=norm.is_first_issue,
            is_milestone_issue=norm.is_milestone_issue,
            milestone_issue_number=norm.milestone_issue_number,
            importance_signals_json=norm.importance_signals_json,
            decision_signals_json=norm.decision_signals_json,
            pull_count=norm.pull_count,
            want_count=norm.want_count,
            variant_count=norm.variant_count,
            cover_image_url=norm.cover_image_url,
            thumbnail_url=norm.thumbnail_url,
            high_resolution_image_url=norm.high_resolution_image_url,
            product_url=norm.product_url,
            normalized_title_key=norm.normalized_title_key,
            sync_status="SYNCED",
        )
        session.add(row)
        try:
            session.commit()
            session.refresh(row)
        except Exception:
            _safe_session_rollback(session)
            raise
        return row, True, False

    created = False
    updated = _apply_mutable_fields(existing, norm, overwrite_nulls_only=overwrite_nulls_only)
    if updated:
        session.add(existing)
        try:
            session.commit()
            session.refresh(existing)
        except Exception:
            _safe_session_rollback(session)
            raise
    return existing, created, updated


def find_locg_issue_by_comic_id(
    session: Session,
    comic_id: str,
    *,
    source_name: str = LOCG_SOURCE_NAME,
) -> ExternalCatalogIssue | None:
    pattern = f"%/comic/{comic_id}/%"
    return session.exec(
        select(ExternalCatalogIssue).where(
            ExternalCatalogIssue.source_name == source_name,
            ExternalCatalogIssue.source_url.like(pattern),
        )
    ).first()


@dataclass
class LocgVariantPersistStats:
    found: int = 0
    persisted: int = 0
    skipped_missing_parent: int = 0
    skipped_missing_variant_url: int = 0
    skipped_missing_title: int = 0
    skipped_duplicate: int = 0
    upsert_errors: int = 0
    parents_ensured_from_list: int = 0
    parents_ensured_from_variant_rows: int = 0
    variant_upsert_success: int = 0
    variant_upsert_failure: int = 0
    first_variant_error: dict[str, Any] | None = None
    first_variant_failure: dict[str, Any] | None = None
    skipped_unavoidable_special_case: int = 0
    skipped_missing_parent_samples: list[dict[str, Any]] = field(default_factory=list)

    def _record_first_failure(self, payload: dict[str, Any]) -> None:
        if self.first_variant_failure is None:
            self.first_variant_failure = payload
            self.first_variant_error = payload

    def skipped_total(self) -> int:
        return (
            self.skipped_missing_parent
            + self.skipped_missing_variant_url
            + self.skipped_missing_title
            +             self.skipped_duplicate
            + self.skipped_unavoidable_special_case
            + self.upsert_errors
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "persisted": self.persisted,
            "skipped_missing_parent": self.skipped_missing_parent,
            "skipped_missing_variant_url": self.skipped_missing_variant_url,
            "skipped_missing_title": self.skipped_missing_title,
            "skipped_duplicate": self.skipped_duplicate,
            "upsert_errors": self.upsert_errors,
            "parents_ensured_from_list": self.parents_ensured_from_list,
            "parents_ensured_from_variant_rows": self.parents_ensured_from_variant_rows,
            "skipped_unavoidable_special_case": self.skipped_unavoidable_special_case,
            "skipped_missing_parent_samples": self.skipped_missing_parent_samples[:20],
            "variant_upsert_success": self.variant_upsert_success,
            "variant_upsert_failure": self.variant_upsert_failure,
            "first_variant_error": self.first_variant_error,
            "first_variant_failure": self.first_variant_failure,
        }


_CONSOLE_ALWAYS_PHASES = frozenset(
    {
        "start",
        "complete",
        "parent_stub_upsert_failed",
        "parent_stub_from_variant_failed",
        "parent_stub_on_demand_failed",
        "skipped_missing_parent",
        "skipped_unavoidable_special_case",
        "variant_upsert_failed",
    }
)


def _variant_persist_trace(
    event: dict[str, Any],
    *,
    trace_path: Path | None,
    verbose_console: bool = False,
) -> None:
    line = json.dumps(event, default=str, ensure_ascii=False)
    phase = event.get("phase")
    if verbose_console or phase in _CONSOLE_ALWAYS_PHASES:
        print(f"[variant-persist] {json.dumps(event, default=str, ensure_ascii=True)}", flush=True)
    if trace_path is not None:
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        with trace_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def upsert_locg_list_variant_rows(
    session: Session,
    variant_rows: list[Any],
    *,
    list_html: str | None = None,
    page_date: date | None = None,
    debug_trace_path: Path | None = None,
    verbose_console: bool = False,
) -> LocgVariantPersistStats:
    """Persist variant rows parsed from release calendar list HTML."""
    from app.services.external_catalog.league_of_comic_geeks import (
        LOCG_SOURCE_NAME,
        LocgListVariantRowStub,
    )
    from app.services.external_catalog.locg_live_html import (
        list_variant_row_to_upsert_dict,
        parse_release_date_live_page,
    )
    from app.services.external_catalog.normalization import normalize_locg_issue

    stats = LocgVariantPersistStats(found=len(variant_rows))
    if debug_trace_path is not None and debug_trace_path.exists():
        debug_trace_path.unlink()

    _variant_persist_trace(
        {
            "phase": "start",
            "found": len(variant_rows),
            "page_date": page_date.isoformat() if page_date else None,
        },
        trace_path=debug_trace_path,
        verbose_console=verbose_console,
    )

    if list_html and page_date is not None:
        for stub in parse_release_date_live_page(list_html, page_date=page_date):
            norm = normalize_locg_issue(
                {
                    "source_name": LOCG_SOURCE_NAME,
                    "source_url": stub.source_url,
                    "title": stub.title,
                    "publisher": stub.publisher,
                    "release_date": stub.release_date or page_date,
                    "price": stub.price,
                    "cover_image_url": stub.cover_image_url,
                },
                source_name=LOCG_SOURCE_NAME,
            )
            try:
                upsert_external_issue(session, norm, overwrite_nulls_only=True)
                stats.parents_ensured_from_list += 1
            except Exception as exc:
                _safe_session_rollback(session)
                stats.upsert_errors += 1
                payload = {
                    "phase": "parent_stub_upsert_failed",
                    "variant_url": None,
                    "title": stub.title,
                    "parent_comic_id": _comic_id_from_url(stub.source_url),
                    **format_db_exception(exc),
                }
                stats._record_first_failure(payload)
                _variant_persist_trace(
                    payload, trace_path=debug_trace_path, verbose_console=verbose_console
                )

    from app.services.external_catalog.locg_parent_stub import (
        comic_id_from_locg_url,
        parent_stub_dict_from_variant_row,
    )

    seen_parent_urls: set[str] = set()
    for row in variant_rows:
        if not isinstance(row, LocgListVariantRowStub):
            continue
        parent_url = (row.parent_source_url or "").strip()
        if not parent_url or parent_url in seen_parent_urls:
            continue
        seen_parent_urls.add(parent_url)
        comic_id = comic_id_from_locg_url(parent_url)
        if comic_id and find_locg_issue_by_comic_id(session, comic_id):
            continue
        stub_payload = parent_stub_dict_from_variant_row(
            row, page_date=page_date, source_name=LOCG_SOURCE_NAME
        )
        if stub_payload is None:
            continue
        norm = normalize_locg_issue(stub_payload, source_name=LOCG_SOURCE_NAME)
        try:
            upsert_external_issue(session, norm, overwrite_nulls_only=True)
            stats.parents_ensured_from_variant_rows += 1
            _variant_persist_trace(
                {
                    "phase": "parent_stub_from_variant_row",
                    "parent_source_url": parent_url,
                    "parent_comic_id": comic_id,
                    "title": stub_payload.get("title"),
                },
                trace_path=debug_trace_path,
                verbose_console=verbose_console,
            )
        except Exception as exc:
            _safe_session_rollback(session)
            stats.upsert_errors += 1
            payload = {
                "phase": "parent_stub_from_variant_failed",
                "parent_source_url": parent_url,
                **format_db_exception(exc),
            }
            stats._record_first_failure(payload)
            _variant_persist_trace(
                payload, trace_path=debug_trace_path, verbose_console=verbose_console
            )

    total = len(variant_rows)
    for idx, row in enumerate(variant_rows, start=1):
        if not isinstance(row, LocgListVariantRowStub):
            stats.upsert_errors += 1
            continue
        if not (row.source_url or "").strip():
            stats.skipped_missing_variant_url += 1
            continue
        if not (row.variant_name or row.title or "").strip():
            stats.skipped_missing_title += 1
            continue
        parent_url_comic_id = comic_id_from_locg_url(row.parent_source_url)
        parent = find_locg_issue_by_comic_id(session, parent_url_comic_id)
        if parent is None:
            parent = find_locg_issue_by_comic_id(session, row.parent_comic_id)
        if parent is None:
            stub_payload = parent_stub_dict_from_variant_row(
                row, page_date=page_date, source_name=LOCG_SOURCE_NAME
            )
            if stub_payload is not None:
                try:
                    norm = normalize_locg_issue(stub_payload, source_name=LOCG_SOURCE_NAME)
                    parent, _, _ = upsert_external_issue(
                        session, norm, overwrite_nulls_only=True
                    )
                    stats.parents_ensured_from_variant_rows += 1
                except Exception as exc:
                    _safe_session_rollback(session)
                    _variant_persist_trace(
                        {
                            "phase": "parent_stub_on_demand_failed",
                            "variant_url": row.source_url,
                            **format_db_exception(exc),
                        },
                        trace_path=debug_trace_path,
                        verbose_console=verbose_console,
                    )
                    parent = None
        if parent is None:
            if not (row.parent_source_url or "").strip():
                stats.skipped_unavoidable_special_case += 1
                reason = "missing_parent_source_url"
            else:
                stats.skipped_missing_parent += 1
                reason = "parent_not_in_db_after_stub_attempt"
            sample = {
                "variant_url": row.source_url,
                "variant_comic_id": row.variant_comic_id,
                "parent_comic_id": row.parent_comic_id,
                "parent_url_comic_id": parent_url_comic_id,
                "title": row.title,
                "parent_source_url": row.parent_source_url,
                "parent_issue_id": None,
                "reason": reason,
                "parent_url_derivable": bool(parent_url_comic_id),
            }
            if len(stats.skipped_missing_parent_samples) < 20:
                stats.skipped_missing_parent_samples.append(sample)
            _variant_persist_trace(
                {
                    "phase": "skipped_missing_parent"
                    if reason != "missing_parent_source_url"
                    else "skipped_unavoidable_special_case",
                    "index": idx,
                    "total": total,
                    **sample,
                },
                trace_path=debug_trace_path,
                verbose_console=verbose_console,
            )
            continue

        title = (row.variant_name or row.title or "").strip()
        _variant_persist_trace(
            {
                "phase": "before_upsert",
                "index": idx,
                "total": total,
                "variant_url": row.source_url,
                "title": title,
                "parent_comic_id": row.parent_comic_id,
                "variant_comic_id": row.variant_comic_id,
                "parent_issue_id": int(parent.id or 0),
            },
            trace_path=debug_trace_path,
            verbose_console=verbose_console,
        )
        try:
            created, updated = upsert_variants(
                session, parent, [list_variant_row_to_upsert_dict(row)]
            )
            touched = created + updated
            stats.persisted += touched
            stats.variant_upsert_success += 1
            _variant_persist_trace(
                {
                    "phase": "after_upsert_ok",
                    "index": idx,
                    "total": total,
                    "variant_url": row.source_url,
                    "title": title,
                    "parent_comic_id": row.parent_comic_id,
                    "created": created,
                    "updated": updated,
                },
                trace_path=debug_trace_path,
                verbose_console=verbose_console,
            )
        except Exception as exc:
            _safe_session_rollback(session)
            stats.variant_upsert_failure += 1
            stats.upsert_errors += 1
            payload = {
                "phase": "variant_upsert_failed",
                "index": idx,
                "total": total,
                "variant_url": row.source_url,
                "title": title,
                "parent_comic_id": row.parent_comic_id,
                "variant_comic_id": row.variant_comic_id,
                **format_db_exception(exc),
            }
            stats._record_first_failure(payload)
            _variant_persist_trace(
                payload, trace_path=debug_trace_path, verbose_console=verbose_console
            )

    _variant_persist_trace(
        {
            "phase": "complete",
            "variant_upsert_success": stats.variant_upsert_success,
            "variant_upsert_failure": stats.variant_upsert_failure,
            "first_variant_failure": stats.first_variant_failure,
            "persisted": stats.persisted,
            "skipped_missing_parent": stats.skipped_missing_parent,
        },
        trace_path=debug_trace_path,
        verbose_console=True,
    )
    if debug_trace_path is not None:
        summary_path = debug_trace_path.with_name("variant_persist_summary.json")
        summary_path.write_text(
            json.dumps(stats.to_dict(), indent=2, default=str),
            encoding="utf-8",
        )
    return stats


def _comic_id_from_url(url: str) -> str:
    import re

    m = re.search(r"/comic/(\d+)", url or "")
    return m.group(1) if m else ""


def upsert_variants(
    session: Session,
    issue: ExternalCatalogIssue,
    variants: list[dict[str, Any]],
) -> tuple[int, int]:
    created = 0
    updated = 0
    for raw in variants:
        cover_label = (raw.get("cover_label") or raw.get("cover") or None)
        variant_name = (raw.get("variant_name") or raw.get("name") or None)
        if cover_label is None and variant_name is None:
            continue
        existing = session.exec(
            select(ExternalCatalogVariant).where(
                ExternalCatalogVariant.external_issue_id == int(issue.id or 0),
                ExternalCatalogVariant.cover_label == cover_label,
                ExternalCatalogVariant.variant_name == variant_name,
            )
        ).first()
        if existing:
            touched = False
            for attr in ("artist", "ratio_value", "price", "image_url", "source_url", "variant_detail_url"):
                val = raw.get(attr)
                if val is not None and getattr(existing, attr) != val:
                    setattr(existing, attr, val)
                    touched = True
            if touched:
                session.add(existing)
            updated += 1
            continue
        session.add(
            ExternalCatalogVariant(
                external_issue_id=int(issue.id or 0),
                cover_label=cover_label,
                variant_name=variant_name,
                artist=raw.get("artist"),
                ratio_value=raw.get("ratio_value"),
                price=raw.get("price"),
                image_url=raw.get("image_url"),
                source_url=raw.get("source_url"),
                variant_detail_url=raw.get("variant_detail_url"),
            )
        )
        created += 1
    if created or updated:
        try:
            session.commit()
        except Exception:
            _safe_session_rollback(session)
            raise
    return created, updated


def upsert_creators(
    session: Session,
    issue: ExternalCatalogIssue,
    creators: list[dict[str, Any]],
) -> int:
    created = 0
    for raw in creators:
        name = (raw.get("creator_name") or raw.get("name") or "").strip()
        if not name:
            continue
        role = (raw.get("role") or None)
        existing = session.exec(
            select(ExternalCatalogCreator).where(
                ExternalCatalogCreator.external_issue_id == int(issue.id or 0),
                ExternalCatalogCreator.creator_name == name,
                ExternalCatalogCreator.role == role,
            )
        ).first()
        if existing:
            continue
        session.add(
            ExternalCatalogCreator(
                external_issue_id=int(issue.id or 0),
                creator_name=name,
                role=raw.get("role") or role,
                role_display=raw.get("role_display") or role,
                source_url=raw.get("source_url"),
            )
        )
        created += 1
    if created:
        session.commit()
    return created


def upsert_characters(
    session: Session,
    issue: ExternalCatalogIssue,
    characters: list[dict[str, Any]],
) -> int:
    created = 0
    for raw in characters:
        name = (raw.get("character_name") or raw.get("name") or "").strip()
        if not name:
            continue
        role = (raw.get("role") or None)
        existing = session.exec(
            select(ExternalCatalogCharacter).where(
                ExternalCatalogCharacter.external_issue_id == int(issue.id or 0),
                ExternalCatalogCharacter.character_name == name,
                ExternalCatalogCharacter.role == role,
            )
        ).first()
        if existing:
            for attr in ("alias", "universe", "source_url"):
                val = raw.get(attr)
                if val is not None and getattr(existing, attr) != val:
                    setattr(existing, attr, val)
                    session.add(existing)
            continue
        session.add(
            ExternalCatalogCharacter(
                external_issue_id=int(issue.id or 0),
                character_name=name,
                alias=raw.get("alias"),
                role=role,
                universe=raw.get("universe"),
                source_url=raw.get("source_url"),
            )
        )
        created += 1
    if created:
        session.commit()
    return created


def should_skip_browser_resume(
    session: Session,
    *,
    source_url: str,
    refresh_existing: bool,
) -> bool:
    if refresh_existing:
        return False
    row = session.exec(
        select(ExternalCatalogIssue).where(
            ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
            ExternalCatalogIssue.source_url == source_url,
        )
    ).first()
    if row is None:
        return False
    return bool(row.pull_count is not None and row.description)


def _extraction_sample(norm: NormalizedLocgIssue, *, source_url: str) -> dict[str, Any]:
    return {
        "source_url": source_url,
        "title": norm.title,
        "pull_count": norm.pull_count,
        "want_count": norm.want_count,
        "pull_count_extracted": norm.pull_count is not None,
        "want_count_extracted": norm.want_count is not None,
        "creator_credits_extracted": len(norm.creators) > 0,
        "creator_credits_count": len(norm.creators),
        "variants_extracted": len(norm.variants) > 0,
        "variants_count": len(norm.variants),
        "cover_image_extracted": bool(norm.cover_image_url),
        "thumbnail_extracted": bool(norm.thumbnail_url),
        "high_res_extracted": bool(norm.high_resolution_image_url),
        "description_extracted": bool(norm.description),
        "story_summary_extracted": bool(norm.story_summary),
        "decision_signals_built": bool(norm.decision_signals_json),
    }


def _process_detail_url(
    session: Session | None,
    *,
    seed: dict[str, Any],
    client: LocgHttpClient,
    counters: SyncCounters,
    dry_run: bool,
    refresh_existing: bool,
    html_detail: str | None = None,
    validation_samples: list[dict[str, Any]] | None = None,
) -> None:
    url = str(seed.get("source_url") or "")
    if not url:
        return
    if session is not None and not refresh_existing:
        existing = _find_issue(
            session,
            source_name=LOCG_SOURCE_NAME,
            source_url=url,
            source_issue_id=str(seed.get("source_issue_id") or "") or None,
        )
        if existing and existing.pull_count is not None and existing.description:
            return
    try:
        html = html_detail if html_detail is not None else fetch_issue_detail_page(url, client=client)
        detail = parse_issue_detail_page(html)
        detail["source_url"] = url
        merged = merge_detail_into_seed(seed, detail)
        norm = normalize_locg_issue(merged, source_name=LOCG_SOURCE_NAME)
        if dry_run:
            if validation_samples is not None:
                validation_samples.append(_extraction_sample(norm, source_url=url))
            return
        assert session is not None
        row, created, updated = upsert_external_issue(session, norm, overwrite_nulls_only=True)
        if created:
            counters.issues_created += 1
        elif updated:
            counters.issues_updated += 1
        v_c, v_u = upsert_variants(session, row, norm.variants)
        counters.variants_created += v_c + v_u
        counters.creators_created += upsert_creators(session, row, norm.creators)
    except Exception as exc:  # noqa: BLE001 — sync continues
        counters.errors_count += 1
        if len(counters.error_sample) < 20:
            counters.error_sample.append(f"{url}: {exc}")


def _calendar_dates_between(start_date: date, end_date: date) -> list[date]:
    dates: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        dates.append(cursor)
        cursor += timedelta(days=1)
    return dates


def probe_locg_backfill(
    *,
    start_date: date,
    end_date: date,
    max_detail_pages: int = 10,
    delay_seconds: float = 1.5,
) -> dict[str, Any]:
    """HTTP + parse validation without database writes (dry-run probe)."""
    client = LocgHttpClient(delay_seconds=delay_seconds)
    counters = SyncCounters()
    validation_samples: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    detail_budget = max_detail_pages
    calendar_dates = _calendar_dates_between(start_date, end_date)
    blocked = False
    try:
        for page_date in calendar_dates:
            try:
                html = fetch_release_date_page(page_date, client=client)
            except LocgAccessBlockedError as exc:
                blocked = True
                counters.errors_count += 1
                counters.error_sample.append(str(exc))
                continue
            except LocgHttpError as exc:
                counters.errors_count += 1
                counters.error_sample.append(str(exc))
                continue
            counters.pages_scanned += 1
            stubs = parse_release_date_page(html, page_date=page_date)
            for stub in stubs:
                if stub.source_url in seen_urls:
                    continue
                seen_urls.add(stub.source_url)
                if detail_budget <= 0:
                    break
                try:
                    _process_detail_url(
                        None,
                        seed=stub_to_detail_seed(stub),
                        client=client,
                        counters=counters,
                        dry_run=True,
                        refresh_existing=False,
                        validation_samples=validation_samples,
                    )
                except (LocgAccessBlockedError, LocgHttpError) as exc:
                    blocked = True
                    counters.errors_count += 1
                    counters.error_sample.append(str(exc))
                detail_budget -= 1
    finally:
        client.close()

    def _count(flag: str) -> int:
        return sum(1 for row in validation_samples if row.get(flag))

    return {
        "mode": "probe_dry_run",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "calendar_dates_tried": [d.isoformat() for d in calendar_dates],
        "pages_scanned": counters.pages_scanned,
        "list_issue_urls_seen": len(seen_urls),
        "detail_pages_fetched": len(validation_samples),
        "errors_count": counters.errors_count,
        "error_sample": counters.error_sample[:10],
        "extraction_summary": {
            "pull_count": _count("pull_count_extracted"),
            "want_count": _count("want_count_extracted"),
            "creator_credits": _count("creator_credits_extracted"),
            "variants": _count("variants_extracted"),
            "cover_images": _count("cover_image_extracted"),
        },
        "samples": validation_samples[:10],
        "access_blocked": blocked,
        "blocking_issue": (
            "LoCG returned 403/429; run validation from a network/IP allowed by LoCG or use licensed API."
            if blocked and not validation_samples
            else None
        ),
    }


def backfill_calendar(
    session: Session | None,
    *,
    start_date: date,
    end_date: date | None = None,
    through_farthest_available: bool = False,
    max_detail_pages: int = LOCG_MAX_DETAIL_PAGES_PER_RUN,
    dry_run: bool = False,
    resume: bool = False,
    refresh_existing: bool = False,
    delay_seconds: float | None = None,
    discover_dates: list[date] | None = None,
    max_detail_pages_override: int | None = None,
    calendar_dates: list[date] | None = None,
) -> dict[str, Any]:
    if dry_run:
        if end_date is None:
            raise ValueError("dry_run requires end_date for probe mode")
        return probe_locg_backfill(
            start_date=start_date,
            end_date=end_date,
            max_detail_pages=max_detail_pages_override or max_detail_pages,
            delay_seconds=delay_seconds or 1.5,
        )

    ensure_locg_source(session)
    client = LocgHttpClient(delay_seconds=delay_seconds or 1.5)
    counters = SyncCounters()
    run = create_sync_run(
        session,
        source_name=LOCG_SOURCE_NAME,
        sync_type=SYNC_BACKFILL,
        start_date=start_date,
        end_date=end_date,
    )
    try:
        if calendar_dates is not None:
            discover_dates = calendar_dates
        elif discover_dates is None:
            discover_dates = discover_available_release_dates(
                start_date,
                max_months=12 if through_farthest_available else 6,
                client=client,
                through_farthest_available=through_farthest_available,
            )
        if end_date:
            discover_dates = [d for d in discover_dates if start_date <= d <= end_date]
        elif not through_farthest_available:
            discover_dates = [d for d in discover_dates if d >= start_date]

        seen_urls: set[str] = set()
        detail_budget = max_detail_pages_override if max_detail_pages_override is not None else max_detail_pages

        for page_date in discover_dates:
            if resume:
                prior = session.exec(
                    select(ExternalCatalogSyncRun)
                    .where(
                        ExternalCatalogSyncRun.source_name == LOCG_SOURCE_NAME,
                        ExternalCatalogSyncRun.sync_type == SYNC_BACKFILL,
                        ExternalCatalogSyncRun.status.in_((SYNC_COMPLETED, SYNC_PARTIAL)),
                        ExternalCatalogSyncRun.end_date == page_date,
                    )
                    .order_by(ExternalCatalogSyncRun.id.desc())
                ).first()
                if prior is not None:
                    continue
            try:
                html = fetch_release_date_page(page_date, client=client)
            except (LocgAccessBlockedError, LocgHttpError) as exc:
                counters.errors_count += 1
                if len(counters.error_sample) < 20:
                    counters.error_sample.append(str(exc))
                continue
            counters.pages_scanned += 1
            stubs = parse_release_date_page(html, page_date=page_date)
            for stub in stubs:
                if stub.source_url in seen_urls:
                    continue
                seen_urls.add(stub.source_url)
                if detail_budget <= 0:
                    break
                try:
                    _process_detail_url(
                        session,
                        seed=stub_to_detail_seed(stub),
                        client=client,
                        counters=counters,
                        dry_run=dry_run,
                        refresh_existing=refresh_existing,
                    )
                except (LocgAccessBlockedError, LocgHttpError) as exc:
                    counters.errors_count += 1
                    if len(counters.error_sample) < 20:
                        counters.error_sample.append(str(exc))
                detail_budget -= 1
            if not dry_run:
                run.end_date = page_date
                session.add(run)
                session.commit()

        status = SYNC_PARTIAL if counters.errors_count else SYNC_COMPLETED
        if detail_budget <= 0 and seen_urls:
            status = SYNC_PARTIAL
        if not dry_run:
            complete_sync_run(session, run=run, counters=counters, status=status)
    except Exception as exc:  # noqa: BLE001
        fail_sync_run(session, run=run, message=str(exc))
        raise
    finally:
        client.close()

    return {
        "sync_run_id": run.id,
        "status": run.status,
        "pages_scanned": counters.pages_scanned,
        "issues_created": counters.issues_created,
        "issues_updated": counters.issues_updated,
        "variants_created": counters.variants_created,
        "creators_created": counters.creators_created,
        "errors_count": counters.errors_count,
        "error_sample": counters.error_sample[:10],
        "dry_run": dry_run,
        "access_blocked": counters.errors_count > 0 and counters.pages_scanned == 0,
        "blocking_issue": (
            "LoCG HTTP 403/429 from this environment; retry on production network or licensed feed."
            if counters.errors_count > 0 and counters.pages_scanned == 0
            else None
        ),
    }


def _max_stored_release_date(session: Session) -> date | None:
    from sqlalchemy import func

    value = session.exec(
        select(func.max(ExternalCatalogIssue.release_date)).where(
            ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME
        )
    ).one()
    return value


def sync_new_weeks(session: Session, *, delay_seconds: float | None = None) -> dict[str, Any]:
    today = date.today()
    max_date = _max_stored_release_date(session) or today
    start = max_date + timedelta(days=1)
    return backfill_calendar(
        session,
        start_date=start,
        end_date=None,
        through_farthest_available=True,
        max_detail_pages=LOCG_MAX_DETAIL_PAGES_PER_RUN,
        dry_run=False,
        resume=False,
        refresh_existing=False,
        delay_seconds=delay_seconds,
    )


def refresh_upcoming_signals(
    session: Session,
    *,
    days_forward: int = 90,
    refresh_details: bool = False,
    max_detail_pages: int = LOCG_MAX_DETAIL_PAGES_PER_RUN,
    delay_seconds: float | None = None,
) -> dict[str, Any]:
    today = date.today()
    horizon = today + timedelta(days=days_forward)
    rows = session.exec(
        select(ExternalCatalogIssue).where(
            ExternalCatalogIssue.source_name == LOCG_SOURCE_NAME,
            ExternalCatalogIssue.release_date.is_not(None),
            ExternalCatalogIssue.release_date >= today,
            ExternalCatalogIssue.release_date <= horizon,
        )
    ).all()

    client = LocgHttpClient(delay_seconds=delay_seconds or 1.5)
    counters = SyncCounters()
    run = create_sync_run(
        session,
        source_name=LOCG_SOURCE_NAME,
        sync_type=SYNC_REFRESH,
        start_date=today,
        end_date=horizon,
    )
    budget = max_detail_pages
    try:
        for row in rows:
            if budget <= 0:
                break
            url = row.source_url
            if not url:
                continue
            prior_variant_count = row.variant_count
            try:
                html = fetch_issue_detail_page(url, client=client)
                detail = parse_issue_detail_page(html)
                seed = {
                    "title": row.title,
                    "publisher": row.publisher,
                    "source_url": url,
                    "source_issue_id": row.source_issue_id,
                    "release_date": row.release_date,
                }
                merged = merge_detail_into_seed(seed, detail)
                norm = normalize_locg_issue(merged, source_name=LOCG_SOURCE_NAME)
                issue_row, _created, was_updated = upsert_external_issue(
                    session, norm, overwrite_nulls_only=True
                )
                if was_updated:
                    counters.issues_updated += 1
                if refresh_details or (
                    prior_variant_count is not None
                    and norm.variant_count is not None
                    and norm.variant_count != prior_variant_count
                ):
                    v_c, v_u = upsert_variants(session, issue_row, norm.variants)
                    counters.variants_created += v_c + v_u
                    counters.creators_created += upsert_creators(session, issue_row, norm.creators)
                budget -= 1
            except Exception as exc:  # noqa: BLE001
                counters.errors_count += 1
                if len(counters.error_sample) < 20:
                    counters.error_sample.append(f"{url}: {exc}")
        status = SYNC_PARTIAL if counters.errors_count else SYNC_COMPLETED
        complete_sync_run(session, run=run, counters=counters, status=status)
    finally:
        client.close()

    return {
        "sync_run_id": run.id,
        "status": run.status,
        "issues_updated": counters.issues_updated,
        "variants_created": counters.variants_created,
        "creators_created": counters.creators_created,
        "errors_count": counters.errors_count,
    }
