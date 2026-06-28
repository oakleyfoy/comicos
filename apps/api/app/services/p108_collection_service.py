"""P108 collection CRUD, clone, reset, and delete."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlmodel import Session

from app.models import (
    DailyCollectorAction,
    IntakeSession,
    IntakeSessionItem,
    InventoryCopy,
    Order,
    OrderItem,
    PhotoImportCandidate,
    PhotoImportDetectedBook,
    PhotoImportImage,
    PhotoImportSession,
    PullList,
    PullListIssue,
    RecommendationRunV2,
    RecommendationScoreV2,
    RetailerOrderItemSnapshot,
    RetailerOrderSnapshot,
    RetailerSyncRun,
    User,
)
from app.models.inventory_scan_session import InventoryScanItem, InventoryScanSession
from app.models.p108_collection import (
    COLLECTION_TYPE_REAL,
    COLLECTION_TYPE_SANDBOX,
    COLLECTION_TYPE_TEST,
    UserDataCollection,
    utc_now,
)
from app.models.p80_mobile_scan import P80MobileScan
from app.services.legacy_spine_availability import legacy_customer_order_table_exists
from app.services.collection_context import (
    ensure_default_real_collection,
    get_collection_for_user,
    require_active_collection_id,
)

logger = logging.getLogger(__name__)


def _default_clone_name(source_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    return f"Test Copy of {source_name} - {stamp}"


def _clear_other_defaults(session: Session, *, owner_user_id: int, keep_id: int | None = None) -> None:
    stmt = (
        update(UserDataCollection)
        .where(UserDataCollection.owner_user_id == owner_user_id)
        .where(UserDataCollection.deleted_at.is_(None))
        .where(UserDataCollection.is_default.is_(True))
    )
    if keep_id is not None:
        stmt = stmt.where(UserDataCollection.id != keep_id)
    session.execute(stmt.values(is_default=False, updated_at=utc_now()))


def list_collections_for_user(session: Session, *, user_id: int) -> list[UserDataCollection]:
    return list(
        session.scalars(
            select(UserDataCollection)
            .where(UserDataCollection.owner_user_id == user_id)
            .where(UserDataCollection.deleted_at.is_(None))
            .order_by(UserDataCollection.is_default.desc(), UserDataCollection.id.asc())
        ).all()
    )


def create_collection(
    session: Session,
    *,
    user_id: int,
    name: str,
    collection_type: str = COLLECTION_TYPE_TEST,
    is_default: bool = False,
) -> UserDataCollection:
    if collection_type not in (COLLECTION_TYPE_REAL, COLLECTION_TYPE_TEST, COLLECTION_TYPE_SANDBOX):
        raise HTTPException(status_code=400, detail="Invalid collection type.")
    now = utc_now()
    row = UserDataCollection(
        owner_user_id=user_id,
        name=name.strip() or "Untitled Collection",
        collection_type=collection_type,
        is_default=is_default,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    if is_default:
        _clear_other_defaults(session, owner_user_id=user_id, keep_id=int(row.id or 0))
        row.is_default = True
        user = session.get(User, user_id)
        if user is not None:
            user.active_collection_id = int(row.id or 0)
            session.add(user)
    session.add(row)
    return row


def set_default_collection(session: Session, *, user_id: int, collection_id: int) -> UserDataCollection:
    row = get_collection_for_user(session, user_id=user_id, collection_id=collection_id)
    _clear_other_defaults(session, owner_user_id=user_id, keep_id=int(row.id or 0))
    row.is_default = True
    row.updated_at = utc_now()
    session.add(row)
    user = session.get(User, user_id)
    if user is not None:
        user.active_collection_id = int(row.id or 0)
        session.add(user)
    return row


def set_active_collection(session: Session, *, user: User, collection_id: int) -> UserDataCollection:
    assert user.id is not None
    row = get_collection_for_user(session, user_id=int(user.id), collection_id=collection_id)
    user.active_collection_id = int(row.id or 0)
    session.add(user)
    return row


def _row_copy(model: Any, *, overrides: dict[str, Any]) -> Any:
    data = model.model_dump(exclude={"id"})
    data.update(overrides)
    return model.__class__(**data)


def clone_collection(
    session: Session,
    *,
    user_id: int,
    source_collection_id: int,
    name: str | None = None,
    collection_type: str = COLLECTION_TYPE_TEST,
) -> UserDataCollection:
    source = get_collection_for_user(session, user_id=user_id, collection_id=source_collection_id)
    snapshot_at = utc_now()
    target = create_collection(
        session,
        user_id=user_id,
        name=name or _default_clone_name(source.name),
        collection_type=collection_type,
        is_default=False,
    )
    target.source_collection_id = int(source.id or 0)
    target.source_snapshot_at = snapshot_at
    session.add(target)
    session.flush()
    target_id = int(target.id or 0)

    order_map: dict[int, int] = {}
    if legacy_customer_order_table_exists(session):
        for order in session.scalars(select(Order).where(Order.collection_id == source.id)).all():
            copy = _row_copy(order, overrides={"collection_id": target_id})
            session.add(copy)
            session.flush()
            if order.id is not None and copy.id is not None:
                order_map[int(order.id)] = int(copy.id)

    order_item_map: dict[int, int] = {}
    if order_map:
        for item in session.scalars(select(OrderItem).where(OrderItem.order_id.in_(order_map.keys()))).all():
            copy = _row_copy(item, overrides={"order_id": order_map[int(item.order_id)]})
            session.add(copy)
            session.flush()
            if item.id is not None and copy.id is not None:
                order_item_map[int(item.id)] = int(copy.id)

    inv_map: dict[int, int] = {}
    for inv in session.scalars(select(InventoryCopy).where(InventoryCopy.collection_id == source.id)).all():
        new_order_item = order_item_map.get(int(inv.order_item_id)) if inv.order_item_id else None
        copy = _row_copy(
            inv,
            overrides={
                "collection_id": target_id,
                "order_item_id": new_order_item,
            },
        )
        session.add(copy)
        session.flush()
        if inv.id is not None and copy.id is not None:
            inv_map[int(inv.id)] = int(copy.id)

    for snap in session.scalars(select(RetailerOrderSnapshot).where(RetailerOrderSnapshot.collection_id == source.id)).all():
        copy = _row_copy(snap, overrides={"collection_id": target_id})
        session.add(copy)
        session.flush()
        if snap.id is None or copy.id is None:
            continue
        for line in session.scalars(
            select(RetailerOrderItemSnapshot).where(
                RetailerOrderItemSnapshot.retailer_order_snapshot_id == snap.id
            )
        ).all():
            line_copy = _row_copy(
                line,
                overrides={
                    "retailer_order_snapshot_id": int(copy.id),
                },
            )
            session.add(line_copy)

    for run in session.scalars(select(RetailerSyncRun).where(RetailerSyncRun.collection_id == source.id)).all():
        session.add(_row_copy(run, overrides={"collection_id": target_id}))

    session_map: dict[int, int] = {}
    for photo in session.scalars(select(PhotoImportSession).where(PhotoImportSession.collection_id == source.id)).all():
        ps = _row_copy(
            photo,
            overrides={
                "collection_id": target_id,
                "session_token": secrets.token_urlsafe(24)[:64],
            },
        )
        session.add(ps)
        session.flush()
        if photo.id is not None and ps.id is not None:
            session_map[int(photo.id)] = int(ps.id)

    image_map: dict[int, int] = {}
    if session_map:
        for img in session.exec(
            select(PhotoImportImage).where(PhotoImportImage.session_id.in_(session_map.keys()))
        ).all():
            im = _row_copy(img, overrides={"session_id": session_map[int(img.session_id)]})
            session.add(im)
            session.flush()
            if img.id is not None and im.id is not None:
                image_map[int(img.id)] = int(im.id)

    book_map: dict[int, int] = {}
    if session_map:
        for book in session.exec(
            select(PhotoImportDetectedBook).where(PhotoImportDetectedBook.session_id.in_(session_map.keys()))
        ).all():
            bk = _row_copy(
                book,
                overrides={
                    "session_id": session_map[int(book.session_id)],
                    "image_id": image_map.get(int(book.image_id), book.image_id),
                },
            )
            session.add(bk)
            session.flush()
            if book.id is not None and bk.id is not None:
                book_map[int(book.id)] = int(bk.id)

    if book_map:
        for cand in session.exec(
            select(PhotoImportCandidate).where(PhotoImportCandidate.detected_book_id.in_(book_map.keys()))
        ).all():
            session.add(
                _row_copy(cand, overrides={"detected_book_id": book_map[int(cand.detected_book_id)]})
            )

    pull_map: dict[int, int] = {}
    for pl in session.scalars(select(PullList).where(PullList.collection_id == source.id)).all():
        pl_copy = _row_copy(pl, overrides={"collection_id": target_id})
        session.add(pl_copy)
        session.flush()
        if pl.id is not None and pl_copy.id is not None:
            pull_map[int(pl.id)] = int(pl_copy.id)

    if pull_map:
        for issue in session.scalars(select(PullListIssue).where(PullListIssue.pull_list_id.in_(pull_map.keys()))).all():
            session.add(
                _row_copy(issue, overrides={"pull_list_id": pull_map[int(issue.pull_list_id)]})
            )

    for action in session.exec(
        select(DailyCollectorAction).where(DailyCollectorAction.collection_id == source.id)
    ).all():
        session.add(_row_copy(action, overrides={"collection_id": target_id}))

    scan_map: dict[int, int] = {}
    for scan in session.exec(
        select(InventoryScanSession).where(InventoryScanSession.collection_id == source.id)
    ).all():
        sc = _row_copy(
            scan,
            overrides={
                "collection_id": target_id,
                "purchase_order_id": order_map.get(int(scan.purchase_order_id))
                if scan.purchase_order_id
                else None,
            },
        )
        session.add(sc)
        session.flush()
        if scan.id is not None and sc.id is not None:
            scan_map[int(scan.id)] = int(sc.id)

    if scan_map:
        for item in session.exec(
            select(InventoryScanItem).where(InventoryScanItem.session_id.in_(scan_map.keys()))
        ).all():
            inv_id = inv_map.get(int(item.inventory_copy_id)) if item.inventory_copy_id else None
            session.add(
                _row_copy(
                    item,
                    overrides={
                        "session_id": scan_map[int(item.session_id)],
                        "inventory_copy_id": inv_id,
                    },
                )
            )

    intake_map: dict[int, int] = {}
    for intake in session.scalars(select(IntakeSession).where(IntakeSession.collection_id == source.id)).all():
        ic = _row_copy(
            intake,
            overrides={
                "collection_id": target_id,
                "session_token": secrets.token_urlsafe(24)[:64],
            },
        )
        session.add(ic)
        session.flush()
        if intake.id is not None and ic.id is not None:
            intake_map[int(intake.id)] = int(ic.id)

    if intake_map:
        for item in session.exec(
            select(IntakeSessionItem).where(IntakeSessionItem.session_id.in_(intake_map.keys()))
        ).all():
            session.add(
                _row_copy(item, overrides={"session_id": intake_map[int(item.session_id)]})
            )

    for mobile in session.scalars(select(P80MobileScan).where(P80MobileScan.collection_id == source.id)).all():
        session.add(
            _row_copy(
                mobile,
                overrides={
                    "collection_id": target_id,
                    "inventory_copy_id": inv_map.get(int(mobile.inventory_copy_id))
                    if mobile.inventory_copy_id
                    else None,
                },
            )
        )

    run_map: dict[int, int] = {}
    for run in session.exec(
        select(RecommendationRunV2).where(RecommendationRunV2.collection_id == source.id)
    ).all():
        rc = _row_copy(run, overrides={"collection_id": target_id})
        session.add(rc)
        session.flush()
        if run.id is not None and rc.id is not None:
            run_map[int(run.id)] = int(rc.id)

    if run_map:
        for score in session.exec(
            select(RecommendationScoreV2).where(RecommendationScoreV2.collection_id == source.id)
        ).all():
            session.add(
                _row_copy(
                    score,
                    overrides={
                        "collection_id": target_id,
                        "recommendation_run_id": run_map[int(score.recommendation_run_id)],
                    },
                )
            )

    session.flush()
    return target


def _delete_collection_owned_rows(session: Session, *, collection_id: int) -> None:
    cid = int(collection_id)
    scan_ids = list(
        session.scalars(select(InventoryScanSession.id).where(InventoryScanSession.collection_id == cid)).all()
    )
    if scan_ids:
        session.execute(delete(InventoryScanItem).where(InventoryScanItem.session_id.in_(scan_ids)))
    session.execute(delete(InventoryScanSession).where(InventoryScanSession.collection_id == cid))

    photo_ids = list(
        session.scalars(select(PhotoImportSession.id).where(PhotoImportSession.collection_id == cid)).all()
    )
    if photo_ids:
        book_ids = list(
            session.exec(
                select(PhotoImportDetectedBook.id).where(PhotoImportDetectedBook.session_id.in_(photo_ids))
            ).all()
        )
        if book_ids:
            session.execute(delete(PhotoImportCandidate).where(PhotoImportCandidate.detected_book_id.in_(book_ids)))
        session.execute(delete(PhotoImportDetectedBook).where(PhotoImportDetectedBook.session_id.in_(photo_ids)))
        session.execute(delete(PhotoImportImage).where(PhotoImportImage.session_id.in_(photo_ids)))
    session.execute(delete(PhotoImportSession).where(PhotoImportSession.collection_id == cid))

    snap_ids = list(
        session.scalars(select(RetailerOrderSnapshot.id).where(RetailerOrderSnapshot.collection_id == cid)).all()
    )
    if snap_ids:
        session.execute(
            delete(RetailerOrderItemSnapshot).where(
                RetailerOrderItemSnapshot.retailer_order_snapshot_id.in_(snap_ids)
            )
        )
    session.execute(delete(RetailerOrderSnapshot).where(RetailerOrderSnapshot.collection_id == cid))
    session.execute(delete(RetailerSyncRun).where(RetailerSyncRun.collection_id == cid))

    session.execute(delete(P80MobileScan).where(P80MobileScan.collection_id == cid))

    intake_ids = list(session.scalars(select(IntakeSession.id).where(IntakeSession.collection_id == cid)).all())
    if intake_ids:
        session.execute(delete(IntakeSessionItem).where(IntakeSessionItem.session_id.in_(intake_ids)))
    session.execute(delete(IntakeSession).where(IntakeSession.collection_id == cid))

    session.execute(delete(InventoryCopy).where(InventoryCopy.collection_id == cid))

    if legacy_customer_order_table_exists(session):
        order_ids = list(session.scalars(select(Order.id).where(Order.collection_id == cid)).all())
        if order_ids:
            session.execute(delete(OrderItem).where(OrderItem.order_id.in_(order_ids)))
        session.execute(delete(Order).where(Order.collection_id == cid))

    pull_ids = list(session.scalars(select(PullList.id).where(PullList.collection_id == cid)).all())
    if pull_ids:
        session.execute(delete(PullListIssue).where(PullListIssue.pull_list_id.in_(pull_ids)))
    session.execute(delete(PullList).where(PullList.collection_id == cid))

    session.execute(delete(DailyCollectorAction).where(DailyCollectorAction.collection_id == cid))

    score_ids = list(
        session.scalars(select(RecommendationScoreV2.id).where(RecommendationScoreV2.collection_id == cid)).all()
    )
    if score_ids:
        from app.models.recommendation_v2 import RecommendationDecisionV2, RecommendationScoreComponentV2

        session.execute(
            delete(RecommendationScoreComponentV2).where(
                RecommendationScoreComponentV2.recommendation_score_id.in_(score_ids)
            )
        )
        session.execute(
            delete(RecommendationDecisionV2).where(
                RecommendationDecisionV2.recommendation_score_id.in_(score_ids)
            )
        )
    session.execute(delete(RecommendationScoreV2).where(RecommendationScoreV2.collection_id == cid))
    session.execute(delete(RecommendationRunV2).where(RecommendationRunV2.collection_id == cid))


def reset_collection(
    session: Session,
    *,
    user_id: int,
    collection_id: int,
    allow_real: bool = False,
) -> UserDataCollection:
    row = get_collection_for_user(session, user_id=user_id, collection_id=collection_id)
    if row.collection_type == COLLECTION_TYPE_REAL and not allow_real:
        raise HTTPException(status_code=403, detail="Real collections cannot be reset.")
    _delete_collection_owned_rows(session, collection_id=int(row.id or 0))
    row.updated_at = utc_now()
    session.add(row)
    return row


def soft_delete_collection(session: Session, *, user_id: int, collection_id: int) -> None:
    row = get_collection_for_user(session, user_id=user_id, collection_id=collection_id)
    if row.collection_type == COLLECTION_TYPE_REAL:
        raise HTTPException(status_code=403, detail="Real collections cannot be deleted.")
    if row.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the default collection.")
    user = session.get(User, user_id)
    if user is not None and user.active_collection_id == row.id:
        default_row = ensure_default_real_collection(session, user_id=user_id)
        user.active_collection_id = int(default_row.id or 0)
        session.add(user)
    row.deleted_at = utc_now()
    row.updated_at = utc_now()
    row.is_default = False
    session.add(row)


def assign_new_row_collection_id(session: Session, user: User, row: Any) -> None:
    """Set collection_id on a new row before flush."""
    if not hasattr(row, "collection_id"):
        return
    row.collection_id = require_active_collection_id(session, user)
