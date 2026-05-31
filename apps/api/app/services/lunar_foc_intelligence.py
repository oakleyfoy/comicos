from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlmodel import Session

from app.models.lunar_feed import LunarFocAlert
from app.services.lunar_csv_parser import row_product_code


def _pick(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        if row.get(key):
            return row[key]
    return ""


def _parse_date(value: str) -> date | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            if fmt == "%Y-%m-%d":
                return date.fromisoformat(cleaned)
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def generate_foc_alerts(
    session: Session,
    *,
    owner_user_id: int,
    feed_run_id: int,
    rows: list[dict[str, str]],
    horizon_days: int = 21,
) -> list[LunarFocAlert]:
    today = date.today()
    cutoff = today + timedelta(days=horizon_days)
    created: list[LunarFocAlert] = []
    for row in rows:
        foc_date = _parse_date(_pick(row, "FOCDate", "FOC Date", "foc_date"))
        if foc_date is None or foc_date < today or foc_date > cutoff:
            continue
        product_code = row_product_code(row)
        title = _pick(row, "Title", "ProductName", "title")
        alert = LunarFocAlert(
            owner_user_id=owner_user_id,
            feed_run_id=feed_run_id,
            product_code=product_code,
            title=title,
            foc_date=foc_date,
            alert_status="OPEN",
        )
        session.add(alert)
        created.append(alert)
    session.commit()
    for alert in created:
        session.refresh(alert)
    return created
