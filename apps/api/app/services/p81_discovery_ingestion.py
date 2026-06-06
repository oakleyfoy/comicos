"""P81-01 ingest discovery candidates from P50/P74 and external catalog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogCreator, ExternalCatalogIssue, ExternalCatalogVariant
from app.models.p81_discovery import P81DiscoveryOpportunity, utc_now
from app.models.release_event_history import P74_CHANGE_NEW_VARIANT, P74ReleaseChangeRecord
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.services.p81_discovery_scoring import P81ScoreInput, category_for_score, score_discovery_opportunity

_INGEST_HORIZON_DAYS = 120


@dataclass
class _Candidate:
    opportunity_key: str
    opportunity_type: str
    title: str
    summary: str
    publisher: str
    series_name: str
    issue_number: str
    variant_label: str
    release_date: date | None
    source_type: str
    source_ref_id: int | None
    release_issue_id: int | None
    external_catalog_issue_id: int | None
    creators: list[str]


def _norm_key(*parts: str) -> str:
    return "|".join(p.strip().lower()[:80] for p in parts if p is not None)


def _is_future(d: date | None, *, today: date) -> bool:
    return d is not None and d >= today


def _candidates_from_releases(session: Session, *, owner_user_id: int, today: date) -> list[_Candidate]:
    horizon = today + timedelta(days=_INGEST_HORIZON_DAYS)
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(ReleaseIssue.release_date.is_not(None))
        .where(ReleaseIssue.release_date >= today)
        .where(ReleaseIssue.release_date <= horizon)
    ).all()
    out: list[_Candidate] = []
    for issue, series in rows:
        num = (issue.issue_number or "").strip().lstrip("#")
        title = issue.title or f"{series.series_name} #{issue.issue_number}"
        base = _Candidate(
            opportunity_key=_norm_key("release", series.publisher, series.series_name, issue.issue_number, ""),
            opportunity_type="NEW_1" if num == "1" else "MILESTONE",
            title=title,
            summary=issue.title or "",
            publisher=series.publisher,
            series_name=series.series_name,
            issue_number=issue.issue_number,
            variant_label="",
            release_date=issue.release_date,
            source_type="LUNAR",
            source_ref_id=int(issue.id or 0),
            release_issue_id=int(issue.id or 0),
            external_catalog_issue_id=None,
            creators=[],
        )
        if num == "1":
            base.opportunity_type = "NEW_1"
            out.append(base)
            if series.series_type.upper() in {"NEW", "ONGOING", "LIMITED"}:
                series_c = _Candidate(
                    **{**base.__dict__, "opportunity_type": "NEW_SERIES", "opportunity_key": _norm_key("series", series.publisher, series.series_name, "1", "")}
                )
                out.append(series_c)
        try:
            n = int(float(num))
            if n in {100, 200, 300, 500, 1000}:
                mile = _Candidate(
                    **{**base.__dict__, "opportunity_type": "MILESTONE", "opportunity_key": _norm_key("milestone", series.publisher, series.series_name, issue.issue_number, "")}
                )
                out.append(mile)
        except ValueError:
            pass
        blob = (issue.title or "").lower()
        if "anniversary" in blob:
            ann = _Candidate(
                **{**base.__dict__, "opportunity_type": "ANNIVERSARY", "opportunity_key": _norm_key("anniversary", series.publisher, series.series_name, issue.issue_number, "")}
            )
            out.append(ann)

    signals = session.exec(
        select(ReleaseKeySignal, ReleaseIssue, ReleaseSeries)
        .join(ReleaseIssue, ReleaseKeySignal.issue_id == ReleaseIssue.id)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseKeySignal.owner_user_id == owner_user_id)
        .order_by(ReleaseKeySignal.created_at.desc())
        .limit(40)
    ).all()
    for signal, issue, series in signals:
        payload = signal.signal_payload_json or {}
        creators = [str(payload.get("creator") or payload.get("creator_name") or "")]
        ctype = "CREATOR_PROJECT" if "CREATOR" in signal.signal_type.upper() else "NEW_1"
        out.append(
            _Candidate(
                opportunity_key=_norm_key("signal", signal.signal_type, str(issue.id), ""),
                opportunity_type=ctype,
                title=issue.title or f"{series.series_name} #{issue.issue_number}",
                summary=str(payload.get("summary") or ""),
                publisher=series.publisher,
                series_name=series.series_name,
                issue_number=issue.issue_number,
                variant_label="",
                release_date=issue.release_date,
                source_type="RELEASE_MONITORING",
                source_ref_id=int(signal.id or 0),
                release_issue_id=int(issue.id or 0),
                external_catalog_issue_id=None,
                creators=[c for c in creators if c],
            )
        )

    variant_changes = session.exec(
        select(P74ReleaseChangeRecord)
        .where(P74ReleaseChangeRecord.owner_user_id == owner_user_id)
        .where(P74ReleaseChangeRecord.change_type == P74_CHANGE_NEW_VARIANT)
        .order_by(P74ReleaseChangeRecord.detected_at.desc())
        .limit(30)
    ).all()
    for ch in variant_changes:
        after = ch.after_json or {}
        vname = str(after.get("variant_name") or "New variant")
        issue = session.get(ReleaseIssue, ch.issue_id) if ch.issue_id else None
        series = session.get(ReleaseSeries, issue.series_id) if issue and issue.series_id else None
        if issue is None or series is None:
            continue
        out.append(
            _Candidate(
                opportunity_key=_norm_key("variant", str(ch.issue_id), vname),
                opportunity_type="VARIANT_EXPANSION",
                title=f"{series.series_name} #{issue.issue_number} — {vname}",
                summary="New variant detected via release monitoring",
                publisher=series.publisher,
                series_name=series.series_name,
                issue_number=issue.issue_number,
                variant_label=vname,
                release_date=issue.release_date,
                source_type="RELEASE_MONITORING",
                source_ref_id=int(ch.id or 0),
                release_issue_id=int(issue.id or 0),
                external_catalog_issue_id=None,
                creators=[],
            )
        )

    for issue, series in rows:
        variants = session.exec(select(ReleaseVariant).where(ReleaseVariant.issue_id == int(issue.id or 0))).all()
        for var in variants:
            if var.ratio_value and var.ratio_value >= 25:
                label = var.variant_name or f"1:{var.ratio_value}"
                out.append(
                    _Candidate(
                        opportunity_key=_norm_key("ratio", str(issue.id), label),
                        opportunity_type="VARIANT_EXPANSION",
                        title=f"{series.series_name} #{issue.issue_number} — {label}",
                        summary="Incentive variant on upcoming release",
                        publisher=series.publisher,
                        series_name=series.series_name,
                        issue_number=issue.issue_number,
                        variant_label=label,
                        release_date=issue.release_date,
                        source_type="LUNAR",
                        source_ref_id=int(var.id or 0),
                        release_issue_id=int(issue.id or 0),
                        external_catalog_issue_id=None,
                        creators=[],
                    )
                )
    return out


def _candidates_from_external_catalog(session: Session, *, today: date) -> list[_Candidate]:
    since = today - timedelta(days=45)
    issues = session.exec(
        select(ExternalCatalogIssue)
        .where(ExternalCatalogIssue.release_date.is_not(None))
        .where(ExternalCatalogIssue.release_date >= today)
        .order_by(ExternalCatalogIssue.discovered_at.desc())
        .limit(200)
    ).all()
    out: list[_Candidate] = []
    for row in issues:
        if row.discovered_at and row.discovered_at.date() < since:
            continue
        creators = [
            c.creator_name
            for c in session.exec(
                select(ExternalCatalogCreator).where(ExternalCatalogCreator.external_issue_id == int(row.id or 0))
            ).all()
        ]
        otype = "NEW_1" if row.is_first_issue else "MILESTONE" if row.is_milestone_issue else "NEW_SERIES"
        if row.milestone_issue_number:
            otype = "MILESTONE"
        desc = (row.description or row.story_summary or "")[:500]
        if "anniversary" in (row.title + desc).lower():
            otype = "ANNIVERSARY"
        for cname in creators:
            if any(k in cname.lower() for k in ("johnson", "stegman", "hickman")):
                otype = "CREATOR_PROJECT"
                break
        variants = session.exec(
            select(ExternalCatalogVariant).where(ExternalCatalogVariant.external_issue_id == int(row.id or 0))
        ).all()
        variant_label = ""
        if variants:
            v = variants[0]
            if v.ratio_value and v.ratio_value >= 25:
                otype = "VARIANT_EXPANSION"
                variant_label = v.variant_name or f"1:{v.ratio_value}"
        out.append(
            _Candidate(
                opportunity_key=_norm_key("catalog", row.source_name, row.publisher, row.series_name, row.issue_number or "", variant_label),
                opportunity_type=otype,
                title=row.title or f"{row.series_name} {row.issue_number or ''}".strip(),
                summary=desc,
                publisher=row.publisher,
                series_name=row.series_name,
                issue_number=row.issue_number or "",
                variant_label=variant_label,
                release_date=row.release_date,
                source_type="EXTERNAL_CATALOG",
                source_ref_id=int(row.id or 0),
                release_issue_id=None,
                external_catalog_issue_id=int(row.id or 0),
                creators=creators[:5],
            )
        )
    return out


def ingest_discovery_opportunities(session: Session, *, owner_user_id: int) -> int:
    """Refresh registry from upstream sources; returns rows upserted."""
    today = date.today()
    candidates = _candidates_from_releases(session, owner_user_id=owner_user_id, today=today)
    candidates.extend(_candidates_from_external_catalog(session, today=today))

    existing = {
        row.opportunity_key: row
        for row in session.exec(
            select(P81DiscoveryOpportunity).where(P81DiscoveryOpportunity.owner_user_id == owner_user_id)
        ).all()
    }
    upserted = 0
    now = utc_now()
    for cand in candidates:
        if not cand.title:
            continue
        score, signals = score_discovery_opportunity(
            P81ScoreInput(
                opportunity_type=cand.opportunity_type,
                title=cand.title,
                summary=cand.summary,
                series_name=cand.series_name,
                issue_number=cand.issue_number,
                variant_label=cand.variant_label,
                publisher=cand.publisher,
                creators=cand.creators,
            )
        )
        category = category_for_score(score)
        row = existing.get(cand.opportunity_key)
        if row is None:
            row = P81DiscoveryOpportunity(
                owner_user_id=owner_user_id,
                opportunity_key=cand.opportunity_key,
                opportunity_type=cand.opportunity_type,
                registry_status="DISCOVERED",
                discovery_date=today,
                created_at=now,
            )
            existing[cand.opportunity_key] = row
        row.title = cand.title
        row.summary = cand.summary
        row.publisher = cand.publisher
        row.series_name = cand.series_name
        row.issue_number = cand.issue_number
        row.variant_label = cand.variant_label
        row.release_date = cand.release_date
        row.source_type = cand.source_type
        row.source_ref_id = cand.source_ref_id
        row.release_issue_id = cand.release_issue_id
        row.external_catalog_issue_id = cand.external_catalog_issue_id
        row.creator_metadata_json = {"creators": cand.creators}
        row.signals_json = signals
        row.discovery_score = score
        row.score_category = category
        row.registry_status = "QUALIFIED" if score >= 40 else "DISCOVERED"
        if score >= 50:
            row.registry_status = "SCORED"
        if category != "LOW_PRIORITY":
            row.registry_status = "PUBLISHED"
        row.updated_at = now
        session.add(row)
        upserted += 1
    session.flush()
    return upserted
