from app.db.base import metadata
from app.models import (
    ComicIssue,
    ComicTitle,
    InventoryCopy,
    InventoryFmvSnapshot,
    Order,
    OrderItem,
    Publisher,
    User,
    Variant,
)


def test_models_import() -> None:
    assert Publisher is not None
    assert ComicTitle is not None
    assert ComicIssue is not None
    assert Variant is not None
    assert Order is not None
    assert OrderItem is not None
    assert InventoryCopy is not None
    assert InventoryFmvSnapshot is not None
    assert User is not None


def test_metadata_contains_expected_tables() -> None:
    expected_tables = {
        "publisher",
        "comic_title",
        "comic_issue",
        "variant",
        "customer_order",
        "order_item",
        "inventory_copy",
        "inventory_fmv_snapshot",
        "user",
    }

    assert expected_tables.issubset(set(metadata.tables))
