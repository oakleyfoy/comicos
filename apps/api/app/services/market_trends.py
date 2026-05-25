from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlmodel import Session, delete, select

from app.models import (
    MarketFmvCompReference,
    MarketFmvSnapshot,
    MarketSaleRecord,
    MarketSource,
    MarketTrendEvidence,
    MarketTrendSnapshot,
)
from app.schemas.market_fmv import MarketFmvSnapshotSummaryRead
from app.schemas.market_sales import MarketSaleSummaryRead
from app.schemas.market_trends import (
    MarketTrendDirection,
    MarketTrendEvidenceRead,
    MarketTrendGenerateResponse,
    MarketTrendLiquidityDirection,
    MarketTrendSnapshotListResponse,
    MarketTrendSnapshotRead,
    MarketTrendSnapshotScope,
    MarketTrendSnapshotSummaryRead,
    MarketTrendStrength,
    MarketTrendWindow,
)
from app.services.market_sales import _market_sale_summary

SNAPSHOT_VERSION = "market-trend-v1"
WINDOW_DAYS: dict[MarketTrendWindow, int] = {
    "seven_day": 7,
    "thirty_day": 30,
    "ninety_day": 90,
    "one_year": 365,
}
_SCOPE_RANK: dict[MarketTrendSnapshotScope, int] = {
    "raw": 0,
    "graded": 1,
    "graded_by_company": 2,
    "graded_by_grade": 3,
}
_WINDOW_RANK: dict[MarketTrendWindow, int] = {
    "seven_day": 0,
    "thirty_day": 1,
    "ninety_day": 2,
    "one_year": 3,
}
_DIRECTION_RANK: dict[MarketTrendDirection, int] = {
    "rising": 0,
    "stable": 1,
    "falling": 2,
    "volatile": 3,
}
_STRENGTH_RANK: dict[MarketTrendStrength, int] = {
    "very_high": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
    "very_low": 4,
}
_LIQUIDITY_RANK: dict[MarketTrendLiquidityDirection, int] = {
    "improving": 0,
    "stable": 1,
    "weakening": 2,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _quantize_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantize_score(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / Decimal("2")


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


@dataclass(frozen=True)
class _TrendKey:
    canonical_issue_id: int | None
    metadata_identity_key: str | None
    snapshot_scope: MarketTrendSnapshotScope
    grading_company: str | None
    normalized_grade: str | None
    currency_code: str


@dataclass(frozen=True)
class _DailyTrendPoint:
    snapshot_date: date
    median_value: Decimal | None
    weighted_value: Decimal | None
    representative_value: Decimal
    median_snapshot_id: int | None
    weighted_snapshot_id: int | None
    comp_count: int
    snapshot_ids: list[int]


@dataclass(frozen=True)
class _TrendAnalysis:
    key: _TrendKey
    trend_window: MarketTrendWindow
    window_days: int
    snapshots: list[MarketFmvSnapshot]
    daily_points: list[_DailyTrendPoint]
    comp_count: int
    percent_change: Decimal
    volatility_score: float
    trend_direction: MarketTrendDirection
    trend_strength: MarketTrendStrength
    liquidity_direction: MarketTrendLiquidityDirection
    stale_data: bool
    evidence_json: dict
    comp_sale_ids: list[int]


def _market_source_or_404(session: Session, *, market_source_id: int) -> MarketSource:
    source = session.get(MarketSource, market_source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Market source not found")
    return source


def _trend_key_for_snapshot(row: MarketFmvSnapshot) -> _TrendKey:
    return _TrendKey(
        canonical_issue_id=row.canonical_issue_id,
        metadata_identity_key=_trim(row.metadata_identity_key),
        snapshot_scope=row.snapshot_scope,  # type: ignore[arg-type]
        grading_company=_trim(row.grading_company),
        normalized_grade=_trim(row.normalized_grade),
        currency_code=row.currency_code.upper(),
    )


def _snapshot_summary_read(row: MarketTrendSnapshot) -> MarketTrendSnapshotSummaryRead:
    return MarketTrendSnapshotSummaryRead.model_validate(row, from_attributes=True)


def _load_snapshot(session: Session, *, snapshot_id: int) -> MarketTrendSnapshot:
    row = session.get(MarketTrendSnapshot, snapshot_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market trend snapshot not found")
    return row


def _load_evidence(session: Session, *, snapshot_id: int) -> list[MarketTrendEvidence]:
    return session.exec(
        select(MarketTrendEvidence)
        .where(MarketTrendEvidence.market_trend_snapshot_id == snapshot_id)
        .order_by(
            MarketTrendEvidence.evidence_type.asc(),
            MarketTrendEvidence.market_sale_record_id.asc(),
            MarketTrendEvidence.market_fmv_snapshot_id.asc(),
            MarketTrendEvidence.id.asc(),
        )
    ).all()


def _snapshot_read(session: Session, row: MarketTrendSnapshot) -> MarketTrendSnapshotRead:
    evidence_rows = _load_evidence(session, snapshot_id=int(row.id or 0))
    return MarketTrendSnapshotRead(
        **_snapshot_summary_read(row).model_dump(),
        evidence_items=[_evidence_read(session, evidence_row) for evidence_row in evidence_rows],
    )


def _evidence_read(session: Session, row: MarketTrendEvidence) -> MarketTrendEvidenceRead:
    sale_summary: MarketSaleSummaryRead | None = None
    snapshot_summary: MarketFmvSnapshotSummaryRead | None = None
    if row.market_sale_record_id is not None:
        sale = session.get(MarketSaleRecord, row.market_sale_record_id)
        if sale is not None:
            source = _market_source_or_404(session, market_source_id=sale.market_source_id)
            sale_summary = _market_sale_summary(
                record=sale,
                source=source,
                issue_count=0,
            )
    if row.market_fmv_snapshot_id is not None:
        snapshot = session.get(MarketFmvSnapshot, row.market_fmv_snapshot_id)
        if snapshot is not None:
            snapshot_summary = MarketFmvSnapshotSummaryRead.model_validate(snapshot, from_attributes=True)
    return MarketTrendEvidenceRead(
        id=int(row.id or 0),
        market_trend_snapshot_id=row.market_trend_snapshot_id,
        market_sale_record_id=row.market_sale_record_id,
        market_fmv_snapshot_id=row.market_fmv_snapshot_id,
        evidence_type=row.evidence_type,  # type: ignore[arg-type]
        evidence_json=dict(row.evidence_json or {}),
        created_at=row.created_at,
        market_sale_record=sale_summary,
        market_fmv_snapshot=snapshot_summary,
    )


def _group_fmv_snapshots_by_day(snapshots: list[MarketFmvSnapshot]) -> list[_DailyTrendPoint]:
    points: list[_DailyTrendPoint] = []
    by_date: defaultdict[date, list[MarketFmvSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        by_date[snapshot.snapshot_date].append(snapshot)

    for snapshot_date in sorted(by_date):
        rows = sorted(
            by_date[snapshot_date],
            key=lambda row: (
                0 if row.valuation_method == "weighted_recent_sales" else 1,
                0 if row.valuation_method == "median_recent_sales" else 1,
                row.id or 0,
            ),
        )
        median_row = next((row for row in rows if row.valuation_method == "median_recent_sales"), None)
        weighted_row = next((row for row in rows if row.valuation_method == "weighted_recent_sales"), None)
        if weighted_row is not None:
            representative_row = weighted_row
            representative_value = Decimal(weighted_row.estimated_fmv)
        elif median_row is not None:
            representative_row = median_row
            representative_value = Decimal(median_row.estimated_fmv)
        else:
            representative_row = rows[0]
            representative_value = Decimal(representative_row.estimated_fmv)
        comp_count = sum(int(row.comp_count) for row in rows)
        points.append(
            _DailyTrendPoint(
                snapshot_date=snapshot_date,
                median_value=Decimal(median_row.estimated_fmv) if median_row is not None else None,
                weighted_value=Decimal(weighted_row.estimated_fmv) if weighted_row is not None else None,
                representative_value=representative_value,
                median_snapshot_id=median_row.id if median_row is not None else None,
                weighted_snapshot_id=weighted_row.id if weighted_row is not None else None,
                comp_count=comp_count,
                snapshot_ids=[int(row.id or 0) for row in rows],
            )
        )
    return points


def _window_snapshots_for_key(
    snapshots: list[MarketFmvSnapshot],
    *,
    window_days: int,
    today: date,
) -> tuple[list[MarketFmvSnapshot], bool]:
    cutoff = today - timedelta(days=window_days - 1)
    in_window = [row for row in snapshots if row.snapshot_date >= cutoff]
    if in_window:
        return in_window, False
    recent = sorted(snapshots, key=lambda row: (row.snapshot_date, row.id or 0))
    if not recent:
        return [], True
    return recent[-2:] if len(recent) >= 2 else recent, True


def _volatility_score(points: list[_DailyTrendPoint], *, comp_sale_ids: list[int]) -> tuple[float, Decimal, Decimal, int]:
    if len(points) <= 1:
        return 0.0, Decimal("0"), Decimal("0"), 0
    representative_values = [point.representative_value for point in points]
    low = min(representative_values)
    high = max(representative_values)
    spread_pct = Decimal("0")
    if low > 0:
        spread_pct = _quantize_percent(((high - low) / low) * Decimal("100"))

    divergence_pcts: list[Decimal] = []
    for point in points:
        if point.weighted_value is not None and point.median_value is not None and point.median_value > 0:
            divergence_pcts.append(
                _quantize_percent((abs(point.weighted_value - point.median_value) / point.median_value) * Decimal("100"))
            )
    avg_divergence = _mean(divergence_pcts) if divergence_pcts else Decimal("0")

    deltas = [points[index].representative_value - points[index - 1].representative_value for index in range(1, len(points))]
    directional_flips = 0
    previous_sign = 0
    for delta in deltas:
        sign = _sign(delta)
        if sign == 0:
            continue
        if previous_sign != 0 and sign != previous_sign:
            directional_flips += 1
        previous_sign = sign

    cadence_penalty = Decimal("0")
    if len(comp_sale_ids) <= 1:
        cadence_penalty = Decimal("12")
    elif len(comp_sale_ids) < len(points):
        cadence_penalty = Decimal("6")
    score = (
        min(spread_pct, Decimal("100")) * Decimal("0.48")
        + min(avg_divergence, Decimal("100")) * Decimal("0.32")
        + Decimal(min(directional_flips * 14, 28))
        + cadence_penalty
    )
    return _quantize_score(float(score)), spread_pct, _quantize_percent(avg_divergence), directional_flips


def _trend_direction(
    *,
    percent_change: Decimal,
    volatility_score: float,
    spread_pct: Decimal,
    directional_flips: int,
    points: list[_DailyTrendPoint],
) -> MarketTrendDirection:
    if len(points) <= 1:
        return "stable"
    if volatility_score >= 60 or directional_flips >= 2 or spread_pct >= Decimal("35"):
        return "volatile"
    if percent_change >= Decimal("5"):
        return "rising"
    if percent_change <= Decimal("-5"):
        return "falling"
    return "stable"


def _trend_strength(percent_change: Decimal, volatility_score: float, stale_data: bool) -> MarketTrendStrength:
    magnitude = abs(percent_change)
    if stale_data:
        if magnitude >= Decimal("15"):
            return "low"
        return "very_low"
    if magnitude >= Decimal("30") and volatility_score < 40:
        return "very_high"
    if magnitude >= Decimal("20") and volatility_score < 55:
        return "high"
    if magnitude >= Decimal("10"):
        return "medium"
    if magnitude >= Decimal("3"):
        return "low"
    return "very_low"


def _liquidity_direction(
    *,
    comp_sale_dates: list[date],
    window_days: int,
    stale_data: bool,
) -> MarketTrendLiquidityDirection:
    if len(comp_sale_dates) <= 1:
        return "stable"
    if stale_data:
        return "weakening"
    comp_sale_dates = sorted(set(comp_sale_dates))
    range_days = max((comp_sale_dates[-1] - comp_sale_dates[0]).days, 1)
    midpoint = comp_sale_dates[0] + timedelta(days=max(range_days // 2, 1))
    early_count = sum(1 for sale_date in comp_sale_dates if sale_date < midpoint)
    late_count = sum(1 for sale_date in comp_sale_dates if sale_date >= midpoint)
    gaps = [(comp_sale_dates[index] - comp_sale_dates[index - 1]).days for index in range(1, len(comp_sale_dates))]
    avg_gap = sum(gaps) / len(gaps) if gaps else float(window_days)
    if late_count >= max(early_count + 1, int(early_count * 1.2)) and avg_gap <= range_days / 4:
        return "improving"
    if early_count >= max(late_count + 1, int(late_count * 1.2)) and avg_gap >= range_days / 5:
        return "weakening"
    return "stable"


def _analysis_for_key(
    *,
    key: _TrendKey,
    snapshots: list[MarketFmvSnapshot],
    trend_window: MarketTrendWindow,
    today: date,
    refs_by_snapshot_id: dict[int, list[MarketFmvCompReference]],
    sale_by_id: dict[int, MarketSaleRecord],
) -> _TrendAnalysis | None:
    window_days = WINDOW_DAYS[trend_window]
    analysis_snapshots, stale_data = _window_snapshots_for_key(snapshots, window_days=window_days, today=today)
    if not analysis_snapshots:
        return None
    daily_points = _group_fmv_snapshots_by_day(analysis_snapshots)
    if not daily_points:
        return None

    first_value = daily_points[0].representative_value
    last_value = daily_points[-1].representative_value
    percent_change = Decimal("0")
    if first_value > 0:
        percent_change = _quantize_percent(((last_value - first_value) / first_value) * Decimal("100"))

    comp_sale_ids: list[int] = []
    comp_sale_dates: list[date] = []
    latest_snapshot_date = max(point.snapshot_date for point in daily_points)
    for snapshot in analysis_snapshots:
        refs = refs_by_snapshot_id.get(int(snapshot.id or 0), [])
        for ref in refs:
            if ref.excluded_reason is not None:
                continue
            sale_id = int(ref.market_sale_record_id)
            if sale_id not in comp_sale_ids:
                comp_sale_ids.append(sale_id)
            sale = sale_by_id.get(sale_id)
            if sale is not None and sale.sale_date is not None:
                comp_sale_dates.append(sale.sale_date)

    volatility_score, spread_pct, avg_divergence_pct, directional_flips = _volatility_score(daily_points, comp_sale_ids=comp_sale_ids)
    liquidity_direction = _liquidity_direction(
        comp_sale_dates=comp_sale_dates,
        window_days=window_days,
        stale_data=stale_data,
    )
    trend_direction = _trend_direction(
        percent_change=percent_change,
        volatility_score=volatility_score,
        spread_pct=spread_pct,
        directional_flips=directional_flips,
        points=daily_points,
    )
    trend_strength = _trend_strength(percent_change, volatility_score, stale_data)

    evidence_json = {
        "trend_version": SNAPSHOT_VERSION,
        "analysis_date": today.isoformat(),
        "window_days": window_days,
        "window_cutoff": (today - timedelta(days=window_days - 1)).isoformat(),
        "snapshot_ids": [int(snapshot.id or 0) for snapshot in analysis_snapshots],
        "snapshot_dates": [snapshot.snapshot_date.isoformat() for snapshot in analysis_snapshots],
        "daily_points": [
            {
                "snapshot_date": point.snapshot_date.isoformat(),
                "representative_value": str(point.representative_value),
                "median_value": str(point.median_value) if point.median_value is not None else None,
                "weighted_value": str(point.weighted_value) if point.weighted_value is not None else None,
                "snapshot_ids": point.snapshot_ids,
                "comp_count": point.comp_count,
            }
            for point in daily_points
        ],
        "first_value": str(first_value),
        "last_value": str(last_value),
        "percent_change": str(percent_change),
        "price_spread_pct": str(spread_pct),
        "weighted_median_divergence_pct": str(avg_divergence_pct),
        "directional_flips": directional_flips,
        "comp_sale_ids": comp_sale_ids,
        "comp_count": len(comp_sale_ids),
        "liquidity_direction": liquidity_direction,
        "trend_direction": trend_direction,
        "trend_strength": trend_strength,
        "volatility_score": volatility_score,
        "stale_data": stale_data,
        "latest_snapshot_date": latest_snapshot_date.isoformat(),
    }

    return _TrendAnalysis(
        key=key,
        trend_window=trend_window,
        window_days=window_days,
        snapshots=analysis_snapshots,
        daily_points=daily_points,
        comp_count=len(comp_sale_ids),
        percent_change=percent_change,
        volatility_score=volatility_score,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        liquidity_direction=liquidity_direction,
        stale_data=stale_data,
        evidence_json=evidence_json,
        comp_sale_ids=comp_sale_ids,
    )


def _window_evidence_rows(
    *,
    analysis: _TrendAnalysis,
    refs_by_snapshot_id: dict[int, list[MarketFmvCompReference]],
    sale_by_id: dict[int, MarketSaleRecord],
    market_trend_snapshot_id: int,
) -> list[MarketTrendEvidence]:
    now = utc_now()
    rows: list[MarketTrendEvidence] = []

    for snapshot in analysis.snapshots:
        rows.append(
            MarketTrendEvidence(
                market_trend_snapshot_id=market_trend_snapshot_id,
                market_sale_record_id=None,
                market_fmv_snapshot_id=int(snapshot.id or 0),
                evidence_type="fmv_snapshot",
                evidence_json={
                    "snapshot_id": int(snapshot.id or 0),
                    "snapshot_date": snapshot.snapshot_date.isoformat(),
                    "valuation_method": snapshot.valuation_method,
                    "estimated_fmv": str(snapshot.estimated_fmv),
                    "comp_count": snapshot.comp_count,
                    "stale_data": bool(snapshot.stale_data),
                    "currency_code": snapshot.currency_code,
                },
                created_at=now,
            )
        )

    comp_details: dict[int, dict[str, object]] = {}
    for snapshot in analysis.snapshots:
        for ref in refs_by_snapshot_id.get(int(snapshot.id or 0), []):
            if ref.excluded_reason is not None:
                continue
            sale_id = int(ref.market_sale_record_id)
            detail = comp_details.setdefault(
                sale_id,
                {
                    "snapshot_ids": [],
                    "appearance_count": 0,
                    "latest_snapshot_id": int(snapshot.id or 0),
                    "latest_sale_date": None,
                    "latest_sale_price": None,
                },
            )
            detail["appearance_count"] = int(detail["appearance_count"]) + 1
            snapshot_ids = list(detail["snapshot_ids"])  # type: ignore[list-item]
            snapshot_ids.append(int(snapshot.id or 0))
            detail["snapshot_ids"] = sorted(set(snapshot_ids))
            detail["latest_snapshot_id"] = int(snapshot.id or 0)
            sale = sale_by_id.get(sale_id)
            if sale is not None:
                if sale.sale_date is not None:
                    detail["latest_sale_date"] = sale.sale_date.isoformat()
                price = sale.total_price if sale.total_price is not None else sale.sale_price
                if price is not None:
                    detail["latest_sale_price"] = str(price)

    for sale_id in sorted(comp_details):
        sale = sale_by_id.get(sale_id)
        if sale is None:
            continue
        rows.append(
            MarketTrendEvidence(
                market_trend_snapshot_id=market_trend_snapshot_id,
                market_sale_record_id=sale_id,
                market_fmv_snapshot_id=int(comp_details[sale_id]["latest_snapshot_id"]),
                evidence_type="comp_reference",
                evidence_json={
                    "sale_id": sale_id,
                    "snapshot_ids": comp_details[sale_id]["snapshot_ids"],
                    "appearance_count": comp_details[sale_id]["appearance_count"],
                    "latest_sale_date": comp_details[sale_id]["latest_sale_date"],
                    "latest_sale_price": comp_details[sale_id]["latest_sale_price"],
                    "currency_code": sale.currency_code,
                },
                created_at=now,
            )
        )

    rows.append(
        MarketTrendEvidence(
            market_trend_snapshot_id=market_trend_snapshot_id,
            market_sale_record_id=None,
            market_fmv_snapshot_id=int(analysis.snapshots[-1].id or 0),
            evidence_type="liquidity_signal",
            evidence_json={
                "liquidity_direction": analysis.liquidity_direction,
                "comp_count": analysis.comp_count,
                "window_days": analysis.window_days,
                "sale_count": len(analysis.comp_sale_ids),
                "sale_ids": analysis.comp_sale_ids,
                "stale_data": analysis.stale_data,
            },
            created_at=now,
        )
    )
    rows.append(
        MarketTrendEvidence(
            market_trend_snapshot_id=market_trend_snapshot_id,
            market_sale_record_id=None,
            market_fmv_snapshot_id=int(analysis.snapshots[-1].id or 0),
            evidence_type="volatility_signal",
            evidence_json={
                "trend_direction": analysis.trend_direction,
                "trend_strength": analysis.trend_strength,
                "volatility_score": analysis.volatility_score,
                "percent_change": str(analysis.percent_change),
                "stale_data": analysis.stale_data,
            },
            created_at=now,
        )
    )
    return rows


def _build_list_response(rows: list[MarketTrendSnapshot]) -> MarketTrendSnapshotListResponse:
    summaries = [_snapshot_summary_read(row) for row in rows]
    summaries.sort(
        key=lambda row: (
            _WINDOW_RANK.get(row.trend_window, 99),
            -row.created_at.timestamp(),
            _SCOPE_RANK.get(row.snapshot_scope, 99),
            _DIRECTION_RANK.get(row.trend_direction, 99),
            _STRENGTH_RANK.get(row.trend_strength, 99),
            _LIQUIDITY_RANK.get(row.liquidity_direction, 99),
            row.id,
        )
    )
    by_direction = Counter(row.trend_direction for row in summaries)
    by_strength = Counter(row.trend_strength for row in summaries)
    by_liquidity = Counter(row.liquidity_direction for row in summaries)
    return MarketTrendSnapshotListResponse(
        items=summaries,
        total=len(summaries),
        by_trend_direction={key: int(value) for key, value in by_direction.items()},
        by_trend_strength={key: int(value) for key, value in by_strength.items()},
        by_liquidity_direction={key: int(value) for key, value in by_liquidity.items()},
        stale_count=sum(1 for row in summaries if row.stale_data),
    )


def _base_list_query(session: Session) -> list[MarketTrendSnapshot]:
    return session.exec(select(MarketTrendSnapshot)).all()


def _filter_rows(
    rows: list[MarketTrendSnapshot],
    *,
    snapshot_scope: MarketTrendSnapshotScope | None = None,
    grading_company: str | None = None,
    normalized_grade: str | None = None,
    trend_direction: MarketTrendDirection | None = None,
    trend_strength: MarketTrendStrength | None = None,
    liquidity_direction: MarketTrendLiquidityDirection | None = None,
    stale_data: bool | None = None,
    currency: str | None = None,
    trend_window: MarketTrendWindow | None = None,
    metadata_identity_key: str | None = None,
) -> list[MarketTrendSnapshot]:
    filtered: list[MarketTrendSnapshot] = []
    for row in rows:
        if snapshot_scope is not None and row.snapshot_scope != snapshot_scope:
            continue
        if grading_company is not None and _trim(row.grading_company or "") != _trim(grading_company):
            continue
        if normalized_grade is not None and _trim(row.normalized_grade or "") != _trim(normalized_grade):
            continue
        if trend_direction is not None and row.trend_direction != trend_direction:
            continue
        if trend_strength is not None and row.trend_strength != trend_strength:
            continue
        if liquidity_direction is not None and row.liquidity_direction != liquidity_direction:
            continue
        if stale_data is not None and bool(row.stale_data) != stale_data:
            continue
        if currency is not None and row.currency_code.upper() != currency.strip().upper():
            continue
        if trend_window is not None and row.trend_window != trend_window:
            continue
        if metadata_identity_key is not None and row.metadata_identity_key != metadata_identity_key:
            continue
        filtered.append(row)
    return filtered


def _trend_rows_by_signature(session: Session) -> dict[_TrendKey, list[MarketFmvSnapshot]]:
    rows = session.exec(
        select(MarketFmvSnapshot).order_by(
            MarketFmvSnapshot.canonical_issue_id.asc().nullsfirst(),
            MarketFmvSnapshot.metadata_identity_key.asc().nullsfirst(),
            MarketFmvSnapshot.snapshot_scope.asc(),
            MarketFmvSnapshot.grading_company.asc().nullsfirst(),
            MarketFmvSnapshot.normalized_grade.asc().nullsfirst(),
            MarketFmvSnapshot.currency_code.asc(),
            MarketFmvSnapshot.snapshot_date.asc(),
            MarketFmvSnapshot.valuation_method.asc(),
            MarketFmvSnapshot.id.asc(),
        )
    ).all()
    grouped: defaultdict[_TrendKey, list[MarketFmvSnapshot]] = defaultdict(list)
    for row in rows:
        grouped[_trend_key_for_snapshot(row)].append(row)
    return grouped


def _refs_and_sales_index(
    session: Session,
    snapshots: list[MarketFmvSnapshot],
) -> tuple[dict[int, list[MarketFmvCompReference]], dict[int, MarketSaleRecord]]:
    snapshot_ids = [int(snapshot.id or 0) for snapshot in snapshots if snapshot.id is not None]
    refs_by_snapshot_id: dict[int, list[MarketFmvCompReference]] = defaultdict(list)
    sale_ids: set[int] = set()
    if snapshot_ids:
        refs = session.exec(
            select(MarketFmvCompReference)
            .where(MarketFmvCompReference.market_fmv_snapshot_id.in_(snapshot_ids))
            .order_by(
                MarketFmvCompReference.market_fmv_snapshot_id.asc(),
                MarketFmvCompReference.excluded_reason.asc(),
                MarketFmvCompReference.weighting_factor.desc(),
                MarketFmvCompReference.market_sale_record_id.asc(),
                MarketFmvCompReference.id.asc(),
            )
        ).all()
        for ref in refs:
            refs_by_snapshot_id[int(ref.market_fmv_snapshot_id)].append(ref)
            sale_ids.add(int(ref.market_sale_record_id))
    sale_by_id: dict[int, MarketSaleRecord] = {}
    if sale_ids:
        sale_rows = session.exec(select(MarketSaleRecord).where(MarketSaleRecord.id.in_(sorted(sale_ids)))).all()
        sale_by_id = {int(row.id or 0): row for row in sale_rows if row.id is not None}
    return refs_by_snapshot_id, sale_by_id


def generate_market_trend_snapshots(session: Session) -> MarketTrendGenerateResponse:
    grouped = _trend_rows_by_signature(session)
    today = date.today()
    touched_rows: list[MarketTrendSnapshot] = []
    all_analysis_snapshots: list[MarketFmvSnapshot] = []
    for rows in grouped.values():
        all_analysis_snapshots.extend(rows)
    refs_by_snapshot_id, sale_by_id = _refs_and_sales_index(session, all_analysis_snapshots)

    existing_rows = session.exec(select(MarketTrendSnapshot)).all()
    now = utc_now()
    for key, rows in grouped.items():
        for trend_window in ("seven_day", "thirty_day", "ninety_day", "one_year"):
            analysis = _analysis_for_key(
                key=key,
                snapshots=rows,
                trend_window=trend_window,  # type: ignore[arg-type]
                today=today,
                refs_by_snapshot_id=refs_by_snapshot_id,
                sale_by_id=sale_by_id,
            )
            if analysis is None:
                continue
            row = next(
                (
                    candidate
                    for candidate in existing_rows
                    if candidate.canonical_issue_id == key.canonical_issue_id
                    and candidate.metadata_identity_key == key.metadata_identity_key
                    and candidate.snapshot_scope == key.snapshot_scope
                    and candidate.grading_company == key.grading_company
                    and candidate.normalized_grade == key.normalized_grade
                    and candidate.currency_code == key.currency_code
                    and candidate.trend_window == trend_window
                ),
                None,
            )
            if row is None:
                row = MarketTrendSnapshot(
                    canonical_issue_id=key.canonical_issue_id,
                    metadata_identity_key=key.metadata_identity_key,
                    snapshot_scope=key.snapshot_scope,
                    grading_company=key.grading_company,
                    normalized_grade=key.normalized_grade,
                    currency_code=key.currency_code,
                    trend_window=trend_window,
                    created_at=now,
                )
                existing_rows.append(row)
            row.trend_direction = analysis.trend_direction
            row.trend_strength = analysis.trend_strength
            row.liquidity_direction = analysis.liquidity_direction
            row.comp_count = analysis.comp_count
            row.percent_change = analysis.percent_change
            row.volatility_score = analysis.volatility_score
            row.stale_data = analysis.stale_data
            row.evidence_json = analysis.evidence_json
            row.updated_at = now
            session.add(row)
            session.flush()

            session.exec(delete(MarketTrendEvidence).where(MarketTrendEvidence.market_trend_snapshot_id == int(row.id or 0)))
            evidence_rows = _window_evidence_rows(
                analysis=analysis,
                refs_by_snapshot_id=refs_by_snapshot_id,
                sale_by_id=sale_by_id,
                market_trend_snapshot_id=int(row.id or 0),
            )
            for evidence_row in evidence_rows:
                session.add(evidence_row)
            touched_rows.append(row)

    session.commit()
    summaries = [_snapshot_summary_read(row) for row in touched_rows]
    summaries.sort(
        key=lambda row: (
            _WINDOW_RANK.get(row.trend_window, 99),
            -row.updated_at.timestamp(),
            _SCOPE_RANK.get(row.snapshot_scope, 99),
            row.currency_code,
            row.id,
        )
    )
    return MarketTrendGenerateResponse(snapshot_count=len(summaries), snapshots=summaries)


def list_market_trends(
    session: Session,
    *,
    snapshot_scope: MarketTrendSnapshotScope | None = None,
    grading_company: str | None = None,
    grade: str | None = None,
    trend_direction: MarketTrendDirection | None = None,
    trend_strength: MarketTrendStrength | None = None,
    liquidity_direction: MarketTrendLiquidityDirection | None = None,
    stale_data: bool | None = None,
    currency: str | None = None,
    trend_window: MarketTrendWindow | None = None,
    metadata_identity_key: str | None = None,
) -> MarketTrendSnapshotListResponse:
    rows = _base_list_query(session)
    rows = _filter_rows(
        rows,
        snapshot_scope=snapshot_scope,
        grading_company=grading_company,
        normalized_grade=grade,
        trend_direction=trend_direction,
        trend_strength=trend_strength,
        liquidity_direction=liquidity_direction,
        stale_data=stale_data,
        currency=currency,
        trend_window=trend_window,
        metadata_identity_key=metadata_identity_key,
    )
    return _build_list_response(rows)


def get_market_trend_snapshot(session: Session, *, snapshot_id: int) -> MarketTrendSnapshotRead:
    return _snapshot_read(session, _load_snapshot(session, snapshot_id=snapshot_id))

