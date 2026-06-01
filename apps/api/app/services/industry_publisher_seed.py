from __future__ import annotations

from sqlmodel import Session, select

from app.models.industry_publisher import IndustryPublisher
from app.services.industry_publisher_registry import (
    INDUSTRY_PUBLISHER_REGISTRY,
    IndustryPublisherSeedDefinition,
)


def industry_publisher_definitions() -> list[IndustryPublisherSeedDefinition]:
    return [
        IndustryPublisherSeedDefinition(
            publisher_code=code,
            publisher_name=name,
            scan_priority=priority,
        )
        for code, name, priority in INDUSTRY_PUBLISHER_REGISTRY
    ]


def ensure_industry_publishers_for_owner(session: Session, *, owner_user_id: int) -> int:
    existing = {
        row.publisher_code: row
        for row in session.exec(
            select(IndustryPublisher).where(IndustryPublisher.owner_user_id == owner_user_id)
        ).all()
    }
    created = 0
    for definition in industry_publisher_definitions():
        if definition.publisher_code in existing:
            continue
        row = IndustryPublisher(
            owner_user_id=owner_user_id,
            publisher_code=definition.publisher_code,
            publisher_name=definition.publisher_name,
            scan_enabled=True,
            inclusion_status="INCLUDED",
            scan_priority=definition.scan_priority,
            classification_mode="STANDARD",
        )
        session.add(row)
        created += 1
    if created:
        session.commit()
    return created
