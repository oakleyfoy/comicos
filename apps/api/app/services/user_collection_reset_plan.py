"""FK-aware delete plan for per-user collection reset."""

from __future__ import annotations

import importlib
import pkgutil
import re
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import ColumnElement, false, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.ddl import sort_tables
from sqlmodel import SQLModel

import app.models as models
from app.models import (
    CoverImage,
    DraftImport,
    GmailImportRecord,
    InventoryCopy,
    Order,
    OrderItem,
    PortfolioItem,
    RecommendationScoreV2,
    RetailerOrderSnapshot,
    User,
)
from app.services.user_collection_reset_scope import (
    NEVER_DELETE_MODELS,
    UserCollectionScope,
    cover_image_id_predicate,
    cover_image_link_decision_predicate,
    cover_image_match_predicate,
    cover_image_predicate,
    draft_in,
    gmail_import_predicate,
    inventory_in,
    order_in,
    order_item_in,
    owner,
    portfolio_in,
    receiving_in,
    recommendation_score_v2_id_in,
    retailer_order_snapshot_in,
)

ScopePredicate = Callable[[UserCollectionScope], ColumnElement[bool]]

_CUSTOM_PREDICATES: dict[type[SQLModel], ScopePredicate] = {
    CoverImage: cover_image_predicate,
    GmailImportRecord: gmail_import_predicate,
    PortfolioItem: lambda s: portfolio_in(s, PortfolioItem.portfolio_id),
}

_CUSTOM_LABELS: dict[type[SQLModel], str] = {
    Order: "customer_orders",
    DraftImport: "draft_imports",
    InventoryCopy: "inventory_copies",
    OrderItem: "order_items",
    PortfolioItem: "portfolio_items",
}

_CYCLE_BREAK_NULL_FK: frozenset[tuple[str, str]] = frozenset(
    {
        ("draft_import", "cover_image"),
        ("inventory_copy", "cover_image"),
        ("p92_import_line_cover_resolution", "inventory_copy"),
        ("p92_import_line_cover_resolution", "draft_import"),
    }
)

_CRITICAL_DELETE_BEFORE: tuple[tuple[str, str], ...] = (
    ("p92_import_health_event", "draft_import"),
    ("p92_import_line_cover_resolution", "draft_import"),
    ("recommendation_score_component_v2", "recommendation_score_v2"),
    ("recommendation_decision_v2", "recommendation_score_v2"),
    ("portfolio_items", "inventory_copy"),
    ("inventory_copy", "order_item"),
    ("order_item", "customer_order"),
)

_FK_SCOPE_BINDINGS: tuple[tuple[str, Callable[..., ColumnElement[bool]]], ...] = (
    ("inventory_copy_id", inventory_in),
    ("inventory_item_id", inventory_in),
    ("draft_import_id", draft_in),
    ("order_id", order_in),
    ("order_item_id", order_item_in),
    ("portfolio_id", portfolio_in),
    ("receiving_session_id", receiving_in),
    ("recommendation_score_id", recommendation_score_v2_id_in),
    ("retailer_order_snapshot_id", retailer_order_snapshot_in),
)

_COVER_IMAGE_CHILD_MODELS: tuple[type[SQLModel], ...] = (
    models.CoverImageMatchCandidate,
    models.CoverImageLinkDecision,
    models.CoverImageOcrCandidate,
    models.CoverImageOcrQualityAnalysis,
    models.CoverImageOcrReconciliationWarning,
    models.CoverImageOcrRegion,
    models.CoverImageOcrResult,
    models.CoverImageBarcodeCandidate,
    models.CoverImageFingerprint,
    models.CoverImageDerivative,
)


@dataclass(frozen=True)
class ForeignKeyEdge:
    child_table: str
    parent_table: str
    constraint_name: str
    column_names: tuple[str, ...]


@dataclass
class DeletePlanStep:
    order: int
    table_name: str
    label: str
    model: type[SQLModel]
    predicate: ScopePredicate
    scope_reason: str
    row_count: int = 0
    depends_on: list[str] = field(default_factory=list)


@dataclass
class PlanValidationIssue:
    kind: str
    message: str
    child_table: str | None = None
    parent_table: str | None = None
    constraint_name: str | None = None


class CollectionResetPlanError(Exception):
    def __init__(self, issues: list[PlanValidationIssue]) -> None:
        super().__init__(issues[0].message if issues else "invalid reset plan")
        self.issues = issues


def iter_mapped_models() -> list[type[SQLModel]]:
    discovered: list[type[SQLModel]] = []
    seen: set[type[SQLModel]] = set()

    def add_model(value: object) -> None:
        if not isinstance(value, type) or not issubclass(value, SQLModel):
            return
        if value in seen:
            return
        if getattr(value, "__table__", None) is None:
            return
        seen.add(value)
        discovered.append(value)

    for value in vars(models).values():
        add_model(value)

    import app.models as models_pkg

    for module_info in pkgutil.walk_packages(models_pkg.__path__, f"{models_pkg.__name__}."):
        module = importlib.import_module(module_info.name)
        for value in vars(module).values():
            add_model(value)

    return discovered


def table_name_for(model: type[SQLModel]) -> str:
    return str(getattr(model, "__tablename__", model.__name__))


def label_for(model: type[SQLModel]) -> str:
    return _CUSTOM_LABELS.get(model, table_name_for(model))


def model_for_table(table_name: str) -> type[SQLModel] | None:
    for model in iter_mapped_models():
        if table_name_for(model) == table_name:
            return model
    return None


def introspect_foreign_keys() -> list[ForeignKeyEdge]:
    edges: list[ForeignKeyEdge] = []
    seen: set[tuple[str, str, str]] = set()
    for model in iter_mapped_models():
        table = model.__table__
        child = table.name
        for fk in table.foreign_key_constraints:
            parent = fk.referred_table.name
            name = fk.name or f"{child}_{parent}_fkey"
            key = (child, parent, name)
            if key in seen:
                continue
            seen.add(key)
            edges.append(
                ForeignKeyEdge(
                    child_table=child,
                    parent_table=parent,
                    constraint_name=name,
                    column_names=tuple(col.name for col in fk.columns),
                )
            )
    return edges


def _scope_reason_for(model: type[SQLModel], predicate: ScopePredicate) -> str:
    if model in _CUSTOM_PREDICATES:
        return f"custom:{table_name_for(model)}"
    fields = model.model_fields
    if "user_id" in fields:
        return "user_id"
    if "owner_user_id" in fields:
        return "owner_user_id"
    bound = [name for name, _ in _FK_SCOPE_BINDINGS if name in fields]
    if bound:
        return "fk:" + ",".join(bound)
    return "scoped"


def build_scope_predicate(model: type[SQLModel]) -> ScopePredicate | None:
    if model in NEVER_DELETE_MODELS or model is User:
        return None
    if model in _CUSTOM_PREDICATES:
        return _CUSTOM_PREDICATES[model]
    if model is models.CoverImageMatchCandidate:
        return cover_image_match_predicate
    if model is models.CoverImageLinkDecision:
        return cover_image_link_decision_predicate
    if model in _COVER_IMAGE_CHILD_MODELS:
        col = getattr(model, "cover_image_id")
        return lambda scope, column=col: cover_image_id_predicate(scope, column)

    fields = model.model_fields
    has_user = "user_id" in fields
    has_owner = "owner_user_id" in fields
    fk_fields = [name for name, _ in _FK_SCOPE_BINDINGS if name in fields]
    if not (has_user or has_owner or fk_fields):
        return None

    def predicate(scope: UserCollectionScope) -> ColumnElement[bool]:
        resolved: list[ColumnElement[bool]] = []
        if has_user:
            resolved.append(getattr(model, "user_id") == scope.user_id)
        if has_owner:
            resolved.append(owner(scope, getattr(model, "owner_user_id")))
        for field_name, binder in _FK_SCOPE_BINDINGS:
            if field_name in fields:
                resolved.append(binder(scope, getattr(model, field_name)))
        if len(resolved) == 1:
            return resolved[0]
        return or_(*resolved)

    return predicate


def _mutual_fk_tables(child_table: str, parent_table: str, fk_edges: list[ForeignKeyEdge]) -> bool:
    has_ab = any(e.child_table == child_table and e.parent_table == parent_table for e in fk_edges)
    has_ba = any(e.child_table == parent_table and e.parent_table == child_table for e in fk_edges)
    return has_ab and has_ba


def _sort_delete_steps_by_metadata(steps: list[DeletePlanStep]) -> list[DeletePlanStep]:
    if not steps:
        return []
    by_table = {step.table_name: step for step in steps}
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"Cannot correctly sort tables;.*")
        sorted_tables = sort_tables([step.model.__table__ for step in steps])
    ordered = [by_table[table.name] for table in reversed(sorted_tables) if table.name in by_table]
    seen = {step.table_name for step in ordered}
    for step in steps:
        if step.table_name not in seen:
            ordered.append(step)
    return ordered


def _move_step_before(steps: list[DeletePlanStep], *, child_table: str, parent_table: str) -> list[DeletePlanStep]:
    table_order = [step.table_name for step in steps]
    if child_table not in table_order or parent_table not in table_order:
        return steps
    child_idx = table_order.index(child_table)
    parent_idx = table_order.index(parent_table)
    if child_idx < parent_idx:
        return steps
    step = steps.pop(child_idx)
    parent_idx = table_order.index(parent_table)
    steps.insert(parent_idx, step)
    return steps


def _repair_delete_order(steps: list[DeletePlanStep], fk_edges: list[ForeignKeyEdge]) -> list[DeletePlanStep]:
    repaired = list(steps)
    plan_tables = {step.table_name for step in repaired}
    max_passes = len(repaired) * 4 + 8
    for _ in range(max_passes):
        index = {step.table_name: idx for idx, step in enumerate(repaired)}
        moved = False
        for edge in fk_edges:
            if edge.child_table not in plan_tables or edge.parent_table not in plan_tables:
                continue
            if (edge.child_table, edge.parent_table) in _CYCLE_BREAK_NULL_FK:
                continue
            if _mutual_fk_tables(edge.child_table, edge.parent_table, fk_edges):
                continue
            if index[edge.child_table] > index[edge.parent_table]:
                repaired = _move_step_before(repaired, child_table=edge.child_table, parent_table=edge.parent_table)
                moved = True
                break
        if not moved:
            break
    for idx, step in enumerate(repaired, start=1):
        step.order = idx
    return repaired


def _apply_critical_order(steps: list[DeletePlanStep]) -> list[DeletePlanStep]:
    by_table = {step.table_name: step for step in steps}
    ordered = list(steps)
    table_order = [step.table_name for step in ordered]

    def move_before(child: str, parent: str) -> None:
        if child not in table_order or parent not in table_order:
            return
        ci, pi = table_order.index(child), table_order.index(parent)
        if ci < pi:
            return
        step = by_table[child]
        ordered.pop(ci)
        table_order.pop(ci)
        pi = table_order.index(parent)
        ordered.insert(pi, step)
        table_order.insert(pi, child)

    for child, parent in _CRITICAL_DELETE_BEFORE:
        move_before(child, parent)
    for index, step in enumerate(ordered, start=1):
        step.order = index
    return ordered


def build_collection_reset_plan(*, validate: bool = True) -> list[DeletePlanStep]:
    fk_edges = introspect_foreign_keys()
    candidates: list[DeletePlanStep] = []
    for model in iter_mapped_models():
        predicate = build_scope_predicate(model)
        if predicate is None:
            continue
        table = table_name_for(model)
        candidates.append(
            DeletePlanStep(
                order=0,
                table_name=table,
                label=label_for(model),
                model=model,
                predicate=predicate,
                scope_reason=_scope_reason_for(model, predicate),
            )
        )

    ordered_steps = _sort_delete_steps_by_metadata(candidates)
    by_name = {step.table_name: step for step in ordered_steps}

    for step in ordered_steps:
        step.depends_on = sorted(
            {
                edge.parent_table
                for edge in fk_edges
                if edge.child_table == step.table_name
                and edge.parent_table in by_name
            }
        )

    ordered_steps = _apply_critical_order(ordered_steps)
    ordered_steps = _repair_delete_order(ordered_steps, fk_edges)

    if validate:
        issues = validate_collection_reset_plan(ordered_steps, fk_edges)
        if issues:
            raise CollectionResetPlanError(issues)

    return ordered_steps


def validate_collection_reset_plan(
    plan: list[DeletePlanStep],
    fk_edges: list[ForeignKeyEdge] | None = None,
) -> list[PlanValidationIssue]:
    fk_edges = fk_edges or introspect_foreign_keys()
    issues: list[PlanValidationIssue] = []
    plan_tables = {step.table_name for step in plan}
    index = {step.table_name: step.order for step in plan}
    preserved = {table_name_for(model) for model in NEVER_DELETE_MODELS}

    for edge in fk_edges:
        if edge.child_table not in plan_tables or edge.parent_table not in plan_tables:
            continue
        if (edge.child_table, edge.parent_table) in _CYCLE_BREAK_NULL_FK:
            continue
        if _mutual_fk_tables(edge.child_table, edge.parent_table, fk_edges):
            continue
        if index[edge.child_table] > index[edge.parent_table]:
            issues.append(
                PlanValidationIssue(
                    kind="order",
                    message=(
                        f"{edge.child_table} must delete before {edge.parent_table} "
                        f"(FK {edge.constraint_name})"
                    ),
                    child_table=edge.child_table,
                    parent_table=edge.parent_table,
                    constraint_name=edge.constraint_name,
                )
            )

    for edge in fk_edges:
        if edge.parent_table not in plan_tables or edge.child_table in plan_tables:
            continue
        if edge.parent_table in preserved:
            continue
        if edge.parent_table not in {
            "inventory_copy",
            "order_item",
            "customer_order",
            "draft_import",
            "retailer_order_snapshot",
            "gmail_import_record",
            "portfolio",
        }:
            continue
        child_model = model_for_table(edge.child_table)
        if child_model is None or child_model in NEVER_DELETE_MODELS:
            continue
        if build_scope_predicate(child_model) is None:
            continue
        issues.append(
            PlanValidationIssue(
                kind="missing_child",
                message=(
                    f"Table {edge.child_table} references {edge.parent_table} but is not in the delete plan "
                    f"(FK {edge.constraint_name})"
                ),
                child_table=edge.child_table,
                parent_table=edge.parent_table,
                constraint_name=edge.constraint_name,
            )
        )

    return issues


def parse_fk_failure(exc: BaseException) -> tuple[str | None, str | None, str | None]:
    """Return (constraint_name, referencing_table, suggested_child) from DB FK error."""
    message = str(getattr(exc, "orig", exc))
    constraint = None
    match = re.search(r'constraint "([^"]+)"', message, flags=re.IGNORECASE)
    if match:
        constraint = match.group(1)
    referencing = None
    ref_match = re.search(r'on table "([^"]+)"', message, flags=re.IGNORECASE)
    if ref_match:
        referencing = ref_match.group(1)
    suggested = None
    for edge in introspect_foreign_keys():
        if constraint and edge.constraint_name == constraint:
            suggested = edge.child_table
            break
        if referencing and edge.child_table == referencing:
            suggested = edge.child_table
            break
    return constraint, referencing, suggested


def enrich_integrity_error(exc: IntegrityError) -> str:
    constraint, referencing, suggested = parse_fk_failure(exc)
    parts = [str(exc.orig if hasattr(exc, "orig") else exc)]
    if constraint:
        parts.append(f"fk_constraint={constraint}")
    if referencing:
        parts.append(f"referencing_table={referencing}")
    if suggested:
        parts.append(f"suggested_missing_child={suggested}")
    return "; ".join(parts)
