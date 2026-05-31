"""add collector intelligence foundation (P51-01)

Revision ID: 20260818_0168
Revises: 20260817_0167
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260818_0168"
down_revision = "20260817_0167"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "franchise_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("franchise_name", sa.String(length=160), nullable=False),
        sa.Column("primary_publisher", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("franchise_name", name="uq_franchise_profile_name"),
    )
    op.create_index("ix_franchise_profile_franchise_name", "franchise_profile", ["franchise_name"])
    op.create_index("ix_franchise_profile_primary_publisher", "franchise_profile", ["primary_publisher"])
    op.create_index("ix_franchise_profile_status", "franchise_profile", ["status"])

    op.create_table(
        "franchise_popularity_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("franchise_id", sa.Integer(), nullable=False),
        sa.Column("popularity_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("longevity_score", sa.Float(), nullable=False),
        sa.Column("collector_strength_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["franchise_id"], ["franchise_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_franchise_popularity_score_franchise_id", "franchise_popularity_score", ["franchise_id"])
    op.create_index("ix_franchise_popularity_score_popularity_score", "franchise_popularity_score", ["popularity_score"])
    op.create_index("ix_franchise_popularity_score_source_version", "franchise_popularity_score", ["source_version"])
    op.create_index(
        "ix_franchise_popularity_franchise_created",
        "franchise_popularity_score",
        ["franchise_id", "created_at", "id"],
    )

    op.create_table(
        "character_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_name", sa.String(length=160), nullable=False),
        sa.Column("publisher", sa.String(length=120), nullable=False),
        sa.Column("franchise_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["franchise_id"], ["franchise_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_name", "publisher", name="uq_character_profile_name_publisher"),
    )
    op.create_index("ix_character_profile_character_name", "character_profile", ["character_name"])
    op.create_index("ix_character_profile_franchise_id", "character_profile", ["franchise_id"])
    op.create_index("ix_character_profile_status", "character_profile", ["status"])
    op.create_index("ix_character_profile_publisher_name", "character_profile", ["publisher", "character_name", "id"])

    op.create_table(
        "character_popularity_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("popularity_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("collector_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_character_popularity_score_character_id", "character_popularity_score", ["character_id"])
    op.create_index(
        "ix_character_popularity_score_popularity_score", "character_popularity_score", ["popularity_score"]
    )
    op.create_index("ix_character_popularity_score_source_version", "character_popularity_score", ["source_version"])
    op.create_index(
        "ix_character_popularity_character_created",
        "character_popularity_score",
        ["character_id", "created_at", "id"],
    )

    op.create_table(
        "character_alias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("alias_name", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "alias_name", name="uq_character_alias"),
    )
    op.create_index("ix_character_alias_character_id", "character_alias", ["character_id"])
    op.create_index("ix_character_alias_alias_name", "character_alias", ["alias_name"])
    op.create_index("ix_character_alias_name", "character_alias", ["alias_name", "id"])

    op.create_table(
        "character_appearance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("appearance_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character_profile.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_character_appearance_character_id", "character_appearance", ["character_id"])
    op.create_index("ix_character_appearance_release_issue_id", "character_appearance", ["release_issue_id"])
    op.create_index("ix_character_appearance_appearance_type", "character_appearance", ["appearance_type"])
    op.create_index(
        "ix_character_appearance_issue", "character_appearance", ["release_issue_id", "appearance_type", "id"]
    )

    op.create_table(
        "creator_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_name", sa.String(length=160), nullable=False),
        sa.Column("creator_role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_name", "creator_role", name="uq_creator_profile_name_role"),
    )
    op.create_index("ix_creator_profile_creator_name", "creator_profile", ["creator_name"])
    op.create_index("ix_creator_profile_creator_role", "creator_profile", ["creator_role"])
    op.create_index("ix_creator_profile_status", "creator_profile", ["status"])

    op.create_table(
        "creator_popularity_score",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("popularity_score", sa.Float(), nullable=False),
        sa.Column("demand_score", sa.Float(), nullable=False),
        sa.Column("collector_score", sa.Float(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("source_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creator_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_creator_popularity_score_creator_id", "creator_popularity_score", ["creator_id"])
    op.create_index("ix_creator_popularity_score_popularity_score", "creator_popularity_score", ["popularity_score"])
    op.create_index("ix_creator_popularity_score_source_version", "creator_popularity_score", ["source_version"])
    op.create_index(
        "ix_creator_popularity_creator_created", "creator_popularity_score", ["creator_id", "created_at", "id"]
    )

    op.create_table(
        "creator_alias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("creator_id", sa.Integer(), nullable=False),
        sa.Column("alias_name", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["creator_id"], ["creator_profile.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("creator_id", "alias_name", name="uq_creator_alias"),
    )
    op.create_index("ix_creator_alias_creator_id", "creator_alias", ["creator_id"])
    op.create_index("ix_creator_alias_alias_name", "creator_alias", ["alias_name"])
    op.create_index("ix_creator_alias_name", "creator_alias", ["alias_name", "id"])

    op.create_table(
        "release_intelligence_match",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("release_issue_id", sa.Integer(), nullable=False),
        sa.Column("release_variant_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False),
        sa.Column("match_payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["release_issue_id"], ["release_issue.id"]),
        sa.ForeignKeyConstraint(["release_variant_id"], ["release_variant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_user_id",
            "release_issue_id",
            "release_variant_id",
            "entity_type",
            "entity_id",
            name="uq_release_intelligence_match",
        ),
    )
    op.create_index("ix_release_intelligence_match_owner_user_id", "release_intelligence_match", ["owner_user_id"])
    op.create_index("ix_release_intelligence_match_release_issue_id", "release_intelligence_match", ["release_issue_id"])
    op.create_index("ix_release_intelligence_match_release_variant_id", "release_intelligence_match", ["release_variant_id"])
    op.create_index("ix_release_intelligence_match_entity_type", "release_intelligence_match", ["entity_type"])
    op.create_index("ix_release_intelligence_match_entity_id", "release_intelligence_match", ["entity_id"])
    op.create_index(
        "ix_release_intelligence_match_owner_issue",
        "release_intelligence_match",
        ["owner_user_id", "release_issue_id", "id"],
    )


def downgrade() -> None:
    op.drop_table("release_intelligence_match")
    op.drop_table("creator_alias")
    op.drop_table("creator_popularity_score")
    op.drop_table("creator_profile")
    op.drop_table("character_appearance")
    op.drop_table("character_alias")
    op.drop_table("character_popularity_score")
    op.drop_table("character_profile")
    op.drop_table("franchise_popularity_score")
    op.drop_table("franchise_profile")
