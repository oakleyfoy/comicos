from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlmodel import Session

from app.models.lunar_scheduler import LunarScheduleConfig


@dataclass(frozen=True)
class LunarFileSnapshot:
    file_name: str
    file_period: str
    checksum: str
    content_bytes: bytes
    source_url: str


@dataclass(frozen=True)
class LunarChangeDecision:
    should_import: bool
    reason: str
    is_new_file: bool
    is_changed_file: bool


def calculate_file_checksum(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()


def track_last_imported_file(config: LunarScheduleConfig) -> tuple[str, str, str, datetime | None]:
    return (
        config.last_imported_file_name,
        config.last_imported_file_period,
        config.last_imported_checksum,
        config.last_imported_at,
    )


def detect_new_file(
    *,
    last_file_name: str,
    last_file_period: str,
    snapshot: LunarFileSnapshot,
) -> bool:
    if not last_file_name and not last_file_period:
        return True
    if snapshot.file_period != last_file_period:
        return True
    if snapshot.file_name != last_file_name:
        return True
    return False


def detect_changed_file(*, last_checksum: str, snapshot: LunarFileSnapshot) -> bool:
    if not last_checksum:
        return True
    return snapshot.checksum != last_checksum


def evaluate_import_decision(
    session: Session,
    *,
    owner_user_id: int,
    snapshot: LunarFileSnapshot,
    config: LunarScheduleConfig | None = None,
) -> LunarChangeDecision:
    if config is None:
        from sqlmodel import select

        config = session.exec(
            select(LunarScheduleConfig).where(LunarScheduleConfig.owner_user_id == owner_user_id)
        ).first()
    last_name, last_period, last_checksum, _ = track_last_imported_file(config) if config else ("", "", "", None)
    is_new = detect_new_file(last_file_name=last_name, last_file_period=last_period, snapshot=snapshot)
    is_changed = detect_changed_file(last_checksum=last_checksum, snapshot=snapshot)
    if is_new:
        return LunarChangeDecision(should_import=True, reason="NEW_FILE", is_new_file=True, is_changed_file=False)
    if is_changed:
        return LunarChangeDecision(
            should_import=True,
            reason="CHANGED_FILE",
            is_new_file=False,
            is_changed_file=True,
        )
    return LunarChangeDecision(should_import=False, reason="UNCHANGED", is_new_file=False, is_changed_file=False)


def persist_last_imported_file(
    session: Session,
    *,
    config: LunarScheduleConfig,
    snapshot: LunarFileSnapshot,
) -> LunarScheduleConfig:
    config.last_imported_file_name = snapshot.file_name
    config.last_imported_file_period = snapshot.file_period
    config.last_imported_checksum = snapshot.checksum
    config.last_imported_at = datetime.now(timezone.utc)
    config.updated_at = datetime.now(timezone.utc)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config
