from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.models import (
    MarketSourceImportRun,
    MarketSourceImportRunEvent,
    MarketSaleNormalizationIssue,
    MarketSaleRecord,
    MarketSaleRecordImage,
    MarketSource,
    MarketSourceSnapshot,
)
from app.schemas.market_sales import (
    MarketSaleIssueSeverity,
    MarketSaleIssueType,
    MarketSaleListResponse,
    MarketSaleNormalizationIssueRead,
    MarketSaleRead,
    MarketSaleRecordImageRead,
    MarketSaleRecordImageUpsertPayload,
    MarketSourceImportRunCreatePayload,
    MarketSourceImportRunEventRead,
    MarketSourceImportRunListResponse,
    MarketSourceImportRunRead,
    MarketSourceImportRunStatus,
    MarketSourceImportRunSummaryRead,
    MarketSaleSummaryRead,
    MarketSaleUpsertPayload,
    MarketSourceRead,
    MarketSourceSnapshotRead,
    MarketSourceType,
)
from app.services.metadata_enrichment import normalize_issue_number, normalize_publisher_name


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class _MarketSourceSeed:
    source_name: str
    source_type: MarketSourceType
    import_priority: int
    notes: str | None
    supports_raw: bool = True
    supports_graded: bool = True
    supports_variants: bool = True
    enabled: bool = True


SYSTEM_MARKET_SOURCE_PRESETS: tuple[_MarketSourceSeed, ...] = (
    _MarketSourceSeed(
        source_name="eBay",
        source_type="marketplace",
        import_priority=10,
        notes="Deterministic marketplace registry row for future manual imports.",
    ),
    _MarketSourceSeed(
        source_name="Heritage Auctions",
        source_type="auction",
        import_priority=20,
        notes="Auction registry row for deterministic market-sale capture.",
    ),
    _MarketSourceSeed(
        source_name="MyComicShop",
        source_type="fixed_price",
        import_priority=30,
        notes="Fixed-price marketplace row for catalog-style sales imports.",
    ),
    _MarketSourceSeed(
        source_name="ComicLink",
        source_type="auction",
        import_priority=40,
        notes="Secondary auction registry row for comparables.",
    ),
    _MarketSourceSeed(
        source_name="GPA",
        source_type="historical_archive",
        import_priority=50,
        supports_raw=False,
        supports_variants=False,
        notes="Historical archive source row used for deterministic comps reference.",
    ),
    _MarketSourceSeed(
        source_name="Shortboxed",
        source_type="marketplace",
        import_priority=60,
        notes="Marketplace registry row for modern market-sale records.",
    ),
    _MarketSourceSeed(
        source_name="HipComic",
        source_type="marketplace",
        import_priority=70,
        notes="Marketplace registry row for lightweight market-sale imports.",
    ),
)

MARKET_IMPORT_RUN_ALLOWED_TRANSITIONS: dict[MarketSourceImportRunStatus, frozenset[MarketSourceImportRunStatus]] = {
    "pending": frozenset({"running", "cancelled"}),
    "running": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

MARKET_IMPORT_RUN_EVENT_BY_STATUS: dict[MarketSourceImportRunStatus, str] = {
    "pending": "created",
    "running": "started",
    "completed": "completed",
    "cancelled": "cancelled",
}

SUPPORTED_CURRENCY_CODES = {
    "AUD",
    "CAD",
    "EUR",
    "GBP",
    "JPY",
    "USD",
}

ISSUE_SEVERITY_BY_TYPE: dict[MarketSaleIssueType, MarketSaleIssueSeverity] = {
    "missing_issue_number": "warning",
    "ambiguous_variant": "warning",
    "invalid_grade": "warning",
    "malformed_title": "warning",
    "missing_sale_price": "warning",
    "duplicate_listing": "warning",
    "unsupported_currency": "critical",
}


def _normalize_spaces(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", str(value).replace("\u2013", "-").replace("\u2014", "-").strip())
    return normalized or None


def _normalize_title(value: str | None) -> str | None:
    return _normalize_spaces(value)


def _normalize_variant(value: str | None) -> str | None:
    return _normalize_spaces(value)


def _normalize_grade(value: str | None) -> str | None:
    normalized = _normalize_spaces(value)
    if normalized is None:
        return None
    return normalized.upper()


def _normalize_cert_number(value: str | None) -> str | None:
    normalized = _normalize_spaces(value)
    if normalized is None:
        return None
    return normalized.upper()


def _normalize_currency_code(value: str | None) -> str | None:
    normalized = _normalize_spaces(value)
    if normalized is None:
        return None
    return normalized.upper()


def ensure_system_market_sources(session: Session) -> None:
    existing = set(session.exec(select(MarketSource.source_name)).all())
    touched = False
    now = utc_now()
    for preset in SYSTEM_MARKET_SOURCE_PRESETS:
        if preset.source_name in existing:
            continue
        session.add(
            MarketSource(
                source_name=preset.source_name,
                source_type=preset.source_type,
                enabled=preset.enabled,
                import_priority=preset.import_priority,
                supports_raw=preset.supports_raw,
                supports_graded=preset.supports_graded,
                supports_variants=preset.supports_variants,
                notes=preset.notes,
                created_at=now,
                updated_at=now,
            )
        )
        touched = True
    if touched:
        session.commit()


def list_market_sources(session: Session) -> list[MarketSourceRead]:
    ensure_system_market_sources(session)
    rows = session.exec(
        select(MarketSource).order_by(
            MarketSource.import_priority.asc(),
            MarketSource.source_name.asc(),
            MarketSource.id.asc(),
        )
    ).all()
    return [MarketSourceRead.model_validate(row, from_attributes=True) for row in rows]


def get_market_source_read(session: Session, *, market_source_id: int) -> MarketSourceRead:
    ensure_system_market_sources(session)
    row = _get_market_source_or_404(session, market_source_id=market_source_id)
    return MarketSourceRead.model_validate(row, from_attributes=True)


def _get_market_source_or_404(session: Session, *, market_source_id: int) -> MarketSource:
    row = session.get(MarketSource, market_source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market source not found")
    return row


def _trim_optional_text(value: str | None) -> str | None:
    normalized = _normalize_spaces(value)
    return normalized


def _market_import_run_summary(
    *,
    run: MarketSourceImportRun,
    source: MarketSource,
) -> MarketSourceImportRunSummaryRead:
    if run.id is None:
        raise ValueError("market source import run must be flushed before serialization")
    return MarketSourceImportRunSummaryRead(
        id=run.id,
        market_source_id=run.market_source_id,
        source_name=source.source_name,
        source_type=source.source_type,  # type: ignore[arg-type]
        created_by_user_id=run.created_by_user_id,
        status=run.status,  # type: ignore[arg-type]
        total_records=run.total_records,
        imported_records=run.imported_records,
        failed_records=run.failed_records,
        skipped_records=run.skipped_records,
        notes=run.notes,
        created_at=run.created_at,
        updated_at=run.updated_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _market_import_run_event_read(row: MarketSourceImportRunEvent) -> MarketSourceImportRunEventRead:
    return MarketSourceImportRunEventRead.model_validate(row, from_attributes=True)


def _market_import_run_detail(
    session: Session,
    *,
    run: MarketSourceImportRun,
) -> MarketSourceImportRunRead:
    source = _get_market_source_or_404(session, market_source_id=run.market_source_id)
    event_rows = session.exec(
        select(MarketSourceImportRunEvent)
        .where(MarketSourceImportRunEvent.import_run_id == run.id)
        .order_by(
            MarketSourceImportRunEvent.created_at.asc(),
            MarketSourceImportRunEvent.id.asc(),
        )
    ).all()
    summary = _market_import_run_summary(run=run, source=source)
    return MarketSourceImportRunRead(
        **summary.model_dump(),
        events=[_market_import_run_event_read(row) for row in event_rows],
    )


def _assert_market_import_run_transition(run: MarketSourceImportRun, *, target_status: MarketSourceImportRunStatus) -> None:
    current_status = run.status  # type: ignore[assignment]
    allowed_next = MARKET_IMPORT_RUN_ALLOWED_TRANSITIONS.get(current_status) or frozenset()
    if target_status not in allowed_next:
        raise HTTPException(status_code=400, detail=f"Cannot transition market import run from {current_status} to {target_status}")


def _append_market_import_run_event(
    session: Session,
    *,
    run: MarketSourceImportRun,
    actor_user_id: int | None,
    previous_status: MarketSourceImportRunStatus | None,
    new_status: MarketSourceImportRunStatus,
    details_json: dict[str, object] | None = None,
) -> None:
    if run.id is None:
        raise ValueError("market source import run must be flushed before recording events")
    event_type = MARKET_IMPORT_RUN_EVENT_BY_STATUS[new_status]
    session.add(
        MarketSourceImportRunEvent(
            import_run_id=run.id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            actor_user_id=actor_user_id,
            details_json=dict(details_json or {}),
            created_at=utc_now(),
        )
    )


def list_market_import_runs_for_owner(
    session: Session,
    *,
    current_user_id: int,
) -> MarketSourceImportRunListResponse:
    ensure_system_market_sources(session)
    stmt = (
        select(MarketSourceImportRun, MarketSource)
        .join(MarketSource, MarketSourceImportRun.market_source_id == MarketSource.id)
        .where(MarketSourceImportRun.created_by_user_id == current_user_id)
        .order_by(MarketSourceImportRun.created_at.desc(), MarketSourceImportRun.id.desc())
    )
    rows = session.exec(stmt).all()
    return MarketSourceImportRunListResponse(
        items=[
            _market_import_run_summary(run=run, source=source)
            for run, source in rows
        ]
    )


def list_market_import_runs_for_ops(session: Session) -> MarketSourceImportRunListResponse:
    ensure_system_market_sources(session)
    stmt = (
        select(MarketSourceImportRun, MarketSource)
        .join(MarketSource, MarketSourceImportRun.market_source_id == MarketSource.id)
        .order_by(MarketSourceImportRun.created_at.desc(), MarketSourceImportRun.id.desc())
    )
    rows = session.exec(stmt).all()
    return MarketSourceImportRunListResponse(
        items=[
            _market_import_run_summary(run=run, source=source)
            for run, source in rows
        ]
    )


def _get_market_import_run_for_owner_or_404(
    session: Session,
    *,
    run_id: int,
    current_user_id: int | None,
) -> MarketSourceImportRun:
    run = session.get(MarketSourceImportRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Market source import run not found")
    if current_user_id is not None and run.created_by_user_id != current_user_id:
        raise HTTPException(status_code=404, detail="Market source import run not found")
    return run


def get_market_import_run_for_owner(
    session: Session,
    *,
    current_user_id: int,
    run_id: int,
) -> MarketSourceImportRunRead:
    ensure_system_market_sources(session)
    return _market_import_run_detail(
        session,
        run=_get_market_import_run_for_owner_or_404(session, run_id=run_id, current_user_id=current_user_id),
    )


def get_market_import_run_for_ops(session: Session, *, run_id: int) -> MarketSourceImportRunRead:
    ensure_system_market_sources(session)
    return _market_import_run_detail(
        session,
        run=_get_market_import_run_for_owner_or_404(session, run_id=run_id, current_user_id=None),
    )


def create_market_import_run_for_ops(
    session: Session,
    *,
    actor_user_id: int | None,
    payload: MarketSourceImportRunCreatePayload,
) -> MarketSourceImportRunRead:
    ensure_system_market_sources(session)
    source = _get_market_source_or_404(session, market_source_id=payload.market_source_id)
    now = utc_now()
    run = MarketSourceImportRun(
        market_source_id=source.id or payload.market_source_id,
        created_by_user_id=actor_user_id,
        status="pending",
        total_records=0,
        imported_records=0,
        failed_records=0,
        skipped_records=0,
        notes=_trim_optional_text(payload.notes),
        created_at=now,
        updated_at=now,
        started_at=None,
        completed_at=None,
    )
    session.add(run)
    session.flush()
    _append_market_import_run_event(
        session,
        run=run,
        actor_user_id=actor_user_id,
        previous_status=None,
        new_status="pending",
        details_json={"source_name": source.source_name, "source_type": source.source_type},
    )
    session.commit()
    session.refresh(run)
    return _market_import_run_detail(session, run=run)


def _transition_market_import_run(
    session: Session,
    *,
    run: MarketSourceImportRun,
    target_status: MarketSourceImportRunStatus,
    actor_user_id: int | None,
) -> MarketSourceImportRunRead:
    if run.id is None:
        raise HTTPException(status_code=404, detail="Market source import run not found")
    _assert_market_import_run_transition(run, target_status=target_status)
    before_status = run.status  # type: ignore[assignment]
    now = utc_now()
    run.status = target_status
    run.updated_at = now
    if target_status == "running":
        run.started_at = run.started_at or now
    if target_status in {"cancelled", "completed"}:
        run.completed_at = run.completed_at or now
    session.add(run)
    session.flush()
    _append_market_import_run_event(
        session,
        run=run,
        actor_user_id=actor_user_id,
        previous_status=before_status,
        new_status=target_status,
        details_json={"source_name": _get_market_source_or_404(session, market_source_id=run.market_source_id).source_name},
    )
    session.commit()
    session.refresh(run)
    return _market_import_run_detail(session, run=run)


def start_market_import_run_for_ops(
    session: Session,
    *,
    run_id: int,
    actor_user_id: int | None,
) -> MarketSourceImportRunRead:
    run = _get_market_import_run_for_owner_or_404(session, run_id=run_id, current_user_id=None)
    if run.status != "pending":
        raise HTTPException(status_code=400, detail="Market import run can only start while pending")
    return _transition_market_import_run(session, run=run, target_status="running", actor_user_id=actor_user_id)


def cancel_market_import_run_for_ops(
    session: Session,
    *,
    run_id: int,
    actor_user_id: int | None,
) -> MarketSourceImportRunRead:
    run = _get_market_import_run_for_owner_or_404(session, run_id=run_id, current_user_id=None)
    if run.status not in {"pending", "running"}:
        raise HTTPException(status_code=400, detail="Market import run already finalized")
    return _transition_market_import_run(session, run=run, target_status="cancelled", actor_user_id=actor_user_id)


def complete_market_import_run_for_ops(
    session: Session,
    *,
    run_id: int,
    actor_user_id: int | None,
) -> MarketSourceImportRunRead:
    run = _get_market_import_run_for_owner_or_404(session, run_id=run_id, current_user_id=None)
    if run.status != "running":
        raise HTTPException(status_code=400, detail="Market import run can only complete while running")
    return _transition_market_import_run(session, run=run, target_status="completed", actor_user_id=actor_user_id)


def _issue_detail(
    *,
    basis: str,
    existing_record_ids: list[int] | None = None,
    matched_record_id: int | None = None,
    raw_value: str | None = None,
    normalized_value: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"basis": basis}
    if existing_record_ids is not None:
        payload["existing_record_ids"] = existing_record_ids
    if matched_record_id is not None:
        payload["matched_record_id"] = matched_record_id
    if raw_value is not None:
        payload["raw_value"] = raw_value
    if normalized_value is not None:
        payload["normalized_value"] = normalized_value
    return payload


def _add_issue_spec(
    specs: list[tuple[MarketSaleIssueType, MarketSaleIssueSeverity, dict[str, object]]],
    issue_type: MarketSaleIssueType,
    **details: object,
) -> None:
    specs.append((issue_type, ISSUE_SEVERITY_BY_TYPE[issue_type], details))


def _normalize_payload(
    payload: MarketSaleUpsertPayload,
    *,
    session: Session,
) -> tuple[dict[str, object], list[tuple[MarketSaleIssueType, MarketSaleIssueSeverity, dict[str, object]]]]:
    issue_specs: list[tuple[MarketSaleIssueType, MarketSaleIssueSeverity, dict[str, object]]] = []

    raw_title = _normalize_spaces(payload.raw_title) or ""
    normalized_title = _normalize_title(payload.raw_title)
    if not raw_title:
        _add_issue_spec(issue_specs, "malformed_title", basis="blank_title")
    elif raw_title != payload.raw_title:
        _add_issue_spec(
            issue_specs,
            "malformed_title",
            basis="whitespace_normalization",
            raw_value=payload.raw_title,
            normalized_value=raw_title,
        )

    raw_issue = _normalize_spaces(payload.raw_issue) or ""
    normalized_issue = normalize_issue_number(payload.raw_issue).canonical_value
    if not raw_issue or normalized_issue is None:
        _add_issue_spec(
            issue_specs,
            "missing_issue_number",
            basis="missing_or_unsupported_issue",
            raw_value=payload.raw_issue,
        )

    raw_publisher = _normalize_spaces(payload.raw_publisher)
    normalized_publisher = normalize_publisher_name(payload.raw_publisher, session=session).canonical_value

    raw_variant = _normalize_variant(payload.raw_variant)
    normalized_variant = raw_variant
    if raw_variant is not None and any(marker in raw_variant for marker in ("/", "&", ",", ";")):
        _add_issue_spec(
            issue_specs,
            "ambiguous_variant",
            basis="variant_delimiters",
            raw_value=raw_variant,
        )

    raw_grade = _normalize_spaces(payload.raw_grade)
    normalized_grade = _normalize_grade(payload.raw_grade)
    if raw_grade is not None:
        grade_token = re.sub(r"\s+", "", normalized_grade or "")
        if not grade_token or not any(char.isdigit() for char in grade_token):
            _add_issue_spec(
                issue_specs,
                "invalid_grade",
                basis="non_numeric_grade",
                raw_value=raw_grade,
                normalized_value=normalized_grade,
            )

    raw_cert_number = _normalize_cert_number(payload.raw_cert_number)
    normalized_cert_number = raw_cert_number

    raw_currency_code = _normalize_spaces(payload.currency_code)
    currency_code = _normalize_currency_code(payload.currency_code)
    if currency_code is None or len(currency_code) != 3 or not currency_code.isalpha() or currency_code not in SUPPORTED_CURRENCY_CODES:
        _add_issue_spec(
            issue_specs,
            "unsupported_currency",
            basis="unsupported_currency_code",
            raw_value=payload.currency_code,
            normalized_value=currency_code,
        )

    if payload.sale_price is None:
        _add_issue_spec(issue_specs, "missing_sale_price", basis="missing_sale_price")

    normalized_status = "normalized"
    if any(severity == "critical" for _, severity, _ in issue_specs):
        normalized_status = "normalization_failed"
    elif issue_specs:
        normalized_status = "partially_normalized"
    else:
        if (
            normalized_title == raw_title
            and normalized_issue == raw_issue
            and normalized_publisher == raw_publisher
            and normalized_variant == raw_variant
            and normalized_grade == raw_grade
            and normalized_cert_number == raw_cert_number
            and currency_code == raw_currency_code
        ):
            normalized_status = "raw"

    normalized_values: dict[str, object] = {
        "listing_type": payload.listing_type,
        "raw_title": raw_title,
        "normalized_title": normalized_title,
        "raw_issue": raw_issue,
        "normalized_issue": normalized_issue,
        "raw_publisher": raw_publisher,
        "normalized_publisher": normalized_publisher,
        "raw_variant": raw_variant,
        "normalized_variant": normalized_variant,
        "raw_grade": raw_grade,
        "normalized_grade": normalized_grade,
        "raw_cert_number": raw_cert_number,
        "normalized_cert_number": normalized_cert_number,
        "sale_price": payload.sale_price,
        "shipping_price": payload.shipping_price,
        "total_price": payload.total_price,
        "currency_code": currency_code,
        "sale_date": payload.sale_date,
        "seller_name": _normalize_spaces(payload.seller_name),
        "buyer_name": _normalize_spaces(payload.buyer_name),
        "is_graded": payload.is_graded,
        "grading_company": payload.grading_company,
        "is_signed": payload.is_signed,
        "source_url": _normalize_spaces(payload.source_url),
        "normalization_status": normalized_status,
    }
    return normalized_values, issue_specs


def _append_source_metadata_history(
    existing_metadata: dict[str, object] | None,
    payload: MarketSaleUpsertPayload,
    *,
    normalized_values: dict[str, object],
) -> dict[str, object]:
    now = utc_now().isoformat()
    normalized_values_json = {
        key: value.isoformat() if isinstance(value, date) else str(value) if isinstance(value, Decimal) else value
        for key, value in normalized_values.items()
    }
    metadata = dict(existing_metadata or {})
    history = list(metadata.get("history") or [])
    history.append(
        {
            "captured_at": now,
            "payload": payload.model_dump(mode="json"),
            "normalized_values": normalized_values_json,
        }
    )
    metadata["history"] = history
    metadata["latest_payload"] = payload.model_dump(mode="json")
    metadata["latest_normalized_values"] = normalized_values_json
    return metadata


def _issue_rows_for_record(
    session: Session,
    *,
    record: MarketSaleRecord,
    source_listing_duplicate: MarketSaleRecord | None = None,
) -> list[tuple[MarketSaleIssueType, MarketSaleIssueSeverity, dict[str, object]]]:
    specs: list[tuple[MarketSaleIssueType, MarketSaleIssueSeverity, dict[str, object]]] = []

    if source_listing_duplicate is not None and source_listing_duplicate.id is not None:
        _add_issue_spec(
            specs,
            "duplicate_listing",
            basis="source_listing_id",
            matched_record_id=source_listing_duplicate.id,
            raw_value=record.source_listing_id,
        )

    if record.normalized_cert_number and record.sale_price is not None and record.sale_date is not None:
        same_cert_rows = session.exec(
            select(MarketSaleRecord.id)
            .where(MarketSaleRecord.id != record.id)
            .where(MarketSaleRecord.normalized_cert_number == record.normalized_cert_number)
            .where(MarketSaleRecord.sale_price == record.sale_price)
            .where(MarketSaleRecord.sale_date == record.sale_date)
            .order_by(MarketSaleRecord.id.asc())
        ).all()
        if same_cert_rows:
            _add_issue_spec(
                specs,
                "duplicate_listing",
                basis="cert_price_sale_date",
                existing_record_ids=[int(row_id) for row_id in same_cert_rows],
                raw_value=record.raw_cert_number,
                normalized_value=record.normalized_cert_number,
            )

    if (
        record.normalized_title
        and record.normalized_issue
        and record.sale_date is not None
        and record.total_price is not None
    ):
        same_identity_rows = session.exec(
            select(MarketSaleRecord.id)
            .where(MarketSaleRecord.id != record.id)
            .where(MarketSaleRecord.normalized_title == record.normalized_title)
            .where(MarketSaleRecord.normalized_issue == record.normalized_issue)
            .where(MarketSaleRecord.normalized_publisher == record.normalized_publisher)
            .where(MarketSaleRecord.normalized_variant == record.normalized_variant)
            .where(MarketSaleRecord.total_price == record.total_price)
            .where(MarketSaleRecord.sale_date == record.sale_date)
            .order_by(MarketSaleRecord.id.asc())
        ).all()
        if same_identity_rows:
            _add_issue_spec(
                specs,
                "duplicate_listing",
                basis="normalized_identity_total_price_sale_date",
                existing_record_ids=[int(row_id) for row_id in same_identity_rows],
                raw_value=record.raw_title,
                normalized_value=record.normalized_title,
            )

    return specs


def _add_issues(
    session: Session,
    *,
    record_id: int,
    issue_specs: list[tuple[MarketSaleIssueType, MarketSaleIssueSeverity, dict[str, object]]],
) -> None:
    for issue_type, severity, details in issue_specs:
        session.add(
            MarketSaleNormalizationIssue(
                market_sale_record_id=record_id,
                issue_type=issue_type,
                severity=severity,
                details_json=details,
                created_at=utc_now(),
            )
        )


def _append_images(
    session: Session,
    *,
    record_id: int,
    images: list[MarketSaleRecordImageUpsertPayload],
) -> None:
    if not images:
        return
    existing_max_order = session.exec(
        select(func.max(MarketSaleRecordImage.display_order)).where(MarketSaleRecordImage.market_sale_record_id == record_id)
    ).one()
    next_order = int(existing_max_order or -1) + 1
    for image in images:
        display_order = image.display_order if image.display_order is not None else next_order
        next_order = max(next_order, display_order + 1)
        session.add(
            MarketSaleRecordImage(
                market_sale_record_id=record_id,
                image_url=_normalize_spaces(image.image_url),
                image_sha256=_normalize_spaces(image.image_sha256),
                display_order=display_order,
                created_at=utc_now(),
            )
        )


def _market_sale_summary(
    *,
    record: MarketSaleRecord,
    source: MarketSource,
    issue_count: int = 0,
) -> MarketSaleSummaryRead:
    if record.id is None:
        raise ValueError("market sale record must be flushed before serialization")
    return MarketSaleSummaryRead(
        id=record.id,
        market_source_id=record.market_source_id,
        source_name=source.source_name,
        source_type=source.source_type,  # type: ignore[arg-type]
        source_listing_id=record.source_listing_id,
        source_snapshot_id=record.source_snapshot_id,
        listing_type=record.listing_type,  # type: ignore[arg-type]
        raw_title=record.raw_title,
        normalized_title=record.normalized_title,
        raw_issue=record.raw_issue,
        normalized_issue=record.normalized_issue,
        sale_price=record.sale_price,
        shipping_price=record.shipping_price,
        total_price=record.total_price,
        currency_code=record.currency_code,
        sale_date=record.sale_date,
        is_graded=record.is_graded,
        grading_company=record.grading_company,  # type: ignore[arg-type]
        is_signed=record.is_signed,
        normalization_status=record.normalization_status,  # type: ignore[arg-type]
        normalization_issue_count=issue_count,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _market_sale_detail(
    session: Session,
    *,
    record: MarketSaleRecord,
) -> MarketSaleRead:
    source = _get_market_source_or_404(session, market_source_id=record.market_source_id)
    issue_rows = session.exec(
        select(MarketSaleNormalizationIssue).where(MarketSaleNormalizationIssue.market_sale_record_id == record.id).order_by(
            MarketSaleNormalizationIssue.created_at.asc(),
            MarketSaleNormalizationIssue.id.asc(),
        )
    ).all()
    image_rows = session.exec(
        select(MarketSaleRecordImage)
        .where(MarketSaleRecordImage.market_sale_record_id == record.id)
        .order_by(MarketSaleRecordImage.display_order.asc(), MarketSaleRecordImage.id.asc())
    ).all()
    snapshot = session.get(MarketSourceSnapshot, record.source_snapshot_id) if record.source_snapshot_id is not None else None
    summary = _market_sale_summary(record=record, source=source, issue_count=len(issue_rows))
    return MarketSaleRead(
        **summary.model_dump(),
        raw_publisher=record.raw_publisher,
        normalized_publisher=record.normalized_publisher,
        raw_variant=record.raw_variant,
        normalized_variant=record.normalized_variant,
        raw_grade=record.raw_grade,
        normalized_grade=record.normalized_grade,
        raw_cert_number=record.raw_cert_number,
        normalized_cert_number=record.normalized_cert_number,
        seller_name=record.seller_name,
        buyer_name=record.buyer_name,
        source_url=record.source_url,
        source_metadata_json=record.source_metadata_json or {},
        review_status=record.review_status,  # type: ignore[arg-type]
        images=[MarketSaleRecordImageRead.model_validate(row, from_attributes=True) for row in image_rows],
        normalization_issues=[
            MarketSaleNormalizationIssueRead.model_validate(row, from_attributes=True) for row in issue_rows
        ],
        source_snapshot=MarketSourceSnapshotRead.model_validate(snapshot, from_attributes=True) if snapshot else None,
    )


def list_market_sales(
    session: Session,
    *,
    source: str | None = None,
    publisher: str | None = None,
    normalized_title: str | None = None,
    normalized_issue: str | None = None,
    grading_company: str | None = None,
    is_graded: bool | None = None,
    normalization_status: str | None = None,
    sale_date_from: date | None = None,
    sale_date_to: date | None = None,
) -> MarketSaleListResponse:
    ensure_system_market_sources(session)
    stmt = select(MarketSaleRecord, MarketSource).join(MarketSource, MarketSaleRecord.market_source_id == MarketSource.id)
    if source:
        source_term = source.strip()
        stmt = stmt.where(
            or_(
                MarketSource.source_name.ilike(f"%{source_term}%"),
                MarketSource.source_type.ilike(f"%{source_term}%"),
            )
        )
    if publisher:
        stmt = stmt.where(MarketSaleRecord.normalized_publisher == _normalize_spaces(publisher))
    if normalized_title:
        stmt = stmt.where(MarketSaleRecord.normalized_title == _normalize_spaces(normalized_title))
    if normalized_issue:
        stmt = stmt.where(MarketSaleRecord.normalized_issue == _normalize_spaces(normalized_issue))
    if grading_company:
        stmt = stmt.where(func.upper(MarketSaleRecord.grading_company) == grading_company.strip().upper())
    if is_graded is not None:
        stmt = stmt.where(MarketSaleRecord.is_graded.is_(is_graded))
    if normalization_status:
        stmt = stmt.where(MarketSaleRecord.normalization_status == normalization_status)
    if sale_date_from is not None:
        stmt = stmt.where(MarketSaleRecord.sale_date >= sale_date_from)
    if sale_date_to is not None:
        stmt = stmt.where(MarketSaleRecord.sale_date <= sale_date_to)
    stmt = stmt.order_by(
        MarketSaleRecord.sale_date.desc().nullslast(),
        MarketSource.source_name.asc(),
        MarketSaleRecord.normalized_title.asc(),
        MarketSaleRecord.normalized_issue.asc(),
        MarketSaleRecord.id.asc(),
    )
    rows = session.exec(stmt).all()
    record_ids = [int(record.id) for record, _source in rows if record.id is not None]
    issue_counts: dict[int, int] = {}
    if record_ids:
        counts = session.exec(
            select(
                MarketSaleNormalizationIssue.market_sale_record_id,
                func.count(MarketSaleNormalizationIssue.id),
            )
            .where(MarketSaleNormalizationIssue.market_sale_record_id.in_(record_ids))
            .group_by(MarketSaleNormalizationIssue.market_sale_record_id)
        ).all()
        issue_counts = {int(record_id): int(total or 0) for record_id, total in counts}
    return MarketSaleListResponse(
        items=[
            _market_sale_summary(
                record=record,
                source=source_row,
                issue_count=issue_counts.get(int(record.id or 0), 0),
            )
            for record, source_row in rows
        ]
    )


def get_market_sale_record(session: Session, *, market_sale_record_id: int) -> MarketSaleRead:
    ensure_system_market_sources(session)
    record = session.get(MarketSaleRecord, market_sale_record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Market sale record not found")
    return _market_sale_detail(session, record=record)


def upsert_market_sale_record(
    session: Session,
    *,
    payload: MarketSaleUpsertPayload,
) -> MarketSaleRead:
    ensure_system_market_sources(session)
    source = _get_market_source_or_404(session, market_source_id=payload.market_source_id)
    if not source.enabled:
        raise HTTPException(status_code=400, detail="Market source is disabled")
    if payload.source_snapshot_id is not None and session.get(MarketSourceSnapshot, payload.source_snapshot_id) is None:
        raise HTTPException(status_code=404, detail="Market source snapshot not found")

    normalized_values, issue_specs = _normalize_payload(payload, session=session)
    source_listing_duplicate = None
    if payload.source_listing_id is not None:
        source_listing_duplicate = session.exec(
            select(MarketSaleRecord)
            .where(MarketSaleRecord.market_source_id == payload.market_source_id)
            .where(MarketSaleRecord.source_listing_id == payload.source_listing_id)
        ).first()

    record = source_listing_duplicate or MarketSaleRecord(
        market_source_id=payload.market_source_id,
        source_listing_id=payload.source_listing_id,
    )
    is_update = record.id is not None
    now = utc_now()
    for key, value in normalized_values.items():
        setattr(record, key, value)
    record.market_source_id = payload.market_source_id
    record.source_listing_id = payload.source_listing_id
    record.source_snapshot_id = payload.source_snapshot_id
    record.source_metadata_json = _append_source_metadata_history(
        record.source_metadata_json if is_update else {},
        payload,
        normalized_values=normalized_values,
    )
    record.updated_at = now
    if not is_update:
        record.created_at = now
        session.add(record)
    else:
        session.add(record)
    session.flush()

    image_payloads = list(payload.images)
    if image_payloads:
        _append_images(session, record_id=record.id or 0, images=image_payloads)

    record_issue_specs = list(issue_specs)
    record_issue_specs.extend(_issue_rows_for_record(session, record=record, source_listing_duplicate=source_listing_duplicate))
    _add_issues(session, record_id=record.id or 0, issue_specs=record_issue_specs)
    session.flush()
    session.commit()
    session.refresh(record)
    return _market_sale_detail(session, record=record)

