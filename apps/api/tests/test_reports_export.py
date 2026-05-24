import csv
import io
import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.reports_export import INVENTORY_OPS_CSV_COLUMNS, INVENTORY_OWNER_CSV_COLUMNS, sanitize_report_filename


def test_sanitize_report_filename_strips_controls() -> None:
    assert sanitize_report_filename("  hello\nWORLD\t") == "hello-world"


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_order(client: TestClient, token: str, *, publisher: str, title: str) -> None:
    payload = {
        "retailer": "Store",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
        "items": [
            {
                "title": title,
                "publisher": publisher,
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.0,
            },
        ],
    }
    response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert response.status_code == 201


def _parse_inventory_csv(content: bytes) -> tuple[list[str], list[list[str]]]:
    text = content.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    assert rows
    header = rows[0]
    return header, rows[1:]


def test_owner_inventory_export_csv_columns_order_and_no_fmv_headers(client: TestClient) -> None:
    tok = register_and_login(client, "csvcols@example.com")
    create_order(client, tok, publisher="Image", title="Alpha")
    res = client.get("/reports/inventory.csv", headers=auth_headers(tok))
    assert res.status_code == 200
    header, _ = _parse_inventory_csv(res.content)

    allowed = ",".join(header)
    assert "current_fmv" not in allowed
    assert "gain_loss" not in allowed

    expected = [
        "inventory_copy_id",
        "title",
        "publisher",
        "issue_number",
        "cover_name",
        "printing",
        "ratio",
        "variant_type",
        "cover_artist",
        "retailer",
        "order_date",
        "purchase_date",
        "acquisition_cost",
        "grade_status",
        "hold_status",
        "star_rating",
        "condition_notes",
        "release_date",
        "release_year",
        "release_status",
        "order_status",
        "expected_ship_date",
        "received_at",
        "asset_state",
        "is_in_hand",
        "order_arrival_classifications",
        "risk_types",
        "duplicate_ownership_group_keys",
        "inventory_intelligence_json",
        "duplicate_ownership_json",
        "run_detection_json",
        "inventory_risks_json",
        "inventory_action_center_json",
    ]
    assert header == expected
    ctype = res.headers.get("content-type", "")
    assert "text/csv" in ctype
    cd = res.headers.get("content-disposition", "")
    assert cd.startswith("attachment;")
    assert "filename*=" in cd.lower()


def test_owner_inventory_export_scopes_other_users(client: TestClient) -> None:
    alice = register_and_login(client, "alice-rpt@example.com")
    bob = register_and_login(client, "bob-rpt@example.com")
    create_order(client, alice, publisher="Image", title="Alice Book")
    create_order(client, bob, publisher="Image", title="Bob Book")

    res = client.get("/reports/inventory.csv", headers=auth_headers(alice))
    assert res.status_code == 200
    _, data_rows = _parse_inventory_csv(res.content)
    assert len(data_rows) == 1
    titles = [r[1] for r in data_rows]
    assert titles == ["Alice Book"]


def test_owner_inventory_deterministic_sort_by_publisher_then_title(client: TestClient) -> None:
    tok = register_and_login(client, "sort-rpt@example.com")
    create_order(client, tok, publisher="Zebra Comics", title="AAA")
    create_order(client, tok, publisher="Acme Comics", title="BBB")
    create_order(client, tok, publisher="Acme Comics", title="AAA")

    res = client.get("/reports/inventory.csv", headers=auth_headers(tok))
    _, data_rows = _parse_inventory_csv(res.content)
    assert len(data_rows) == 3
    publishers = [r[2] for r in data_rows]
    titles = [r[1] for r in data_rows]
    assert publishers == sorted(publishers)
    acme_indices = [i for i, p in enumerate(publishers) if p == "Acme Comics"]
    assert titles[acme_indices[0]] == "AAA"
    assert titles[acme_indices[1]] == "BBB"


def test_owner_inventory_filter_publisher_export(client: TestClient) -> None:
    tok = register_and_login(client, "filter-rpt@example.com")
    create_order(client, tok, publisher="DC", title="Bat")
    create_order(client, tok, publisher="Marvel", title="Spidey")

    res = client.get("/reports/inventory.csv?publisher=Marvel", headers=auth_headers(tok))
    _, data_rows = _parse_inventory_csv(res.content)
    assert len(data_rows) == 1
    assert data_rows[0][2] == "Marvel"


def test_owner_inventory_json_sorted_keys_and_lists_rows(client: TestClient) -> None:
    tok = register_and_login(client, "json-rpt@example.com")
    create_order(client, tok, publisher="Image", title="Omega")
    res = client.get("/reports/inventory.json", headers=auth_headers(tok))
    assert res.status_code == 200
    decoded = json.loads(res.content.decode("utf-8"))

    keys = sorted(decoded.keys())
    assert keys == ["columns", "filters", "generated_as_of_date", "rows", "schema"]
    cols = decoded["columns"]
    assert cols == list(INVENTORY_OWNER_CSV_COLUMNS)

    filt_keys = decoded["filters"]
    assert isinstance(filt_keys, dict)
    assert sorted(filt_keys.keys()) == list(filt_keys.keys())

    inventory_blob = decoded["rows"][0]
    assert "current_fmv" not in inventory_blob
    assert "gain_loss" not in inventory_blob
    ctype = res.headers.get("content-type", "")
    assert "application/json" in ctype
    cd = res.headers.get("content-disposition", "")
    assert cd.startswith("attachment;")
    assert "filename*=" in cd.lower()


def test_reports_export_repeat_download_stable(client: TestClient) -> None:
    tok = register_and_login(client, "stab-rpt@example.com")
    create_order(client, tok, publisher="Image", title="Omega")
    res1 = client.get("/reports/inventory.csv", headers=auth_headers(tok))
    res2 = client.get("/reports/inventory.csv", headers=auth_headers(tok))
    assert res1.status_code == res2.status_code == 200
    assert res1.content == res2.content


def test_ops_reports_require_admin(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-exp@example.com")
    get_settings.cache_clear()

    register_and_login(client, "user-exp@example.com")
    outsider = register_and_login(client, "outsider-exp@example.com")

    endpoints = (
        "/ops/reports/inventory.csv",
        "/ops/reports/inventory.json",
        "/ops/reports/action-center.csv",
        "/ops/reports/order-arrival.csv",
        "/ops/reports/run-detection.csv",
        "/ops/reports/timeline.csv",
        "/ops/reports/collection-summary.json",
    )
    for ep in endpoints:
        res = client.get(ep, headers=auth_headers(outsider))
        assert res.status_code == 403


def test_ops_inventory_export_includes_owner_column(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-exp@example.com")
    get_settings.cache_clear()

    bob = register_and_login(client, "ops-bob-exp@example.com")
    alice = register_and_login(client, "ops-alice-exp@example.com")
    create_order(client, alice, publisher="Image", title="AAA")
    create_order(client, bob, publisher="Image", title="BBB")

    ops = register_and_login(client, "ops-exp@example.com")

    res = client.get("/ops/reports/inventory.csv", headers=auth_headers(ops))
    assert res.status_code == 200

    header, data_rows = _parse_inventory_csv(res.content)
    assert header[1] == "owner_user_id"
    assert tuple(header[:2]) == ("inventory_copy_id", "owner_user_id")
    assert tuple(header) == tuple(INVENTORY_OPS_CSV_COLUMNS)
    assert len(data_rows) == 2
    ids = sorted(int(r[0]) for r in data_rows)
    assert ids[0] < ids[1]
