"""Scanner profile presets (deterministic persistence; no runtime hardware)."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import case, or_
from sqlmodel import Session, select

from app.models import ScanSession, ScannerProfile
from app.models.asset_ledger import utc_now

from app.schemas.scanner_profiles import (
    ScannerProfileCreatePayload,
    ScannerProfileListResponse,
    ScannerProfileRead,
    ScannerProfileSnapshotRead,
    ScannerProfileUpdatePayload,
)


@dataclass(frozen=True)
class _PresetRow:
    profile_name: str
    scanner_type: str
    dpi: int | None
    color_mode: str
    file_format: str
    duplex_enabled: bool
    feeder_enabled: bool
    recommended_use: str
    is_default: bool
    notes: str | None


SYSTEM_SCANNER_PROFILE_PRESETS: tuple[_PresetRow, ...] = (
    _PresetRow(
        profile_name="Fujitsu Bulk 300dpi Color PNG",
        scanner_type="fujitsu_bulk",
        dpi=300,
        color_mode="color",
        file_format="png",
        duplex_enabled=True,
        feeder_enabled=True,
        recommended_use="bulk_ingest",
        is_default=True,
        notes="Suggested Fujitsu ADF bulk preset (metadata only — adjust your driver manually).",
    ),
    _PresetRow(
        profile_name="Fujitsu Bulk 400dpi Color PNG",
        scanner_type="fujitsu_bulk",
        dpi=400,
        color_mode="color",
        file_format="png",
        duplex_enabled=True,
        feeder_enabled=True,
        recommended_use="bulk_ingest",
        is_default=False,
        notes="Higher-resolution Fujitsu bulk suggestion.",
    ),
    _PresetRow(
        profile_name="Epson High-Res 600dpi Color PNG",
        scanner_type="epson_high_res",
        dpi=600,
        color_mode="color",
        file_format="png",
        duplex_enabled=False,
        feeder_enabled=False,
        recommended_use="high_res_review",
        is_default=False,
        notes="Suggested flatbed/transparency workflow for OCR review scans.",
    ),
    _PresetRow(
        profile_name="Epson Archival 1200dpi TIFF",
        scanner_type="epson_high_res",
        dpi=1200,
        color_mode="color",
        file_format="tif",
        duplex_enabled=False,
        feeder_enabled=False,
        recommended_use="archival_scan",
        is_default=False,
        notes="Archival master capture suggestion (large files expected).",
    ),
)


def ensure_system_scanner_profile_presets(session: Session) -> None:
    """Idempotent inserts for bundled suggestions (owner_user_id NULL)."""

    existing_stmt = (
        select(ScannerProfile.profile_name).where(ScannerProfile.owner_user_id.is_(None))  # noqa: E711
    )
    existing = set(session.exec(existing_stmt).all())
    touched = False
    for preset in SYSTEM_SCANNER_PROFILE_PRESETS:
        if preset.profile_name in existing:
            continue
        now = utc_now()
        session.add(
            ScannerProfile(
                owner_user_id=None,
                profile_name=preset.profile_name,
                scanner_type=preset.scanner_type,
                dpi=preset.dpi,
                color_mode=preset.color_mode,
                file_format=preset.file_format,
                duplex_enabled=preset.duplex_enabled,
                feeder_enabled=preset.feeder_enabled,
                recommended_use=preset.recommended_use,
                is_default=preset.is_default,
                notes=preset.notes,
                created_at=now,
                updated_at=now,
            ),
        )
        touched = True
    if touched:
        session.commit()

    stmt_system_defaults = (
        select(ScannerProfile)
        .where(ScannerProfile.owner_user_id.is_(None))  # noqa: E711
        .where(ScannerProfile.is_default.is_(True))  # noqa: E712
    )
    sys_defaults = list(session.exec(stmt_system_defaults).all())
    if len(sys_defaults) > 1:
        keep = sorted(sys_defaults, key=lambda r: (int(r.id or 0)))[0]
        for row in sys_defaults:
            if int(row.id or 0) != int(keep.id or 0):
                row.is_default = False
                row.updated_at = utc_now()
                session.add(row)
        session.commit()


def snapshot_dict_from_profile(row: ScannerProfile) -> dict:
    payload = ScannerProfileSnapshotRead(
        profile_name=row.profile_name,
        scanner_type=str(row.scanner_type),  # type: ignore[arg-type]
        dpi=row.dpi,
        color_mode=str(row.color_mode),  # type: ignore[arg-type]
        file_format=str(row.file_format),  # type: ignore[arg-type]
        duplex_enabled=bool(row.duplex_enabled),
        feeder_enabled=bool(row.feeder_enabled),
        recommended_use=str(row.recommended_use),  # type: ignore[arg-type]
    )
    return payload.model_dump()


def scanner_profile_readable_by_owner(*, profile: ScannerProfile, owner_user_id: int | None) -> bool:
    if profile.owner_user_id is None:
        return True
    if owner_user_id is None:
        return False
    return int(profile.owner_user_id) == int(owner_user_id)


def get_profile_or_404(session: Session, *, profile_id: int) -> ScannerProfile:
    row = session.get(ScannerProfile, profile_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Scanner profile not found")
    return row


def require_profile_usable_for_session(session: Session, *, owner_user_id: int, profile_id: int) -> ScannerProfile:
    profile = get_profile_or_404(session, profile_id=profile_id)
    if not scanner_profile_readable_by_owner(profile=profile, owner_user_id=owner_user_id):
        raise HTTPException(status_code=403, detail="Scanner profile is not usable for this account")
    return profile


def _clear_owner_defaults(session: Session, *, owner_user_id: int, keep_id: int | None) -> None:
    rows = session.exec(select(ScannerProfile).where(ScannerProfile.owner_user_id == owner_user_id)).all()
    for row in rows:
        rid = row.id
        if row.is_default and rid is not None and (keep_id is None or int(rid) != int(keep_id)):
            row.is_default = False
            row.updated_at = utc_now()
            session.add(row)


def create_scanner_profile(
    session: Session,
    *,
    owner_user_id: int,
    payload: ScannerProfileCreatePayload,
) -> ScannerProfileRead:
    ensure_system_scanner_profile_presets(session)
    if payload.is_default:
        _clear_owner_defaults(session, owner_user_id=owner_user_id, keep_id=None)

    now = utc_now()
    row = ScannerProfile(
        owner_user_id=owner_user_id,
        profile_name=payload.profile_name.strip(),
        scanner_type=str(payload.scanner_type),
        dpi=payload.dpi,
        color_mode=str(payload.color_mode),
        file_format=str(payload.file_format),
        duplex_enabled=payload.duplex_enabled,
        feeder_enabled=payload.feeder_enabled,
        recommended_use=str(payload.recommended_use),
        is_default=payload.is_default,
        notes=payload.notes.strip() if payload.notes else None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)

    return ScannerProfileRead.model_validate(row, from_attributes=True)


def list_scanner_profiles_for_owner(session: Session, *, owner_user_id: int) -> ScannerProfileListResponse:
    ensure_system_scanner_profile_presets(session)

    globals_first = (
        select(ScannerProfile)
        .where(
            or_(
                ScannerProfile.owner_user_id.is_(None),
                ScannerProfile.owner_user_id == owner_user_id,
            )
        )
        .order_by(
            case((ScannerProfile.owner_user_id.is_(None), 0), else_=1),
            ScannerProfile.profile_name.asc(),
            ScannerProfile.id.asc(),
        )
    )
    rows = session.exec(globals_first).all()
    return ScannerProfileListResponse(items=[ScannerProfileRead.model_validate(r, from_attributes=True) for r in rows])


def list_scanner_profiles_ops(session: Session) -> ScannerProfileListResponse:
    ensure_system_scanner_profile_presets(session)
    stmt = select(ScannerProfile).order_by(
        case((ScannerProfile.owner_user_id.is_(None), 0), else_=1),
        ScannerProfile.owner_user_id.asc(),
        ScannerProfile.profile_name.asc(),
        ScannerProfile.id.asc(),
    )
    rows = session.exec(stmt).all()
    return ScannerProfileListResponse(items=[ScannerProfileRead.model_validate(r, from_attributes=True) for r in rows])


def get_scanner_profile_detail_for_owner(session: Session, *, owner_user_id: int, profile_id: int) -> ScannerProfileRead:
    profile = get_profile_or_404(session, profile_id=profile_id)
    if not scanner_profile_readable_by_owner(profile=profile, owner_user_id=owner_user_id):
        raise HTTPException(status_code=404, detail="Scanner profile not found")
    return ScannerProfileRead.model_validate(profile, from_attributes=True)


def update_scanner_profile_for_owner(
    session: Session,
    *,
    owner_user_id: int,
    profile_id: int,
    payload: ScannerProfileUpdatePayload,
) -> ScannerProfileRead:
    profile = get_profile_or_404(session, profile_id=profile_id)
    if profile.owner_user_id is None:
        raise HTTPException(status_code=403, detail="System scanner profiles cannot be edited here")
    if int(profile.owner_user_id) != int(owner_user_id):
        raise HTTPException(status_code=404, detail="Scanner profile not found")

    patch = payload.model_dump(exclude_unset=True)

    if patch.get("is_default") is True:
        _clear_owner_defaults(session, owner_user_id=int(owner_user_id), keep_id=int(profile.id))

    for attr, val in patch.items():
        setattr(profile, attr, val)

    profile.updated_at = utc_now()
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return ScannerProfileRead.model_validate(profile, from_attributes=True)


def delete_scanner_profile_for_owner(session: Session, *, owner_user_id: int, profile_id: int) -> None:
    profile = get_profile_or_404(session, profile_id=profile_id)
    if profile.owner_user_id is None:
        raise HTTPException(status_code=403, detail="System scanner profiles cannot be deleted")
    if int(profile.owner_user_id) != int(owner_user_id):
        raise HTTPException(status_code=404, detail="Scanner profile not found")

    dangling = session.exec(select(ScanSession).where(ScanSession.scanner_profile_id == profile_id)).all()
    for ref in dangling:
        ref.scanner_profile_id = None
        session.add(ref)

    session.delete(profile)
    session.commit()

