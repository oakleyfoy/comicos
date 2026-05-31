from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session, select

from app.models.release_intelligence import ReleaseIssue
from app.models.spec_intelligence import WeeklyBuyList, WeeklyBuyListItem
from app.schemas.spec_intelligence import (
    SpecAgentExecutionRead,
    WeeklyBuyListDetailRead,
    WeeklyBuyListItemRead,
    WeeklyBuyListRead,
)
from app.services.spec_intelligence import AGENT_WEEKLY_BUY_LIST, run_with_spec_execution
from app.services.spec_recommendation_agent import list_recommendations_for_owner


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _buy_category(recommendation_type: str) -> str:
    return {
        "STRONG_BUY": "Must Buy",
        "BUY": "Strong Buy",
        "WATCH": "Watch",
        "PASS": "Pass",
    }.get(recommendation_type, "Pass")


def _read_detail(session: Session, row: WeeklyBuyList) -> WeeklyBuyListDetailRead:
    items = session.exec(
        select(WeeklyBuyListItem)
        .where(WeeklyBuyListItem.weekly_buy_list_id == int(row.id or 0))
        .order_by(WeeklyBuyListItem.ranking_score.desc(), WeeklyBuyListItem.id.asc())
    ).all()
    return WeeklyBuyListDetailRead(
        weekly_buy_list=WeeklyBuyListRead.model_validate(row),
        items=[WeeklyBuyListItemRead.model_validate(item) for item in items],
    )


def run_weekly_buy_list(
    session: Session,
    *,
    owner_user_id: int,
) -> tuple[WeeklyBuyListDetailRead, SpecAgentExecutionRead]:
    def runner():
        recommendations, _ = list_recommendations_for_owner(session, owner_user_id=owner_user_id, limit=500, offset=0)
        issue_rows = {
            int(row.id or 0): row
            for row in session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
        }
        week = _week_start(date.today())
        buy_list = WeeklyBuyList(owner_user_id=owner_user_id, week_start_date=week)
        session.add(buy_list)
        session.commit()
        session.refresh(buy_list)

        ranked = sorted(recommendations, key=lambda row: row.recommendation_score, reverse=True)
        for rec in ranked:
            issue = issue_rows.get(rec.release_issue_id)
            if issue is None:
                continue
            item = WeeklyBuyListItem(
                weekly_buy_list_id=int(buy_list.id or 0),
                release_issue_id=rec.release_issue_id,
                buy_category=_buy_category(rec.recommendation_type),
                ranking_score=rec.recommendation_score,
            )
            session.add(item)
        session.commit()
        return _read_detail(session, buy_list)

    result, execution = run_with_spec_execution(
        session,
        owner_user_id=owner_user_id,
        agent_code=AGENT_WEEKLY_BUY_LIST,
        runner=runner,
    )
    return result, SpecAgentExecutionRead.model_validate(execution)


def list_weekly_buy_lists_for_owner(session: Session, *, owner_user_id: int, limit: int = 50, offset: int = 0):
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    rows = session.exec(
        select(WeeklyBuyList)
        .where(WeeklyBuyList.owner_user_id == owner_user_id)
        .order_by(WeeklyBuyList.generated_at.desc(), WeeklyBuyList.id.desc())
    ).all()
    page = rows[offset : offset + limit]
    return [_read_detail(session, row) for row in page], len(rows)
