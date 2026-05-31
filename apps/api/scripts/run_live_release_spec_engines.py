"""Run Release Platform + Spec engines on live Lunar catalog; print top lists."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlmodel import Session, select

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.session import get_engine
from app.models import User
from app.models.lunar_feed import LunarFeedRun
from app.models.release_intelligence import ReleaseIssue, ReleaseKeySignal, ReleaseSeries, ReleaseVariant
from app.services.continue_run_planning import build_continue_run_planning
from app.services.lunar_release_refresh import refresh_release_intelligence_after_lunar_import
from app.services.opportunity_intelligence import build_opportunity_intelligence
from app.services.release_horizon_engine import build_release_horizons, list_issues_in_horizon_window
from app.services.run_continuity_agent import _inventory_issue_rows
from app.services.weekly_buy_list_agent import run_weekly_buy_list


def _within_90_days(issue: ReleaseIssue, *, today: date) -> bool:
    if issue.release_date is None:
        return False
    delta = (issue.release_date - today).days
    return 0 <= delta <= 90


def _fmt_issue(issue: ReleaseIssue, series: ReleaseSeries) -> str:
    rd = issue.release_date.isoformat() if issue.release_date else "TBD"
    return f"{series.publisher} | {series.series_name} #{issue.issue_number} | release {rd} | {issue.title[:80]}"


def _resolve_owner(session: Session) -> User:
    run = session.exec(select(LunarFeedRun).order_by(LunarFeedRun.id.desc())).first()
    if run is None:
        raise SystemExit("No LunarFeedRun found")
    user = session.get(User, run.owner_user_id)
    if user is None:
        raise SystemExit("Lunar owner not found")
    return user


def main() -> None:
    today = date.today()
    engine = get_engine()
    with Session(engine) as session:
        owner = _resolve_owner(session)
        assert owner.id is not None
        owner_id = int(owner.id)
        inventory_rows = len(list(_inventory_issue_rows(session, owner_user_id=owner_id)))

        refresh = refresh_release_intelligence_after_lunar_import(session, owner_user_id=owner_id)
        buy_list, _buy_exec = run_weekly_buy_list(session, owner_user_id=owner_id)
        horizons = build_release_horizons(session, owner_user_id=owner_id)
        opportunities = build_opportunity_intelligence(session, owner_user_id=owner_id)
        run_plans = build_continue_run_planning(session, owner_user_id=owner_id)

        issue_map = {
            int(issue.id or 0): (issue, series)
            for issue, series in session.exec(
                select(ReleaseIssue, ReleaseSeries)
                .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
                .where(ReleaseIssue.owner_user_id == owner_id)
            ).all()
        }

        def in90_issue_id(release_issue_id: int) -> bool:
            pair = issue_map.get(release_issue_id)
            if pair is None:
                return False
            return _within_90_days(pair[0], today=today)

        new_number_ones = [
            {
                "rank": idx,
                "score": row.ranking_score,
                "line": _fmt_issue(row.issue, row.series),
            }
            for idx, row in enumerate(
                [r for r in opportunities.top_new_number_ones if in90_issue_id(r.release_issue_id)][:25],
                start=1,
            )
        ]

        ratio_variants: list[dict[str, object]] = []
        variants = session.exec(
            select(ReleaseVariant, ReleaseIssue, ReleaseSeries)
            .join(ReleaseIssue, ReleaseVariant.issue_id == ReleaseIssue.id)
            .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)
            .where(ReleaseIssue.owner_user_id == owner_id)
            .where(ReleaseVariant.ratio_value.is_not(None))
            .order_by(ReleaseVariant.ratio_value.desc(), ReleaseVariant.id.desc())
        ).all()
        for variant, issue, series in variants:
            if not _within_90_days(issue, today=today):
                continue
            ratio_variants.append(
                {
                    "rank": len(ratio_variants) + 1,
                    "ratio": f"1:{variant.ratio_value}",
                    "variant": variant.variant_name,
                    "line": _fmt_issue(issue, series),
                }
            )
            if len(ratio_variants) >= 25:
                break

        special_signal_types = {
            "MILESTONE_NUMBERING",
            "FIRST_APPEARANCE",
            "ORIGIN_ISSUE",
            "ANNIVERSARY_ISSUE",
            "DEATH_ISSUE",
            "STATUS_QUO_CHANGE",
        }
        milestone_ranked = [
            r
            for r in opportunities.top_milestone_books
            if in90_issue_id(r.release_issue_id)
        ]
        milestone_ids = {r.release_issue_id for r in milestone_ranked}
        extra_special: list = []
        for issue, series in list_issues_in_horizon_window(session, owner_user_id=owner_id, max_release_days=90):
            signals = {
                s.signal_type
                for s in session.exec(
                    select(ReleaseKeySignal)
                    .where(ReleaseKeySignal.issue_id == int(issue.id or 0))
                    .where(ReleaseKeySignal.owner_user_id == owner_id)
                ).all()
            }
            if not signals.intersection(special_signal_types):
                continue
            if int(issue.id or 0) in milestone_ids:
                continue
            from app.services.opportunity_scoring import compute_opportunity_ranking_score

            score, _ = compute_opportunity_ranking_score(
                session,
                owner_user_id=owner_id,
                issue=issue,
                series=series,
                signal_types=signals,
            )
            extra_special.append((score, issue, series, sorted(signals)))
        extra_special.sort(key=lambda row: row[0], reverse=True)
        milestones_out: list[dict[str, object]] = []
        for row in milestone_ranked:
            milestones_out.append(
                {
                    "rank": len(milestones_out) + 1,
                    "score": row.ranking_score,
                    "line": _fmt_issue(row.issue, row.series),
                }
            )
            if len(milestones_out) >= 25:
                break
        if len(milestones_out) < 25:
            for score, issue, series, signals in extra_special:
                milestones_out.append(
                    {
                        "rank": len(milestones_out) + 1,
                        "score": round(score, 2),
                        "signals": signals[:4],
                        "line": _fmt_issue(issue, series),
                    }
                )
                if len(milestones_out) >= 25:
                    break

        spec_top = [
            {
                "rank": idx,
                "score": row.ranking_score,
                "rec_type": row.recommendation.recommendation_type if row.recommendation else None,
                "line": _fmt_issue(row.issue, row.series),
            }
            for idx, row in enumerate(
                [r for r in opportunities.top_spec_opportunities if in90_issue_id(r.release_issue_id)][:25],
                start=1,
            )
        ]

        buy_buckets: dict[str, list[dict[str, object]]] = {
            "Must Buy": [],
            "Strong Buy": [],
            "Watch": [],
            "Pass": [],
        }
        for item in buy_list.items:
            issue = session.get(ReleaseIssue, item.release_issue_id)
            if issue is None:
                continue
            series = session.get(ReleaseSeries, issue.series_id)
            if series is None:
                continue
            entry = {
                "score": round(item.ranking_score, 2),
                "line": _fmt_issue(issue, series),
            }
            bucket = buy_buckets.get(item.buy_category, buy_buckets["Pass"])
            bucket.append(entry)

        continue_run_count = sum(1 for p in run_plans if p.plan_type == "CONTINUE_RUN")
        new_opp_count = sum(1 for p in run_plans if p.plan_type == "NEW_OPPORTUNITY")

        report = {
            "owner_user_id": owner_id,
            "inventory_copy_rows": inventory_rows,
            "engines_ran": refresh.__dict__,
            "next_90_days_count": len(horizons.next_90_days),
            "continue_run_alerts": continue_run_count,
            "new_opportunity_alerts": new_opp_count,
            "top_25_new_number_ones_next_90_days": new_number_ones,
            "top_25_ratio_variants_next_90_days": ratio_variants,
            "top_25_milestone_special_next_90_days": milestones_out,
            "top_25_spec_opportunities_next_90_days": spec_top,
            "weekly_buy_list": {
                category: items[:25] for category, items in buy_buckets.items()
            },
            "weekly_buy_list_totals": {k: len(v) for k, v in buy_buckets.items()},
        }
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
