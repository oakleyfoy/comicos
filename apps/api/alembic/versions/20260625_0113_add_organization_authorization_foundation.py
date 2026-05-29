"""add organization authorization foundation

Revision ID: 20260625_0113
Revises: 20260624_0112
Create Date: 2026-06-25 00:13:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260625_0113"
down_revision = "20260624_0112"
branch_labels = None
depends_on = None


SYSTEM_ROLES = (
    ("owner", "Owner"),
    ("admin", "Admin"),
    ("manager", "Manager"),
    ("staff", "Staff"),
    ("viewer", "Viewer"),
)


def upgrade() -> None:
    op.create_table(
        "organization_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("role_key", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("system_managed", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "role_key", name="uq_organization_role_org_key"),
    )
    op.create_index("ix_organization_role_org_created", "organization_roles", ["organization_id", "created_at", "id"])

    op.create_table(
        "organization_membership_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_member_id", sa.Integer(), nullable=False),
        sa.Column("organization_role_id", sa.Integer(), nullable=False),
        sa.Column("assigned_by_user_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_member_id"], ["organization_members.id"]),
        sa.ForeignKeyConstraint(["organization_role_id"], ["organization_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_member_id", "organization_role_id", name="uq_org_member_role_assignment"),
    )
    op.create_index("ix_org_member_role_member_assigned", "organization_membership_roles", ["organization_member_id", "assigned_at", "id"])
    op.create_index("ix_org_member_role_role_assigned", "organization_membership_roles", ["organization_role_id", "assigned_at", "id"])

    op.create_table(
        "organization_permission_audits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("action_key", sa.String(length=64), nullable=False),
        sa.Column("permission_result", sa.String(length=24), nullable=False),
        sa.Column("evaluation_context_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["target_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_perm_audit_org_created", "organization_permission_audits", ["organization_id", "created_at", "id"])
    op.create_index("ix_org_perm_audit_actor_created", "organization_permission_audits", ["actor_user_id", "created_at", "id"])
    op.create_index("ix_org_perm_audit_target_created", "organization_permission_audits", ["target_user_id", "created_at", "id"])
    op.create_index("ix_org_perm_audit_action_created", "organization_permission_audits", ["action_key", "created_at", "id"])

    connection = op.get_bind()
    organizations = connection.execute(
        sa.text("SELECT id, owner_user_id, created_at FROM organizations ORDER BY id")
    ).mappings().all()
    if not organizations:
        return

    role_rows = []
    for organization in organizations:
        for role_key, display_name in SYSTEM_ROLES:
            role_rows.append(
                {
                    "organization_id": organization["id"],
                    "role_key": role_key,
                    "display_name": display_name,
                    "system_managed": True,
                    "created_at": organization["created_at"],
                }
            )
    role_table = sa.table(
        "organization_roles",
        sa.column("organization_id", sa.Integer()),
        sa.column("role_key", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("system_managed", sa.Boolean()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(role_table, role_rows)

    owner_roles = connection.execute(
        sa.text(
            """
            SELECT r.id AS role_id, r.organization_id
            FROM organization_roles r
            WHERE r.role_key = 'owner'
            ORDER BY r.organization_id, r.id
            """
        )
    ).mappings().all()
    owner_members = connection.execute(
        sa.text(
            """
            SELECT m.id AS member_id, m.organization_id, m.user_id, m.joined_at
            FROM organization_members m
            JOIN organizations o ON o.id = m.organization_id AND o.owner_user_id = m.user_id
            ORDER BY m.organization_id, m.id
            """
        )
    ).mappings().all()
    viewer_roles = connection.execute(
        sa.text(
            """
            SELECT r.id AS role_id, r.organization_id
            FROM organization_roles r
            WHERE r.role_key = 'viewer'
            ORDER BY r.organization_id, r.id
            """
        )
    ).mappings().all()
    active_non_owner_members = connection.execute(
        sa.text(
            """
            SELECT m.id AS member_id, m.organization_id, m.user_id, m.joined_at
            FROM organization_members m
            JOIN organizations o ON o.id = m.organization_id
            WHERE m.user_id <> o.owner_user_id AND m.membership_status = 'ACTIVE'
            ORDER BY m.organization_id, m.id
            """
        )
    ).mappings().all()
    owner_role_id_by_org = {row["organization_id"]: row["role_id"] for row in owner_roles}
    viewer_role_id_by_org = {row["organization_id"]: row["role_id"] for row in viewer_roles}
    member_role_rows = [
        {
            "organization_member_id": row["member_id"],
            "organization_role_id": owner_role_id_by_org[row["organization_id"]],
            "assigned_by_user_id": row["user_id"],
            "assigned_at": row["joined_at"],
        }
        for row in owner_members
        if row["organization_id"] in owner_role_id_by_org
    ]
    member_role_rows.extend(
        {
            "organization_member_id": row["member_id"],
            "organization_role_id": viewer_role_id_by_org[row["organization_id"]],
            "assigned_by_user_id": row["user_id"],
            "assigned_at": row["joined_at"],
        }
        for row in active_non_owner_members
        if row["organization_id"] in viewer_role_id_by_org
    )
    if member_role_rows:
        member_role_table = sa.table(
            "organization_membership_roles",
            sa.column("organization_member_id", sa.Integer()),
            sa.column("organization_role_id", sa.Integer()),
            sa.column("assigned_by_user_id", sa.Integer()),
            sa.column("assigned_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(member_role_table, member_role_rows)


def downgrade() -> None:
    op.drop_table("organization_permission_audits")
    op.drop_table("organization_membership_roles")
    op.drop_table("organization_roles")
