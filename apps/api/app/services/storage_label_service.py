"""P79-02 printable label and QR payload foundation (no mobile scan)."""

from __future__ import annotations

from sqlmodel import Session, select

from app.models.storage_location import P79_KIND_RACK, P79_KIND_SHELF, P79StorageBox, P79StorageLocation
from app.schemas.storage_locator_audit import P79StorageLabelRead
from app.services.storage_assignment_service import build_location_path
from app.services.storage_capacity import occupied_slots_for_box


def _qr_payload(entity_type: str, entity_id: int) -> str:
    return f"comicos://p79/storage/{entity_type.lower()}/{entity_id}"


def _ancestor_path(session: Session, *, owner_user_id: int, loc: P79StorageLocation) -> str:
    chain = [loc.name]
    parent_id = loc.parent_id
    while parent_id is not None:
        parent = session.get(P79StorageLocation, parent_id)
        if parent is None or parent.owner_user_id != owner_user_id:
            break
        chain.append(parent.name)
        parent_id = parent.parent_id
    chain.reverse()
    return " / ".join(chain)


def build_storage_label(
    session: Session,
    *,
    owner_user_id: int,
    entity_type: str,
    entity_id: int,
) -> P79StorageLabelRead:
    kind = entity_type.strip().lower()
    if kind == "box":
        box = session.get(P79StorageBox, entity_id)
        if box is None or box.owner_user_id != owner_user_id:
            raise ValueError("Box not found")
        path_segs = build_location_path(session, owner_user_id=owner_user_id, shelf_location_id=box.shelf_location_id)
        path = " / ".join(s.name for s in path_segs) + f" / {box.name}"
        used = occupied_slots_for_box(session, box_id=entity_id)
        return P79StorageLabelRead(
            entity_type="box",
            entity_id=entity_id,
            label_code=f"P79-BOX-{entity_id}",
            qr_payload=_qr_payload("box", entity_id),
            printable_title=f"Box {box.name}",
            storage_path=path,
            capacity=int(box.capacity),
            current_count=used,
        )

    loc = session.get(P79StorageLocation, entity_id)
    if loc is None or loc.owner_user_id != owner_user_id:
        raise ValueError("Location not found")
    if kind == "location" and loc.location_kind != "LOCATION":
        raise ValueError("Entity is not a top-level location")
    if kind == "rack" and loc.location_kind != P79_KIND_RACK:
        raise ValueError("Entity is not a rack")
    if kind == "shelf" and loc.location_kind != P79_KIND_SHELF:
        raise ValueError("Entity is not a shelf")
    if kind not in {"location", "rack", "shelf"}:
        raise ValueError("Unsupported entity_type")

    path = _ancestor_path(session, owner_user_id=owner_user_id, loc=loc)
    cap = loc.capacity
    count = None
    if kind == "shelf":
        boxes = session.exec(select(P79StorageBox).where(P79StorageBox.shelf_location_id == entity_id)).all()
        count = sum(occupied_slots_for_box(session, box_id=int(b.id or 0)) for b in boxes)
        cap = cap or sum(int(b.capacity) for b in boxes)

    return P79StorageLabelRead(
        entity_type=kind,
        entity_id=entity_id,
        label_code=f"P79-{kind.upper()}-{entity_id}",
        qr_payload=_qr_payload(kind, entity_id),
        printable_title=loc.name,
        storage_path=path,
        capacity=cap,
        current_count=count,
    )
