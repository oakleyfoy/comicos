"""Wipe non-catalog collection data for catalog-unification test resets.

Deletes operational / legacy-spine rows in FK-safe order. Does NOT touch
catalog_* tables (master catalog spine).

Usage (from apps/api):
  python scripts/unify_wipe_test_collection.py --dry-run
  python scripts/unify_wipe_test_collection.py --email user@example.com
  python scripts/unify_wipe_test_collection.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import delete, func, select, update
from sqlmodel import Session

from app.db.session import get_engine
from app.models import (
    Acquisition,
    CoverImage,
    DraftImport,
    GmailImportRecord,
    GradingCandidate,
    GradingCandidateEvidence,
    GradingCandidateLifecycleEvent,
    GradingCandidateSnapshot,
    InventoryCopy,
    InventoryScanItem,
    InventoryScanSession,
    Order,
    OrderItem,
    OpsEvent,
    User,
)
from app.models.photo_import import (
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportImage,
    PhotoImportSession,
)
from app.models.photo_import_vision_read import PhotoImportVisionRead
from app.models.p92_import_health import P92ImportHealthEvent
from app.models.p92_import_line_cover import P92ImportLineCoverResolution
from app.models.acquisition import AcquisitionPlaceholderIssue
from app.models.portfolio import PortfolioItem
from app.services.legacy_spine_availability import legacy_customer_order_table_exists

try:
    from app.models.p80_mobile_operations import P80MobileIntakeSession
except ImportError:  # pragma: no cover
    P80MobileIntakeSession = None  # type: ignore[misc, assignment]


def _resolve_user_id(session: Session, email: str | None) -> int | None:
    if not email:
        return None
    user = session.exec(select(User).where(User.email == email)).first()
    if user is None or user.id is None:
        raise SystemExit(f"No user found for email {email!r}")
    return int(user.id)


def _count_rows(session: Session, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    for clause in where:
        stmt = stmt.where(clause)
    return int(session.exec(stmt).one()[0])


def _delete_rows(session: Session, model, *where) -> int:
    before = _count_rows(session, model, *where)
    if before == 0:
        return 0
    stmt = delete(model)
    for clause in where:
        stmt = stmt.where(clause)
    session.exec(stmt)
    return before


def _null_draft_import_primary_covers(session: Session, user_id: int | None) -> int:
    before = _count_rows(
        session,
        DraftImport,
        DraftImport.primary_cover_image_id.is_not(None),
        *([DraftImport.user_id == user_id] if user_id is not None else []),
    )
    if before == 0:
        return 0
    stmt = update(DraftImport).values(primary_cover_image_id=None).where(
        DraftImport.primary_cover_image_id.is_not(None)
    )
    if user_id is not None:
        stmt = stmt.where(DraftImport.user_id == user_id)
    session.exec(stmt)
    return before


def _delete_draft_import_cover_images(session: Session, user_id: int | None) -> int:
    where = [CoverImage.draft_import_id.is_not(None)]
    if user_id is not None:
        where.append(
            CoverImage.draft_import_id.in_(select(DraftImport.id).where(DraftImport.user_id == user_id))
        )
    return _delete_rows(session, CoverImage, *where)


def _inventory_copy_id_subquery(user_id: int | None):
    stmt = select(InventoryCopy.id)
    if user_id is not None:
        stmt = stmt.where(InventoryCopy.user_id == user_id)
    return stmt


def _delete_for_inventory_copies(session: Session, model, column, user_id: int | None) -> int:
    subq = _inventory_copy_id_subquery(user_id)
    return _delete_rows(session, model, column.in_(subq))


def _scalar_ids(session: Session, stmt) -> list[int]:
    return [int(x) for x in session.scalars(stmt).all() if x is not None]


def _photo_session_ids(session: Session, user_id: int | None) -> list[int]:
    stmt = select(PhotoImportSession.id)
    if user_id is not None:
        stmt = stmt.where(PhotoImportSession.user_id == user_id)
    return _scalar_ids(session, stmt)


def _scan_session_ids(session: Session, user_id: int | None) -> list[int]:
    stmt = select(InventoryScanSession.id)
    if user_id is not None:
        stmt = stmt.where(InventoryScanSession.user_id == user_id)
    return _scalar_ids(session, stmt)


def _grading_candidate_ids(session: Session, user_id: int | None) -> list[int]:
    stmt = select(GradingCandidate.id)
    if user_id is not None:
        stmt = stmt.where(GradingCandidate.owner_user_id == user_id)
    return _scalar_ids(session, stmt)


def wipe_collection(*, session: Session, dry_run: bool, user_id: int | None) -> dict[str, int | bool]:
    report: dict[str, int | bool] = {"dry_run": dry_run}
    if user_id is not None:
        report["user_id"] = user_id

    photo_ids = _photo_session_ids(session, user_id)
    scan_ids = _scan_session_ids(session, user_id)
    candidate_ids = _grading_candidate_ids(session, user_id)

    steps: list[tuple[str, callable]] = []

    if photo_ids:
        steps.extend(
            [
                (
                    "photo_import_vision_read",
                    lambda: _delete_rows(
                        session,
                        PhotoImportVisionRead,
                        PhotoImportVisionRead.session_id.in_(photo_ids),
                    ),
                ),
                (
                    "photo_import_candidate",
                    lambda: _delete_rows(
                        session,
                        PhotoImportCandidate,
                        PhotoImportCandidate.detected_book_id.in_(
                            select(PhotoImportDetectedBook.id).where(
                                PhotoImportDetectedBook.session_id.in_(photo_ids)
                            )
                        ),
                    ),
                ),
                (
                    "photo_import_detected_book",
                    lambda: _delete_rows(
                        session,
                        PhotoImportDetectedBook,
                        PhotoImportDetectedBook.session_id.in_(photo_ids),
                    ),
                ),
                (
                    "photo_import_image",
                    lambda: _delete_rows(
                        session,
                        PhotoImportImage,
                        PhotoImportImage.session_id.in_(photo_ids),
                    ),
                ),
            ]
        )
    steps.append(
        (
            "photo_import_session",
            lambda: _delete_rows(
                session,
                PhotoImportSession,
                *([PhotoImportSession.user_id == user_id] if user_id is not None else []),
            ),
        )
    )

    if P80MobileIntakeSession is not None:
        steps.append(
            (
                "mobile_intake_session",
                lambda: _delete_rows(
                    session,
                    P80MobileIntakeSession,
                    *([P80MobileIntakeSession.owner_user_id == user_id] if user_id is not None else []),
                ),
            )
        )

    if scan_ids:
        steps.append(
            (
                "inventory_scan_item",
                lambda: _delete_rows(
                    session,
                    InventoryScanItem,
                    InventoryScanItem.session_id.in_(scan_ids),
                ),
            )
        )
    steps.append(
        (
            "inventory_scan_session",
            lambda: _delete_rows(
                session,
                InventoryScanSession,
                *([InventoryScanSession.user_id == user_id] if user_id is not None else []),
            ),
        )
    )

    if candidate_ids:
        for label, model in (
            ("grading_candidate_evidence", GradingCandidateEvidence),
            ("grading_candidate_lifecycle_event", GradingCandidateLifecycleEvent),
            ("grading_candidate_snapshot", GradingCandidateSnapshot),
        ):
            steps.append(
                (
                    label,
                    lambda m=model: _delete_rows(
                        session,
                        m,
                        m.grading_candidate_id.in_(candidate_ids),
                    ),
                )
            )
    steps.append(
        (
            "grading_candidate",
            lambda: _delete_rows(
                session,
                GradingCandidate,
                *([GradingCandidate.owner_user_id == user_id] if user_id is not None else []),
            ),
        )
    )

    order_filter = [Order.user_id == user_id] if user_id is not None else []
    copy_filter = [InventoryCopy.user_id == user_id] if user_id is not None else []

    steps.extend(
        [
            (
                "p92_import_line_cover_resolution",
                lambda: _delete_for_inventory_copies(
                    session, P92ImportLineCoverResolution, P92ImportLineCoverResolution.inventory_copy_id, user_id
                ),
            ),
            (
                "cover_image",
                lambda: _delete_for_inventory_copies(session, CoverImage, CoverImage.inventory_copy_id, user_id),
            ),
            (
                "portfolio_item",
                lambda: _delete_rows(
                    session,
                    PortfolioItem,
                    *(
                        [
                            PortfolioItem.inventory_item_id.in_(
                                select(InventoryCopy.id).where(InventoryCopy.user_id == user_id)
                            )
                        ]
                        if user_id is not None
                        else []
                    ),
                ),
            ),
            ("inventory_copy", lambda: _delete_rows(session, InventoryCopy, *copy_filter)),
            (
                "acquisition_placeholder_issue",
                lambda: _delete_rows(
                    session,
                    AcquisitionPlaceholderIssue,
                    *(
                        [
                            AcquisitionPlaceholderIssue.acquisition_id.in_(
                                select(Acquisition.id).where(Acquisition.user_id == user_id)
                            )
                        ]
                        if user_id is not None
                        else []
                    ),
                ),
            ),
            ("acquisition", lambda: _delete_rows(session, Acquisition, *([Acquisition.user_id == user_id] if user_id else []))),
        ]
    )
    legacy_orders = legacy_customer_order_table_exists(session)
    if legacy_orders:
        steps.extend(
            [
                (
                    "order_item",
                    lambda: _delete_rows(
                        session,
                        OrderItem,
                        *([OrderItem.order_id.in_(select(Order.id).where(Order.user_id == user_id))] if user_id else []),
                    ),
                ),
                ("customer_order", lambda: _delete_rows(session, Order, *order_filter)),
            ]
        )
    steps.extend(
        [
            ("ops_event", lambda: _delete_rows(session, OpsEvent)),
            ("gmail_import_record", lambda: _delete_rows(session, GmailImportRecord)),
            ("p92_import_health_event", lambda: _delete_rows(session, P92ImportHealthEvent)),
            ("p92_import_line_cover_all", lambda: _delete_rows(session, P92ImportLineCoverResolution)),
            (
                "draft_import_primary_cover_unlink",
                lambda: _null_draft_import_primary_covers(session, user_id),
            ),
            ("cover_image_draft_import", lambda: _delete_draft_import_cover_images(session, user_id)),
            ("draft_import", lambda: _delete_rows(session, DraftImport, *([DraftImport.user_id == user_id] if user_id else []))),
        ]
    )

    for key, fn in steps:
        if dry_run:
            # Re-count using the same filters where cheap; destructive steps skipped.
            report[key] = 0
        else:
            report[key] = fn()

    if dry_run:
        # Dry-run counts (no mutations).
        report["photo_import_session"] = _count_rows(
            session,
            PhotoImportSession,
            *([PhotoImportSession.user_id == user_id] if user_id is not None else []),
        )
        report["inventory_scan_session"] = _count_rows(
            session,
            InventoryScanSession,
            *([InventoryScanSession.user_id == user_id] if user_id is not None else []),
        )
        report["grading_candidate"] = _count_rows(
            session,
            GradingCandidate,
            *([GradingCandidate.owner_user_id == user_id] if user_id is not None else []),
        )
        report["inventory_copy"] = _count_rows(session, InventoryCopy, *copy_filter)
        report["acquisition"] = _count_rows(
            session,
            Acquisition,
            *([Acquisition.user_id == user_id] if user_id is not None else []),
        )
        report["customer_order"] = (
            _count_rows(session, Order, *order_filter) if legacy_customer_order_table_exists(session) else 0
        )
        report["draft_import"] = _count_rows(
            session,
            DraftImport,
            *([DraftImport.user_id == user_id] if user_id is not None else []),
        )
    else:
        session.commit()

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Wipe test collection data (not catalog_*).")
    parser.add_argument("--email", default=None, help="Limit deletes to this user email.")
    parser.add_argument("--dry-run", action="store_true", help="Count only; do not delete.")
    args = parser.parse_args()

    with Session(get_engine()) as session:
        user_id = _resolve_user_id(session, args.email)
        report = wipe_collection(session=session, dry_run=args.dry_run, user_id=user_id)

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
