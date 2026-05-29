from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session, select

from app.models import OrganizationRole


@dataclass(frozen=True)
class SystemRoleDefinition:
    sort_order: int
    role_key: str
    display_name: str
    permission_keys: tuple[str, ...]


PERMISSION_ORDER: tuple[str, ...] = (
    "organization:view",
    "organization:update",
    "organization:archive",
    "members:view",
    "members:invite",
    "members:remove",
    "members:roles:update",
    "inventory:view",
    "inventory:create",
    "inventory:update",
    "inventory:delete",
    "operations:view",
    "operations:manage",
    "audit:view",
)

SYSTEM_ROLE_DEFINITIONS: tuple[SystemRoleDefinition, ...] = (
    SystemRoleDefinition(
        sort_order=1,
        role_key="owner",
        display_name="Owner",
        permission_keys=PERMISSION_ORDER,
    ),
    SystemRoleDefinition(
        sort_order=2,
        role_key="admin",
        display_name="Admin",
        permission_keys=(
            "organization:view",
            "organization:update",
            "members:view",
            "members:invite",
            "members:remove",
            "members:roles:update",
            "inventory:view",
            "inventory:create",
            "inventory:update",
            "inventory:delete",
            "operations:view",
            "operations:manage",
            "audit:view",
        ),
    ),
    SystemRoleDefinition(
        sort_order=3,
        role_key="manager",
        display_name="Manager",
        permission_keys=(
            "organization:view",
            "members:view",
            "members:invite",
            "inventory:view",
            "inventory:create",
            "inventory:update",
            "operations:view",
        ),
    ),
    SystemRoleDefinition(
        sort_order=4,
        role_key="staff",
        display_name="Staff",
        permission_keys=(
            "organization:view",
            "members:view",
            "inventory:view",
            "inventory:create",
            "inventory:update",
        ),
    ),
    SystemRoleDefinition(
        sort_order=5,
        role_key="viewer",
        display_name="Viewer",
        permission_keys=(
            "organization:view",
            "members:view",
            "inventory:view",
        ),
    ),
)

ROLE_ORDER: dict[str, int] = {row.role_key: row.sort_order for row in SYSTEM_ROLE_DEFINITIONS}
ROLE_DEFINITION_BY_KEY: dict[str, SystemRoleDefinition] = {row.role_key: row for row in SYSTEM_ROLE_DEFINITIONS}


def ordered_permission_keys() -> tuple[str, ...]:
    return PERMISSION_ORDER


def ordered_role_keys() -> tuple[str, ...]:
    return tuple(row.role_key for row in SYSTEM_ROLE_DEFINITIONS)


def get_role_definition(role_key: str) -> SystemRoleDefinition:
    return ROLE_DEFINITION_BY_KEY[role_key]


def resolve_permission_keys(role_keys: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    allowed = {
        permission
        for role_key in role_keys
        for permission in ROLE_DEFINITION_BY_KEY.get(role_key, SystemRoleDefinition(999, "", "", tuple())).permission_keys
    }
    return tuple(permission for permission in PERMISSION_ORDER if permission in allowed)


def role_sort_key(role_key: str) -> tuple[int, str]:
    return ROLE_ORDER.get(role_key, 999), role_key


def ensure_system_roles(session: Session, *, organization_id: int, created_at: datetime | None = None) -> list[OrganizationRole]:
    rows = session.exec(
        select(OrganizationRole)
        .where(OrganizationRole.organization_id == organization_id)
        .order_by(OrganizationRole.created_at.asc(), OrganizationRole.id.asc())
    ).all()
    by_key = {row.role_key: row for row in rows}
    changed = False
    for definition in SYSTEM_ROLE_DEFINITIONS:
        if definition.role_key in by_key:
            continue
        row = OrganizationRole(
            organization_id=organization_id,
            role_key=definition.role_key,
            display_name=definition.display_name,
            system_managed=True,
            created_at=created_at,
        )
        session.add(row)
        changed = True
    if changed:
        session.flush()
        rows = session.exec(
            select(OrganizationRole)
            .where(OrganizationRole.organization_id == organization_id)
            .order_by(OrganizationRole.created_at.asc(), OrganizationRole.id.asc())
        ).all()
    return sorted(rows, key=lambda row: role_sort_key(row.role_key))
