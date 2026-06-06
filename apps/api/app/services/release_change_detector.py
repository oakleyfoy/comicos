"""P74-01 release change detection and event persistence."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlmodel import Session

from app.models.release_event_history import (
    P74_CHANGE_COVER,
    P74_CHANGE_METADATA,
    P74_CHANGE_NEW_ISSUE,
    P74_CHANGE_NEW_VARIANT,
    P74_CHANGE_PUBLISHER,
    P74_CHANGE_RELEASE_DATE,
    P74_CHANGE_REMOVED,
    P74_CHANGE_RESTORED,
    P74_EVENT_DISCOVERED,
    P74_EVENT_RELEASE_DATE_CHANGED,
    P74_EVENT_REMOVED,
    P74_EVENT_RESTORED,
    P74_EVENT_UPDATED,
    P74_EVENT_VARIANT_ADDED,
    P74ReleaseChangeRecord,
    P74ReleaseEventHistory,
)
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def snapshot_issue(issue: ReleaseIssue, series: ReleaseSeries | None = None) -> dict:
    data = {
        "release_uuid": issue.release_uuid,
        "issue_number": issue.issue_number,
        "title": issue.title,
        "foc_date": _iso(issue.foc_date),
        "release_date": _iso(issue.release_date),
        "cover_price": issue.cover_price,
        "release_status": issue.release_status,
        "series_id": issue.series_id,
    }
    if series is not None:
        data["publisher"] = series.publisher
        data["series_name"] = series.series_name
    return data


def snapshot_variant(variant: ReleaseVariant) -> dict:
    return {
        "variant_uuid": variant.variant_uuid,
        "variant_name": variant.variant_name,
        "variant_type": variant.variant_type,
        "ratio_value": variant.ratio_value,
        "ratio_type": variant.ratio_type,
        "is_incentive_variant": variant.is_incentive_variant,
        "cover_artist": variant.cover_artist,
    }


def _append_event(
    session: Session,
    *,
    owner_user_id: int,
    event_type: str,
    issue_id: int | None = None,
    variant_id: int | None = None,
    payload: dict | None = None,
) -> P74ReleaseEventHistory:
    row = P74ReleaseEventHistory(
        owner_user_id=owner_user_id,
        issue_id=issue_id,
        variant_id=variant_id,
        event_type=event_type,
        payload_json=dict(payload or {}),
    )
    session.add(row)
    session.flush()
    return row


def _append_change(
    session: Session,
    *,
    owner_user_id: int,
    change_type: str,
    before_json: dict,
    after_json: dict,
    issue_id: int | None = None,
    variant_id: int | None = None,
) -> P74ReleaseChangeRecord:
    row = P74ReleaseChangeRecord(
        owner_user_id=owner_user_id,
        issue_id=issue_id,
        variant_id=variant_id,
        change_type=change_type,
        before_json=before_json,
        after_json=after_json,
        detected_at=utc_now(),
    )
    session.add(row)
    session.flush()
    return row


def record_issue_discovered(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> None:
    after = snapshot_issue(issue, series)
    _append_change(
        session,
        owner_user_id=owner_user_id,
        change_type=P74_CHANGE_NEW_ISSUE,
        before_json={},
        after_json=after,
        issue_id=int(issue.id or 0),
    )
    _append_event(
        session,
        owner_user_id=owner_user_id,
        event_type=P74_EVENT_DISCOVERED,
        issue_id=int(issue.id or 0),
        payload={"publisher": series.publisher, "series_name": series.series_name, "issue_number": issue.issue_number},
    )
    session.flush()


def detect_and_record_issue_update(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
    before: dict,
) -> list[str]:
    after = snapshot_issue(issue, series)
    if before == after:
        return []
    detected: list[str] = []
    if before.get("release_date") != after.get("release_date"):
        _append_change(
            session,
            owner_user_id=owner_user_id,
            change_type=P74_CHANGE_RELEASE_DATE,
            before_json=before,
            after_json=after,
            issue_id=int(issue.id or 0),
        )
        _append_event(
            session,
            owner_user_id=owner_user_id,
            event_type=P74_EVENT_RELEASE_DATE_CHANGED,
            issue_id=int(issue.id or 0),
            payload={"before": before.get("release_date"), "after": after.get("release_date")},
        )
        detected.append(P74_CHANGE_RELEASE_DATE)
    if before.get("publisher") != after.get("publisher"):
        _append_change(
            session,
            owner_user_id=owner_user_id,
            change_type=P74_CHANGE_PUBLISHER,
            before_json=before,
            after_json=after,
            issue_id=int(issue.id or 0),
        )
        detected.append(P74_CHANGE_PUBLISHER)
    if before.get("title") != after.get("title") or before.get("cover_price") != after.get("cover_price"):
        _append_change(
            session,
            owner_user_id=owner_user_id,
            change_type=P74_CHANGE_COVER,
            before_json=before,
            after_json=after,
            issue_id=int(issue.id or 0),
        )
        detected.append(P74_CHANGE_COVER)
    other_meta = (
        before.get("foc_date") != after.get("foc_date")
        or before.get("release_status") != after.get("release_status")
        or before.get("issue_number") != after.get("issue_number")
    )
    if other_meta and P74_CHANGE_RELEASE_DATE not in detected:
        _append_change(
            session,
            owner_user_id=owner_user_id,
            change_type=P74_CHANGE_METADATA,
            before_json=before,
            after_json=after,
            issue_id=int(issue.id or 0),
        )
        detected.append(P74_CHANGE_METADATA)
    if detected:
        _append_event(
            session,
            owner_user_id=owner_user_id,
            event_type=P74_EVENT_UPDATED,
            issue_id=int(issue.id or 0),
            payload={"change_types": detected},
        )
    session.flush()
    return detected


def record_variant_added(
    session: Session,
    *,
    owner_user_id: int,
    issue_id: int,
    variant: ReleaseVariant,
    late_added: bool = False,
) -> None:
    after = snapshot_variant(variant)
    after["late_added"] = late_added
    _append_change(
        session,
        owner_user_id=owner_user_id,
        change_type=P74_CHANGE_NEW_VARIANT,
        before_json={},
        after_json=after,
        issue_id=issue_id,
        variant_id=int(variant.id or 0),
    )
    _append_event(
        session,
        owner_user_id=owner_user_id,
        event_type=P74_EVENT_VARIANT_ADDED,
        issue_id=issue_id,
        variant_id=int(variant.id or 0),
        payload={"late_added": late_added, **after},
    )
    session.flush()


def record_issue_removed(
    session: Session,
    *,
    owner_user_id: int,
    issue_id: int,
    before: dict,
) -> None:
    _append_change(
        session,
        owner_user_id=owner_user_id,
        change_type=P74_CHANGE_REMOVED,
        before_json=before,
        after_json={},
        issue_id=issue_id,
    )
    _append_event(
        session,
        owner_user_id=owner_user_id,
        event_type=P74_EVENT_REMOVED,
        issue_id=issue_id,
        payload=before,
    )
    session.flush()


def record_issue_restored(
    session: Session,
    *,
    owner_user_id: int,
    issue: ReleaseIssue,
    series: ReleaseSeries,
) -> None:
    after = snapshot_issue(issue, series)
    _append_change(
        session,
        owner_user_id=owner_user_id,
        change_type=P74_CHANGE_RESTORED,
        before_json={},
        after_json=after,
        issue_id=int(issue.id or 0),
    )
    _append_event(
        session,
        owner_user_id=owner_user_id,
        event_type=P74_EVENT_RESTORED,
        issue_id=int(issue.id or 0),
        payload=after,
    )
    session.flush()
