"""P39-06 deterministic portfolio ↔ market coupling (read-only relational bridge)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import (
    ComicIssue,
    ComicTitle,
    ConcentrationRiskSnapshot,
    InventoryCopy,
    MarketAcquisitionNormalizedCandidate,
    MarketAcquisitionOpportunityItem,
    MarketAcquisitionOpportunitySnapshot,
    MarketAcquisitionScore,
    MarketAcquisitionScoreSnapshot,
    MarketAcquisitionSignal,
    Portfolio,
    PortfolioExposureSnapshot,
    PortfolioItem,
    PortfolioLiquiditySnapshot,
    PortfolioMarketCouplingEdge,
    PortfolioMarketCouplingEvidence,
    PortfolioMarketCouplingHistory,
    PortfolioMarketCouplingSnapshot,
    Publisher,
    Variant,
)
from app.services.market_feed import append_market_feed_event
from app.schemas.portfolio_market_coupling import (
    InventoryPortfolioMarketCouplingTeaserRead,
    PortfolioMarketCouplingDetailRead,
    PortfolioMarketCouplingEdgeListResponse,
    PortfolioMarketCouplingEdgeRead,
    PortfolioMarketCouplingEvidenceRead,
    PortfolioMarketCouplingGeneratePayload,
    PortfolioMarketCouplingGenerateResponse,
    PortfolioMarketCouplingHistoryListResponse,
    PortfolioMarketCouplingHistoryRead,
    PortfolioMarketCouplingSnapshotListResponse,
    PortfolioMarketCouplingSnapshotRead,
)
from app.services.market_scoring import _slug

ZERO = Decimal("0")

TYPE_PRIORITY_ADJ: dict[str, int] = {
    "CONCENTRATION_CONFLICT": -35,
    "CATEGORY_MATCH": 4,
    "PARTIAL_MATCH": 6,
    "LIQUIDITY_MATCH": 5,
    "DIVERSIFICATION_MATCH": 7,
    "CONCENTRATION_MATCH": 6,
    "DIRECT_MATCH": 10,
}

STRENGTH_BASE: dict[str, int] = {
    "ELITE": 90,
    "HIGH": 75,
    "MEDIUM": 60,
    "LOW": 46,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clamp_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
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


def snapshot_to_read(row: PortfolioMarketCouplingSnapshot) -> PortfolioMarketCouplingSnapshotRead:
    return PortfolioMarketCouplingSnapshotRead.model_validate(row)


def edge_to_read(edge: PortfolioMarketCouplingEdge) -> PortfolioMarketCouplingEdgeRead:
    return PortfolioMarketCouplingEdgeRead(
        id=int(edge.id or 0),
        snapshot_id=int(edge.portfolio_market_coupling_snapshot_id or 0),
        market_candidate_id=int(edge.market_normalized_candidate_id),
        market_acquisition_opportunity_item_id=int(edge.market_acquisition_opportunity_item_id),
        portfolio_item_id=int(edge.portfolio_item_id)
        if edge.portfolio_item_id is not None
        else None,
        coupling_type=str(edge.coupling_type),
        coupling_strength=str(edge.coupling_strength),
        coupling_score=int(edge.coupling_score),
        explanation_json=edge.explanation_json or {},
        created_at=edge.created_at,
    )


def evidence_to_read(
    evidence: PortfolioMarketCouplingEvidence,
) -> PortfolioMarketCouplingEvidenceRead:
    return PortfolioMarketCouplingEvidenceRead(
        id=int(evidence.id or 0),
        snapshot_id=int(evidence.portfolio_market_coupling_snapshot_id or 0),
        evidence_type=str(evidence.evidence_type),
        source_id=int(evidence.source_id) if evidence.source_id is not None else None,
        source_table=evidence.source_table,
        evidence_value_json=evidence.evidence_value_json or {},
        created_at=evidence.created_at,
    )


def history_to_read(row: PortfolioMarketCouplingHistory) -> PortfolioMarketCouplingHistoryRead:
    return PortfolioMarketCouplingHistoryRead(
        id=int(row.id or 0),
        owner_user_id=int(row.owner_user_id),
        snapshot_id=int(row.portfolio_market_coupling_snapshot_id or 0),
        snapshot_checksum=str(row.snapshot_checksum),
        alignment_score=row.alignment_score,
        market_opportunity_count=int(row.market_opportunity_count),
        high_fit_market_items=int(row.high_fit_market_items),
        snapshot_date=row.snapshot_date,
        created_at=row.created_at,
    )


def _pick_latest_score_row(
    session: Session,
    *,
    owner_user_id: int,
    normalized_candidate_ids: list[int],
    snapshot_date: date,
) -> dict[int, MarketAcquisitionScore]:
    if not normalized_candidate_ids:
        return {}

    cid_set = tuple(sorted(set(normalized_candidate_ids)))

    stmt = (
        select(
            MarketAcquisitionScore.id,
            MarketAcquisitionScore.normalized_candidate_id,
            MarketAcquisitionScoreSnapshot.id.label("snapshot_id"),
        )
        .join(
            MarketAcquisitionScoreSnapshot,
            MarketAcquisitionScoreSnapshot.id
            == MarketAcquisitionScore.market_acquisition_score_snapshot_id,
        )
        .where(
            MarketAcquisitionScore.normalized_candidate_id.in_(list(cid_set)),
            MarketAcquisitionScoreSnapshot.owner_user_id == owner_user_id,
            MarketAcquisitionScoreSnapshot.snapshot_date == snapshot_date,
        )
        .order_by(
            MarketAcquisitionScore.normalized_candidate_id.asc(),
            col(MarketAcquisitionScoreSnapshot.id).desc(),
            col(MarketAcquisitionScore.id).desc(),
        )
    )

    picks: dict[int, int] = {}
    for sc_id_int, cand_id, _sns in session.exec(stmt).all():
        cid_int = int(cand_id)
        if cid_int not in picks:
            picks[cid_int] = int(sc_id_int)

    if not picks:
        return {}

    score_ids = list(sorted(set(picks.values())))
    objs = session.exec(
        select(MarketAcquisitionScore).where(col(MarketAcquisitionScore.id).in_(score_ids))
    ).all()

    out: dict[int, MarketAcquisitionScore] = {}
    for row in objs:
        cid = int(row.normalized_candidate_id)
        sid = int(row.id or 0)
        if picks.get(cid) == sid:
            out[cid] = row
    return out


@dataclass(frozen=True, slots=True)
class _PortfolioLine:
    portfolio_item_id: int
    comic_issue_id: int | None
    publisher_slug: str
    title_issue_key: str


def _load_portfolio_lines(session: Session, *, owner_user_id: int) -> list[_PortfolioLine]:
    stmt = (
        select(
            PortfolioItem.id,
            ComicIssue.id,
            Publisher.name,
            ComicTitle.name,
            ComicIssue.issue_number,
        )
        .join(Portfolio, Portfolio.id == PortfolioItem.portfolio_id)
        .join(InventoryCopy, InventoryCopy.id == PortfolioItem.inventory_item_id)
        .join(Variant, Variant.id == InventoryCopy.variant_id)
        .join(ComicIssue, ComicIssue.id == Variant.comic_issue_id)
        .join(ComicTitle, ComicTitle.id == ComicIssue.comic_title_id)
        .join(Publisher, Publisher.id == ComicTitle.publisher_id)
        .where(
            Portfolio.owner_user_id == owner_user_id,
            Portfolio.status == "ACTIVE",
            PortfolioItem.removed_at.is_(None),
        )
        .order_by(col(PortfolioItem.id).asc())
    )
    rows = session.exec(stmt).all()

    out: list[_PortfolioLine] = []
    for pid, issue_id, pub_name, tit_name, iss_num in rows:
        pub_slug = _slug(pub_name or "")
        title_issue_key = _slug(f"{tit_name}::{iss_num}")
        iid_val = None if issue_id is None else int(issue_id)
        out.append(
            _PortfolioLine(
                portfolio_item_id=int(pid),
                comic_issue_id=iid_val,
                publisher_slug=pub_slug,
                title_issue_key=title_issue_key,
            ),
        )
    return out


def _publisher_overexposed_keys(
    session: Session, *, owner_user_id: int, as_of_date: date
) -> set[str]:
    rows = session.exec(
        select(
            PortfolioExposureSnapshot.exposure_type,
            PortfolioExposureSnapshot.exposure_key,
            PortfolioExposureSnapshot.exposure_status,
        ).where(
            PortfolioExposureSnapshot.owner_user_id == owner_user_id,
            PortfolioExposureSnapshot.snapshot_date == as_of_date,
        ),
    ).all()
    risky: set[str] = set()
    for et, ek, stat in rows:
        if str(et or "").lower() != "publisher":
            continue
        st_u = str(stat or "").strip().upper()
        if st_u in {"OVEREXPOSED", "CRITICAL"}:
            risky.add(str(ek))
    return risky


def _portfolio_aggregate(session: Session, *, owner_user_id: int) -> tuple[Decimal | None, int]:
    summed, counted = session.exec(
        select(
            func.coalesce(func.sum(InventoryCopy.current_fmv), ZERO),
            func.count(InventoryCopy.id),
        ).where(
            InventoryCopy.user_id == owner_user_id,
        ),
    ).one()
    amt = summed if summed is not None else None
    c = int(counted or 0)
    if amt is None:
        return None, c
    return Decimal(str(amt)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), c


def _concentration_rollup(
    session: Session,
    *,
    owner_user_id: int,
    as_of: date,
) -> tuple[Decimal | None, Decimal | None]:
    snaps = session.exec(
        select(ConcentrationRiskSnapshot).where(
            ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
            ConcentrationRiskSnapshot.snapshot_date == as_of,
        ),
    ).all()
    if not snaps:
        newest = session.exec(
            select(func.max(ConcentrationRiskSnapshot.snapshot_date)).where(
                ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
            ),
        ).one()
        if newest is None:
            return None, None
        snaps = session.exec(
            select(ConcentrationRiskSnapshot).where(
                ConcentrationRiskSnapshot.owner_user_id == owner_user_id,
                ConcentrationRiskSnapshot.snapshot_date == newest,
            ),
        ).all()
    conc_vals = [
        Decimal(str(s.concentration_score)) for s in snaps if s.concentration_score is not None
    ]
    div_vals = [
        Decimal(str(s.diversification_score)) for s in snaps if s.diversification_score is not None
    ]

    diversification = (
        (sum(div_vals, ZERO) / Decimal(len(div_vals))).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        if div_vals
        else None
    )
    concentration = (
        max(conc_vals).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if conc_vals else None
    )
    return diversification, concentration


def _liquidity_efficiency(
    session: Session, *, owner_user_id: int, as_of_date: date
) -> Decimal | None:
    eff = session.exec(
        select(PortfolioLiquiditySnapshot.liquidity_efficiency_score)
        .where(
            PortfolioLiquiditySnapshot.owner_user_id == owner_user_id,
            PortfolioLiquiditySnapshot.snapshot_date == as_of_date,
        )
        .order_by(col(PortfolioLiquiditySnapshot.id).desc()),
    ).first()
    if eff is not None:
        return Decimal(str(eff)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    fallback = session.exec(
        select(PortfolioLiquiditySnapshot.liquidity_efficiency_score)
        .where(PortfolioLiquiditySnapshot.owner_user_id == owner_user_id)
        .order_by(
            col(PortfolioLiquiditySnapshot.snapshot_date).desc(),
            col(PortfolioLiquiditySnapshot.id).desc(),
        ),
    ).first()
    if fallback is None:
        return None
    return Decimal(str(fallback)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def deterministic_coupling_score(
    *,
    coupling_type: str,
    signal_strength: str,
    portfolio_fit_score: Decimal | None,
    duplication_overlap_penalty: int,
    liquidity_alignment_bonus: int,
    concentration_alignment_bonus: int,
) -> int:
    strength_key = signal_strength.strip().upper() if signal_strength else "MEDIUM"
    base = STRENGTH_BASE.get(strength_key, 55)
    t_adj = TYPE_PRIORITY_ADJ.get(coupling_type, 0)

    pf = portfolio_fit_score if portfolio_fit_score is not None else Decimal("55")
    pf_term = int((pf - Decimal("55")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    pf_term = max(-12, min(12, pf_term))

    raw = (
        base
        + t_adj
        + pf_term
        - int(duplication_overlap_penalty)
        + int(liquidity_alignment_bonus)
        + int(
            concentration_alignment_bonus,
        )
    )
    return max(0, min(100, raw))


def _edge_sort_key(edge: dict[str, Any]) -> tuple[int, int, str, str, int]:
    return (
        int(edge["candidate_id"]),
        int(edge["portfolio_item_id"] or 0),
        str(edge["coupling_type"]),
        str(edge["coupling_strength"]),
        int(edge["market_acquisition_opportunity_item_id"]),
    )


def _build_edges(
    *,
    opportunity_items: list[MarketAcquisitionOpportunityItem],
    candidates: dict[int, MarketAcquisitionNormalizedCandidate],
    signals: dict[int, MarketAcquisitionSignal],
    scores_by_candidate: dict[int, MarketAcquisitionScore],
    portfolio_lines: list[_PortfolioLine],
    overexposed_pub_keys: set[str],
    liquidity_efficiency: Decimal | None,
    snapshot_date: date,
) -> list[dict[str, Any]]:
    owned_issue_ids = {ln.comic_issue_id for ln in portfolio_lines if ln.comic_issue_id is not None}
    owned_title_keys = {ln.title_issue_key for ln in portfolio_lines}

    def lines_for_issue(issue_id: int | None) -> list[_PortfolioLine]:
        if issue_id is None:
            return []
        return sorted(
            [ln for ln in portfolio_lines if ln.comic_issue_id == issue_id],
            key=lambda ln: ln.portfolio_item_id,
        )

    def first_line_by_publisher(pub: str) -> _PortfolioLine | None:
        matches = [ln for ln in portfolio_lines if ln.publisher_slug == pub]
        return min(matches, key=lambda ln: ln.portfolio_item_id) if matches else None

    def default_pid() -> int | None:
        return portfolio_lines[0].portfolio_item_id if portfolio_lines else None

    edges: list[dict[str, Any]] = []

    for item in sorted(opportunity_items, key=lambda r: int(r.id or 0)):
        opp_item_id = int(item.id or 0)
        cand_id = int(item.candidate_id)
        sig_id = int(item.market_acquisition_signal_id)

        cand = candidates.get(cand_id)
        sig = signals.get(sig_id)
        if cand is None or sig is None:
            continue
        score_row = scores_by_candidate.get(cand_id)

        pub_slug_c = _slug(cand.canonical_publisher or "")
        title_issue_c = _slug(f"{cand.canonical_title}::{cand.canonical_issue_number or ''}")

        canonical_issue_id: int | None = None
        if score_row and score_row.canonical_comic_issue_id is not None:
            canonical_issue_id = int(score_row.canonical_comic_issue_id)

        dup_penalty = 0
        sig_type = str(sig.signal_type)
        if sig_type == "REDUNDANT_ASSET":
            dup_penalty = max(dup_penalty, 28)
        if title_issue_c in owned_title_keys:
            dup_penalty = max(dup_penalty, 12)

        sig_strength_u = str(sig.signal_strength or "").upper()

        liquidity_match_signal = sig_type == "LIQUIDITY_OPPORTUNITY"
        liquidity_deficit = (
            liquidity_efficiency is not None and liquidity_efficiency < Decimal("76.5000")
            if liquidity_efficiency is not None
            else False
        )

        pf = score_row.portfolio_fit_score if score_row else None

        conflict_emitted_for_item = False

        redundant_lines = (
            sorted(
                [ln for ln in portfolio_lines if ln.title_issue_key == title_issue_c],
                key=lambda ln: ln.portfolio_item_id,
            )
            if sig_type == "REDUNDANT_ASSET"
            and title_issue_c in owned_title_keys
            and canonical_issue_id is None
            else []
        )
        if redundant_lines:
            for ln in redundant_lines:
                sc = deterministic_coupling_score(
                    coupling_type="CONCENTRATION_CONFLICT",
                    signal_strength=sig_strength_u,
                    portfolio_fit_score=pf,
                    duplication_overlap_penalty=40,
                    liquidity_alignment_bonus=6 if liquidity_match_signal else 0,
                    concentration_alignment_bonus=8,
                )
                edges.append(
                    {
                        "candidate_id": cand_id,
                        "market_acquisition_opportunity_item_id": opp_item_id,
                        "portfolio_item_id": ln.portfolio_item_id,
                        "coupling_type": "CONCENTRATION_CONFLICT",
                        "coupling_strength": "LOW",
                        "coupling_score": sc,
                        "explanation_json": _json_safe(
                            {
                                "reason": "redundant_asset_title_overlap",
                                "title_issue_key": title_issue_c,
                                "signal_type": sig_type,
                            },
                        ),
                    },
                )
            conflict_emitted_for_item = True

        conflict_lines_issue: list[_PortfolioLine] = []
        if canonical_issue_id is not None and canonical_issue_id in owned_issue_ids:
            conflict_lines_issue = lines_for_issue(canonical_issue_id)

        for ln in conflict_lines_issue:
            sc = deterministic_coupling_score(
                coupling_type="CONCENTRATION_CONFLICT",
                signal_strength=sig_strength_u,
                portfolio_fit_score=pf,
                duplication_overlap_penalty=40,
                liquidity_alignment_bonus=6 if liquidity_match_signal else 0,
                concentration_alignment_bonus=(
                    min(
                        10,
                        int(score_row.concentration_reduction_score),
                    )
                    if score_row and score_row.concentration_reduction_score is not None
                    else 0
                ),
            )
            edges.append(
                {
                    "candidate_id": cand_id,
                    "market_acquisition_opportunity_item_id": opp_item_id,
                    "portfolio_item_id": ln.portfolio_item_id,
                    "coupling_type": "CONCENTRATION_CONFLICT",
                    "coupling_strength": "LOW",
                    "coupling_score": sc,
                    "explanation_json": _json_safe(
                        {
                            "reason": "held_canonical_issue_overlap",
                            "canonical_issue_id": canonical_issue_id,
                            "signal_type": sig_type,
                        },
                    ),
                },
            )
            conflict_emitted_for_item = True

        if canonical_issue_id is not None and canonical_issue_id not in owned_issue_ids:
            sc = deterministic_coupling_score(
                coupling_type="DIRECT_MATCH",
                signal_strength=sig_strength_u,
                portfolio_fit_score=pf,
                duplication_overlap_penalty=dup_penalty,
                liquidity_alignment_bonus=10
                if liquidity_match_signal and liquidity_deficit
                else (4 if liquidity_match_signal else 0),
                concentration_alignment_bonus=5 if sig_type == "PORTFOLIO_GAP_FILL" else 0,
            )
            edges.append(
                {
                    "candidate_id": cand_id,
                    "market_acquisition_opportunity_item_id": opp_item_id,
                    "portfolio_item_id": None,
                    "coupling_type": "DIRECT_MATCH",
                    "coupling_strength": sig_strength_u,
                    "coupling_score": sc,
                    "explanation_json": _json_safe(
                        {
                            "reason": "catalog_issue_not_held",
                            "canonical_issue_id": canonical_issue_id,
                            "signal_type": sig_type,
                        },
                    ),
                },
            )

        if not conflict_emitted_for_item and not (
            canonical_issue_id is not None and canonical_issue_id not in owned_issue_ids
        ):
            pid_partial: int | None = None
            for ln in sorted(portfolio_lines, key=lambda x: x.portfolio_item_id):
                if ln.title_issue_key == title_issue_c:
                    pid_partial = ln.portfolio_item_id
                    break

            has_partial_match = pid_partial is not None
            if has_partial_match:
                sc = deterministic_coupling_score(
                    coupling_type="PARTIAL_MATCH",
                    signal_strength=sig_strength_u,
                    portfolio_fit_score=pf,
                    duplication_overlap_penalty=dup_penalty,
                    liquidity_alignment_bonus=8
                    if liquidity_match_signal and liquidity_deficit
                    else 0,
                    concentration_alignment_bonus=4 if sig_type == "PORTFOLIO_GAP_FILL" else 0,
                )
                edges.append(
                    {
                        "candidate_id": cand_id,
                        "market_acquisition_opportunity_item_id": opp_item_id,
                        "portfolio_item_id": int(pid_partial),
                        "coupling_type": "PARTIAL_MATCH",
                        "coupling_strength": sig_strength_u,
                        "coupling_score": sc,
                        "explanation_json": _json_safe(
                            {
                                "reason": "title_issue_alignment",
                                "title_issue_key": title_issue_c,
                                "signal_type": sig_type,
                            },
                        ),
                    },
                )

            cat_line_used: _PortfolioLine | None = None
            if not has_partial_match:
                for ln in sorted(portfolio_lines, key=lambda x: x.portfolio_item_id):
                    if ln.publisher_slug == pub_slug_c and ln.title_issue_key != title_issue_c:
                        cat_line_used = ln
                        break
                if cat_line_used is None:
                    cand_line_fb = first_line_by_publisher(pub_slug_c)
                    if cand_line_fb is not None and cand_line_fb.title_issue_key != title_issue_c:
                        cat_line_used = cand_line_fb

            if cat_line_used is not None and not has_partial_match:
                sc = deterministic_coupling_score(
                    coupling_type="CATEGORY_MATCH",
                    signal_strength=sig_strength_u,
                    portfolio_fit_score=pf,
                    duplication_overlap_penalty=dup_penalty,
                    liquidity_alignment_bonus=4 if liquidity_match_signal else 0,
                    concentration_alignment_bonus=0,
                )
                edges.append(
                    {
                        "candidate_id": cand_id,
                        "market_acquisition_opportunity_item_id": opp_item_id,
                        "portfolio_item_id": cat_line_used.portfolio_item_id,
                        "coupling_type": "CATEGORY_MATCH",
                        "coupling_strength": sig_strength_u,
                        "coupling_score": sc,
                        "explanation_json": _json_safe(
                            {
                                "reason": "publisher_cluster",
                                "publisher_slug": pub_slug_c,
                                "signal_type": sig_type,
                            },
                        ),
                    },
                )

        def has_edge(ctype: str) -> bool:
            return any(
                e["coupling_type"] == ctype
                and e["candidate_id"] == cand_id
                and e["market_acquisition_opportunity_item_id"] == opp_item_id
                for e in edges
            )

        if liquidity_match_signal and liquidity_deficit and not has_edge("LIQUIDITY_MATCH"):
            lb_adj = (
                max(10, min(22, int(Decimal("78") - (liquidity_efficiency or ZERO))))
                if liquidity_efficiency is not None
                else 15
            )
            sc = deterministic_coupling_score(
                coupling_type="LIQUIDITY_MATCH",
                signal_strength=sig_strength_u,
                portfolio_fit_score=pf,
                duplication_overlap_penalty=dup_penalty,
                liquidity_alignment_bonus=lb_adj,
                concentration_alignment_bonus=0,
            )
            edges.append(
                {
                    "candidate_id": cand_id,
                    "market_acquisition_opportunity_item_id": opp_item_id,
                    "portfolio_item_id": default_pid(),
                    "coupling_type": "LIQUIDITY_MATCH",
                    "coupling_strength": sig_strength_u,
                    "coupling_score": sc,
                    "explanation_json": _json_safe(
                        {
                            "reason": "portfolio_liquidity_surface",
                            "liquidity_efficiency_hint": liquidity_efficiency is not None,
                            "signal_type": sig_type,
                        },
                    ),
                },
            )

        if (
            sig_type == "PORTFOLIO_GAP_FILL"
            and pub_slug_c not in overexposed_pub_keys
            and not has_edge(
                "DIVERSIFICATION_MATCH",
            )
        ):
            sc = deterministic_coupling_score(
                coupling_type="DIVERSIFICATION_MATCH",
                signal_strength=sig_strength_u,
                portfolio_fit_score=pf,
                duplication_overlap_penalty=dup_penalty,
                liquidity_alignment_bonus=4 if liquidity_deficit else 0,
                concentration_alignment_bonus=7,
            )
            edges.append(
                {
                    "candidate_id": cand_id,
                    "market_acquisition_opportunity_item_id": opp_item_id,
                    "portfolio_item_id": default_pid(),
                    "coupling_type": "DIVERSIFICATION_MATCH",
                    "coupling_strength": sig_strength_u,
                    "coupling_score": sc,
                    "explanation_json": _json_safe(
                        {
                            "reason": "publisher_not_overexposed",
                            "publisher_slug": pub_slug_c,
                            "exposure_anchor_date": snapshot_date.isoformat(),
                            "signal_type": sig_type,
                        },
                    ),
                },
            )

        if (
            sig_type == "CONCENTRATION_REDUCTION"
            and pub_slug_c in overexposed_pub_keys
            and not has_edge(
                "CONCENTRATION_MATCH",
            )
        ):
            pivot_line = first_line_by_publisher(pub_slug_c)
            pivot = pivot_line.portfolio_item_id if pivot_line else default_pid()
            sc = deterministic_coupling_score(
                coupling_type="CONCENTRATION_MATCH",
                signal_strength=sig_strength_u,
                portfolio_fit_score=pf,
                duplication_overlap_penalty=dup_penalty,
                liquidity_alignment_bonus=5 if liquidity_deficit else 0,
                concentration_alignment_bonus=11,
            )
            edges.append(
                {
                    "candidate_id": cand_id,
                    "market_acquisition_opportunity_item_id": opp_item_id,
                    "portfolio_item_id": pivot,
                    "coupling_type": "CONCENTRATION_MATCH",
                    "coupling_strength": sig_strength_u,
                    "coupling_score": sc,
                    "explanation_json": _json_safe(
                        {
                            "reason": "publisher_overexposed_bucket",
                            "publisher_slug": pub_slug_c,
                            "signal_type": sig_type,
                        },
                    ),
                },
            )

    edges.sort(key=_edge_sort_key)
    return edges


def _summarize_opp_snap(opportunity_snap: MarketAcquisitionOpportunitySnapshot) -> dict[str, Any]:
    return {
        "id": int(opportunity_snap.id or 0),
        "checksum": opportunity_snap.snapshot_checksum,
        "total_candidates": opportunity_snap.total_candidates,
        "total_signals": opportunity_snap.total_signals,
    }


def _derive_metrics_from_edges(
    edge_payloads: list[dict[str, Any]],
    *,
    opp_items_count: int,
    scores_by_candidate: dict[int, MarketAcquisitionScore],
    candidates: dict[int, MarketAcquisitionNormalizedCandidate],
    opp_item_candidate_map: dict[int, int],
) -> dict[str, Any]:
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for e in edge_payloads:
        buckets[int(e["market_acquisition_opportunity_item_id"])].append(e)

    aligned = 0
    high_fit = 0
    low_fit = 0

    for oid in sorted(opp_item_candidate_map.keys()):
        evs = buckets.get(oid, [])
        pos = [x for x in evs if x["coupling_type"] != "CONCENTRATION_CONFLICT"]
        if pos:
            aligned += 1
            strengths = [str(x["coupling_strength"]).upper() for x in pos]
            if any(s in {"ELITE", "HIGH"} for s in strengths):
                high_fit += 1
            elif all(s == "LOW" for s in strengths):
                low_fit += 1

    misaligned = max(0, opp_items_count - aligned)

    non_conflict_scores = [
        Decimal(int(x["coupling_score"]))
        for x in edge_payloads
        if x["coupling_type"] != "CONCENTRATION_CONFLICT"
    ]
    conflict_scores = [
        Decimal(int(x["coupling_score"]))
        for x in edge_payloads
        if x["coupling_type"] == "CONCENTRATION_CONFLICT"
    ]

    def avg(xs: list[Decimal]) -> Decimal | None:
        if not xs:
            return None
        return (sum(xs, ZERO) / Decimal(len(xs))).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    def avg_for(ctype: str) -> Decimal | None:
        scores = [
            Decimal(int(x["coupling_score"])) for x in edge_payloads if x["coupling_type"] == ctype
        ]
        return avg(scores)

    portfolio_alignment = avg(non_conflict_scores)
    div_gap = avg_for("DIVERSIFICATION_MATCH")
    liq_gap = avg_for("LIQUIDITY_MATCH")
    concentration_offset: Decimal | None = None
    if conflict_scores:
        concentration_offset = (
            -sum(conflict_scores, ZERO) / Decimal(len(conflict_scores))
        ).quantize(
            Decimal("0.0001"),
            rounding=ROUND_HALF_UP,
        )

    signal_coverage = (
        (Decimal(aligned) / Decimal(opp_items_count)).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
        if opp_items_count > 0
        else None
    )

    scored_fit = sum(1 for cid in opp_item_candidate_map.values() if cid in scores_by_candidate)
    scoring_cov = (
        (Decimal(scored_fit) / Decimal(opp_items_count)).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
        if opp_items_count > 0
        else None
    )

    norm_ok = 0
    total_cands = 0
    for cid in set(opp_item_candidate_map.values()):
        cnd = candidates.get(cid)
        total_cands += 1
        if cnd is not None and str(cnd.normalization_status) == "SUCCESS":
            norm_ok += 1
    norm_cov = (
        (Decimal(norm_ok) / Decimal(total_cands)).quantize(
            Decimal("0.00000001"), rounding=ROUND_HALF_UP
        )
        if total_cands > 0
        else None
    )

    return {
        "aligned_opportunity_count": aligned,
        "misaligned_opportunity_count": misaligned,
        "high_fit_market_items": high_fit,
        "low_fit_market_items": low_fit,
        "portfolio_market_alignment_score": portfolio_alignment,
        "diversification_gap_alignment_score": div_gap,
        "liquidity_gap_alignment_score": liq_gap,
        "concentration_offset_score": concentration_offset,
        "signal_coverage_ratio": signal_coverage,
        "scoring_coverage_ratio": scoring_cov,
        "normalization_coverage_ratio": norm_cov,
    }


def generate_coupling_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    payload: PortfolioMarketCouplingGeneratePayload | None,
) -> PortfolioMarketCouplingGenerateResponse:
    resolved_payload = payload or PortfolioMarketCouplingGeneratePayload(
        opportunity_snapshot_id=None
    )
    opportunity_snapshot_id = resolved_payload.opportunity_snapshot_id

    if opportunity_snapshot_id is None:
        row = session.exec(
            select(MarketAcquisitionOpportunitySnapshot)
            .where(
                MarketAcquisitionOpportunitySnapshot.owner_user_id == owner_user_id,
            )
            .order_by(
                col(MarketAcquisitionOpportunitySnapshot.snapshot_date).desc(),
                col(MarketAcquisitionOpportunitySnapshot.id).desc(),
            ),
        ).first()
        if row is None:
            raise HTTPException(
                status_code=404, detail="Market opportunity snapshot not found for coupling."
            )
        opportunity_snap = row
    else:
        opportunity_snap = session.get(
            MarketAcquisitionOpportunitySnapshot, opportunity_snapshot_id
        )
        if opportunity_snap is None:
            raise HTTPException(status_code=404, detail="Market opportunity snapshot not found.")
        if int(opportunity_snap.owner_user_id or -1) != owner_user_id:
            raise HTTPException(status_code=404, detail="Market opportunity snapshot not found.")

    opp_items = session.exec(
        select(MarketAcquisitionOpportunityItem)
        .where(
            MarketAcquisitionOpportunityItem.market_acquisition_opportunity_snapshot_id
            == int(opportunity_snap.id or 0),
            MarketAcquisitionOpportunityItem.owner_user_id == owner_user_id,
        )
        .order_by(col(MarketAcquisitionOpportunityItem.id).asc()),
    ).all()
    if not opp_items:
        raise HTTPException(
            status_code=400, detail="Opportunity snapshot has no items for coupling."
        )

    cand_ids = [int(it.candidate_id) for it in opp_items]
    sig_ids = [int(it.market_acquisition_signal_id) for it in opp_items]

    candidates_map = {
        int(row.id or 0): row
        for row in session.exec(
            select(MarketAcquisitionNormalizedCandidate).where(
                col(MarketAcquisitionNormalizedCandidate.id).in_(list(set(cand_ids))),
            ),
        ).all()
    }
    signals_map = {
        int(row.id or 0): row
        for row in session.exec(
            select(MarketAcquisitionSignal).where(
                col(MarketAcquisitionSignal.id).in_(list(set(sig_ids)))
            )
        ).all()
    }

    opp_item_candidate_map = {int(it.id or 0): int(it.candidate_id) for it in opp_items}

    sd = opportunity_snap.snapshot_date
    scores_by_candidate = _pick_latest_score_row(
        session,
        owner_user_id=owner_user_id,
        normalized_candidate_ids=cand_ids,
        snapshot_date=sd,
    )

    portfolio_lines = _load_portfolio_lines(session, owner_user_id=owner_user_id)
    total_value, total_items_owned = _portfolio_aggregate(session, owner_user_id=owner_user_id)
    diversification, concentration = _concentration_rollup(
        session, owner_user_id=owner_user_id, as_of=sd
    )
    liquidity_eff = _liquidity_efficiency(session, owner_user_id=owner_user_id, as_of_date=sd)

    ov_pub = _publisher_overexposed_keys(session, owner_user_id=owner_user_id, as_of_date=sd)

    edge_payloads = _build_edges(
        opportunity_items=list(opp_items),
        candidates=candidates_map,
        signals=signals_map,
        scores_by_candidate=scores_by_candidate,
        portfolio_lines=portfolio_lines,
        overexposed_pub_keys=ov_pub,
        liquidity_efficiency=liquidity_eff,
        snapshot_date=sd,
    )

    coupling_checksum_payload = {
        "opportunity_snapshot": _summarize_opp_snap(opportunity_snap),
        "portfolio_anchor": {
            "total_inventory_items": total_items_owned,
            "lines": sorted(ln.portfolio_item_id for ln in portfolio_lines),
        },
        "edges": [_json_safe(e) for e in edge_payloads],
    }
    chk = _hash_payload(coupling_checksum_payload)

    dup_row = session.exec(
        select(PortfolioMarketCouplingSnapshot).where(
            PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id,
            PortfolioMarketCouplingSnapshot.market_acquisition_opportunity_snapshot_id
            == int(opportunity_snap.id or 0),
            PortfolioMarketCouplingSnapshot.snapshot_checksum == chk,
        ),
    ).first()
    if dup_row is not None:
        counted = session.exec(
            select(func.count(PortfolioMarketCouplingEdge.id)).where(
                PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id
                == int(dup_row.id or 0),
            ),
        ).first()
        if counted is None:
            ct = 0
        elif isinstance(counted, tuple):
            ct = int(counted[0])
        else:
            ct = int(counted)
        return PortfolioMarketCouplingGenerateResponse(
            replayed=True,
            snapshot=snapshot_to_read(dup_row),
            total_edges=ct,
        )

    metrics = _derive_metrics_from_edges(
        edge_payloads,
        opp_items_count=len(opp_items),
        scores_by_candidate=scores_by_candidate,
        candidates=candidates_map,
        opp_item_candidate_map=opp_item_candidate_map,
    )

    snap_row = PortfolioMarketCouplingSnapshot(
        owner_user_id=owner_user_id,
        market_acquisition_opportunity_snapshot_id=int(opportunity_snap.id or 0),
        portfolio_total_value=total_value,
        portfolio_total_items=total_items_owned,
        portfolio_diversification_score=diversification,
        portfolio_concentration_score=concentration,
        portfolio_liquidity_score=liquidity_eff,
        market_opportunity_count=len(opp_items),
        aligned_opportunity_count=int(metrics["aligned_opportunity_count"]),
        misaligned_opportunity_count=int(metrics["misaligned_opportunity_count"]),
        high_fit_market_items=int(metrics["high_fit_market_items"]),
        low_fit_market_items=int(metrics["low_fit_market_items"]),
        portfolio_market_alignment_score=metrics["portfolio_market_alignment_score"],
        diversification_gap_alignment_score=metrics["diversification_gap_alignment_score"],
        liquidity_gap_alignment_score=metrics["liquidity_gap_alignment_score"],
        concentration_offset_score=metrics["concentration_offset_score"],
        signal_coverage_ratio=metrics["signal_coverage_ratio"],
        scoring_coverage_ratio=metrics["scoring_coverage_ratio"],
        normalization_coverage_ratio=metrics["normalization_coverage_ratio"],
        snapshot_checksum=chk,
        snapshot_date=sd,
    )
    session.add(snap_row)
    session.flush()

    dup_edges = sum(1 for row in edge_payloads if row["coupling_type"] == "CONCENTRATION_CONFLICT")
    evidences_payloads: list[tuple[str, dict[str, Any]]] = [
        (
            "PORTFOLIO_STATE",
            _json_safe(
                {
                    "portfolio_total_items": total_items_owned,
                    "portfolio_line_count": len(portfolio_lines),
                    "diversification_score": str(diversification)
                    if diversification is not None
                    else None,
                    "concentration_score": str(concentration)
                    if concentration is not None
                    else None,
                    "liquidity_efficiency_hint": str(liquidity_eff)
                    if liquidity_eff is not None
                    else None,
                    "portfolio_total_value": str(total_value) if total_value is not None else None,
                },
            ),
        ),
        (
            "MARKET_SIGNAL",
            _json_safe(
                {
                    "opportunity_snapshot_id": int(opportunity_snap.id or 0),
                    "opportunity_checksum": opportunity_snap.snapshot_checksum,
                    "signals_in_items": sorted(set(sig_ids)),
                },
            ),
        ),
        (
            "MARKET_SCORE",
            _json_safe(
                {
                    "score_snapshot_date": sd.isoformat(),
                    "scored_candidate_ids": sorted(scores_by_candidate.keys()),
                    "opp_items": sorted(opp_item_candidate_map.keys()),
                },
            ),
        ),
        (
            "NORMALIZED_CANDIDATE",
            _json_safe(
                {
                    "distinct_candidates": sorted(set(cand_ids)),
                    "normalization_success": sum(
                        1
                        for cid in sorted(set(cand_ids))
                        if candidates_map.get(cid)
                        and str(candidates_map[cid].normalization_status) == "SUCCESS"  # noqa: E501
                    ),
                    "normalization_status_flags": sorted(
                        {
                            str(candidates_map[cid].normalization_status)
                            for cid in cand_ids
                            if candidates_map.get(cid)
                        },
                    ),
                },
            ),
        ),
        ("DUPLICATE_INTELLIGENCE", _json_safe({"concentration_conflict_edges": dup_edges})),
        (
            "CONCENTRATION_RISK",
            _json_safe(
                {"overexposed_publisher_slugs": sorted(ov_pub), "snapshot_date": sd.isoformat()}
            ),
        ),
    ]

    for etype, ejson in evidences_payloads:
        session.add(
            PortfolioMarketCouplingEvidence(
                portfolio_market_coupling_snapshot_id=int(snap_row.id or 0),
                evidence_type=etype,
                source_id=int(opportunity_snap.id or 0),
                source_table="market_acquisition_opportunity_snapshot",
                evidence_value_json=ejson if isinstance(ejson, dict) else {},
            ),
        )

    for row in edge_payloads:
        session.add(
            PortfolioMarketCouplingEdge(
                portfolio_market_coupling_snapshot_id=int(snap_row.id or 0),
                market_normalized_candidate_id=int(row["candidate_id"]),
                market_acquisition_opportunity_item_id=int(
                    row["market_acquisition_opportunity_item_id"]
                ),
                portfolio_item_id=row["portfolio_item_id"],
                coupling_type=str(row["coupling_type"]),
                coupling_strength=str(row["coupling_strength"]),
                coupling_score=int(row["coupling_score"]),
                explanation_json=row["explanation_json"]
                if isinstance(row["explanation_json"], dict)
                else {},
            ),
        )

    session.add(
        PortfolioMarketCouplingHistory(
            owner_user_id=owner_user_id,
            portfolio_market_coupling_snapshot_id=int(snap_row.id or 0),
            snapshot_checksum=chk,
            alignment_score=snap_row.portfolio_market_alignment_score,
            market_opportunity_count=len(opp_items),
            high_fit_market_items=snap_row.high_fit_market_items,
            snapshot_date=sd,
        ),
    )
    append_market_feed_event(
        session,
        owner_user_id=owner_user_id,
        event_type="COUPLING_GENERATED",
        severity="WARNING" if snap_row.misaligned_opportunity_count > 0 else "INFO",
        snapshot_date=sd,
        event_payload_json={
            "coupling_snapshot_id": int(snap_row.id or 0),
            "opportunity_snapshot_id": int(snap_row.market_acquisition_opportunity_snapshot_id or 0),
            "snapshot_checksum": chk,
            "market_opportunity_count": len(opp_items),
            "aligned_opportunity_count": int(snap_row.aligned_opportunity_count),
            "misaligned_opportunity_count": int(snap_row.misaligned_opportunity_count),
            "high_fit_market_items": int(snap_row.high_fit_market_items),
            "low_fit_market_items": int(snap_row.low_fit_market_items),
        },
        coupling_snapshot_id=int(snap_row.id or 0),
        opportunity_snapshot_id=int(snap_row.market_acquisition_opportunity_snapshot_id or 0),
    )
    append_market_feed_event(
        session,
        owner_user_id=owner_user_id,
        event_type="SNAPSHOT_CREATED",
        severity="INFO",
        snapshot_date=sd,
        event_payload_json={
            "layer": "coupling",
            "coupling_snapshot_id": int(snap_row.id or 0),
            "snapshot_checksum": chk,
        },
        coupling_snapshot_id=int(snap_row.id or 0),
    )
    session.commit()
    session.refresh(snap_row)
    return PortfolioMarketCouplingGenerateResponse(
        replayed=False,
        snapshot=snapshot_to_read(snap_row),
        total_edges=len(edge_payloads),
    )


def _assert_coupling_owner(
    session: Session, *, owner_user_id: int, snapshot_id: int
) -> PortfolioMarketCouplingSnapshot:
    row = session.get(PortfolioMarketCouplingSnapshot, snapshot_id)
    if row is None or int(row.owner_user_id) != owner_user_id:
        raise HTTPException(status_code=404, detail="Portfolio market coupling snapshot not found.")
    return row


def get_coupling_detail_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_id: int,
) -> PortfolioMarketCouplingDetailRead:
    snap = _assert_coupling_owner(session, owner_user_id=owner_user_id, snapshot_id=snapshot_id)

    edges = session.exec(
        select(PortfolioMarketCouplingEdge)
        .where(
            PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id == int(snap.id or 0)
        )
        .order_by(
            PortfolioMarketCouplingEdge.market_normalized_candidate_id.asc(),
            PortfolioMarketCouplingEdge.portfolio_item_id.asc(),
            PortfolioMarketCouplingEdge.coupling_type.asc(),
            PortfolioMarketCouplingEdge.market_acquisition_opportunity_item_id.asc(),
            col(PortfolioMarketCouplingEdge.id).asc(),
        ),
    ).all()

    evidence = session.exec(
        select(PortfolioMarketCouplingEvidence)
        .where(
            PortfolioMarketCouplingEvidence.portfolio_market_coupling_snapshot_id
            == int(snap.id or 0),
        )
        .order_by(
            PortfolioMarketCouplingEvidence.evidence_type.asc(),
            col(PortfolioMarketCouplingEvidence.id).asc(),
        ),
    ).all()

    return PortfolioMarketCouplingDetailRead(
        snapshot=snapshot_to_read(snap),
        edges=[edge_to_read(e) for e in edges],
        evidence=[evidence_to_read(ev) for ev in evidence],
    )


def get_coupling_detail_ops(
    session: Session,
    *,
    snapshot_id: int,
    owner_filter: int | None,
) -> PortfolioMarketCouplingDetailRead:
    snap = session.get(PortfolioMarketCouplingSnapshot, snapshot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Portfolio market coupling snapshot not found.")
    if owner_filter is not None and int(snap.owner_user_id) != owner_filter:
        raise HTTPException(status_code=404, detail="Portfolio market coupling snapshot not found.")
    owner_user_id_int = int(snap.owner_user_id)
    return get_coupling_detail_owner(
        session, owner_user_id=owner_user_id_int, snapshot_id=snapshot_id
    )


def list_coupling_snapshots_owner(
    session: Session,
    *,
    owner_user_id: int,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    min_alignment_score: Decimal | None,
    limit: int,
    offset: int,
) -> PortfolioMarketCouplingSnapshotListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    filt = [PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id]
    if snapshot_date_from is not None:
        filt.append(col(PortfolioMarketCouplingSnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to is not None:
        filt.append(col(PortfolioMarketCouplingSnapshot.snapshot_date) <= snapshot_date_to)
    if min_alignment_score is not None:
        filt.append(
            col(PortfolioMarketCouplingSnapshot.portfolio_market_alignment_score)
            >= min_alignment_score
        )

    count_stmt = select(func.count()).select_from(PortfolioMarketCouplingSnapshot).where(*filt)
    count_row = session.exec(count_stmt).first()
    if count_row is None:
        total = 0
    elif isinstance(count_row, tuple):
        total = int(count_row[0])
    else:
        total = int(count_row)

    stmt = (
        select(PortfolioMarketCouplingSnapshot)
        .where(*filt)
        .order_by(
            col(PortfolioMarketCouplingSnapshot.snapshot_date).desc(),
            col(PortfolioMarketCouplingSnapshot.id).desc(),
        )
        .offset(off)
        .limit(lim)
    )
    page = session.exec(stmt).all()
    return PortfolioMarketCouplingSnapshotListResponse(
        total_items=total,
        items=[snapshot_to_read(row) for row in page],
        limit=lim,
        offset=off,
    )


def list_coupling_snapshots_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    min_alignment_score: Decimal | None,
    limit: int,
    offset: int,
) -> PortfolioMarketCouplingSnapshotListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    filt = []
    if owner_user_id is not None:
        filt.append(PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id)
    if snapshot_date_from is not None:
        filt.append(col(PortfolioMarketCouplingSnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to is not None:
        filt.append(col(PortfolioMarketCouplingSnapshot.snapshot_date) <= snapshot_date_to)
    if min_alignment_score is not None:
        filt.append(
            col(PortfolioMarketCouplingSnapshot.portfolio_market_alignment_score)
            >= min_alignment_score
        )

    count_stmt = select(func.count()).select_from(PortfolioMarketCouplingSnapshot)
    if filt:
        count_stmt = count_stmt.where(*filt)

    count_row = session.exec(count_stmt).first()
    if count_row is None:
        total = 0
    elif isinstance(count_row, tuple):
        total = int(count_row[0])
    else:
        total = int(count_row)

    stmt = select(PortfolioMarketCouplingSnapshot)
    if filt:
        stmt = stmt.where(*filt)
    stmt = (
        stmt.order_by(
            col(PortfolioMarketCouplingSnapshot.snapshot_date).desc(),
            col(PortfolioMarketCouplingSnapshot.id).desc(),
        )
        .offset(off)
        .limit(lim)
    )
    page = session.exec(stmt).all()
    return PortfolioMarketCouplingSnapshotListResponse(
        total_items=total,
        items=[snapshot_to_read(row) for row in page],
        limit=lim,
        offset=off,
    )


def list_coupling_edges_owner(
    session: Session,
    *,
    owner_user_id: int,
    coupling_snapshot_id: int | None,
    coupling_type: str | None,
    coupling_strength: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    min_coupling_score: int | None,
    limit: int,
    offset: int,
) -> PortfolioMarketCouplingEdgeListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)

    stmt = (
        select(PortfolioMarketCouplingEdge)
        .join(
            PortfolioMarketCouplingSnapshot,
            PortfolioMarketCouplingSnapshot.id
            == PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id,
        )
        .where(PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id)
    )
    if coupling_snapshot_id is not None:
        stmt = stmt.where(
            PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id
            == coupling_snapshot_id,
        )
    if coupling_type is not None:
        stmt = stmt.where(PortfolioMarketCouplingEdge.coupling_type == coupling_type)
    if coupling_strength is not None:
        stmt = stmt.where(PortfolioMarketCouplingEdge.coupling_strength == coupling_strength)
    if snapshot_date_from is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) <= snapshot_date_to)
    if min_coupling_score is not None:
        stmt = stmt.where(PortfolioMarketCouplingEdge.coupling_score >= min_coupling_score)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_row = session.exec(count_stmt).first()
    total = (
        0
        if count_row is None
        else int(count_row[0])
        if isinstance(count_row, tuple)
        else int(count_row)
    )

    ordered = (
        stmt.order_by(
            PortfolioMarketCouplingEdge.market_normalized_candidate_id.asc(),
            PortfolioMarketCouplingEdge.portfolio_item_id.asc(),
            PortfolioMarketCouplingEdge.coupling_type.asc(),
            PortfolioMarketCouplingEdge.market_acquisition_opportunity_item_id.asc(),
            col(PortfolioMarketCouplingEdge.id).asc(),
        )
        .offset(off)
        .limit(lim)
    )

    rows = session.exec(ordered).all()
    return PortfolioMarketCouplingEdgeListResponse(
        total_items=total,
        items=[edge_to_read(r) for r in rows],
        limit=lim,
        offset=off,
    )


def list_coupling_edges_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    coupling_snapshot_id: int | None,
    coupling_type: str | None,
    coupling_strength: str | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    min_coupling_score: int | None,
    limit: int,
    offset: int,
) -> PortfolioMarketCouplingEdgeListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioMarketCouplingEdge).join(
        PortfolioMarketCouplingSnapshot,
        PortfolioMarketCouplingSnapshot.id
        == PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id)
    if coupling_snapshot_id is not None:
        stmt = stmt.where(
            PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id
            == coupling_snapshot_id,
        )
    if coupling_type is not None:
        stmt = stmt.where(PortfolioMarketCouplingEdge.coupling_type == coupling_type)
    if coupling_strength is not None:
        stmt = stmt.where(PortfolioMarketCouplingEdge.coupling_strength == coupling_strength)
    if snapshot_date_from is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) <= snapshot_date_to)
    if min_coupling_score is not None:
        stmt = stmt.where(PortfolioMarketCouplingEdge.coupling_score >= min_coupling_score)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_row = session.exec(count_stmt).first()
    total = (
        0
        if count_row is None
        else int(count_row[0])
        if isinstance(count_row, tuple)
        else int(count_row)
    )

    ordered = (
        stmt.order_by(
            PortfolioMarketCouplingSnapshot.owner_user_id.asc(),
            PortfolioMarketCouplingEdge.market_normalized_candidate_id.asc(),
            PortfolioMarketCouplingEdge.portfolio_item_id.asc(),
            PortfolioMarketCouplingEdge.coupling_type.asc(),
            PortfolioMarketCouplingEdge.market_acquisition_opportunity_item_id.asc(),
            col(PortfolioMarketCouplingEdge.id).asc(),
        )
        .offset(off)
        .limit(lim)
    )

    rows = session.exec(ordered).all()
    return PortfolioMarketCouplingEdgeListResponse(
        total_items=total,
        items=[edge_to_read(r) for r in rows],
        limit=lim,
        offset=off,
    )


def list_coupling_history_owner(
    session: Session,
    *,
    owner_user_id: int,
    coupling_snapshot_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    min_alignment_score: Decimal | None,
    limit: int,
    offset: int,
) -> PortfolioMarketCouplingHistoryListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)

    stmt = (
        select(PortfolioMarketCouplingHistory)
        .join(
            PortfolioMarketCouplingSnapshot,
            PortfolioMarketCouplingSnapshot.id
            == PortfolioMarketCouplingHistory.portfolio_market_coupling_snapshot_id,
        )
        .where(PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id)
    )
    if coupling_snapshot_id is not None:
        stmt = stmt.where(
            PortfolioMarketCouplingHistory.portfolio_market_coupling_snapshot_id
            == coupling_snapshot_id,
        )
    if snapshot_date_from is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) <= snapshot_date_to)
    if min_alignment_score is not None:
        stmt = stmt.where(
            col(PortfolioMarketCouplingSnapshot.portfolio_market_alignment_score)
            >= min_alignment_score
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_row = session.exec(count_stmt).first()
    total = (
        0
        if count_row is None
        else int(count_row[0])
        if isinstance(count_row, tuple)
        else int(count_row)
    )

    ordered = (
        stmt.order_by(
            col(PortfolioMarketCouplingSnapshot.snapshot_date).desc(),
            col(PortfolioMarketCouplingHistory.id).desc(),
        )
        .offset(off)
        .limit(lim)
    )
    rows = session.exec(ordered).all()
    return PortfolioMarketCouplingHistoryListResponse(
        total_items=total,
        items=[history_to_read(r) for r in rows],
        limit=lim,
        offset=off,
    )


def list_coupling_history_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    coupling_snapshot_id: int | None,
    snapshot_date_from: date | None,
    snapshot_date_to: date | None,
    min_alignment_score: Decimal | None,
    limit: int,
    offset: int,
) -> PortfolioMarketCouplingHistoryListResponse:
    lim, off = clamp_pagination(limit=limit, offset=offset)
    stmt = select(PortfolioMarketCouplingHistory).join(
        PortfolioMarketCouplingSnapshot,
        PortfolioMarketCouplingSnapshot.id
        == PortfolioMarketCouplingHistory.portfolio_market_coupling_snapshot_id,
    )
    if owner_user_id is not None:
        stmt = stmt.where(PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id)
    if coupling_snapshot_id is not None:
        stmt = stmt.where(
            PortfolioMarketCouplingHistory.portfolio_market_coupling_snapshot_id
            == coupling_snapshot_id,
        )
    if snapshot_date_from is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) >= snapshot_date_from)
    if snapshot_date_to is not None:
        stmt = stmt.where(col(PortfolioMarketCouplingSnapshot.snapshot_date) <= snapshot_date_to)
    if min_alignment_score is not None:
        stmt = stmt.where(
            col(PortfolioMarketCouplingSnapshot.portfolio_market_alignment_score)
            >= min_alignment_score
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    count_row = session.exec(count_stmt).first()
    total = (
        0
        if count_row is None
        else int(count_row[0])
        if isinstance(count_row, tuple)
        else int(count_row)
    )

    ordered = (
        stmt.order_by(
            PortfolioMarketCouplingSnapshot.owner_user_id.asc(),
            col(PortfolioMarketCouplingSnapshot.snapshot_date).desc(),
            col(PortfolioMarketCouplingHistory.id).desc(),
        )
        .offset(off)
        .limit(lim)
    )
    rows = session.exec(ordered).all()
    return PortfolioMarketCouplingHistoryListResponse(
        total_items=total,
        items=[history_to_read(r) for r in rows],
        limit=lim,
        offset=off,
    )


def inventory_portfolio_market_coupling_teaser(
    session: Session,
    *,
    owner_user_id: int,
    inventory_copy_id: int,
) -> InventoryPortfolioMarketCouplingTeaserRead | None:
    snap = session.exec(
        select(PortfolioMarketCouplingSnapshot)
        .where(PortfolioMarketCouplingSnapshot.owner_user_id == owner_user_id)
        .order_by(
            col(PortfolioMarketCouplingSnapshot.snapshot_date).desc(),
            col(PortfolioMarketCouplingSnapshot.id).desc(),
        ),
    ).first()
    if snap is None:
        return None

    pids = session.exec(
        select(PortfolioItem.id).where(
            PortfolioItem.inventory_item_id == inventory_copy_id,
            PortfolioItem.removed_at.is_(None),
        ),
    ).all()
    portfolio_item_ids = [int(r) for r in pids]

    conflicts = 0
    if portfolio_item_ids:
        c_raw = session.exec(
            select(func.count(PortfolioMarketCouplingEdge.id)).where(
                PortfolioMarketCouplingEdge.portfolio_market_coupling_snapshot_id
                == int(snap.id or 0),
                PortfolioMarketCouplingEdge.portfolio_item_id.in_(portfolio_item_ids),
                PortfolioMarketCouplingEdge.coupling_type == "CONCENTRATION_CONFLICT",
            ),
        ).first()
        if c_raw is not None:
            conflicts = int(c_raw[0]) if isinstance(c_raw, tuple) else int(c_raw)

    return InventoryPortfolioMarketCouplingTeaserRead(
        coupling_snapshot_id=int(snap.id or 0),
        portfolio_market_alignment_score=snap.portfolio_market_alignment_score,
        high_fit_market_items=int(snap.high_fit_market_items),
        concentration_conflicts=conflicts,
        snapshot_date=snap.snapshot_date,
        snapshot_checksum=str(snap.snapshot_checksum),
    )
