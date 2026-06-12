from __future__ import annotations

from app.services.user_collection_reset_plan import (
    _CYCLE_BREAK_NULL_FK,
    _mutual_fk_tables,
    build_collection_reset_plan,
    introspect_foreign_keys,
    table_name_for,
    validate_collection_reset_plan,
)
from app.services.user_collection_reset_scope import NEVER_DELETE_MODELS


def test_reset_plan_child_tables_delete_before_parents() -> None:
    plan = build_collection_reset_plan(validate=True)
    fk_edges = introspect_foreign_keys()
    issues = validate_collection_reset_plan(plan, fk_edges)
    assert not issues, issues[0].message if issues else "plan valid"

    index = {step.table_name: step.order for step in plan}
    preserved = {table_name_for(model) for model in NEVER_DELETE_MODELS}
    for edge in fk_edges:
        if edge.child_table not in index or edge.parent_table not in index:
            continue
        if edge.parent_table in preserved:
            continue
        if (edge.child_table, edge.parent_table) in _CYCLE_BREAK_NULL_FK:
            continue
        if _mutual_fk_tables(edge.child_table, edge.parent_table, fk_edges):
            continue
        assert index[edge.child_table] < index[edge.parent_table], (
            f"{edge.child_table} must delete before {edge.parent_table} ({edge.constraint_name})"
        )


def test_reset_plan_known_blockers_order() -> None:
    plan = build_collection_reset_plan(validate=True)
    index = {step.table_name: step.order for step in plan}

    def assert_before(child: str, parent: str) -> None:
        assert child in index and parent in index
        assert index[child] < index[parent], f"{child} should delete before {parent}"

    assert_before("p92_import_health_event", "draft_import")
    assert_before("p92_import_line_cover_resolution", "draft_import")
    assert_before("recommendation_score_component_v2", "recommendation_score_v2")
    assert_before("recommendation_decision_v2", "recommendation_score_v2")
    assert_before("portfolio_item", "inventory_copy")
    assert_before("inventory_copy", "order_item")
    assert_before("order_item", "customer_order")
