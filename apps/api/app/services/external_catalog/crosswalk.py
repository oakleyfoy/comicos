from __future__ import annotations

import re
from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogMatch
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.external_catalog.league_of_comic_geeks import LOCG_SOURCE_NAME
from app.services.external_catalog.normalization import build_normalized_title_key
from app.services.lunar_issue_identity import normalize_lunar_issue_number
from app.services.printing_intelligence import stamp_original_release_from_external

MATCH_MATCHED = "MATCHED_RELEASE_ISSUE"
MATCH_MISSING = "MISSING_FROM_LUNAR"
MATCH_DUPLICATE = "POSSIBLE_DUPLICATE"
MATCH_REVIEW = "NEEDS_REVIEW"

MILESTONE_NUMBERS = frozenset({25, 50, 75, 100, 150, 200, 300})
RELEASE_DATE_TOLERANCE_DAYS = 21


def _norm_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _issue_number_key(value: str | None) -> str:
    if not value:
        return ""
    return normalize_lunar_issue_number(value)


def _title_similarity(a: str, b: str) -> float:
    ta = set(_norm_text(a).split())
    tb = set(_norm_text(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _release_index(
    session: Session,
    *,
    owner_user_id: int,
) -> list[tuple[ReleaseIssue, ReleaseSeries]]:
    return list(
        session.exec(
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
        ).all()
    )


def match_external_to_release(
    external: ExternalCatalogIssue,
    candidates: list[tuple[ReleaseIssue, ReleaseSeries]],
    *,
    today: date,
    horizon_days: int = 90,
) -> tuple[str, int | None, float, str]:
    ext_pub = _norm_text(external.publisher)
    ext_series = _norm_text(external.series_name)
    ext_num = _issue_number_key(external.issue_number)
    ext_key = external.normalized_title_key

    best: tuple[float, ReleaseIssue | None, str] = (0.0, None, "")

    for issue, series in candidates:
        pub = _norm_text(series.publisher)
        series_name = _norm_text(series.series_name)
        num = _issue_number_key(issue.issue_number)
        score = 0.0
        reasons: list[str] = []

        if ext_pub and pub and ext_pub == pub:
            score += 0.25
            reasons.append("publisher")
        if ext_series and series_name and (ext_series in series_name or series_name in ext_series):
            score += 0.35
            reasons.append("series")
        elif _title_similarity(external.series_name, series.series_name) >= 0.6:
            score += 0.2
            reasons.append("series_fuzzy")
        if ext_num and num and ext_num == num:
            score += 0.3
            reasons.append("issue_number")

        if external.release_date and issue.release_date:
            delta = abs((external.release_date - issue.release_date).days)
            if delta <= RELEASE_DATE_TOLERANCE_DAYS:
                score += 0.15
                reasons.append("release_date")
            else:
                score -= 0.1

        release_key = build_normalized_title_key(
            publisher=series.publisher,
            series_name=series.series_name,
            issue_number=issue.issue_number,
        )
        if ext_key and release_key and ext_key == release_key:
            return MATCH_MATCHED, int(issue.id or 0), 0.95, "normalized_title_key"

        title_sim = _title_similarity(external.title, f"{series.series_name} {issue.title}")
        if title_sim >= 0.55:
            score += 0.1 * title_sim
            reasons.append("title_sim")

        if score > best[0]:
            best = (score, issue, ",".join(reasons))

    top_score, top_issue, reason = best
    if top_issue is None:
        in_horizon = (
            external.release_date is not None
            and today <= external.release_date <= today + timedelta(days=horizon_days)
        ) or (
            external.foc_date is not None
            and today <= external.foc_date <= today + timedelta(days=horizon_days)
        )
        if in_horizon:
            return MATCH_MISSING, None, 0.0, "no_release_issue_in_horizon"
        return MATCH_REVIEW, None, 0.0, "no_candidate"

    if top_score >= 0.82:
        return MATCH_MATCHED, int(top_issue.id or 0), min(top_score, 1.0), reason
    if top_score >= 0.65:
        return MATCH_REVIEW, int(top_issue.id or 0), top_score, reason

    in_horizon = (
        external.release_date is not None
        and today <= external.release_date <= today + timedelta(days=horizon_days)
    )
    if in_horizon:
        return MATCH_MISSING, None, top_score, f"weak_match:{reason}"
    return MATCH_REVIEW, None, top_score, f"weak_match:{reason}"


def rebuild_external_catalog_crosswalk(
    session: Session,
    *,
    owner_user_id: int,
    source_name: str = LOCG_SOURCE_NAME,
    horizon_days: int = 90,
) -> dict[str, int]:
    today = date.today()
    externals = session.exec(
        select(ExternalCatalogIssue).where(ExternalCatalogIssue.source_name == source_name)
    ).all()
    candidates = _release_index(session, owner_user_id=owner_user_id)

    counts = {MATCH_MATCHED: 0, MATCH_MISSING: 0, MATCH_DUPLICATE: 0, MATCH_REVIEW: 0}
    matched_release_ids: dict[int, list[int]] = {}

    for ext in externals:
        status, release_id, confidence, reason = match_external_to_release(
            ext,
            candidates,
            today=today,
            horizon_days=horizon_days,
        )
        if status == MATCH_MATCHED and release_id is not None:
            matched_release_ids.setdefault(release_id, []).append(int(ext.id or 0))
            if len(matched_release_ids[release_id]) > 1:
                status = MATCH_DUPLICATE
                reason = "multiple_external_for_release"

        row = session.exec(
            select(ExternalCatalogMatch).where(
                ExternalCatalogMatch.external_issue_id == int(ext.id or 0),
                ExternalCatalogMatch.owner_user_id == owner_user_id,
            )
        ).first()
        if row is None:
            row = ExternalCatalogMatch(
                external_issue_id=int(ext.id or 0),
                owner_user_id=owner_user_id,
                release_issue_id=release_id,
                match_status=status,
                match_confidence=confidence,
                match_reason=reason,
            )
            session.add(row)
        else:
            row.release_issue_id = release_id
            row.match_status = status
            row.match_confidence = confidence
            row.match_reason = reason
            from app.models.external_catalog import utc_now

            row.updated_at = utc_now()
            session.add(row)
        if status == MATCH_MATCHED and release_id is not None:
            release_row = session.get(ReleaseIssue, release_id)
            if release_row is not None:
                stamp_original_release_from_external(
                    release_row,
                    release_date=ext.release_date,
                    title=ext.title or ext.series_name,
                )
                session.add(release_row)
        counts[status] = counts.get(status, 0) + 1

    session.commit()
    return {
        "total": len(externals),
        "matched": counts.get(MATCH_MATCHED, 0),
        "missing_from_lunar": counts.get(MATCH_MISSING, 0),
        "possible_duplicate": counts.get(MATCH_DUPLICATE, 0),
        "needs_review": counts.get(MATCH_REVIEW, 0),
    }


def build_coverage_report(
    session: Session,
    *,
    owner_user_id: int,
    source_name: str = LOCG_SOURCE_NAME,
    high_pull_threshold: int = 100,
    high_want_threshold: int = 100,
) -> dict[str, object]:
    today = date.today()
    externals = session.exec(
        select(ExternalCatalogIssue).where(ExternalCatalogIssue.source_name == source_name)
    ).all()
    matches = session.exec(
        select(ExternalCatalogMatch).where(ExternalCatalogMatch.owner_user_id == owner_user_id)
    ).all()
    match_by_ext = {int(m.external_issue_id): m for m in matches}

    total = len(externals)
    matched = sum(1 for m in matches if m.match_status == MATCH_MATCHED)
    missing = sum(1 for m in matches if m.match_status == MATCH_MISSING)

    def issue_row(issue: ExternalCatalogIssue) -> dict[str, object]:
        return {
            "id": issue.id,
            "title": issue.title,
            "publisher": issue.publisher,
            "series_name": issue.series_name,
            "issue_number": issue.issue_number,
            "release_date": issue.release_date.isoformat() if issue.release_date else None,
            "pull_count": issue.pull_count,
            "want_count": issue.want_count,
            "match_status": match_by_ext.get(int(issue.id or 0)).match_status if issue.id in match_by_ext else None,
        }

    sorted_pull = sorted(externals, key=lambda i: (i.pull_count or 0), reverse=True)
    sorted_want = sorted(externals, key=lambda i: (i.want_count or 0), reverse=True)

    missing_issues = [
        ext
        for ext in externals
        if match_by_ext.get(int(ext.id or 0)) and match_by_ext[int(ext.id or 0)].match_status == MATCH_MISSING
    ]
    missing_pull = sorted(missing_issues, key=lambda i: (i.pull_count or 0), reverse=True)
    missing_want = sorted(missing_issues, key=lambda i: (i.want_count or 0), reverse=True)

    spec_scored = sorted(
        externals,
        key=lambda i: spec_candidate_score(i, today=today),
        reverse=True,
    )

    return {
        "total_external_issues": total,
        "total_matched_to_release_issue": matched,
        "total_missing_from_lunar": missing,
        "match_percentage": round((matched / total) * 100, 2) if total else 0.0,
        "missing_percentage": round((missing / total) * 100, 2) if total else 0.0,
        "number_one_issues_missing": sum(
            1 for i in missing_issues if is_number_one(i.issue_number)
        ),
        "milestone_issues_missing": sum(
            1 for i in missing_issues if is_milestone_issue_number(i.issue_number)
        ),
        "high_pull_missing": sum(
            1 for i in missing_issues if (i.pull_count or 0) >= high_pull_threshold
        ),
        "high_want_missing": sum(
            1 for i in missing_issues if (i.want_count or 0) >= high_want_threshold
        ),
        "top_50_by_pull_count": [issue_row(i) for i in sorted_pull[:50]],
        "top_50_by_want_count": [issue_row(i) for i in sorted_want[:50]],
        "top_50_missing_from_lunar_by_pull_count": [issue_row(i) for i in missing_pull[:50]],
        "top_50_missing_from_lunar_by_want_count": [issue_row(i) for i in missing_want[:50]],
        "top_50_upcoming_spec_candidates": [
            {
                **issue_row(i),
                "spec_candidate_score": spec_candidate_score(i, today=today),
            }
            for i in spec_scored[:50]
        ],
    }


def is_milestone_issue_number(issue_number: str | None) -> bool:
    if not issue_number:
        return False
    cleaned = issue_number.strip().lstrip("#")
    try:
        num = int(float(cleaned))
    except ValueError:
        return False
    return num in MILESTONE_NUMBERS


def is_number_one(issue_number: str | None) -> bool:
    return _issue_number_key(issue_number) in {"1", "1.0"}


def spec_candidate_score(issue: ExternalCatalogIssue, *, today: date) -> float:
    score = 0.0
    if is_number_one(issue.issue_number):
        score += 40.0
    if is_milestone_issue_number(issue.issue_number):
        score += 25.0
    if issue.pull_count and issue.pull_count >= 100:
        score += min(30.0, issue.pull_count / 50.0)
    if issue.want_count and issue.want_count >= 100:
        score += min(25.0, issue.want_count / 60.0)
    if issue.variant_count and issue.variant_count >= 3:
        score += 10.0
    if issue.foc_date and 0 <= (issue.foc_date - today).days <= 30:
        score += 15.0
    return score
