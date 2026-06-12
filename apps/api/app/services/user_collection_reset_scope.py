"""Scope helpers and preserve lists for collection reset."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import ColumnElement, false, or_, select
from sqlmodel import Session, SQLModel

import app.models as models
from app.models import (
    CoverImage,
    DraftImport,
    GmailAccount,
    GmailImportRecord,
    InventoryCopy,
    LunarFeedError,
    LunarFeedRawRow,
    LunarFeedRun,
    LunarFocAlert,
    LunarScheduleConfig,
    LunarScheduledRun,
    LunarScheduledRunError,
    Order,
    OrderItem,
    Organization,
    OrganizationSecurityContext,
    Portfolio,
    ReceivingSession,
    RecommendationScoreV2,
    RetailerOrderSnapshot,
    User,
    UserAuthSession,
    UserAuthSessionEvent,
)


@dataclass(frozen=True)
class UserCollectionScope:
    user_id: int
    inventory_ids: tuple[int, ...] = ()
    order_ids: tuple[int, ...] = ()
    order_item_ids: tuple[int, ...] = ()
    draft_import_ids: tuple[int, ...] = ()
    portfolio_ids: tuple[int, ...] = ()
    receiving_session_ids: tuple[int, ...] = ()
    retailer_order_snapshot_ids: tuple[int, ...] = ()
    gmail_account_id: int | None = None
    cover_image_ids: tuple[int, ...] = ()


_PRESERVE_RELEASE_CATALOG_MODELS: frozenset[type[SQLModel]] = frozenset(
    {
        models.ReleaseSeries,
        models.ReleaseIssue,
        models.ReleaseVariant,
        models.ReleaseKeySignal,
        models.ReleaseAgentExecution,
        models.ReleaseImportRun,
        models.ReleaseImportFile,
        models.ReleaseImportError,
        models.ReleaseIntelligenceMatch,
        models.IndustryPublisher,
        models.IndustryReleaseScanRun,
        models.IndustryReleaseCandidate,
        models.IndustryReleaseSignal,
        models.FutureReleaseMatch,
        models.FutureReleaseAction,
        models.FutureReleaseCertificationRun,
    }
)

# Lunar feed / scheduler ingestion: catalog/release-intelligence infrastructure, not collection data.
_PRESERVE_LUNAR_FEED_MODELS: frozenset[type[SQLModel]] = frozenset(
    {
        LunarFeedRun,
        LunarFeedRawRow,
        LunarFeedError,
        LunarFocAlert,
        LunarScheduleConfig,
        LunarScheduledRun,
        LunarScheduledRunError,
    }
)

# Auth / session / security / org-account infrastructure: never touched by a collection reset.
_PRESERVE_AUTH_SECURITY_MODELS: frozenset[type[SQLModel]] = frozenset(
    {
        UserAuthSession,
        UserAuthSessionEvent,
        OrganizationSecurityContext,
        Organization,
    }
)

NEVER_DELETE_MODELS: frozenset[type[SQLModel]] = frozenset(
    {
        User,
        models.RetailerAccount,
        GmailAccount,
        models.ReleaseWatchlist,
        models.ReleaseWatchlistItem,
        models.WatchlistAgentExecution,
        models.AutoWatchlist,
        models.AutoWatchlistItem,
        models.P81DiscoveryWatchlist,
        models.MarketSource,
        models.MarketSourceSnapshot,
        models.Publisher,
        models.MetadataAlias,
        models.CanonicalSeries,
        models.Variant,
    }
) | _PRESERVE_RELEASE_CATALOG_MODELS | _PRESERVE_LUNAR_FEED_MODELS | _PRESERVE_AUTH_SECURITY_MODELS


# Substring patterns that hard-exclude a table from collection reset. These are precise enough to
# avoid matching legitimate collection/scan tables (e.g. "auth_session" never matches
# "scan_authentication_*"; "session" alone is intentionally NOT used here).
COLLECTION_RESET_EXCLUDED_NAME_PATTERNS: tuple[str, ...] = (
    "auth_session",
    "session_token",
    "security_context",
    "credential",
    "lunar_feed",
    "lunar_schedule",
    "lunar_scheduled",
    "lunar_foc",
    "release_feed",
)


def _table_name(model: type[SQLModel]) -> str:
    return str(getattr(model, "__tablename__", model.__name__))


def is_collection_reset_excluded_table(table_name: str) -> bool:
    """True if a table name matches preserved auth/security/feed/catalog infrastructure."""
    return any(pattern in table_name for pattern in COLLECTION_RESET_EXCLUDED_NAME_PATTERNS)


def is_preserved_model(model: type[SQLModel]) -> bool:
    """Combined preserve check: explicit NEVER_DELETE set plus excluded name patterns."""
    if model in NEVER_DELETE_MODELS or model is User:
        return True
    return is_collection_reset_excluded_table(_table_name(model))


def _scalar_ids(session: Session, statement) -> tuple[int, ...]:
    return tuple(int(value) for value in session.scalars(statement).all())


def build_user_collection_scope(session: Session, *, user_id: int) -> UserCollectionScope:
    inventory_ids = _scalar_ids(session, select(InventoryCopy.id).where(InventoryCopy.user_id == user_id))
    order_ids = _scalar_ids(session, select(Order.id).where(Order.user_id == user_id))
    order_item_ids: tuple[int, ...] = ()
    if order_ids:
        order_item_ids = _scalar_ids(session, select(OrderItem.id).where(OrderItem.order_id.in_(order_ids)))
    draft_import_ids = _scalar_ids(session, select(DraftImport.id).where(DraftImport.user_id == user_id))
    portfolio_ids = _scalar_ids(session, select(Portfolio.id).where(Portfolio.owner_user_id == user_id))
    receiving_session_ids = _scalar_ids(
        session, select(ReceivingSession.id).where(ReceivingSession.owner_user_id == user_id)
    )
    retailer_order_snapshot_ids = _scalar_ids(
        session, select(RetailerOrderSnapshot.id).where(RetailerOrderSnapshot.owner_user_id == user_id)
    )
    gmail_account_id = session.scalar(select(GmailAccount.id).where(GmailAccount.user_id == user_id))
    cover_clauses = []
    if draft_import_ids:
        cover_clauses.append(CoverImage.draft_import_id.in_(draft_import_ids))
    if inventory_ids:
        cover_clauses.append(CoverImage.inventory_copy_id.in_(inventory_ids))
    cover_image_ids: tuple[int, ...] = ()
    if cover_clauses:
        cover_image_ids = _scalar_ids(session, select(CoverImage.id).where(or_(*cover_clauses)))
    return UserCollectionScope(
        user_id=user_id,
        inventory_ids=inventory_ids,
        order_ids=order_ids,
        order_item_ids=order_item_ids,
        draft_import_ids=draft_import_ids,
        portfolio_ids=portfolio_ids,
        receiving_session_ids=receiving_session_ids,
        retailer_order_snapshot_ids=retailer_order_snapshot_ids,
        gmail_account_id=int(gmail_account_id) if gmail_account_id is not None else None,
        cover_image_ids=cover_image_ids,
    )


def owner(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    return column == scope.user_id


def inventory_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.inventory_ids:
        return column.in_(())
    return column.in_(scope.inventory_ids)


def order_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.order_ids:
        return column.in_(())
    return column.in_(scope.order_ids)


def order_item_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.order_item_ids:
        return column.in_(())
    return column.in_(scope.order_item_ids)


def draft_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.draft_import_ids:
        return column.in_(())
    return column.in_(scope.draft_import_ids)


def portfolio_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.portfolio_ids:
        return column.in_(())
    return column.in_(scope.portfolio_ids)


def receiving_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.receiving_session_ids:
        return column.in_(())
    return column.in_(scope.receiving_session_ids)


def retailer_order_snapshot_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.retailer_order_snapshot_ids:
        return column.in_(())
    return column.in_(scope.retailer_order_snapshot_ids)


def recommendation_score_v2_id_in(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    owned_score_ids = select(RecommendationScoreV2.id).where(RecommendationScoreV2.owner_user_id == scope.user_id)
    return column.in_(owned_score_ids)


def cover_image_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return CoverImage.id.in_(scope.cover_image_ids)


def cover_image_id_predicate(scope: UserCollectionScope, column) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return column.in_(scope.cover_image_ids)


def cover_image_match_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return or_(
        models.CoverImageMatchCandidate.source_cover_image_id.in_(scope.cover_image_ids),
        models.CoverImageMatchCandidate.candidate_cover_image_id.in_(scope.cover_image_ids),
    )


def cover_image_link_decision_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if not scope.cover_image_ids:
        return false()
    return or_(
        models.CoverImageLinkDecision.source_cover_image_id.in_(scope.cover_image_ids),
        models.CoverImageLinkDecision.candidate_cover_image_id.in_(scope.cover_image_ids),
    )


def gmail_import_predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
    if scope.gmail_account_id is None:
        return false()
    return GmailImportRecord.gmail_account_id == scope.gmail_account_id
