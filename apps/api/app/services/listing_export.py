"""P36-02 deterministic listing export generation (read-only listings; replay-safe ledger)."""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.config import Settings
from app.models import Listing, ListingExportFile, ListingExportRun, ListingExportRunItem, ListingExportTemplate
from app.models.listing_registry import utc_now as listing_utc_now
from app.schemas.listing_export import (
    EXPORT_CHANNELS,
    ListingExportDashboardSummary,
    ListingExportFileRead,
    ListingExportRunCreate,
    ListingExportRunDetailRead,
    ListingExportRunItemRead,
    ListingExportRunRead,
    ListingExportTemplateRead,
)
from app.services.listing_registry import list_listing_images
from app.services.reports_export import render_csv


def utc_now():  # noqa: ANN201
    return listing_utc_now()


EXPORTABLE_STATUSES = frozenset({"READY", "ACTIVE"})


def clamp_list_export_pagination(*, limit: int, offset: int) -> tuple[int, int]:
    return min(max(limit, 1), 500), max(offset, 0)


def skip_reason_for_status(listing_status: str) -> str:
    mapping = {
        "DRAFT": "SKIP_STATUS_DRAFT",
        "SOLD": "SKIP_STATUS_SOLD",
        "CANCELLED": "SKIP_STATUS_CANCELLED",
        "ARCHIVED": "SKIP_STATUS_ARCHIVED",
    }
    return mapping.get(listing_status, "SKIP_UNKNOWN_STATUS")


_BASE_COLUMNS: tuple[tuple[str, str], ...] = (
    ("listing_id", "listing_id"),
    ("title", "title"),
    ("description", "description"),
    ("condition_summary", "condition_summary"),
    ("asking_price_amount", "asking_price_amount"),
    ("asking_price_currency", "asking_price_currency"),
    ("quantity", "quantity"),
    ("status", "status"),
    ("source_type", "source_type"),
    ("primary_image", "primary_image"),
    ("additional_images", "additional_images"),
    ("created_at", "created_at"),
)

_EBAY_EXTRA: tuple[tuple[str, str], ...] = (
    ("category", "category"),
    ("format", "format"),
    ("duration", "duration"),
    ("shipping_profile", "shipping_profile"),
    ("return_policy", "return_policy"),
    ("payment_policy", "payment_policy"),
)


def _column_map_records(channel: str) -> list[dict[str, str]]:
    pairs = _BASE_COLUMNS + (_EBAY_EXTRA if channel == "ebay" else tuple())
    return [{"field": f, "header": h} for f, h in pairs]


_SEED_CHANNELS: tuple[str, ...] = ("generic_csv", "ebay", "whatnot", "shopify", "hipcomic", "shortboxed")


def ensure_default_templates(session: Session, *, owner_user_id: int) -> None:
    now_ts = utc_now()
    for ch in _SEED_CHANNELS:
        q = (
            select(ListingExportTemplate)
            .where(
                ListingExportTemplate.owner_user_id == owner_user_id,
                ListingExportTemplate.channel == ch,
                ListingExportTemplate.name == "default",
            )
            .limit(1)
        )
        if session.exec(q).first():
            continue
        session.add(
            ListingExportTemplate(
                owner_user_id=owner_user_id,
                channel=ch,
                name="default",
                description=f"Starter template for channel {ch} (P36-02 deterministic export).",
                template_version="2026-05-25",
                column_map_json={"columns": _column_map_records(ch)},
                rules_json={
                    "exportable_statuses": sorted(EXPORTABLE_STATUSES),
                    "starter_template": True,
                },
                is_active=True,
                created_at=now_ts,
                updated_at=now_ts,
            )
        )


def coerce_template_row(row: ListingExportTemplate) -> ListingExportTemplateRead:
    cmap_raw = row.column_map_json or {}
    cmap = cmap_raw if isinstance(cmap_raw, dict | list) else {}
    rules = row.rules_json if isinstance(row.rules_json, dict) else {}
    return ListingExportTemplateRead(
        id=int(row.id),
        owner_user_id=int(row.owner_user_id),
        channel=str(row.channel),
        name=str(row.name),
        description=row.description,
        template_version=str(row.template_version),
        column_map_json=cmap if isinstance(cmap, list) else cmap,
        rules_json=rules,
        is_active=bool(row.is_active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def coerce_run_summary(row: ListingExportRun) -> ListingExportRunRead:
    return ListingExportRunRead(
        id=int(row.id),
        owner_user_id=int(row.owner_user_id),
        template_id=int(row.template_id),
        channel=str(row.channel),
        status=str(row.status),
        requested_listing_count=int(row.requested_listing_count),
        exported_listing_count=int(row.exported_listing_count),
        skipped_listing_count=int(row.skipped_listing_count),
        error_count=int(row.error_count),
        replay_key=row.replay_key,
        checksum=row.checksum,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def coerce_run_item(row: ListingExportRunItem) -> ListingExportRunItemRead:
    lid = getattr(row, "listing_id", None)
    lid_int = int(lid) if lid is not None else None
    return ListingExportRunItemRead(
        id=int(row.id),
        export_run_id=int(row.export_run_id),
        listing_id=lid_int,
        status=str(row.status),
        skip_reason=row.skip_reason,
        error_message=row.error_message,
        row_number=int(row.row_number),
        row_checksum=row.row_checksum,
        created_at=row.created_at,
    )


def coerce_file(row: ListingExportFile) -> ListingExportFileRead:
    return ListingExportFileRead(
        id=int(row.id),
        export_run_id=int(row.export_run_id),
        file_name=str(row.file_name),
        file_type=str(row.file_type),
        storage_path=str(row.storage_path),
        checksum=str(row.checksum),
        row_count=int(row.row_count),
        created_at=row.created_at,
    )


def list_listing_images_sorted(session: Session, listing_id: int):  # noqa: ANN201
    imgs = list_listing_images(session, listing_id)
    prim_idx: int | None = None
    for idx, img in enumerate(imgs):
        if str(img.role).lower() == "primary":
            prim_idx = idx
            break
    if prim_idx is not None and prim_idx > 0:
        return [imgs[prim_idx], *[r for i, r in enumerate(imgs) if i != prim_idx]]
    return imgs


def _image_tokens(session: Session, listing_id: int) -> tuple[str, str]:
    imgs = list_listing_images_sorted(session, listing_id)
    primary = ""
    extras: list[str] = []

    for img in imgs:
        cover_id = getattr(img, "cover_image_id", None)
        scan_id = getattr(img, "scan_session_item_id", None)
        if cover_id is not None:
            tok = f"cover_image:{cover_id}"
        elif scan_id is not None:
            tok = f"scan_item:{scan_id}"
        else:
            tok = "unresolved"
        if not primary:
            primary = tok
        elif tok != primary:
            extras.append(tok)

    extras.sort()
    return primary, "|".join(extras)


def _normalize_canon_scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _canonical_numeric_row(
    session: Session,
    listing: Listing,
    *,
    field_keys: tuple[str, ...],
) -> dict[str, Any]:
    primary, extras = _image_tokens(session, int(listing.id))
    raw: dict[str, Any] = {
        "listing_id": int(listing.id),
        "title": listing.title,
        "description": listing.description,
        "condition_summary": listing.condition_summary,
        "asking_price_amount": _normalize_canon_scalar(listing.asking_price_amount),
        "asking_price_currency": listing.asking_price_currency,
        "quantity": int(listing.quantity),
        "status": str(listing.status),
        "source_type": str(listing.source_type),
        "primary_image": primary,
        "additional_images": extras,
        "created_at": listing.created_at.isoformat() if listing.created_at else "",
        "category": "",
        "format": "",
        "duration": "",
        "shipping_profile": "",
        "return_policy": "",
        "payment_policy": "",
    }
    out: dict[str, Any] = {}
    for k in field_keys:
        if k in raw:
            out[k] = raw[k]
    return out


def _csv_row_cells(*, canon: dict[str, Any], headers: tuple[str, ...], tpl: ListingExportTemplate) -> dict[str, str]:
    cmap = tpl.column_map_json
    cols: list[dict[str, str]] | list[str] = []
    if isinstance(cmap, dict):
        cols = list(cmap.get("columns") or [])
    elif isinstance(cmap, list):
        cols = list(cmap)

    out: dict[str, str] = {}
    if isinstance(cols, list):
        for entry in cols:
            if isinstance(entry, dict):
                fk = entry.get("field")
                hh = entry.get("header")
                if not fk or not hh:
                    continue
                val = canon.get(str(fk), "")
                out[str(hh)] = "" if val is None else str(val)
            elif isinstance(entry, str):
                val = canon.get(entry, "")
                out[entry] = "" if val is None else str(val)
    for h in headers:
        out.setdefault(str(h), "")
    return out


def _headers_from_template(tpl: ListingExportTemplate) -> tuple[tuple[str, ...], tuple[str, ...]]:
    cmap = tpl.column_map_json
    cols: list[Any] = []
    if isinstance(cmap, dict):
        cols = list(cmap.get("columns") or [])
    elif isinstance(cmap, list):
        cols = list(cmap)

    headers: list[str] = []
    field_keys: list[str] = []
    for entry in cols:
        if isinstance(entry, dict):
            fk = entry.get("field")
            hh = entry.get("header")
            if fk and hh:
                field_keys.append(str(fk))
                headers.append(str(hh))
        elif isinstance(entry, str):
            field_keys.append(entry)
            headers.append(entry)
    if not headers:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="export template missing column_map_json.columns",
        )
    return tuple(headers), tuple(field_keys)


def _sanitize_channel(seg: str) -> str:
    s = seg.strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_") or "export"


def _row_checksum_stable(canon: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(canon, separators=(",", ":"), sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def list_templates_owner(session: Session, *, owner_user_id: int) -> list[ListingExportTemplateRead]:
    ensure_default_templates(session, owner_user_id=owner_user_id)
    session.flush()
    rows = session.exec(
        select(ListingExportTemplate)
        .where(
            ListingExportTemplate.owner_user_id == owner_user_id,
            col(ListingExportTemplate.is_active).is_(True),
        )
        .order_by(col(ListingExportTemplate.channel).asc())
        .order_by(col(ListingExportTemplate.name).asc())
        .order_by(col(ListingExportTemplate.id).asc())
    ).all()
    session.commit()
    return [coerce_template_row(r) for r in rows]


def resolve_template(
    session: Session,
    *,
    owner_user_id: int,
    template_id: int | None,
    channel: str | None,
) -> ListingExportTemplate:
    ensure_default_templates(session, owner_user_id=owner_user_id)
    session.flush()
    if template_id is not None:
        tpl = session.get(ListingExportTemplate, template_id)
        if tpl is None or int(tpl.owner_user_id) != owner_user_id or not tpl.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="template not found")
        return tpl

    ch = str(channel or "").strip().lower()
    if not ch or ch not in EXPORT_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_id or valid channel required",
        )
    tpl = session.exec(
        select(ListingExportTemplate).where(
            ListingExportTemplate.owner_user_id == owner_user_id,
            ListingExportTemplate.channel == ch,
            ListingExportTemplate.name == "default",
            col(ListingExportTemplate.is_active).is_(True),
        )
    ).first()
    if tpl is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="default template missing")
    return tpl


def replay_lookup_run(session: Session, *, owner_user_id: int, replay_key: str) -> ListingExportRun | None:
    return session.exec(
        select(ListingExportRun).where(
            ListingExportRun.owner_user_id == owner_user_id,
            ListingExportRun.replay_key == replay_key,
        )
    ).first()


def build_run_detail(
    session: Session,
    *,
    owner_user_id: int,
    export_run_id: int,
    include_children: bool = True,
    allow_cross_owner_ops: bool = False,
) -> ListingExportRunDetailRead:
    row = session.get(ListingExportRun, export_run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export run not found")
    if int(row.owner_user_id) != owner_user_id and not allow_cross_owner_ops:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export run not found")
    base = coerce_run_summary(row)
    if not include_children:
        return ListingExportRunDetailRead.model_validate(
            {**base.model_dump(), "items": [], "files": []}
        )
    item_rows = session.exec(
        select(ListingExportRunItem)
        .where(ListingExportRunItem.export_run_id == export_run_id)
        .order_by(col(ListingExportRunItem.row_number).asc())
        .order_by(col(ListingExportRunItem.id).asc())
    ).all()
    fil = session.exec(
        select(ListingExportFile)
        .where(ListingExportFile.export_run_id == export_run_id)
        .order_by(col(ListingExportFile.id).asc())
    ).all()
    return ListingExportRunDetailRead.model_validate(
        {
            **base.model_dump(),
            "items": [coerce_run_item(ir).model_dump() for ir in item_rows],
            "files": [coerce_file(fr).model_dump() for fr in fil],
        }
    )


def list_runs_owner(
    session: Session,
    *,
    owner_user_id: int,
    limit: int,
    offset: int,
) -> tuple[list[ListingExportRun], int]:
    total = int(
        session.exec(
            select(func.count(col(ListingExportRun.id))).where(
                ListingExportRun.owner_user_id == owner_user_id,
            ),
        ).one(),
    )
    rows = session.exec(
        select(ListingExportRun)
        .where(ListingExportRun.owner_user_id == owner_user_id)
        .order_by(col(ListingExportRun.created_at).desc())
        .order_by(col(ListingExportRun.id).desc())
        .offset(offset)
        .limit(limit),
    ).all()
    return list(rows), total


def list_runs_ops(
    session: Session,
    *,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[ListingExportRun], int]:
    qb = select(ListingExportRun)
    qc = select(func.count(col(ListingExportRun.id))).select_from(ListingExportRun)
    if owner_user_id is not None:
        qb = qb.where(ListingExportRun.owner_user_id == owner_user_id)
        qc = qc.where(ListingExportRun.owner_user_id == owner_user_id)
    total = int(session.exec(qc).one())
    rows = session.exec(
        qb.order_by(col(ListingExportRun.created_at).desc())
        .order_by(col(ListingExportRun.id).desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def dashboard_summary_owner(session: Session, *, owner_user_id: int) -> ListingExportDashboardSummary:
    completed_count = int(
        session.exec(
            select(func.count(col(ListingExportRun.id))).where(
                ListingExportRun.owner_user_id == owner_user_id,
                ListingExportRun.status == "COMPLETED",
            ),
        ).one(),
    )

    skipped_items = session.exec(
        select(func.count(col(ListingExportRunItem.id)))
        .join(ListingExportRun, col(ListingExportRunItem.export_run_id) == col(ListingExportRun.id))
        .where(
            ListingExportRun.owner_user_id == owner_user_id,
            ListingExportRunItem.status == "SKIPPED",
        ),
    ).one()
    skipped_lifetime = int(skipped_items or 0)

    latest = session.exec(
        select(ListingExportRun)
        .where(
            ListingExportRun.owner_user_id == owner_user_id,
            ListingExportRun.status == "COMPLETED",
            col(ListingExportRun.checksum).is_not(None),
        )
        .order_by(col(ListingExportRun.completed_at).desc())
        .order_by(col(ListingExportRun.id).desc())
        .limit(1),
    ).first()
    chk = latest.checksum if latest else None

    recent_rows = session.exec(
        select(ListingExportRun)
        .where(ListingExportRun.owner_user_id == owner_user_id)
        .order_by(col(ListingExportRun.created_at).desc())
        .order_by(col(ListingExportRun.id).desc())
        .limit(10),
    ).all()

    return ListingExportDashboardSummary(
        completed_run_count=completed_count,
        skipped_rows_lifetime_sum=skipped_lifetime,
        latest_completed_checksum=chk,
        recent_runs=[coerce_run_summary(r) for r in recent_rows],
    )


def list_export_files_ops(
    session: Session,
    *,
    export_run_id: int | None,
    owner_user_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[ListingExportFile], int]:
    q = select(ListingExportFile)
    cnt = select(func.count(col(ListingExportFile.id)))
    if export_run_id is not None:
        q = q.where(ListingExportFile.export_run_id == export_run_id)
        cnt = cnt.where(ListingExportFile.export_run_id == export_run_id)
    if owner_user_id is not None:
        q = q.join(ListingExportRun, col(ListingExportFile.export_run_id) == col(ListingExportRun.id)).where(
            ListingExportRun.owner_user_id == owner_user_id,
        )
        cnt = (
            select(func.count(col(ListingExportFile.id)))
            .select_from(ListingExportFile)
            .join(ListingExportRun, col(ListingExportFile.export_run_id) == col(ListingExportRun.id))
            .where(ListingExportRun.owner_user_id == owner_user_id)
        )
        if export_run_id is not None:
            cnt = cnt.where(ListingExportFile.export_run_id == export_run_id)
    total = int(session.exec(cnt).one())
    rows = session.exec(
        q.order_by(col(ListingExportFile.created_at).desc()).offset(offset).limit(limit),
    ).all()
    return list(rows), total


def execute_export_run(
    session: Session,
    *,
    owner_user_id: int,
    settings: Settings,
    payload: ListingExportRunCreate | dict,
) -> tuple[ListingExportRunDetailRead, bool]:
    if not isinstance(payload, ListingExportRunCreate):
        payload = ListingExportRunCreate.model_validate(payload)

    if payload.template_id is None and payload.channel is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="template_id or channel is required",
        )

    rk = payload.replay_key
    if rk:
        dup = replay_lookup_run(session, owner_user_id=owner_user_id, replay_key=rk)
        if dup:
            session.refresh(dup)
            return build_run_detail(session, owner_user_id=owner_user_id, export_run_id=int(dup.id)), True

    tpl = resolve_template(
        session,
        owner_user_id=owner_user_id,
        template_id=payload.template_id,
        channel=payload.channel,
    )
    headers, field_keys = _headers_from_template(tpl)
    listing_ids_sorted = sorted(set(payload.listing_ids))

    now_ts = utc_now()
    run = ListingExportRun(
        owner_user_id=owner_user_id,
        template_id=int(tpl.id),
        channel=str(tpl.channel),
        status="RUNNING",
        requested_listing_count=len(listing_ids_sorted),
        exported_listing_count=0,
        skipped_listing_count=0,
        error_count=0,
        replay_key=rk,
        checksum=None,
        created_at=now_ts,
        started_at=now_ts,
        completed_at=None,
    )
    session.add(run)

    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        if rk:
            dup_hit = replay_lookup_run(session, owner_user_id=owner_user_id, replay_key=rk)
            if dup_hit:
                return (
                    build_run_detail(
                        session,
                        owner_user_id=owner_user_id,
                        export_run_id=int(dup_hit.id),
                    ),
                    True,
                )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="export replay collision")

    run_row = session.get(ListingExportRun, int(run.id))
    if run_row is None:
        raise RuntimeError("export run vanished after flush")

    exported = 0
    skipped_ct = 0
    csv_cells: list[dict[str, str]] = []
    rn = 0
    for lid in listing_ids_sorted:
        rn += 1
        lst = session.get(Listing, lid)

        if lst is None or int(lst.owner_user_id) != owner_user_id:
            skipped_ct += 1
            skip_listing_pk = int(lst.id) if lst is not None else None
            session.add(
                ListingExportRunItem(
                    export_run_id=int(run_row.id),
                    listing_id=skip_listing_pk,
                    status="SKIPPED",
                    skip_reason="SKIP_NOT_OWNED_OR_MISSING",
                    error_message=None,
                    row_number=rn,
                    row_checksum=None,
                    created_at=utc_now(),
                ),
            )
            continue

        if str(lst.status) not in EXPORTABLE_STATUSES:
            skipped_ct += 1
            session.add(
                ListingExportRunItem(
                    export_run_id=int(run_row.id),
                    listing_id=int(lst.id),
                    status="SKIPPED",
                    skip_reason=skip_reason_for_status(str(lst.status)),
                    error_message=None,
                    row_number=rn,
                    row_checksum=None,
                    created_at=utc_now(),
                ),
            )
            continue

        canon = _canonical_numeric_row(session, lst, field_keys=field_keys)
        r_checksum = _row_checksum_stable(canon)
        csv_cells.append(_csv_row_cells(canon=canon, headers=headers, tpl=tpl))

        exported += 1
        session.add(
            ListingExportRunItem(
                export_run_id=int(run_row.id),
                listing_id=int(lst.id),
                status="EXPORTED",
                skip_reason=None,
                error_message=None,
                row_number=rn,
                row_checksum=r_checksum,
                created_at=utc_now(),
            ),
        )

    csv_text = render_csv(headers, csv_cells)
    file_cs = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()

    root = settings.listing_exports_storage_root
    rel_dir = f"{owner_user_id}/{int(run_row.id)}"
    dir_path = root / Path(rel_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    day_part = run_row.created_at.date().isoformat() if run_row.created_at else now_ts.date().isoformat()
    safe_ch = _sanitize_channel(str(tpl.channel))
    fname = f"comic_os_{safe_ch}_export_run_{int(run_row.id)}_{day_part}.csv"
    abs_path = dir_path / fname
    abs_path.write_text(csv_text, encoding="utf-8")
    storage_rel = f"{rel_dir}/{fname}".replace("\\", "/")

    session.add(
        ListingExportFile(
            export_run_id=int(run_row.id),
            file_name=fname,
            file_type="csv",
            storage_path=storage_rel,
            checksum=file_cs,
            row_count=exported,
            created_at=utc_now(),
        ),
    )

    run_row.status = "COMPLETED"
    run_row.exported_listing_count = exported
    run_row.skipped_listing_count = skipped_ct
    run_row.checksum = file_cs
    run_row.completed_at = utc_now()
    session.add(run_row)

    session.commit()
    return build_run_detail(session, owner_user_id=owner_user_id, export_run_id=int(run_row.id)), False


def resolve_export_download_path_session(
    session: Session,
    settings: Settings,
    *,
    owner_user_id: int,
    export_run_id: int,
    file_id: int | None = None,
    allow_ops_any_owner: bool = False,
) -> tuple[Path, ListingExportFile]:
    run = session.get(ListingExportRun, export_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export run not found")
    if int(run.owner_user_id) != owner_user_id and not allow_ops_any_owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export run not found")

    if file_id is not None:
        frow = session.get(ListingExportFile, file_id)
        if frow is None or int(frow.export_run_id) != export_run_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export file not found")
    else:
        frow = session.exec(
            select(ListingExportFile)
            .where(ListingExportFile.export_run_id == export_run_id)
            .order_by(col(ListingExportFile.id).asc())
            .limit(1),
        ).first()
        if frow is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export file not found")

    root = settings.listing_exports_storage_root.resolve()
    rel = str(frow.storage_path).replace("\\", "/")
    if ".." in rel or rel.startswith("/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid storage path")

    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path escape blocked") from exc

    if not target.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="export file missing on disk")

    return target, frow

