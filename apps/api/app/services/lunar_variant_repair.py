from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlmodel import Session, select

from app.models.lunar_feed import LunarFeedRawRow, LunarFeedRun
from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant
from app.schemas.release_intelligence import ReleaseImportFeedRequest
from app.services.lunar_csv_parser import parse_lunar_product_csv
from app.services.lunar_release_normalizer import normalize_lunar_rows
from app.services.lunar_issue_identity import classify_lunar_issue_row, is_legacy_flat_lunar_issue_uuid
from app.services.lunar_variant_identity import build_issue_release_uuid
from app.services.release_import import import_release_feed


@dataclass(frozen=True)
class LunarVariantRepairSummary:
    owner_user_id: int
    issue_groups_processed: int
    canonical_issues_updated: int
    variants_created: int
    variants_matched: int
    duplicate_issues_preserved: int


def _latest_lunar_csv_bytes(session: Session, *, owner_user_id: int) -> bytes | None:
    run = session.exec(
        select(LunarFeedRun)
        .where(LunarFeedRun.owner_user_id == owner_user_id)
        .order_by(LunarFeedRun.id.desc())
    ).first()
    if run is None or run.id is None:
        return None
    rows = session.exec(
        select(LunarFeedRawRow)
        .where(LunarFeedRawRow.feed_run_id == run.id)
        .order_by(LunarFeedRawRow.row_index.asc())
    ).all()
    if not rows:
        return None
    # Reconstruct CSV is expensive; prefer re-download in ops. Use row payloads when stored.
    return None


def repair_lunar_variants_from_rows(
    session: Session,
    *,
    owner_user_id: int,
    rows: list[dict[str, str]],
) -> LunarVariantRepairSummary:
    feed, _errors = normalize_lunar_rows(rows)
    result = import_release_feed(session, owner_user_id=owner_user_id, payload=feed)
    duplicate_issues = _count_duplicate_issue_groups(session, owner_user_id=owner_user_id)
    return LunarVariantRepairSummary(
        owner_user_id=owner_user_id,
        issue_groups_processed=sum(len(series.issues) for series in feed.series),
        canonical_issues_updated=result.issues_matched,
        variants_created=result.variants_created,
        variants_matched=result.variants_matched,
        duplicate_issues_preserved=duplicate_issues,
    )


def list_legacy_flat_issue_rows(session: Session, *, owner_user_id: int) -> list[ReleaseIssue]:
    issues = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
    return [row for row in issues if is_legacy_flat_lunar_issue_uuid(row.release_uuid)]


def legacy_flat_issue_classifications(session: Session, *, owner_user_id: int) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in list_legacy_flat_issue_rows(session, owner_user_id=owner_user_id):
        counts[classify_lunar_issue_row(release_uuid=row.release_uuid)] += 1
    return dict(counts)


def repair_lunar_variants_for_owner(session: Session, *, owner_user_id: int) -> LunarVariantRepairSummary:
    issues = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
    grouped: dict[tuple[int, str], list[ReleaseIssue]] = defaultdict(list)
    for issue in issues:
        grouped[(issue.series_id, issue.issue_number)].append(issue)

    variants_created = 0
    variants_matched = 0
    canonical_updated = 0
    duplicate_preserved = 0

    for (_series_id, issue_number), group in grouped.items():
        if len(group) <= 1:
            continue
        duplicate_preserved += len(group) - 1
        series = session.get(ReleaseSeries, group[0].series_id)
        if series is None:
            continue
        canonical = sorted(group, key=lambda row: row.id or 0)[0]
        target_uuid = build_issue_release_uuid(
            publisher=series.publisher,
            series_name=series.series_name,
            issue_number=issue_number,
        )
        if canonical.release_uuid != target_uuid:
            canonical.release_uuid = target_uuid
            canonical.title = f"{series.series_name} #{issue_number}"
            session.add(canonical)
            session.commit()
            session.refresh(canonical)
            canonical_updated += 1

        pseudo_rows: list[dict[str, str]] = []
        for duplicate in group:
            pseudo_rows.append(
                {
                    "Publisher": series.publisher,
                    "MainDesc": series.series_name,
                    "IssueNumber": issue_number,
                    "Title": duplicate.title,
                    "Code": duplicate.release_uuid.replace("lunar-", ""),
                    "Retail": str(duplicate.cover_price),
                    "FOCDate": duplicate.foc_date.isoformat() if duplicate.foc_date else "",
                    "InStoreDate": duplicate.release_date.isoformat() if duplicate.release_date else "",
                }
            )
        feed, _ = normalize_lunar_rows(pseudo_rows)
        if not feed.series:
            continue
        issue_payload = feed.series[0].issues[0]
        from app.services.release_import import import_variants

        _, created, matched = import_variants(
            session,
            issue_id=int(canonical.id or 0),
            payloads=issue_payload.variants,
        )
        variants_created += created
        variants_matched += matched

    return LunarVariantRepairSummary(
        owner_user_id=owner_user_id,
        issue_groups_processed=len(grouped),
        canonical_issues_updated=canonical_updated,
        variants_created=variants_created,
        variants_matched=variants_matched,
        duplicate_issues_preserved=duplicate_preserved,
    )


def _count_duplicate_issue_groups(session: Session, *, owner_user_id: int) -> int:
    issues = session.exec(select(ReleaseIssue).where(ReleaseIssue.owner_user_id == owner_user_id)).all()
    grouped: dict[tuple[int, str], int] = defaultdict(int)
    for issue in issues:
        grouped[(issue.series_id, issue.issue_number)] += 1
    return sum(count - 1 for count in grouped.values() if count > 1)


def repair_lunar_variants_from_csv_bytes(
    session: Session,
    *,
    owner_user_id: int,
    content_bytes: bytes,
) -> LunarVariantRepairSummary:
    rows = parse_lunar_product_csv(content_bytes)
    return repair_lunar_variants_from_rows(session, owner_user_id=owner_user_id, rows=rows)
