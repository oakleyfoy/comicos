"""Forward-scoped release title index (avoids full-catalog materialization)."""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from typing import Iterable

from sqlmodel import Session, func, select

from app.models.cross_system_recommendation import CrossSystemRecommendation
from app.models.daily_action_engine import DailyCollectorAction
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries
from app.models.unified_collector_intelligence import UnifiedCollectorRecommendation
from app.services.recommendation_catalog_quality import parse_recommendation_display_title
from app.services.recommendation_forward_window import iter_forward_release_rows
from app.services.recommendation_latest_rows import latest_by_key_bounded_scan
from app.services.recommendation_pipeline_diagnostics import process_rss_mb


def display_title(*, series_name: str, issue_number: str) -> str:
    return f"{series_name.strip()} #{issue_number.strip()}"


def _normalize_title_key(title: str) -> str:
    key = title.strip().lower()
    if key.endswith(" (variants)"):
        key = key[: -len(" (variants)")]
    return key


def _index_key_for_pair(issue: ReleaseIssue, series: ReleaseSeries) -> str:
    return display_title(series_name=series.series_name, issue_number=issue.issue_number).strip().lower()


@dataclass(frozen=True)
class ForwardReleaseTitleIndexResult:
    index: dict[str, tuple[ReleaseIssue, ReleaseSeries]]
    title_index_rows_loaded: int
    title_index_source: str
    title_index_memory_mb: float
    title_index_build_ms: float


@dataclass
class RecommendationPipelineIndexCache:
    """Reuse one scoped index across unified → daily → cross-system in a single rebuild."""

    owner_user_id: int
    _result: ForwardReleaseTitleIndexResult | None = None
    _pending_title_keys: set[str] = field(default_factory=set)

    def register_titles(self, titles: Iterable[str]) -> None:
        for title in titles:
            key = _normalize_title_key(title)
            if key:
                self._pending_title_keys.add(key)

    def get_index(self, session: Session) -> dict[str, tuple[ReleaseIssue, ReleaseSeries]]:
        return self.get_result(session).index

    def get_result(self, session: Session) -> ForwardReleaseTitleIndexResult:
        if self._result is None:
            self._result = build_scoped_forward_release_title_index(
                session,
                owner_user_id=self.owner_user_id,
                extra_title_keys=set(self._pending_title_keys),
            )
            self._pending_title_keys.clear()
            return self._result
        if self._pending_title_keys:
            self._result = _extend_scoped_index(
                session,
                owner_user_id=self.owner_user_id,
                base=self._result,
                extra_title_keys=self._pending_title_keys,
            )
            self._pending_title_keys.clear()
        return self._result

    def diagnostics(self) -> dict[str, object]:
        if self._result is None:
            return {}
        return {
            "title_index_rows_loaded": self._result.title_index_rows_loaded,
            "title_index_source": self._result.title_index_source,
            "title_index_memory_mb": self._result.title_index_memory_mb,
            "title_index_build_ms": self._result.title_index_build_ms,
        }


def _collect_recommendation_title_keys(session: Session, *, owner_user_id: int) -> set[str]:
    keys: set[str] = set()
    unified = latest_by_key_bounded_scan(
        session,
        model=UnifiedCollectorRecommendation,
        owner_user_id=owner_user_id,
        owner_field="owner_user_id",
        key_fn=lambda row: (row.recommendation_type, row.title.strip().lower()),
        scan_limit=4000,
    )
    for row in unified.values():
        keys.add(_normalize_title_key(row.title))

    daily = latest_by_key_bounded_scan(
        session,
        model=DailyCollectorAction,
        owner_user_id=owner_user_id,
        owner_field="owner_user_id",
        key_fn=lambda row: (row.action_type, row.title.strip().lower()),
        scan_limit=4000,
    )
    for row in daily.values():
        keys.add(_normalize_title_key(row.title))

    anchor = session.exec(
        select(CrossSystemRecommendation)
        .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
        .order_by(CrossSystemRecommendation.created_at.desc(), CrossSystemRecommendation.id.desc())
        .limit(1)
    ).first()
    if anchor is not None:
        batch = session.exec(
            select(CrossSystemRecommendation)
            .where(CrossSystemRecommendation.owner_user_id == owner_user_id)
            .where(CrossSystemRecommendation.created_at == anchor.created_at)
            .limit(250)
        ).all()
        for row in batch:
            keys.add(_normalize_title_key(row.title))
    return keys


def _lookup_pairs_for_title_keys(
    session: Session,
    *,
    owner_user_id: int,
    title_keys: set[str],
    index: dict[str, tuple[ReleaseIssue, ReleaseSeries]],
) -> tuple[list[tuple[ReleaseIssue, ReleaseSeries]], int]:
    missing = [k for k in title_keys if k and k not in index]
    if not missing:
        return [], 0
    found: list[tuple[ReleaseIssue, ReleaseSeries]] = []
    lookups = 0
    for key in missing[:400]:
        series_name, issue_number = parse_recommendation_display_title(key)
        if not series_name:
            continue
        stmt = (
            select(ReleaseIssue, ReleaseSeries)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_user_id)
            .where(func.lower(ReleaseSeries.series_name) == series_name.strip().lower())
        )
        if issue_number:
            stmt = stmt.where(ReleaseIssue.issue_number == issue_number.strip())
        row = session.exec(stmt.limit(1)).first()
        lookups += 1
        if row is None:
            continue
        issue, series = row
        found.append((issue, series))
    return found, lookups


def build_scoped_forward_release_title_index(
    session: Session,
    *,
    owner_user_id: int,
    extra_title_keys: set[str] | None = None,
) -> ForwardReleaseTitleIndexResult:
    mem_before = process_rss_mb()
    started = time.monotonic()
    sources: list[str] = []

    index: dict[str, tuple[ReleaseIssue, ReleaseSeries]] = {}
    forward_rows = iter_forward_release_rows(session, owner_user_id=owner_user_id)
    sources.append("forward_window")
    for issue, series in forward_rows:
        index[_index_key_for_pair(issue, series)] = (issue, series)

    rec_keys = _collect_recommendation_title_keys(session, owner_user_id=owner_user_id)
    if rec_keys:
        sources.append("latest_recommendation_titles")
    extras = set(extra_title_keys or set())
    extras.update(rec_keys)
    if extras:
        sources.append("extra_title_keys")

    lookup_pairs, lookup_count = _lookup_pairs_for_title_keys(
        session,
        owner_user_id=owner_user_id,
        title_keys=extras,
        index=index,
    )
    if lookup_count:
        sources.append(f"title_lookup({lookup_count})")
    for issue, series in lookup_pairs:
        index[_index_key_for_pair(issue, series)] = (issue, series)

    elapsed_ms = round((time.monotonic() - started) * 1000.0, 2)
    mem_after = process_rss_mb()
    mem_delta = max(0.0, mem_after - mem_before)
    source_label = ",".join(sources) if sources else "empty"
    result = ForwardReleaseTitleIndexResult(
        index=index,
        title_index_rows_loaded=len(index),
        title_index_source=source_label,
        title_index_memory_mb=round(mem_delta, 2),
        title_index_build_ms=elapsed_ms,
    )
    print(
        f"timing title_index.scoped {elapsed_ms:.1f}ms "
        f"rows={result.title_index_rows_loaded} source={source_label} "
        f"memory_mb={result.title_index_memory_mb}",
        file=sys.stderr,
        flush=True,
    )
    return result


def _extend_scoped_index(
    session: Session,
    *,
    owner_user_id: int,
    base: ForwardReleaseTitleIndexResult,
    extra_title_keys: set[str],
) -> ForwardReleaseTitleIndexResult:
    mem_before = process_rss_mb()
    started = time.monotonic()
    index = dict(base.index)
    lookup_pairs, lookup_count = _lookup_pairs_for_title_keys(
        session,
        owner_user_id=owner_user_id,
        title_keys=extra_title_keys,
        index=index,
    )
    for issue, series in lookup_pairs:
        index[_index_key_for_pair(issue, series)] = (issue, series)
    elapsed_ms = round((time.monotonic() - started) * 1000.0, 2)
    mem_after = process_rss_mb()
    source = f"{base.title_index_source}+extend({lookup_count})"
    return ForwardReleaseTitleIndexResult(
        index=index,
        title_index_rows_loaded=len(index),
        title_index_source=source,
        title_index_memory_mb=round(max(0.0, mem_after - mem_before) + base.title_index_memory_mb, 2),
        title_index_build_ms=round(base.title_index_build_ms + elapsed_ms, 2),
    )


def build_full_release_title_index(
    session: Session,
    *,
    owner_user_id: int,
) -> dict[str, tuple[ReleaseIssue, ReleaseSeries]]:
    """Admin / deep rebuild only — loads entire owner release catalog."""
    rows = session.exec(
        select(ReleaseIssue, ReleaseSeries)
        .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
    ).all()
    index: dict[str, tuple[ReleaseIssue, ReleaseSeries]] = {}
    for issue, series in rows:
        index[_index_key_for_pair(issue, series)] = (issue, series)
    return index
