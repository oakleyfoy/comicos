"""Deterministic read-only market/FMV reporting and CSV export rows (P35-10).

No valuation mutation, no forecasting, no recommendations beyond explicit deterministic labels.

"""

from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import InventoryCopy, MarketSaleNormalizationIssue
from app.services.inventory_fmv import (
    inventory_fmv_context_for_scope,
    portfolio_value_summary_for_scope,
)
from app.services.market_fmv import list_market_fmv_snapshots
from app.services.market_sale_comp_eligibility import list_market_comp_eligibility
from app.services.market_sales import list_market_sales
from app.services.market_trends import list_market_trends
from app.services.reports_export import dumps_report_json, render_csv

MARKET_SALES_EXPORT_COLUMNS: tuple[str, ...] = (
    "id",
    "market_source_id",
    "source_name",
    "source_type",
    "listing_type",
    "raw_title",
    "normalized_title",
    "raw_issue",
    "normalized_issue",
    "sale_price",
    "shipping_price",
    "total_price",
    "currency_code",
    "sale_date",
    "is_graded",
    "grading_company",
    "is_signed",
    "normalization_status",
    "normalization_issue_count",
    "created_at",
    "updated_at",
)

MARKET_ELIGIBLE_COMPS_EXPORT_COLUMNS: tuple[str, ...] = (
    "market_sale_record_id",
    "eligibility_status",
    "eligibility_classification",
    "review_status",
    "source_name",
    "source_type",
    "canonical_match_state",
    "normalized_title",
    "raw_title",
    "normalized_issue",
    "raw_issue",
    "sale_price",
    "total_price",
    "currency_code",
    "sale_date",
    "is_graded",
    "grading_company",
)

MARKET_FMV_SNAPSHOT_EXPORT_COLUMNS: tuple[str, ...] = (
    "snapshot_id",
    "canonical_issue_id",
    "metadata_identity_key",
    "snapshot_scope",
    "grading_company",
    "normalized_grade",
    "currency_code",
    "snapshot_date",
    "valuation_method",
    "estimated_fmv",
    "comp_count",
    "confidence_bucket",
    "liquidity_bucket",
    "volatility_bucket",
    "stale_data",
    "created_at",
    "updated_at",
)

MARKET_TREND_EXPORT_COLUMNS: tuple[str, ...] = (
    "snapshot_id",
    "canonical_issue_id",
    "metadata_identity_key",
    "snapshot_scope",
    "grading_company",
    "normalized_grade",
    "currency_code",
    "trend_window",
    "trend_direction",
    "trend_strength",
    "liquidity_direction",
    "comp_count",
    "percent_change",
    "volatility_score",
    "stale_data",
    "created_at",
    "updated_at",
)

PORTFOLIO_VALUE_EXPORT_COLUMNS: tuple[str, ...] = (
    "currency_code",
    "total_active_market_value",
    "raw_market_value",
    "graded_market_value",
    "preorder_informational_value",
    "low_confidence_value",
    "stale_value",
    "no_market_data_count",
    "cancelled_excluded_count",
    "duplicate_group_total_value",
    "duplicate_extra_copy_value",
    "duplicate_value_exposure",
    "duplicate_raw_value",
    "duplicate_graded_value",
)

NO_MARKET_DATA_OWNER_COLUMNS: tuple[str, ...] = (
    "inventory_copy_id",
    "publisher",
    "title",
    "issue_number",
    "ownership_state",
    "metadata_identity_key",
    "grade_status",
)

NO_MARKET_DATA_OPS_COLUMNS: tuple[str, ...] = (
    "inventory_copy_id",
    "owner_user_id",
) + NO_MARKET_DATA_OWNER_COLUMNS[1:]

FMV_QUALITY_OWNER_COLUMNS: tuple[str, ...] = (
    "inventory_copy_id",
    "publisher",
    "title",
    "issue_number",
    "ownership_state",
    "valuation_scope",
    "fmv_confidence_bucket",
    "fmv_liquidity_bucket",
    "fmv_stale_data",
    "fmv_currency_code",
    "fmv_snapshot_id",
    "current_market_fmv",
)

FMV_QUALITY_OPS_COLUMNS: tuple[str, ...] = (
    "inventory_copy_id",
    "owner_user_id",
) + FMV_QUALITY_OWNER_COLUMNS[1:]

NORMALIZATION_ISSUES_EXPORT_COLUMNS: tuple[str, ...] = (
    "issue_type",
    "severity",
    "issue_row_count",
)


def market_sales_export_rows(
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
) -> tuple[list[dict[str, Any]], date]:
    response = list_market_sales(
        session,
        source=source,
        publisher=publisher,
        normalized_title=normalized_title,
        normalized_issue=normalized_issue,
        grading_company=grading_company,
        is_graded=is_graded,
        normalization_status=normalization_status,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    rows = []
    for item in response.items:
        dumped = item.model_dump(mode="json")
        dumped["sale_date"] = dumped.get("sale_date")
        rows.append({col: dumped.get(col) for col in MARKET_SALES_EXPORT_COLUMNS})
    return rows, date.today()


def market_eligible_comps_export_rows(session: Session) -> tuple[list[dict[str, Any]], date]:
    response = list_market_comp_eligibility(session, eligibility_status="eligible")
    rows: list[dict[str, Any]] = []
    for row in response.items:
        rows.append(
            {
                "market_sale_record_id": row.id,
                "eligibility_status": row.eligibility_status,
                "eligibility_classification": row.eligibility_classification,
                "review_status": row.review_status,
                "source_name": row.source_name,
                "source_type": row.source_type,
                "canonical_match_state": row.canonical_match_state,
                "normalized_title": row.normalized_title,
                "raw_title": row.raw_title,
                "normalized_issue": row.normalized_issue,
                "raw_issue": row.raw_issue,
                "sale_price": row.sale_price,
                "total_price": row.total_price,
                "currency_code": row.currency_code,
                "sale_date": row.sale_date.isoformat() if row.sale_date else "",
                "is_graded": row.is_graded,
                "grading_company": row.grading_company or "",
            }
        )
    return rows, date.today()


def market_fmv_snapshot_export_rows(session: Session) -> tuple[list[dict[str, Any]], date]:
    response = list_market_fmv_snapshots(session)
    rows: list[dict[str, Any]] = []
    for item in response.items:
        dumped = item.model_dump(mode="json")
        rows.append(
            {
                "snapshot_id": dumped["id"],
                "canonical_issue_id": dumped.get("canonical_issue_id"),
                "metadata_identity_key": dumped.get("metadata_identity_key"),
                "snapshot_scope": dumped.get("snapshot_scope"),
                "grading_company": dumped.get("grading_company"),
                "normalized_grade": dumped.get("normalized_grade"),
                "currency_code": dumped.get("currency_code"),
                "snapshot_date": dumped.get("snapshot_date"),
                "valuation_method": dumped.get("valuation_method"),
                "estimated_fmv": dumped.get("estimated_fmv"),
                "comp_count": dumped.get("comp_count"),
                "confidence_bucket": dumped.get("confidence_bucket"),
                "liquidity_bucket": dumped.get("liquidity_bucket"),
                "volatility_bucket": dumped.get("volatility_bucket"),
                "stale_data": dumped.get("stale_data"),
                "created_at": dumped.get("created_at"),
                "updated_at": dumped.get("updated_at"),
            }
        )
    return rows, date.today()


def market_trend_export_rows(session: Session) -> tuple[list[dict[str, Any]], date]:
    response = list_market_trends(session)
    rows: list[dict[str, Any]] = []
    for item in response.items:
        dumped = item.model_dump(mode="json")
        rows.append(
            {
                "snapshot_id": dumped["id"],
                "canonical_issue_id": dumped.get("canonical_issue_id"),
                "metadata_identity_key": dumped.get("metadata_identity_key"),
                "snapshot_scope": dumped.get("snapshot_scope"),
                "grading_company": dumped.get("grading_company"),
                "normalized_grade": dumped.get("normalized_grade"),
                "currency_code": dumped.get("currency_code"),
                "trend_window": dumped.get("trend_window"),
                "trend_direction": dumped.get("trend_direction"),
                "trend_strength": dumped.get("trend_strength"),
                "liquidity_direction": dumped.get("liquidity_direction"),
                "comp_count": dumped.get("comp_count"),
                "percent_change": dumped.get("percent_change"),
                "volatility_score": dumped.get("volatility_score"),
                "stale_data": dumped.get("stale_data"),
                "created_at": dumped.get("created_at"),
                "updated_at": dumped.get("updated_at"),
            }
        )
    return rows, date.today()


def portfolio_value_export_rows(
    session: Session,
    *,
    owner_user_id: int | None,
    publisher: str | None = None,
    ownership_state: str | None = None,
) -> tuple[list[dict[str, Any]], date]:
    summary = portfolio_value_summary_for_scope(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        ownership_state=ownership_state,
    )
    rows: list[dict[str, Any]] = []
    for item in sorted(summary.items, key=lambda r: r.currency_code):
        dumped = item.model_dump(mode="json")
        rows.append({col: dumped.get(col) for col in PORTFOLIO_VALUE_EXPORT_COLUMNS})
    return rows, summary.generated_as_of_date


def _inventory_owner_map(session: Session, inventory_ids: list[int]) -> dict[int, int]:
    if not inventory_ids:
        return {}
    rows = session.exec(
        select(InventoryCopy.id, InventoryCopy.user_id).where(InventoryCopy.id.in_(inventory_ids))
    ).all()
    return {int(r.id): int(r.user_id) for r in rows if r.id is not None and r.user_id is not None}


def _fmv_inventory_slice_rows(
    session: Session,
    *,
    owner_user_id: int | None,
    predicate,
    columns: tuple[str, ...],
) -> tuple[list[dict[str, Any]], date]:
    row_maps, attachments, _duplicate = inventory_fmv_context_for_scope(
        session, owner_user_id=owner_user_id, include_detail=False
    )
    owner_lookup = (
        None
        if owner_user_id is not None
        else _inventory_owner_map(session, [int(r["inventory_copy_id"]) for r in row_maps])
    )
    sliced: list[dict[str, Any]] = []
    for row in sorted(row_maps, key=lambda r: int(r["inventory_copy_id"])):
        inv_id = int(row["inventory_copy_id"])
        att = attachments[inv_id]
        if not predicate(att, row):
            continue
        record: dict[str, Any] = {
            "inventory_copy_id": inv_id,
            "publisher": row["publisher"],
            "title": row["title"],
            "issue_number": row["issue_number"],
            "ownership_state": row["ownership_state"],
            "valuation_scope": att.valuation_scope,
            "fmv_confidence_bucket": att.fmv_confidence_bucket,
            "fmv_liquidity_bucket": att.fmv_liquidity_bucket,
            "fmv_stale_data": bool(att.fmv_stale_data) if att.fmv_stale_data is not None else False,
            "fmv_currency_code": att.fmv_currency_code or "",
            "fmv_snapshot_id": att.fmv_snapshot_id,
            "current_market_fmv": att.current_market_fmv,
            "metadata_identity_key": row.get("metadata_identity_key"),
            "grade_status": row["grade_status"],
        }
        if owner_lookup is not None:
            record["owner_user_id"] = owner_lookup.get(inv_id, "")
        sliced.append(record)
    # Narrow to requested columns deterministically
    out = [{col: rec.get(col) for col in columns} for rec in sliced]
    return out, date.today()


def market_no_market_data_inventory_export_rows(
    session: Session,
    *,
    owner_user_id: int | None,
) -> tuple[list[dict[str, Any]], date]:
    def _pred(att, row):
        del row
        return att.valuation_scope == "no_market_data"

    cols = NO_MARKET_DATA_OWNER_COLUMNS if owner_user_id is not None else NO_MARKET_DATA_OPS_COLUMNS
    rows, as_of = _fmv_inventory_slice_rows(
        session, owner_user_id=owner_user_id, predicate=_pred, columns=cols
    )
    return rows, as_of


def market_low_confidence_fmv_inventory_export_rows(
    session: Session,
    *,
    owner_user_id: int | None,
) -> tuple[list[dict[str, Any]], date]:
    low_buckets = frozenset({"low", "very_low"})

    def _pred(att, row):
        del row
        if att.valuation_scope == "low_confidence":
            return True
        if att.current_market_fmv is None:
            return False
        return att.fmv_confidence_bucket in low_buckets

    cols = FMV_QUALITY_OWNER_COLUMNS if owner_user_id is not None else FMV_QUALITY_OPS_COLUMNS
    return _fmv_inventory_slice_rows(
        session, owner_user_id=owner_user_id, predicate=_pred, columns=cols
    )


def market_stale_fmv_inventory_export_rows(
    session: Session, *, owner_user_id: int | None
) -> tuple[list[dict[str, Any]], date]:
    def _pred(att, row):
        del row
        return bool(att.fmv_stale_data) and att.current_market_fmv is not None

    cols = FMV_QUALITY_OWNER_COLUMNS if owner_user_id is not None else FMV_QUALITY_OPS_COLUMNS
    return _fmv_inventory_slice_rows(
        session, owner_user_id=owner_user_id, predicate=_pred, columns=cols
    )


def normalization_issues_aggregate_export_rows(
    session: Session,
) -> tuple[list[dict[str, Any]], date]:
    grouped = session.exec(
        select(
            MarketSaleNormalizationIssue.issue_type,
            MarketSaleNormalizationIssue.severity,
            func.count(MarketSaleNormalizationIssue.id),
        ).group_by(MarketSaleNormalizationIssue.issue_type, MarketSaleNormalizationIssue.severity)
    ).all()
    rows = [
        {
            "issue_type": str(it),
            "severity": str(sev),
            "issue_row_count": int(cnt or 0),
        }
        for it, sev, cnt in sorted(grouped, key=lambda triple: (str(triple[0]), str(triple[1])))
    ]
    return rows, date.today()


def boundary_disclaimers() -> dict[str, str]:
    return {
        "no_forecasting": (
            "Trend and FMV snapshots are descriptive over fixed observation windows only; "
            "they are not predictive."
        ),
        "no_buy_or_sell": (
            "ComicOS does not compute or surface buy/hold/sell recommendations from market data."
        ),
        "no_grading_recommendations": (
            "Eligibility signals never recommend submit-to-grade or crossover actions."
        ),
        "no_speculation_scoring": (
            "There is no numeric speculation upside/downside ranking "
            "beyond deterministic quality buckets."
        ),
    }


def market_deterministic_summary_document(
    session: Session,
    *,
    owner_user_id: int | None,
    publisher: str | None,
    ownership_state: str | None,
) -> dict[str, Any]:
    """Deterministic structured JSON snapshot for market/FMV dashboards."""

    portfolio = portfolio_value_summary_for_scope(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        ownership_state=ownership_state,
    )
    row_maps, attachments, _duplicate = inventory_fmv_context_for_scope(
        session, owner_user_id=owner_user_id, include_detail=False
    )

    coverage: Counter[str] = Counter()
    confidence: Counter[str] = Counter()
    stale_attach = 0
    low_bucket_rows = 0

    owner_lookup = (
        None
        if owner_user_id is not None
        else _inventory_owner_map(session, [int(r["inventory_copy_id"]) for r in row_maps])
    )

    for row in sorted(row_maps, key=lambda r: int(r["inventory_copy_id"])):
        if publisher is not None and row["publisher"] != publisher:
            continue
        if ownership_state is not None and row["ownership_state"] != ownership_state:
            continue
        att = attachments[int(row["inventory_copy_id"])]
        coverage[str(att.valuation_scope)] += 1
        bucket = att.fmv_confidence_bucket or "unspecified"
        confidence[str(bucket)] += 1
        if bool(att.fmv_stale_data) and att.current_market_fmv is not None:
            stale_attach += 1
        if att.fmv_confidence_bucket in {"low", "very_low"} and att.current_market_fmv is not None:
            low_bucket_rows += 1

    comp_list = list_market_comp_eligibility(session)
    trend_response = list_market_trends(session)
    trend_dir = dict(sorted((str(k), int(v)) for k, v in trend_response.by_trend_direction.items()))
    grouped_issues = normalization_issues_aggregate_export_rows(session)[0]

    trace_rows_full = sorted(row_maps, key=lambda r: int(r["inventory_copy_id"]))
    fmv_snapshot_traceability_sample: list[dict[str, Any]] = []
    for row in trace_rows_full:
        if publisher is not None and row["publisher"] != publisher:
            continue
        if ownership_state is not None and row["ownership_state"] != ownership_state:
            continue
        inv_id = int(row["inventory_copy_id"])
        att = attachments[inv_id]
        evid = att.valuation_evidence_json or {}
        snap_id = att.fmv_snapshot_id
        fmv_snapshot_traceability_sample.append(
            {
                "inventory_copy_id": inv_id,
                "owner_user_id": int(owner_lookup[inv_id]) if owner_lookup else None,
                "fmv_snapshot_id": snap_id,
                "evidence_market_fmv_snapshot_id": evid.get("market_fmv_snapshot_id"),
                "evidence_market_trend_snapshot_id": evid.get("market_trend_snapshot_id"),
                "match_reason": evid.get("match_reason"),
            }
        )
    fmv_snapshot_traceability_sample = fmv_snapshot_traceability_sample[:120]

    return {
        "boundary_disclaimers": boundary_disclaimers(),
        "coverage_by_valuation_scope": dict(sorted(coverage.items())),
        "eligible_comps_by_status": dict(
            sorted((str(k), int(v)) for k, v in comp_list.by_eligibility_status.items()),
        ),
        "fmv_confidence_bucket_counts": dict(sorted(confidence.items())),
        "fmv_low_confidence_bucket_rows": low_bucket_rows,
        "fmv_snapshot_traceability_sample": fmv_snapshot_traceability_sample,
        "fmv_stale_attachment_rows": stale_attach,
        "generated_as_of_date": portfolio.generated_as_of_date.isoformat(),
        "normalization_issues_by_type_severity": grouped_issues,
        "portfolio_currency_rows": [
            dict(sorted(row.items())) for row in portfolio.model_dump(mode="json")["items"]
        ],
        "scope": portfolio.scope,
        "scope_filter": {"ownership_state": ownership_state, "publisher": publisher},
        "scope_user_id": portfolio.scope_user_id,
        "market_trends_by_direction": trend_dir,
        "market_trends_stale_count": int(trend_response.stale_count),
        "market_trends_total": int(trend_response.total),
    }


def dumps_market_deterministic_summary_bytes(
    session: Session,
    *,
    owner_user_id: int | None,
    publisher: str | None,
    ownership_state: str | None,
) -> bytes:
    doc = market_deterministic_summary_document(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        ownership_state=ownership_state,
    )
    envelope = dict(doc)
    envelope["report_schema"] = "comic-os.reports.market_deterministic_summary.v1"
    return dumps_report_json(envelope)


def render_market_sales_csv(
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
) -> str:
    rows, _ = market_sales_export_rows(
        session,
        source=source,
        publisher=publisher,
        normalized_title=normalized_title,
        normalized_issue=normalized_issue,
        grading_company=grading_company,
        is_graded=is_graded,
        normalization_status=normalization_status,
        sale_date_from=sale_date_from,
        sale_date_to=sale_date_to,
    )
    return render_csv(MARKET_SALES_EXPORT_COLUMNS, rows)


def render_market_eligible_comps_csv(session: Session) -> str:
    rows, _ = market_eligible_comps_export_rows(session)
    return render_csv(MARKET_ELIGIBLE_COMPS_EXPORT_COLUMNS, rows)


def render_market_fmv_snapshots_csv(session: Session) -> str:
    rows, _ = market_fmv_snapshot_export_rows(session)
    return render_csv(MARKET_FMV_SNAPSHOT_EXPORT_COLUMNS, rows)


def render_market_trends_csv(session: Session) -> str:
    rows, _ = market_trend_export_rows(session)
    return render_csv(MARKET_TREND_EXPORT_COLUMNS, rows)


def render_normalization_issues_summary_csv(session: Session) -> str:
    rows, _ = normalization_issues_aggregate_export_rows(session)
    return render_csv(NORMALIZATION_ISSUES_EXPORT_COLUMNS, rows)


def render_portfolio_value_summary_csv(
    session: Session,
    *,
    owner_user_id: int | None,
    publisher: str | None,
    ownership_state: str | None,
) -> str:
    rows, _ = portfolio_value_export_rows(
        session,
        owner_user_id=owner_user_id,
        publisher=publisher,
        ownership_state=ownership_state,
    )
    return render_csv(PORTFOLIO_VALUE_EXPORT_COLUMNS, rows)


def render_no_market_data_inventory_csv(session: Session, *, owner_user_id: int | None) -> str:
    rows, _ = market_no_market_data_inventory_export_rows(session, owner_user_id=owner_user_id)
    cols = NO_MARKET_DATA_OWNER_COLUMNS if owner_user_id is not None else NO_MARKET_DATA_OPS_COLUMNS
    return render_csv(cols, rows)


def render_low_confidence_inventory_csv(session: Session, *, owner_user_id: int | None) -> str:
    rows, _ = market_low_confidence_fmv_inventory_export_rows(session, owner_user_id=owner_user_id)
    cols = FMV_QUALITY_OWNER_COLUMNS if owner_user_id is not None else FMV_QUALITY_OPS_COLUMNS
    return render_csv(cols, rows)


def render_stale_fmv_inventory_csv(session: Session, *, owner_user_id: int | None) -> str:
    rows, _ = market_stale_fmv_inventory_export_rows(session, owner_user_id=owner_user_id)
    cols = FMV_QUALITY_OWNER_COLUMNS if owner_user_id is not None else FMV_QUALITY_OPS_COLUMNS
    return render_csv(cols, rows)


def dumps_no_market_data_inventory_json(
    session: Session,
    *,
    owner_user_id: int | None,
) -> bytes:
    rows, as_of = market_no_market_data_inventory_export_rows(session, owner_user_id=owner_user_id)
    cols = list(
        NO_MARKET_DATA_OWNER_COLUMNS if owner_user_id is not None else NO_MARKET_DATA_OPS_COLUMNS
    )
    payload = {
        "columns": cols,
        "generated_as_of_date": as_of.isoformat(),
        "report_schema": "comic-os.reports.inventory_no_market_data.v1",
        "rows": rows,
        "scope": "owner" if owner_user_id is not None else "ops",
        "scope_user_id": owner_user_id,
    }
    return dumps_report_json(payload)
