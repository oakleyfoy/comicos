from __future__ import annotations

import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries
from app.models.spec_intelligence import SpecRecommendation, SpecScore
from app.schemas.spec_intelligence import SpecAgentExecutionRead, SpecRecommendationRead
from app.services.personalization_agent import build_owner_preference_profile, score_issue_for_owner
from app.services.recommendation_forward_window import (
    FORWARD_RECOMMENDATION_WINDOW_DAYS,
    iter_forward_release_rows,
)
from app.services.spec_intelligence import AGENT_SPEC_RECOMMENDATION, run_with_spec_execution

# Progress every 50 candidates; batch DB commits for large runs.
PROGRESS_BATCH_SIZE = 50
COMMIT_BATCH_SIZE = 100
SLOW_STEP_SECONDS = 60.0


@dataclass(frozen=True)
class SpecRecommendationsRunOptions:
    """forward_window_only limits work to the 90-day recommendation horizon."""

    forward_window_only: bool = True
    max_candidates: int | None = None
    max_runtime_seconds: float | None = None
    progress_callback: Callable[[str], None] | None = None


def _log(options: SpecRecommendationsRunOptions, message: str) -> None:
    if options.progress_callback is not None:
        options.progress_callback(message)
    else:
        print(f"run_spec_recommendations: {message}", file=sys.stderr, flush=True)


def _timed_step(
    options: SpecRecommendationsRunOptions,
    label: str,
    fn: Callable[[], object],
) -> object:
    started = time.monotonic()
    _log(options, f"step={label} start")
    result = fn()
    elapsed = time.monotonic() - started
    _log(options, f"step={label} done secs={elapsed:.1f}")
    if elapsed >= SLOW_STEP_SECONDS:
        _log(options, f"SLOW STEP (>{int(SLOW_STEP_SECONDS)}s): {label} took {elapsed:.1f}s")
    return result


def latest_score_rows_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    issue_ids: set[int] | None = None,
) -> list[SpecScore]:
    if issue_ids is not None and not issue_ids:
        return []
    stmt = (
        select(SpecScore)
        .join(ReleaseIssue, SpecScore.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(SpecScore.created_at.desc(), SpecScore.id.desc())
    )
    if issue_ids is not None:
        stmt = stmt.where(SpecScore.release_issue_id.in_(sorted(issue_ids)))
    rows = session.exec(stmt).all()
    latest: dict[int, SpecScore] = {}
    for row in rows:
        if row.release_issue_id not in latest:
            latest[row.release_issue_id] = row
    return list(latest.values())


def _latest_recommendation_by_issue(
    session: Session,
    *,
    owner_user_id: int,
    issue_ids: list[int],
) -> dict[int, SpecRecommendation]:
    if not issue_ids:
        return {}
    rows = session.exec(
        select(SpecRecommendation)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .where(SpecRecommendation.release_issue_id.in_(issue_ids))
        .order_by(SpecRecommendation.created_at.desc(), SpecRecommendation.id.desc())
    ).all()
    latest: dict[int, SpecRecommendation] = {}
    for row in rows:
        if row.release_issue_id not in latest:
            latest[row.release_issue_id] = row
    return latest


def _key_signals_by_issue(session: Session, *, issue_ids: list[int]) -> dict[int, list[str]]:
    if not issue_ids:
        return {}
    rows = session.exec(select(ReleaseKeySignal).where(ReleaseKeySignal.issue_id.in_(issue_ids))).all()
    grouped: dict[int, list[str]] = {}
    for row in rows:
        grouped.setdefault(int(row.issue_id), []).append(str(row.signal_type))
    return grouped


def _load_forward_issues(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[set[int], dict[int, tuple[ReleaseIssue, ReleaseSeries]]]:
    rows = iter_forward_release_rows(session, owner_user_id=owner_user_id)
    issue_map: dict[int, tuple[ReleaseIssue, ReleaseSeries]] = {}
    for issue, series in rows:
        if issue.id is None:
            continue
        issue_map[int(issue.id)] = (issue, series)
    return set(issue_map.keys()), issue_map


def _recommendation_type(score: float) -> str:
    if score >= 82:
        return "STRONG_BUY"
    if score >= 62:
        return "BUY"
    if score >= 38:
        return "WATCH"
    return "PASS"


def _build_reason(signals: list[str], matched_preferences: list[str], recommendation_type: str) -> str:
    parts = [f"{recommendation_type} based on release intelligence signals"]
    if signals:
        parts.append(f"signals: {', '.join(signals[:4])}")
    if matched_preferences:
        parts.append(f"matched preferences: {', '.join(matched_preferences[:4])}")
    parts.append("advisory only; no order or inventory mutation.")
    return ". ".join(parts)


def _recommendation_unchanged(
    prior: SpecRecommendation | None,
    *,
    rec_type: str,
    adjusted_score: float,
    reason: str,
) -> bool:
    if prior is None:
        return False
    return (
        prior.recommendation_type == rec_type
        and abs(float(prior.recommendation_score) - adjusted_score) < 1e-6
        and prior.recommendation_reason == reason
    )


def run_spec_recommendations(
    session: Session,
    *,
    owner_user_id: int,
    options: SpecRecommendationsRunOptions | None = None,
) -> tuple[list[SpecRecommendationRead], SpecAgentExecutionRead]:
    opts = options or SpecRecommendationsRunOptions()

    def runner():
        run_started = time.monotonic()
        created: list[SpecRecommendation] = []
        skipped_unchanged = 0
        stop_reason = ""

        forward_ids: set[int] | None = None
        issues: dict[int, tuple[ReleaseIssue, ReleaseSeries]] = {}

        if opts.forward_window_only:
            started = time.monotonic()
            _log(opts, f"step=load_forward_window_{FORWARD_RECOMMENDATION_WINDOW_DAYS}d start")
            forward_ids, issues = _load_forward_issues(session, owner_user_id=owner_user_id)
            window_elapsed = time.monotonic() - started
            _log(
                opts,
                f"step=load_forward_window_{FORWARD_RECOMMENDATION_WINDOW_DAYS}d done secs={window_elapsed:.1f} "
                f"forward_issue_ids={len(forward_ids)}",
            )
            if window_elapsed >= SLOW_STEP_SECONDS:
                _log(
                    opts,
                    f"SLOW STEP (>{int(SLOW_STEP_SECONDS)}s): load_forward_window took {window_elapsed:.1f}s",
                )
            if not forward_ids:
                _log(opts, "step=score_loop skipped no issues in forward window")
                return []

        latest_scores = _timed_step(
            opts,
            "load_latest_spec_scores",
            lambda: latest_score_rows_for_owner(
                session, owner_user_id=owner_user_id, issue_ids=forward_ids
            ),
        )
        assert isinstance(latest_scores, list)
        _log(opts, f"spec_score_candidates={len(latest_scores)}")

        if opts.max_candidates is not None and len(latest_scores) > opts.max_candidates:
            latest_scores = latest_scores[: opts.max_candidates]
            stop_reason = f"candidate_cap={opts.max_candidates}"
            _log(opts, f"step=candidate_cap applied max_candidates={opts.max_candidates}")

        if not latest_scores:
            _log(opts, "step=score_loop skipped no scored issues in scope")
            return []

        candidate_issue_ids = [score.release_issue_id for score in latest_scores]

        if not opts.forward_window_only:
            started = time.monotonic()
            _log(opts, "step=load_issues_for_candidates start")
            issues = {
                int(issue.id or 0): (issue, series)
                for issue, series in session.exec(
                    select(ReleaseIssue, ReleaseSeries)
                    .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
                    .where(ReleaseIssue.owner_user_id == owner_user_id)
                    .where(ReleaseIssue.id.in_(candidate_issue_ids))
                ).all()
            }
            _log(
                opts,
                f"step=load_issues_for_candidates done secs={time.monotonic() - started:.1f} count={len(issues)}",
            )

        signals_by_issue = _timed_step(
            opts,
            "load_key_signals_batch",
            lambda: _key_signals_by_issue(session, issue_ids=candidate_issue_ids),
        )
        assert isinstance(signals_by_issue, dict)
        _log(opts, f"key_signal_issues={len(signals_by_issue)}")

        prior_recommendations = _timed_step(
            opts,
            "load_prior_recommendations_batch",
            lambda: _latest_recommendation_by_issue(
                session, owner_user_id=owner_user_id, issue_ids=candidate_issue_ids
            ),
        )
        assert isinstance(prior_recommendations, dict)

        profile = _timed_step(
            opts,
            "build_owner_preference_profile_once",
            lambda: build_owner_preference_profile(session, owner_user_id=owner_user_id),
        )
        assert isinstance(profile, dict)

        _log(opts, f"step=score_loop start candidates={len(latest_scores)}")
        batch_started = time.monotonic()
        processed = 0
        pending_commit = 0

        for score in latest_scores:
            if opts.max_runtime_seconds is not None:
                if time.monotonic() - run_started >= opts.max_runtime_seconds:
                    stop_reason = f"max_runtime_seconds={opts.max_runtime_seconds}"
                    _log(opts, f"step=score_loop stopped reason={stop_reason} processed={processed}")
                    break

            issue_pair = issues.get(score.release_issue_id)
            if issue_pair is None:
                continue
            issue, series = issue_pair
            personalization = score_issue_for_owner(
                session,
                owner_user_id=owner_user_id,
                issue=issue,
                series=series,
                base_score=score.score_value,
                profile=profile,
            )
            signals = signals_by_issue.get(int(issue.id or 0), [])
            adjusted_score = float(personalization["adjusted_score"])
            rec_type = _recommendation_type(adjusted_score)
            reason = _build_reason(
                signals,
                list(personalization["matched_preferences"]),
                rec_type,
            )
            prior = prior_recommendations.get(score.release_issue_id)
            if _recommendation_unchanged(
                prior, rec_type=rec_type, adjusted_score=adjusted_score, reason=reason
            ):
                skipped_unchanged += 1
                processed += 1
            else:
                recommendation = SpecRecommendation(
                    release_issue_id=score.release_issue_id,
                    recommendation_type=rec_type,
                    recommendation_score=adjusted_score,
                    confidence_score=round(min(0.99, score.confidence_score + 0.05), 3),
                    recommendation_reason=reason,
                )
                session.add(recommendation)
                created.append(recommendation)
                pending_commit += 1
                processed += 1
                if pending_commit >= COMMIT_BATCH_SIZE:
                    commit_started = time.monotonic()
                    session.commit()
                    commit_elapsed = time.monotonic() - commit_started
                    _log(
                        opts,
                        f"step=commit_batch created_total={len(created)} "
                        f"batch_size={pending_commit} secs={commit_elapsed:.1f}",
                    )
                    pending_commit = 0

            if processed % PROGRESS_BATCH_SIZE == 0:
                batch_elapsed = time.monotonic() - batch_started
                _log(
                    opts,
                    f"step=score_loop progress processed={processed}/{len(latest_scores)} "
                    f"created={len(created)} skipped_unchanged={skipped_unchanged} batch_secs={batch_elapsed:.1f}",
                )
                if batch_elapsed >= SLOW_STEP_SECONDS:
                    _log(
                        opts,
                        f"SLOW LOOP (>{int(SLOW_STEP_SECONDS)}s): last {PROGRESS_BATCH_SIZE} candidates "
                        f"took {batch_elapsed:.1f}s (check N+1; profile is cached once per run)",
                    )
                batch_started = time.monotonic()

        if pending_commit > 0:
            commit_started = time.monotonic()
            session.commit()
            _log(
                opts,
                f"step=commit_final pending={pending_commit} secs={time.monotonic() - commit_started:.1f}",
            )
        elif not created:
            _log(opts, "step=commit skipped no new rows")

        for row in created:
            session.refresh(row)

        if processed % PROGRESS_BATCH_SIZE != 0:
            _log(
                opts,
                f"step=score_loop progress processed={processed}/{len(latest_scores)} "
                f"created={len(created)} skipped_unchanged={skipped_unchanged} (final)",
            )

        total_elapsed = time.monotonic() - run_started
        _log(
            opts,
            f"step=complete total_secs={total_elapsed:.1f} created={len(created)} "
            f"skipped_unchanged={skipped_unchanged} stop_reason={stop_reason or 'none'}",
        )
        return [SpecRecommendationRead.model_validate(row) for row in created]

    result, execution = run_with_spec_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_SPEC_RECOMMENDATION,
        runner=runner,
    )
    return result, SpecAgentExecutionRead.model_validate(execution)


def list_recommendations_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(SpecRecommendation)
        .join(ReleaseIssue, SpecRecommendation.release_issue_id == ReleaseIssue.id)
        .where(ReleaseIssue.owner_user_id == owner_user_id)
        .order_by(SpecRecommendation.created_at.desc(), SpecRecommendation.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [SpecRecommendationRead.model_validate(row) for row in page], len(rows)
