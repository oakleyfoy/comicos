from __future__ import annotations

from sqlmodel import Session, select

from app.models.purchase_profile import (
    DEFAULT_PROFILE_TYPE,
    PurchasePreference,
    PurchaseProfile,
    PURCHASE_PROFILE_TYPES,
    utc_now,
)
from app.schemas.purchase_profile import (
    PurchasePreferenceRead,
    PurchasePreferenceUpdate,
    PurchaseProfileRead,
    PurchaseProfileUpdate,
)
from app.services.purchase_profile_scoring import preset_for_profile_type


def _clamp_pref(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _profile_to_read(row: PurchaseProfile) -> PurchaseProfileRead:
    return PurchaseProfileRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        profile_type=row.profile_type,  # type: ignore[arg-type]
        display_name=row.display_name,
        description=row.description,
        is_active=bool(row.is_active),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _preference_to_read(row: PurchasePreference) -> PurchasePreferenceRead:
    return PurchasePreferenceRead(
        id=int(row.id or 0),
        owner_id=int(row.owner_user_id),
        preferred_copy_count=int(row.preferred_copy_count),
        risk_tolerance=float(row.risk_tolerance),
        variant_interest=float(row.variant_interest),
        grading_interest=float(row.grading_interest),
        completionist_score=float(row.completionist_score),
        speculation_score=float(row.speculation_score),
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


def _default_preferences(owner_user_id: int) -> PurchasePreference:
    return PurchasePreference(
        owner_user_id=owner_user_id,
        preferred_copy_count=1,
        risk_tolerance=0.50,
        variant_interest=0.50,
        grading_interest=0.50,
        completionist_score=0.50,
        speculation_score=0.50,
    )


def _default_profile(owner_user_id: int) -> PurchaseProfile:
    preset = preset_for_profile_type(DEFAULT_PROFILE_TYPE)
    return PurchaseProfile(
        owner_user_id=owner_user_id,
        profile_type=DEFAULT_PROFILE_TYPE,
        display_name=str(preset["display_name"]),
        description=str(preset["description"]),
        is_active=True,
    )


def get_purchase_profile(session: Session, *, owner_user_id: int) -> PurchaseProfileRead:
    row = session.exec(select(PurchaseProfile).where(PurchaseProfile.owner_user_id == owner_user_id)).first()
    if row is None:
        row = _default_profile(owner_user_id)
        session.add(row)
        session.commit()
        session.refresh(row)
    return _profile_to_read(row)


def set_purchase_profile(
    session: Session,
    *,
    owner_user_id: int,
    payload: PurchaseProfileUpdate,
) -> PurchaseProfileRead:
    row = session.exec(select(PurchaseProfile).where(PurchaseProfile.owner_user_id == owner_user_id)).first()
    if row is None:
        row = _default_profile(owner_user_id)
        session.add(row)
        session.flush()
        session.refresh(row)

    if payload.profile_type is not None:
        profile_type = payload.profile_type.strip().upper()
        if profile_type not in PURCHASE_PROFILE_TYPES:
            raise ValueError(f"Invalid profile_type: {payload.profile_type}")
        preset = preset_for_profile_type(profile_type)
        row.profile_type = profile_type
        if payload.display_name is None:
            row.display_name = str(preset["display_name"])
        if payload.description is None:
            row.description = str(preset["description"])
        pref = session.exec(select(PurchasePreference).where(PurchasePreference.owner_user_id == owner_user_id)).first()
        if pref is None:
            pref = _default_preferences(owner_user_id)
            session.add(pref)
            session.flush()
            session.refresh(pref)
        for key in ("risk_tolerance", "variant_interest", "grading_interest", "completionist_score", "speculation_score"):
            setattr(pref, key, float(preset[key]))
        pref.updated_at = utc_now()
        session.add(pref)

    if payload.display_name is not None:
        row.display_name = payload.display_name.strip()
    if payload.description is not None:
        row.description = payload.description.strip()
    if payload.is_active is not None:
        row.is_active = bool(payload.is_active)
        if not row.is_active:
            raise ValueError("Purchase profile must remain active; one active profile per owner is required.")

    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _profile_to_read(row)


def get_purchase_preferences(session: Session, *, owner_user_id: int) -> PurchasePreferenceRead:
    row = session.exec(select(PurchasePreference).where(PurchasePreference.owner_user_id == owner_user_id)).first()
    if row is None:
        row = _default_preferences(owner_user_id)
        session.add(row)
        session.commit()
        session.refresh(row)
    return _preference_to_read(row)


def update_purchase_preferences(
    session: Session,
    *,
    owner_user_id: int,
    payload: PurchasePreferenceUpdate,
) -> PurchasePreferenceRead:
    row = session.exec(select(PurchasePreference).where(PurchasePreference.owner_user_id == owner_user_id)).first()
    if row is None:
        row = _default_preferences(owner_user_id)
        session.add(row)
        session.flush()
        session.refresh(row)

    if payload.preferred_copy_count is not None:
        row.preferred_copy_count = int(payload.preferred_copy_count)
    if payload.risk_tolerance is not None:
        row.risk_tolerance = _clamp_pref(payload.risk_tolerance)
    if payload.variant_interest is not None:
        row.variant_interest = _clamp_pref(payload.variant_interest)
    if payload.grading_interest is not None:
        row.grading_interest = _clamp_pref(payload.grading_interest)
    if payload.completionist_score is not None:
        row.completionist_score = _clamp_pref(payload.completionist_score)
    if payload.speculation_score is not None:
        row.speculation_score = _clamp_pref(payload.speculation_score)

    row.updated_at = utc_now()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _preference_to_read(row)
