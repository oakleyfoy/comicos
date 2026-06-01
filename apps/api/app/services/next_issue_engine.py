from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from app.models.collected_run import CollectedRun
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.services.canonical_series import compute_series_key
from app.services.collected_runs import latest_collected_run_rows, persist_collected_runs
from app.services.lunar_issue_identity import classify_lunar_issue_row, normalize_lunar_issue_number
from app.services.metadata_enrichment import normalize_series_title_with_aliases
from app.services.run_detection import parse_issue_number_for_run_detection

CONFIDENCE_EXACT = 1.0
CONFIDENCE_STRONG = 0.75


@dataclass(frozen=True)
class LunarCatalogEntry:
    publisher: str
    series_name: str
    issue_number: str
    release_uuid: str


@dataclass(frozen=True)
class NextIssueCandidate:
    series_name: str
    current_issue: str
    next_issue: str
    confidence: float
    rationale: str


def _normalize_issue_label(value: str) -> str:
    return normalize_lunar_issue_number(value)


def _next_sequential_issue(current_issue: str) -> str | None:
    parsed = parse_issue_number_for_run_detection(current_issue)
    if parsed.kind not in {"integer", "decimal"} or parsed.numeric_value is None:
        return None
    numeric = parsed.numeric_value
    if numeric == numeric.to_integral_value():
        return str(int(numeric) + 1)
    return str(numeric + Decimal("1"))


def _is_lunar_catalog_issue(release_uuid: str) -> bool:
    classification = classify_lunar_issue_row(release_uuid=release_uuid)
    return classification in {"canonical_lunar_issue", "legacy_flat_variant_issue"}


def _load_lunar_release_catalog(session: Session, *, owner_user_id: int) -> list[LunarCatalogEntry]:
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(ReleaseSeries.publisher.asc(), ReleaseSeries.series_name.asc(), ReleaseIssue.issue_number.asc())
    ).all()
    catalog: list[LunarCatalogEntry] = []
    for issue, series in rows:
        if not _is_lunar_catalog_issue(issue.release_uuid):
            continue
        catalog.append(
            LunarCatalogEntry(
                publisher=series.publisher.strip(),
                series_name=series.series_name.strip(),
                issue_number=_normalize_issue_label(issue.issue_number),
                release_uuid=issue.release_uuid,
            )
        )
    return catalog


def _catalog_indexes(
    catalog: list[LunarCatalogEntry],
    *,
    session: Session,
) -> tuple[dict[tuple[str, str, str], LunarCatalogEntry], dict[tuple[str, str], LunarCatalogEntry]]:
    exact: dict[tuple[str, str, str], LunarCatalogEntry] = {}
    by_series_key: dict[tuple[str, str], LunarCatalogEntry] = {}
    for entry in catalog:
        pub_key = entry.publisher.strip().lower()
        series_key = entry.series_name.strip().lower()
        issue_key = _normalize_issue_label(entry.issue_number)
        exact[(pub_key, series_key, issue_key)] = entry
        normalized_series = (
            normalize_series_title_with_aliases(entry.series_name, session=session).canonical_value or entry.series_name
        ).strip()
        sk = compute_series_key(entry.publisher, normalized_series)
        by_series_key[(sk.lower(), issue_key)] = entry
    return exact, by_series_key


def _match_catalog_entry(
    *,
    session: Session,
    publisher: str,
    series_name: str,
    next_issue: str,
    exact_index: dict[tuple[str, str, str], LunarCatalogEntry],
    series_key_index: dict[tuple[str, str], LunarCatalogEntry],
) -> tuple[LunarCatalogEntry | None, float, str]:
    pub_key = publisher.strip().lower()
    series_key = series_name.strip().lower()
    issue_key = _normalize_issue_label(next_issue)
    exact = exact_index.get((pub_key, series_key, issue_key))
    if exact is not None:
        return (
            exact,
            CONFIDENCE_EXACT,
            "Exact Lunar catalog match on publisher, series, and issue number.",
        )

    normalized_series = (
        normalize_series_title_with_aliases(series_name, session=session).canonical_value or series_name
    ).strip()
    sk = compute_series_key(publisher, normalized_series).lower()
    strong = series_key_index.get((sk, issue_key))
    if strong is not None:
        return (
            strong,
            CONFIDENCE_STRONG,
            "Strong Lunar catalog match on normalized series identity and issue number.",
        )

    for entry in exact_index.values():
        if entry.issue_number != issue_key:
            continue
        if entry.series_name.strip().lower() == series_key and entry.publisher.strip().lower() != pub_key:
            return (
                entry,
                CONFIDENCE_STRONG,
                "Strong Lunar catalog match on series and issue; publisher label differs.",
            )
    return None, 0.0, ""


def _collected_runs_for_detection(session: Session, *, owner_user_id: int) -> list[CollectedRun]:
    latest = latest_collected_run_rows(session, owner_user_id=owner_user_id)
    if latest:
        return list(latest.values())
    persist_collected_runs(session, owner_user_id=owner_user_id)
    return list(latest_collected_run_rows(session, owner_user_id=owner_user_id).values())


def generate_next_issues(session: Session, *, owner_user_id: int) -> list[NextIssueCandidate]:
    runs = _collected_runs_for_detection(session, owner_user_id=owner_user_id)
    catalog = _load_lunar_release_catalog(session, owner_user_id=owner_user_id)
    exact_index, series_key_index = _catalog_indexes(catalog, session=session)
    candidates: list[NextIssueCandidate] = []

    for run in runs:
        current = run.latest_owned_issue.strip()
        next_issue = _next_sequential_issue(current)
        if not next_issue:
            continue
        entry, confidence, rationale = _match_catalog_entry(
            session=session,
            publisher=run.publisher,
            series_name=run.series_name,
            next_issue=next_issue,
            exact_index=exact_index,
            series_key_index=series_key_index,
        )
        if entry is None:
            continue
        candidates.append(
            NextIssueCandidate(
                series_name=run.series_name,
                current_issue=current,
                next_issue=_normalize_issue_label(entry.issue_number),
                confidence=confidence,
                rationale=rationale,
            )
        )

    candidates.sort(key=lambda item: item.series_name.lower())
    return candidates
