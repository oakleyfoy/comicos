from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    AcquisitionPrioritySnapshot,
    ComicIssue,
    ComicTitle,
    ConcentrationRiskSnapshot,
    InventoryCopy,
    MarketAcquisitionNormalizedCandidate,
    MarketAcquisitionNormalizationRun,
    MarketAcquisitionScore,
    MarketAcquisitionScoreEvidence,
    MarketAcquisitionScoreHistory,
    MarketAcquisitionScoreSnapshot,
    PortfolioExposureSnapshot,
    PortfolioLiquiditySnapshot,
    Publisher,
    Variant,
)
from app.schemas.market_scoring import (
    InventoryMarketAcquisitionScoreTeaser,
    MarketAcquisitionScoreDetailRead,
    MarketAcquisitionScoreEvidenceRead,
    MarketAcquisitionScoreHistoryListResponse,
    MarketAcquisitionScoreHistoryRead,
    MarketAcquisitionScoreListResponse,
    MarketAcquisitionScoreRead,
    MarketAcquisitionScoreRunPayload,
    MarketAcquisitionScoreRunResponse,
    MarketAcquisitionScoreSnapshotListResponse,
    MarketAcquisitionScoreSnapshotRead,
)
from app.services.market_normalization import (
    deterministic_normalize_publisher,
    deterministic_normalize_title,
)

ZERO = Decimal("0.00")
HUNDRED = Decimal("100.00")
SCORE_QUANT = Decimal("0.01")
SCOPE_ALL_INVENTORY = "ALL_INVENTORY"

PORTFOLIO_FIT_WEIGHT = Decimal("0.25")
LIQUIDITY_WEIGHT = Decimal("0.20")
GRADING_WEIGHT = Decimal("0.20")
DIVERSIFICATION_WEIGHT = Decimal("0.15")
CONCENTRATION_WEIGHT = Decimal("0.10")
RISK_INVERSE_WEIGHT = Decimal("0.10")

GRADE_BAND_SCORES: dict[str, Decimal] = {
    "UNKNOWN": Decimal("30"),
    "POOR": Decimal("10"),
    "GOOD": Decimal("28"),
    "VERY_GOOD": Decimal("42"),
    "FINE": Decimal("55"),
    "VF": Decimal("74"),
    "NM": Decimal("90"),
}

ACQ_PRIORITY_BASE: dict[str, Decimal] = {
    "LOW": Decimal("35"),
    "MEDIUM": Decimal("58"),
    "HIGH": Decimal("78"),
    "ELITE": Decimal("94"),
}

EXPOSURE_STATUS_SCORES: dict[str, Decimal] = {
    "INSUFFICIENT_DATA": Decimal("50"),
    "BALANCED": Decimal("78"),
    "WATCH": Decimal("64"),
    "CONCENTRATED": Decimal("28"),
    "OVEREXPOSED": Decimal("8"),
    "HEALTHY": Decimal("80"),
    "CRITICAL": Decimal("4"),
}

LIQUIDITY_STATUS_SCORES: dict[str, Decimal] = {
    "HEALTHY": Decimal("72"),
    "WATCH": Decimal("58"),
    "CRITICAL": Decimal("20"),
    "HIGH": Decimal("82"),
    "MEDIUM": Decimal("62"),
    "LOW": Decimal("38"),
    "ILLIQUID": Decimal("10"),
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_today() -> date:
    return utc_now().date()


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _score_q(value: Decimal) -> Decimal:
    return min(HUNDRED, max(ZERO, value)).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _money(value: Any | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)
    return Decimal(str(value)).quantize(SCORE_QUANT, rounding=ROUND_HALF_UP)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(SCORE_QUANT, rounding=ROUND_HALF_UP))
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _slug(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "unknown"
    lowered = str(value).strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", "_", lowered)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return (cleaned or "unknown")[:256]


def _recommendation_label(score: Decimal) -> str:
    if score >= Decimal("85"):
        return "STRONG_BUY"
    if score >= Decimal("70"):
        return "BUY"
    if score >= Decimal("50"):
        return "WATCH"
    return "IGNORE"


def _risk_level(score: Decimal) -> str:
    if score >= Decimal("60"):
        return "HIGH"
    if score >= Decimal("35"):
        return "MEDIUM"
    return "LOW"


def _confidence_level(*, matched_issue: bool, evidence_count: int, normalization_status: str) -> str:
    if matched_issue and evidence_count >= 4 and normalization_status == "SUCCESS":
        return "HIGH"
    if matched_issue or evidence_count >= 3:
        return "MEDIUM"
    return "LOW"


def _score_or_zero(value: Decimal | None) -> Decimal:
    return value if value is not None else ZERO


@dataclass(frozen=True)
class _IssueMatch:
    comic_issue_id: int
    title_name: str
    publisher_name: str
    issue_number: str


@dataclass(frozen=True)
class _ScoreContext:
    issue_match: _IssueMatch | None
    acquisition_priority: AcquisitionPrioritySnapshot | None
    publisher_exposure: PortfolioExposureSnapshot | None
    title_exposure: PortfolioExposureSnapshot | None
    publisher_concentration: ConcentrationRiskSnapshot | None
    title_concentration: ConcentrationRiskSnapshot | None
    portfolio_liquidity_snapshot: PortfolioLiquiditySnapshot | None
    existing_issue_count: int


def _latest_by_key[T](rows: list[T], key_fn: Any) -> dict[Any, T]:
    latest: dict[Any, T] = {}
    for row in rows:
        key = key_fn(row)
        if key not in latest:
            latest[key] = row
    return latest


def _resolve_issue_matches(
    session: Session,
    *,
    candidates: list[MarketAcquisitionNormalizedCandidate],
) -> dict[int, _IssueMatch | None]:
    issue_numbers = sorted(
        {
            str(row.canonical_issue_number).strip()
            for row in candidates
            if row.canonical_issue_number is not None and str(row.canonical_issue_number).strip()
        }
    )
    if not issue_numbers:
        return {int(row.id or 0): None for row in candidates}

    issue_rows = list(
        session.exec(
            select(ComicIssue, ComicTitle, Publisher)
            .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
            .join(Publisher, ComicTitle.publisher_id == Publisher.id)
            .where(col(ComicIssue.issue_number).in_(issue_numbers))
            .order_by(col(ComicIssue.id).asc())
        ).all(),
    )

    issue_lookup: dict[tuple[str | None, str, str], list[_IssueMatch]] = {}
    for issue, title, publisher in issue_rows:
        key = (
            deterministic_normalize_publisher(publisher.name),
            deterministic_normalize_title(title.name),
            str(issue.issue_number).strip(),
        )
        issue_lookup.setdefault(key, []).append(
            _IssueMatch(
                comic_issue_id=int(issue.id or 0),
                title_name=str(title.name),
                publisher_name=str(publisher.name),
                issue_number=str(issue.issue_number),
            )
        )

    resolved: dict[int, _IssueMatch | None] = {}
    for row in candidates:
        key = (
            row.canonical_publisher,
            deterministic_normalize_title(row.canonical_title),
            str(row.canonical_issue_number).strip() if row.canonical_issue_number else "",
        )
        matches = issue_lookup.get(key, [])
        resolved[int(row.id or 0)] = matches[0] if len(matches) == 1 else None
    return resolved


def _load_issue_counts(
    session: Session,
    *,
    owner_user_id: int,
    issue_ids: list[int],
) -> dict[int, int]:
    if not issue_ids:
        return {}
    rows = list(
        session.exec(
            select(ComicIssue.id, func.count())
            .join(Variant, Variant.comic_issue_id == ComicIssue.id)
            .join(InventoryCopy, InventoryCopy.variant_id == Variant.id)
            .where(
                InventoryCopy.user_id == owner_user_id,
                col(ComicIssue.id).in_(issue_ids),
            )
            .group_by(ComicIssue.id)
        ).all(),
    )
    return {int(issue_id): int(count) for issue_id, count in rows if issue_id is not None}


def _load_latest_acquisition_priority(
    session: Session,
    *,
    owner_user_id: int,
    issue_ids: list[int],
) -> dict[int, AcquisitionPrioritySnapshot]:
    if not issue_ids:
        return {}
    rows = list(
        session.exec(
            select(AcquisitionPrioritySnapshot)
            .where(
                AcquisitionPrioritySnapshot.owner_user_id == owner_user_id,
                col(AcquisitionPrioritySnapshot.canonical_comic_issue_id).in_(issue_ids),
            )
            .order_by(
                col(AcquisitionPrioritySnapshot.snapshot_date).desc(),
                col(AcquisitionPrioritySnapshot.id).desc(),
            )
        ).all(),
    )
    return _latest_by_key(rows, lambda row: int(row.canonical_comic_issue_id or 0))


def _load_latest_portfolio_liquidity(
    session: Session,
    *,
    owner_user_id: int,
) -> PortfolioLiquiditySnapshot | None:
    return session.exec(
        select(PortfolioLiquiditySnapshot)
        .where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.generation_scope_key == SCOPE_ALL_INVENTORY,
        )
        .order_by(
            col(PortfolioLiquiditySnapshot.snapshot_date).desc(),
            col(PortfolioLiquiditySnapshot.id).desc(),
        )
    ).first()


def _load_latest_exposures(
    session: Session,
    *,
    owner_user_id: int,
    publisher_keys: list[str],
    title_keys: list[str],
) -> tuple[dict[str, PortfolioExposureSnapshot], dict[str, PortfolioExposureSnapshot]]:
    rows = list(
        session.exec(
            select(PortfolioExposureSnapshot)
            .where(
                PortfolioExposureSnapshot.owner_user_id == owner_user_id,
                (
                    (
                        PortfolioExposureSnapshot.exposure_type == "publisher"
                    )
                    & col(PortfolioExposureSnapshot.exposure_key).in_(publisher_keys or ["unknown"])
                )
                | (
                    (
                        PortfolioExposureSnapshot.exposure_type == "title"
                    )
                    & col(PortfolioExposureSnapshot.exposure_key).in_(title_keys or ["unknown"])
                ),
            )
            .order_by(
                col(PortfolioExposureSnapshot.snapshot_date).desc(),
                col(PortfolioExposureSnapshot.id).desc(),
            )
        ).all(),
    )
    latest = _latest_by_key(rows, lambda row: (str(row.exposure_type), str(row.exposure_key)))
    pub_map = {
        key[1]: row
        for key, row in latest.items()
        if key[0] == "publisher"
    }
    title_map = {
        key[1]: row
        for key, row in latest.items()
        if key[0] == "title"
    }
    return pub_map, title_map


def _load_latest_concentration(
    session: Session,
    *,
    owner_user_id: int,
    publisher_keys: list[str],
    title_keys: list[str],
) -> tuple[dict[str, ConcentrationRiskSnapshot], dict[str, ConcentrationRiskSnapshot]]:
    rows = list(
        session.exec(
            select(ConcentrationRiskSnapshot)
            .where(
                ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
                col(ConcentrationRiskSnapshot.portfolio_id).is_(None),
                (
                    (
                        ConcentrationRiskSnapshot.concentration_type == "publisher"
                    )
                    & col(ConcentrationRiskSnapshot.concentration_key).in_(publisher_keys or ["unknown"])
                )
                | (
                    (
                        ConcentrationRiskSnapshot.concentration_type == "title"
                    )
                    & col(ConcentrationRiskSnapshot.concentration_key).in_(title_keys or ["unknown"])
                ),
            )
            .order_by(
                col(ConcentrationRiskSnapshot.snapshot_date).desc(),
                col(ConcentrationRiskSnapshot.id).desc(),
            )
        ).all(),
    )
    latest = _latest_by_key(rows, lambda row: (str(row.concentration_type), str(row.concentration_key)))
    pub_map = {
        key[1]: row
        for key, row in latest.items()
        if key[0] == "publisher"
    }
    title_map = {
        key[1]: row
        for key, row in latest.items()
        if key[0] == "title"
    }
    return pub_map, title_map


def _candidate_title_key(row: MarketAcquisitionNormalizedCandidate, match: _IssueMatch | None) -> str:
    if match is not None:
        return _slug(f"{match.title_name}::{match.issue_number}")
    issue_number = str(row.canonical_issue_number or "").strip()
    return _slug(f"{row.canonical_title}::{issue_number}")


def _context_bundle(
    session: Session,
    *,
    owner_user_id: int,
    candidates: list[MarketAcquisitionNormalizedCandidate],
) -> dict[int, _ScoreContext]:
    matches = _resolve_issue_matches(session, candidates=candidates)
    issue_ids = sorted({match.comic_issue_id for match in matches.values() if match is not None})
    issue_count_map = _load_issue_counts(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    acq_map = _load_latest_acquisition_priority(session, owner_user_id=owner_user_id, issue_ids=issue_ids)
    liquidity_snapshot = _load_latest_portfolio_liquidity(session, owner_user_id=owner_user_id)

    publisher_keys = sorted({_slug(row.canonical_publisher) for row in candidates})
    title_keys = sorted(
        {
            _candidate_title_key(row, matches.get(int(row.id or 0)))
            for row in candidates
        }
    )
    publisher_exposure_map, title_exposure_map = _load_latest_exposures(
        session,
        owner_user_id=owner_user_id,
        publisher_keys=publisher_keys,
        title_keys=title_keys,
    )
    publisher_conc_map, title_conc_map = _load_latest_concentration(
        session,
        owner_user_id=owner_user_id,
        publisher_keys=publisher_keys,
        title_keys=title_keys,
    )

    out: dict[int, _ScoreContext] = {}
    for row in candidates:
        row_id = int(row.id or 0)
        match = matches.get(row_id)
        publisher_key = _slug(row.canonical_publisher)
        title_key = _candidate_title_key(row, match)
        issue_id = match.comic_issue_id if match is not None else 0
        out[row_id] = _ScoreContext(
            issue_match=match,
            acquisition_priority=acq_map.get(issue_id) if issue_id else None,
            publisher_exposure=publisher_exposure_map.get(publisher_key),
            title_exposure=title_exposure_map.get(title_key),
            publisher_concentration=publisher_conc_map.get(publisher_key),
            title_concentration=title_conc_map.get(title_key),
            portfolio_liquidity_snapshot=liquidity_snapshot,
            existing_issue_count=issue_count_map.get(issue_id, 0) if issue_id else 0,
        )
    return out


def _score_from_status(status: str | None, *, default: Decimal = Decimal("50")) -> Decimal:
    if status is None:
        return default
    return EXPOSURE_STATUS_SCORES.get(str(status).upper(), default)


def _liquidity_status_score(status: str | None, *, default: Decimal = Decimal("55")) -> Decimal:
    if status is None:
        return default
    return LIQUIDITY_STATUS_SCORES.get(str(status).upper(), default)


def _discount_to_fmv_boost(
    *,
    price: Decimal | None,
    fmv: Decimal | None,
) -> Decimal:
    if price is None or fmv is None or fmv <= ZERO:
        return ZERO
    ratio = (price / fmv).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if ratio <= Decimal("0.70"):
        return Decimal("18")
    if ratio <= Decimal("0.85"):
        return Decimal("10")
    if ratio <= Decimal("1.00"):
        return Decimal("4")
    if ratio <= Decimal("1.15"):
        return Decimal("-10")
    return Decimal("-22")


def _candidate_signature(row: MarketAcquisitionNormalizedCandidate) -> dict[str, Any]:
    return {
        "id": int(row.id or 0),
        "canonical_title": row.canonical_title,
        "canonical_publisher": row.canonical_publisher,
        "canonical_issue_number": row.canonical_issue_number,
        "canonical_variant": row.canonical_variant,
        "normalized_condition_band": row.normalized_condition_band,
        "normalized_price": _money(row.normalized_price),
        "normalized_fmv_estimate": _money(row.normalized_fmv_estimate),
        "normalization_status": row.normalization_status,
        "flags": row.normalization_flags_json or {},
    }


def _component_scores(
    *,
    row: MarketAcquisitionNormalizedCandidate,
    ctx: _ScoreContext,
) -> tuple[dict[str, Decimal], list[dict[str, Any]], str]:
    ap = ctx.acquisition_priority
    existing_count = ctx.existing_issue_count
    price = _money(row.normalized_price)
    fmv = _money(row.normalized_fmv_estimate)
    condition_score = GRADE_BAND_SCORES.get(str(row.normalized_condition_band), Decimal("30"))
    discount_boost = _discount_to_fmv_boost(price=price, fmv=fmv)
    norm_flags = row.normalization_flags_json or {}

    if ap is not None:
        priority_bonus = ACQ_PRIORITY_BASE.get(str(ap.acquisition_priority), Decimal("50"))
        portfolio_fit = _score_q(
            (_score_or_zero(_money(ap.portfolio_impact_score)) * Decimal("0.60"))
            + (priority_bonus * Decimal("0.25"))
            + (Decimal("15") if existing_count == 0 else Decimal("0"))
        )
        diversification = _score_q(
            (_score_or_zero(_money(ap.diversification_impact)) * Decimal("0.75"))
            + (Decimal("12") if existing_count == 0 else Decimal("0"))
        )
        liquidity = _score_q(
            (_score_or_zero(_money(ap.liquidity_impact)) * Decimal("0.70"))
            + discount_boost
            + (_liquidity_status_score(ctx.portfolio_liquidity_snapshot.liquidity_balance_status) * Decimal("0.10")
               if ctx.portfolio_liquidity_snapshot is not None else Decimal("0"))
        )
        grading = _score_q(
            (_score_or_zero(_money(ap.grading_upside_score)) * Decimal("0.70"))
            + (condition_score * Decimal("0.20"))
            + max(ZERO, discount_boost)
        )
        concentration_reduction = _score_q(
            (_score_or_zero(_money(ap.concentration_reduction_score)) * Decimal("0.80"))
            + (_score_from_status(
                ctx.publisher_concentration.exposure_status if ctx.publisher_concentration is not None else None
            ) * Decimal("0.10"))
        )
    else:
        portfolio_fit = Decimal("70") if ctx.issue_match is not None and existing_count == 0 else Decimal("42")
        diversification = Decimal("72") if existing_count == 0 else Decimal("24")
        liquidity = _score_q(
            (_liquidity_status_score(
                ctx.portfolio_liquidity_snapshot.liquidity_balance_status
                if ctx.portfolio_liquidity_snapshot is not None
                else None
            ) * Decimal("0.70"))
            + discount_boost
        )
        grading = _score_q((condition_score * Decimal("0.85")) + max(ZERO, discount_boost))
        concentration_reduction = _score_q(
            (_score_from_status(
                ctx.publisher_concentration.exposure_status if ctx.publisher_concentration is not None else None
            ) * Decimal("0.60"))
            + (_score_from_status(
                ctx.title_concentration.exposure_status if ctx.title_concentration is not None else None
            ) * Decimal("0.25"))
        )

    if ctx.publisher_exposure is not None and str(ctx.publisher_exposure.exposure_status).upper() == "OVEREXPOSED":
        diversification = _score_q(diversification - Decimal("25"))
    if ctx.title_exposure is not None and str(ctx.title_exposure.exposure_status).upper() == "OVEREXPOSED":
        portfolio_fit = _score_q(portfolio_fit - Decimal("20"))
        concentration_reduction = _score_q(concentration_reduction - Decimal("20"))

    duplicate_penalty = Decimal("0")
    if existing_count >= 1:
        duplicate_penalty = Decimal("18") + (Decimal("10") * Decimal(existing_count - 1))
    if ap is not None and ap.duplication_risk is not None:
        duplicate_penalty = max(duplicate_penalty, _score_or_zero(_money(ap.duplication_risk)) * Decimal("0.55"))

    risk_penalty = Decimal("0")
    if str(row.normalization_status).upper() == "PARTIAL":
        risk_penalty += Decimal("18")
    elif str(row.normalization_status).upper() == "FAILED":
        risk_penalty += Decimal("55")
    if ctx.issue_match is None:
        risk_penalty += Decimal("12")
    if norm_flags.get("missing_publisher"):
        risk_penalty += Decimal("12")
    if norm_flags.get("variant_conflict"):
        risk_penalty += Decimal("10")
    if norm_flags.get("condition_unmapped"):
        risk_penalty += Decimal("8")
    if norm_flags.get("invalid_price"):
        risk_penalty += Decimal("12")
    risk_penalty += duplicate_penalty
    if discount_boost < ZERO:
        risk_penalty += abs(discount_boost)
    if ctx.portfolio_liquidity_snapshot is not None and ctx.portfolio_liquidity_snapshot.liquidity_drag_score is not None:
        risk_penalty += _score_or_zero(_money(ctx.portfolio_liquidity_snapshot.liquidity_drag_score)) * Decimal("0.08")
    risk_penalty = _score_q(risk_penalty)

    final_rank = _score_q(
        (portfolio_fit * PORTFOLIO_FIT_WEIGHT)
        + (liquidity * LIQUIDITY_WEIGHT)
        + (grading * GRADING_WEIGHT)
        + (diversification * DIVERSIFICATION_WEIGHT)
        + (concentration_reduction * CONCENTRATION_WEIGHT)
        + ((_score_q(HUNDRED - risk_penalty)) * RISK_INVERSE_WEIGHT)
    )

    evidence_rows = [
        {
            "evidence_type": "PORTFOLIO_STATE",
            "source_id": int(ap.id or 0) if ap is not None else None,
            "source_table": "acquisition_priority_snapshot" if ap is not None else None,
            "evidence_value_json": {
                "issue_match": ctx.issue_match.comic_issue_id if ctx.issue_match is not None else None,
                "existing_issue_count": existing_count,
                "portfolio_fit_score": portfolio_fit,
                "diversification_score": diversification,
            },
        },
        {
            "evidence_type": "CONCENTRATION_RISK",
            "source_id": int(ctx.publisher_concentration.id or 0) if ctx.publisher_concentration is not None else None,
            "source_table": "concentration_risk_snapshot" if ctx.publisher_concentration is not None else None,
            "evidence_value_json": {
                "publisher_status": ctx.publisher_concentration.exposure_status
                if ctx.publisher_concentration is not None
                else None,
                "title_status": ctx.title_concentration.exposure_status
                if ctx.title_concentration is not None
                else None,
                "concentration_reduction_score": concentration_reduction,
            },
        },
        {
            "evidence_type": "DUPLICATE_INTELLIGENCE",
            "source_id": None,
            "source_table": None,
            "evidence_value_json": {
                "existing_issue_count": existing_count,
                "duplicate_overlap_penalty": _score_q(duplicate_penalty),
            },
        },
        {
            "evidence_type": "LIQUIDITY_ENGINE",
            "source_id": int(ctx.portfolio_liquidity_snapshot.id or 0)
            if ctx.portfolio_liquidity_snapshot is not None
            else None,
            "source_table": "portfolio_liquidity_snapshot" if ctx.portfolio_liquidity_snapshot is not None else None,
            "evidence_value_json": {
                "portfolio_balance_status": ctx.portfolio_liquidity_snapshot.liquidity_balance_status
                if ctx.portfolio_liquidity_snapshot is not None
                else None,
                "liquidity_efficiency_score": _money(
                    ctx.portfolio_liquidity_snapshot.liquidity_efficiency_score
                )
                if ctx.portfolio_liquidity_snapshot is not None
                else None,
                "liquidity_score": liquidity,
            },
        },
        {
            "evidence_type": "NORMALIZATION_LAYER",
            "source_id": int(row.id or 0),
            "source_table": "market_acquisition_normalized_candidate",
            "evidence_value_json": {
                "normalization_status": row.normalization_status,
                "condition_band": row.normalized_condition_band,
                "normalized_price": price,
                "normalized_fmv_estimate": fmv,
                "flags": norm_flags,
            },
        },
    ]

    score_checksum = _hash_payload(
        {
            "candidate": _candidate_signature(row),
            "issue_match": ctx.issue_match.comic_issue_id if ctx.issue_match is not None else None,
            "existing_issue_count": existing_count,
            "acquisition_priority_checksum": ap.checksum if ap is not None else None,
            "publisher_exposure_checksum": ctx.publisher_exposure.checksum if ctx.publisher_exposure is not None else None,
            "title_exposure_checksum": ctx.title_exposure.checksum if ctx.title_exposure is not None else None,
            "publisher_concentration_checksum": (
                ctx.publisher_concentration.checksum if ctx.publisher_concentration is not None else None
            ),
            "title_concentration_checksum": (
                ctx.title_concentration.checksum if ctx.title_concentration is not None else None
            ),
            "portfolio_liquidity_checksum": (
                ctx.portfolio_liquidity_snapshot.checksum
                if ctx.portfolio_liquidity_snapshot is not None
                else None
            ),
            "scores": {
                "portfolio_fit": portfolio_fit,
                "liquidity": liquidity,
                "grading": grading,
                "concentration_reduction": concentration_reduction,
                "diversification": diversification,
                "risk_penalty": risk_penalty,
                "final_rank": final_rank,
            },
        }
    )

    return (
        {
            "acquisition_score": final_rank,
            "portfolio_fit_score": portfolio_fit,
            "liquidity_score": liquidity,
            "grading_upside_score": grading,
            "concentration_reduction_score": concentration_reduction,
            "diversification_score": diversification,
            "risk_penalty_score": risk_penalty,
            "final_rank_score": final_rank,
            "duplicate_overlap_penalty": _score_q(duplicate_penalty),
        },
        evidence_rows,
        score_checksum,
    )


def _score_read(row: MarketAcquisitionScore) -> MarketAcquisitionScoreRead:
    return MarketAcquisitionScoreRead.model_validate(row, from_attributes=True)


def _snapshot_read(row: MarketAcquisitionScoreSnapshot) -> MarketAcquisitionScoreSnapshotRead:
    return MarketAcquisitionScoreSnapshotRead.model_validate(row, from_attributes=True)


def _history_read(row: MarketAcquisitionScoreHistory) -> MarketAcquisitionScoreHistoryRead:
    return MarketAcquisitionScoreHistoryRead.model_validate(row, from_attributes=True)


def _evidence_read(row: MarketAcquisitionScoreEvidence) -> MarketAcquisitionScoreEvidenceRead:
    return MarketAcquisitionScoreEvidenceRead.model_validate(row, from_attributes=True)


def _get_score_owner_or_404(
    session: Session,
    *,
    owner_user_id: int,
    score_id: int,
) -> MarketAcquisitionScore:
    row = session.get(MarketAcquisitionScore, score_id)
    if row is None or row.owner_user_id != owner_user_id:
        raise HTTPException(status_code=404, detail="Market acquisition score not found")
    return row


def _get_score_ops_or_404(session: Session, *, score_id: int) -> MarketAcquisitionScore:
    row = session.get(MarketAcquisitionScore, score_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Market acquisition score not found")
    return row


def run_market_acquisition_scoring_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    payload: MarketAcquisitionScoreRunPayload,
) -> MarketAcquisitionScoreRunResponse:
    snapshot_date = payload.snapshot_date or utc_today()
    normalized_rows = list(
        session.exec(
            select(MarketAcquisitionNormalizedCandidate)
            .where(MarketAcquisitionNormalizedCandidate.owner_user_id == owner_user_id)
            .order_by(col(MarketAcquisitionNormalizedCandidate.id).asc())
        ).all(),
    )

    ctx_map = _context_bundle(session, owner_user_id=owner_user_id, candidates=normalized_rows)
    staged_scores: list[dict[str, Any]] = []
    history_rows: list[MarketAcquisitionScoreHistory] = []
    score_rows_to_insert: list[MarketAcquisitionScore] = []
    evidence_rows_to_insert: list[MarketAcquisitionScoreEvidence] = []

    for row in normalized_rows:
        row_id = int(row.id or 0)
        ctx = ctx_map[row_id]
        component_scores, evidence_payloads, score_checksum = _component_scores(row=row, ctx=ctx)
        label = _recommendation_label(component_scores["final_rank_score"])
        confidence = _confidence_level(
            matched_issue=ctx.issue_match is not None,
            evidence_count=len(evidence_payloads),
            normalization_status=str(row.normalization_status),
        )
        risk_level = _risk_level(component_scores["risk_penalty_score"])
        staged_scores.append(
            {
                "normalized_candidate_id": row_id,
                "canonical_comic_issue_id": ctx.issue_match.comic_issue_id if ctx.issue_match is not None else None,
                "owner_user_id": owner_user_id,
                **component_scores,
                "score_breakdown_json": {
                    "liquidity_weight": str(LIQUIDITY_WEIGHT),
                    "grading_weight": str(GRADING_WEIGHT),
                    "portfolio_gap_weight": str(PORTFOLIO_FIT_WEIGHT),
                    "concentration_weight": str(CONCENTRATION_WEIGHT),
                    "duplicate_overlap_weight": str(RISK_INVERSE_WEIGHT),
                    "duplicate_overlap_penalty": str(component_scores["duplicate_overlap_penalty"]),
                },
                "recommendation_label": label,
                "confidence_level": confidence,
                "risk_level": risk_level,
                "checksum": score_checksum,
                "snapshot_date": snapshot_date,
                "evidence_payloads": evidence_payloads,
            }
        )

    snapshot_checksum = _hash_payload(
        {
            "owner_user_id": owner_user_id,
            "snapshot_date": snapshot_date,
            "scores": [
                {
                    "normalized_candidate_id": row["normalized_candidate_id"],
                    "checksum": row["checksum"],
                    "recommendation_label": row["recommendation_label"],
                }
                for row in staged_scores
            ],
        }
    )
    existing_snapshot = session.exec(
        select(MarketAcquisitionScoreSnapshot)
        .where(
            MarketAcquisitionScoreSnapshot.owner_user_id == owner_user_id,
            MarketAcquisitionScoreSnapshot.snapshot_date == snapshot_date,
            MarketAcquisitionScoreSnapshot.checksum == snapshot_checksum,
        )
        .order_by(col(MarketAcquisitionScoreSnapshot.id).desc())
    ).first()
    if existing_snapshot is not None:
        existing_total = int(
            session.exec(
                select(func.count())
                .where(MarketAcquisitionScore.market_acquisition_score_snapshot_id == int(existing_snapshot.id or 0))
            ).one()
            or 0
        )
        return MarketAcquisitionScoreRunResponse(
            replayed=True,
            snapshot=_snapshot_read(existing_snapshot),
            total_scores=existing_total,
        )

    total = len(staged_scores)
    strong_buy_count = sum(1 for row in staged_scores if row["recommendation_label"] == "STRONG_BUY")
    buy_count = sum(1 for row in staged_scores if row["recommendation_label"] == "BUY")
    watch_count = sum(1 for row in staged_scores if row["recommendation_label"] == "WATCH")
    ignore_count = sum(1 for row in staged_scores if row["recommendation_label"] == "IGNORE")
    high_value_count = sum(
        1 for row in staged_scores if _score_or_zero(row["final_rank_score"]) >= Decimal("70")
    )
    avg_score = _score_q(
        sum((_score_or_zero(row["final_rank_score"]) for row in staged_scores), ZERO) / Decimal(total or 1)
    ) if total else None
    avg_liquidity = _score_q(
        sum((_score_or_zero(row["liquidity_score"]) for row in staged_scores), ZERO) / Decimal(total or 1)
    ) if total else None
    avg_grading = _score_q(
        sum((_score_or_zero(row["grading_upside_score"]) for row in staged_scores), ZERO) / Decimal(total or 1)
    ) if total else None
    avg_fit = _score_q(
        sum((_score_or_zero(row["portfolio_fit_score"]) for row in staged_scores), ZERO) / Decimal(total or 1)
    ) if total else None
    avg_div = _score_q(
        sum((_score_or_zero(row["diversification_score"]) for row in staged_scores), ZERO) / Decimal(total or 1)
    ) if total else None

    snapshot = MarketAcquisitionScoreSnapshot(
        owner_user_id=owner_user_id,
        total_candidates_scored=total,
        avg_score=avg_score,
        avg_liquidity_score=avg_liquidity,
        avg_grading_upside_score=avg_grading,
        high_value_count=high_value_count,
        strong_buy_count=strong_buy_count,
        buy_count=buy_count,
        watch_count=watch_count,
        ignore_count=ignore_count,
        portfolio_alignment_score=avg_fit,
        liquidity_alignment_score=avg_liquidity,
        diversification_alignment_score=avg_div,
        checksum=snapshot_checksum,
        snapshot_date=snapshot_date,
        created_at=utc_now(),
    )
    session.add(snapshot)
    session.flush()
    snapshot_id = int(snapshot.id or 0)

    for staged in staged_scores:
        score_row = MarketAcquisitionScore(
            market_acquisition_score_snapshot_id=snapshot_id,
            normalized_candidate_id=staged["normalized_candidate_id"],
            canonical_comic_issue_id=staged["canonical_comic_issue_id"],
            owner_user_id=owner_user_id,
            acquisition_score=staged["acquisition_score"],
            portfolio_fit_score=staged["portfolio_fit_score"],
            liquidity_score=staged["liquidity_score"],
            grading_upside_score=staged["grading_upside_score"],
            concentration_reduction_score=staged["concentration_reduction_score"],
            diversification_score=staged["diversification_score"],
            risk_penalty_score=staged["risk_penalty_score"],
            final_rank_score=staged["final_rank_score"],
            score_breakdown_json=_json_safe(staged["score_breakdown_json"]),
            recommendation_label=staged["recommendation_label"],
            confidence_level=staged["confidence_level"],
            risk_level=staged["risk_level"],
            checksum=staged["checksum"],
            snapshot_date=snapshot_date,
            created_at=utc_now(),
        )
        score_rows_to_insert.append(score_row)
        session.add(score_row)
        session.flush()
        score_id = int(score_row.id or 0)
        for evidence in staged["evidence_payloads"]:
            evidence_rows_to_insert.append(
                MarketAcquisitionScoreEvidence(
                    score_id=score_id,
                    evidence_type=evidence["evidence_type"],
                    source_id=evidence["source_id"],
                    source_table=evidence["source_table"],
                    evidence_value_json=_json_safe(evidence["evidence_value_json"]),
                    created_at=utc_now(),
                )
            )
        history_rows.append(
            MarketAcquisitionScoreHistory(
                owner_user_id=owner_user_id,
                normalized_candidate_id=staged["normalized_candidate_id"],
                acquisition_score=staged["acquisition_score"],
                recommendation_label=staged["recommendation_label"],
                confidence_level=staged["confidence_level"],
                risk_level=staged["risk_level"],
                checksum=staged["checksum"],
                snapshot_date=snapshot_date,
                created_at=utc_now(),
            )
        )

    for row in evidence_rows_to_insert + history_rows:
        session.add(row)
    session.commit()
    session.refresh(snapshot)
    return MarketAcquisitionScoreRunResponse(
        replayed=False,
        snapshot=_snapshot_read(snapshot),
        total_scores=total,
    )


def list_scores_owner(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_label: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    score_min: Decimal | None = None,
    score_max: Decimal | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionScoreListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionScore).where(MarketAcquisitionScore.owner_user_id == owner_user_id)
    if recommendation_label is not None:
        stmt = stmt.where(MarketAcquisitionScore.recommendation_label == recommendation_label)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionScore.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionScore.risk_level == risk_level)
    if score_min is not None:
        stmt = stmt.where(MarketAcquisitionScore.final_rank_score >= score_min)
    if score_max is not None:
        stmt = stmt.where(MarketAcquisitionScore.final_rank_score <= score_max)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionScore.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionScore.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionScore.snapshot_date).desc(),
                col(MarketAcquisitionScore.final_rank_score).desc(),
                col(MarketAcquisitionScore.id).asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionScoreListResponse(
        items=[_score_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_scores_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    recommendation_label: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    score_min: Decimal | None = None,
    score_max: Decimal | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionScoreListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionScore)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionScore.owner_user_id == owner_user_id)
    if recommendation_label is not None:
        stmt = stmt.where(MarketAcquisitionScore.recommendation_label == recommendation_label)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionScore.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionScore.risk_level == risk_level)
    if score_min is not None:
        stmt = stmt.where(MarketAcquisitionScore.final_rank_score >= score_min)
    if score_max is not None:
        stmt = stmt.where(MarketAcquisitionScore.final_rank_score <= score_max)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionScore.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionScore.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionScore.snapshot_date).desc(),
                col(MarketAcquisitionScore.final_rank_score).desc(),
                col(MarketAcquisitionScore.id).asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionScoreListResponse(
        items=[_score_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def get_score_owner(
    session: Session,
    *,
    owner_user_id: int,
    score_id: int,
) -> MarketAcquisitionScoreDetailRead:
    row = _get_score_owner_or_404(session, owner_user_id=owner_user_id, score_id=score_id)
    evidence = list(
        session.exec(
            select(MarketAcquisitionScoreEvidence)
            .where(MarketAcquisitionScoreEvidence.score_id == int(row.id or 0))
            .order_by(col(MarketAcquisitionScoreEvidence.id).asc())
        ).all(),
    )
    return MarketAcquisitionScoreDetailRead(
        score=_score_read(row),
        evidence=[_evidence_read(ev) for ev in evidence],
    )


def get_score_ops(session: Session, *, score_id: int) -> MarketAcquisitionScoreDetailRead:
    row = _get_score_ops_or_404(session, score_id=score_id)
    evidence = list(
        session.exec(
            select(MarketAcquisitionScoreEvidence)
            .where(MarketAcquisitionScoreEvidence.score_id == int(row.id or 0))
            .order_by(col(MarketAcquisitionScoreEvidence.id).asc())
        ).all(),
    )
    return MarketAcquisitionScoreDetailRead(
        score=_score_read(row),
        evidence=[_evidence_read(ev) for ev in evidence],
    )


def list_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionScoreSnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionScoreSnapshot).where(
        MarketAcquisitionScoreSnapshot.owner_user_id == owner_user_id
    )
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionScoreSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionScoreSnapshot.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionScoreSnapshot.snapshot_date).desc(),
                col(MarketAcquisitionScoreSnapshot.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionScoreSnapshotListResponse(
        items=[_snapshot_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> MarketAcquisitionScoreSnapshotListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionScoreSnapshot)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionScoreSnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionScoreSnapshot.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionScoreSnapshot.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionScoreSnapshot.snapshot_date).desc(),
                col(MarketAcquisitionScoreSnapshot.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionScoreSnapshotListResponse(
        items=[_snapshot_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    recommendation_label: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionScoreHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionScoreHistory).where(
        MarketAcquisitionScoreHistory.owner_user_id == owner_user_id
    )
    if recommendation_label is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.recommendation_label == recommendation_label)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionScoreHistory.snapshot_date).desc(),
                col(MarketAcquisitionScoreHistory.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionScoreHistoryListResponse(
        items=[_history_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def list_history_ops(
    session: Session,
    *,
    owner_user_id: int | None = None,
    recommendation_label: str | None = None,
    confidence_level: str | None = None,
    risk_level: str | None = None,
    snapshot_date_from: date | None = None,
    snapshot_date_to: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> MarketAcquisitionScoreHistoryListResponse:
    limit, offset = clamp_pagination(limit=limit, offset=offset)
    stmt = select(MarketAcquisitionScoreHistory)
    if owner_user_id is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.owner_user_id == owner_user_id)
    if recommendation_label is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.recommendation_label == recommendation_label)
    if confidence_level is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.confidence_level == confidence_level)
    if risk_level is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.risk_level == risk_level)
    if snapshot_date_from is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.snapshot_date >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(MarketAcquisitionScoreHistory.snapshot_date <= snapshot_date_to)
    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one() or 0)
    rows = list(
        session.exec(
            stmt.order_by(
                col(MarketAcquisitionScoreHistory.snapshot_date).desc(),
                col(MarketAcquisitionScoreHistory.id).desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all(),
    )
    return MarketAcquisitionScoreHistoryListResponse(
        items=[_history_read(row) for row in rows],
        total_items=total,
        limit=limit,
        offset=offset,
    )


def inventory_market_acquisition_score_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_item_id: int,
) -> InventoryMarketAcquisitionScoreTeaser | None:
    issue_row = session.exec(
        select(ComicIssue.id)
        .join(Variant, Variant.comic_issue_id == ComicIssue.id)
        .join(InventoryCopy, InventoryCopy.variant_id == Variant.id)
        .where(
            InventoryCopy.user_id == owner_user_id,
            InventoryCopy.id == inventory_item_id,
        )
    ).first()
    if issue_row is None:
        return None
    score_row = session.exec(
        select(MarketAcquisitionScore)
        .where(
            MarketAcquisitionScore.owner_user_id == owner_user_id,
            MarketAcquisitionScore.canonical_comic_issue_id == int(issue_row),
        )
        .order_by(
            col(MarketAcquisitionScore.snapshot_date).desc(),
            col(MarketAcquisitionScore.final_rank_score).desc(),
            col(MarketAcquisitionScore.id).desc(),
        )
    ).first()
    if score_row is None:
        return None
    return InventoryMarketAcquisitionScoreTeaser(
        normalized_candidate_id=int(score_row.normalized_candidate_id),
        final_rank_score=str(_money(score_row.final_rank_score)) if score_row.final_rank_score is not None else None,
        recommendation_label=str(score_row.recommendation_label),
        confidence_level=str(score_row.confidence_level),
        risk_level=str(score_row.risk_level),
        liquidity_score=str(_money(score_row.liquidity_score)) if score_row.liquidity_score is not None else None,
        grading_upside_score=str(_money(score_row.grading_upside_score))
        if score_row.grading_upside_score is not None
        else None,
        snapshot_date=score_row.snapshot_date,
    )
