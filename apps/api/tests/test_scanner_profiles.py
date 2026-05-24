"""P34-07 scanner profile presets (metadata only; session snapshot freeze — no drivers)."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.models import ScanSession

from test_inventory import auth_headers, register_and_login


def _profiles_sort_key(profile: dict) -> tuple[int, int, str, int]:
    owner_id = profile["owner_user_id"]
    return (
        0 if owner_id is None else 1,
        owner_id or 0,
        profile["profile_name"],
        int(profile["id"]),
    )


def test_scanner_profile_list_deterministic_ordering(client: TestClient) -> None:
    owner_token = register_and_login(client, "scanner-sort-a@example.com")
    hdr = auth_headers(owner_token)

    rsp = client.get("/scanner-profiles", headers=hdr)
    assert rsp.status_code == 200
    items = rsp.json()["items"]
    assert len(items) >= 4
    assert items == sorted(items, key=_profiles_sort_key)
    assert any(
        row["owner_user_id"] is None and "Fujitsu Bulk 300dpi Color PNG" in row["profile_name"] for row in items
    )

    client.post(
        "/scanner-profiles",
        json={
            "profile_name": "Zebra Owner Preset",
            "scanner_type": "generic_flatbed",
            "dpi": 150,
            "color_mode": "grayscale",
            "file_format": "jpg",
            "recommended_use": "intake_receiving",
        },
        headers=hdr,
    )
    client.post(
        "/scanner-profiles",
        json={
            "profile_name": "Alpha Owner Preset",
            "scanner_type": "generic_flatbed",
            "dpi": 151,
            "color_mode": "grayscale",
            "file_format": "jpg",
            "recommended_use": "intake_receiving",
        },
        headers=hdr,
    )
    rsp2 = client.get("/scanner-profiles", headers=hdr)
    assert rsp2.status_code == 200
    rows = rsp2.json()["items"]
    assert rows == sorted(rows, key=_profiles_sort_key)


def test_owner_crud_roundtrip_and_system_profiles_readonly(client: TestClient) -> None:
    token = register_and_login(client, "scanner-crud@example.com")
    hdr = auth_headers(token)

    created = client.post(
        "/scanner-profiles",
        json={
            "profile_name": "My ADF",
            "scanner_type": "fujitsu_bulk",
            "dpi": 400,
            "color_mode": "color",
            "file_format": "png",
            "duplex_enabled": True,
            "feeder_enabled": True,
            "recommended_use": "bulk_ingest",
            "is_default": True,
            "notes": "Owner notes",
        },
        headers=hdr,
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    assert created.json()["is_default"] is True

    one = client.get(f"/scanner-profiles/{pid}", headers=hdr)
    assert one.status_code == 200
    assert one.json()["profile_name"] == "My ADF"

    patched = client.patch(
        f"/scanner-profiles/{pid}",
        json={"profile_name": "My ADF v2", "dpi": 500},
        headers=hdr,
    )
    assert patched.status_code == 200
    assert patched.json()["profile_name"] == "My ADF v2"
    assert patched.json()["dpi"] == 500

    lst = client.get("/scanner-profiles", headers=hdr).json()["items"]
    sys_id = next(r["id"] for r in lst if r["owner_user_id"] is None)

    assert client.patch(f"/scanner-profiles/{sys_id}", json={"notes": "nope"}, headers=hdr).status_code == 403
    assert client.delete(f"/scanner-profiles/{sys_id}", headers=hdr).status_code == 403

    deleted = client.delete(f"/scanner-profiles/{pid}", headers=hdr)
    assert deleted.status_code == 204
    assert client.get(f"/scanner-profiles/{pid}", headers=hdr).status_code == 404


def test_owner_cannot_fetch_other_accounts_profile(client: TestClient) -> None:
    token_a = register_and_login(client, "scan-prof-a@example.com")
    token_b = register_and_login(client, "scan-prof-b@example.com")
    hdr_a = auth_headers(token_a)
    hdr_b = auth_headers(token_b)

    row = client.post(
        "/scanner-profiles",
        json={"profile_name": "Private", "scanner_type": "manual_upload"},
        headers=hdr_a,
    )
    pid = row.json()["id"]

    assert client.get(f"/scanner-profiles/{pid}", headers=hdr_b).status_code == 404


def test_default_profile_exclusive_per_owner(client: TestClient) -> None:
    token = register_and_login(client, "scan-default-x@example.com")
    hdr = auth_headers(token)
    first = client.post(
        "/scanner-profiles",
        json={"profile_name": "Default One", "scanner_type": "generic_flatbed", "is_default": True},
        headers=hdr,
    )
    assert first.status_code == 201
    id_one = first.json()["id"]

    second = client.post(
        "/scanner-profiles",
        json={"profile_name": "Default Two", "scanner_type": "generic_flatbed", "is_default": True},
        headers=hdr,
    )
    assert second.status_code == 201
    id_two = second.json()["id"]

    assert client.get(f"/scanner-profiles/{id_one}", headers=hdr).json()["is_default"] is False
    assert client.get(f"/scanner-profiles/{id_two}", headers=hdr).json()["is_default"] is True


def test_session_create_freezes_snapshot_and_profile_patch_does_not_mutate_session(client: TestClient) -> None:
    token = register_and_login(client, "scan-freeze@example.com")
    hdr = auth_headers(token)
    pid = client.post(
        "/scanner-profiles",
        json={
            "profile_name": "Snapshot Source",
            "scanner_type": "epson_high_res",
            "dpi": 600,
            "color_mode": "color",
            "file_format": "png",
            "recommended_use": "high_res_review",
        },
        headers=hdr,
    ).json()["id"]

    sess = client.post(
        "/scan-sessions",
        json={"session_type": "bulk_ingest", "scanner_profile_id": pid},
        headers=hdr,
    )
    assert sess.status_code == 201
    sid = sess.json()["id"]

    detail = client.get(f"/scan-sessions/{sid}", headers=hdr).json()
    assert detail["scanner_profile_id"] == pid
    snap = detail["scanner_profile_snapshot"]
    assert snap is not None
    assert snap["dpi"] == 600

    client.patch(f"/scanner-profiles/{pid}", json={"dpi": 777}, headers=hdr)

    after = client.get(f"/scan-sessions/{sid}", headers=hdr).json()
    assert after["scanner_profile_snapshot"]["dpi"] == 600


def test_delete_profile_sets_session_fk_null_preserves_snapshot(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "scan-fk-null@example.com")
    hdr = auth_headers(token)
    pid = client.post(
        "/scanner-profiles",
        json={"profile_name": "Delete Me", "scanner_type": "generic_flatbed"},
        headers=hdr,
    ).json()["id"]

    sid = client.post(
        "/scan-sessions",
        json={"session_type": "bulk_ingest", "scanner_profile_id": pid},
        headers=hdr,
    ).json()["id"]

    assert client.delete(f"/scanner-profiles/{pid}", headers=hdr).status_code == 204

    session.expire_all()
    refreshed = session.get(ScanSession, sid)
    assert refreshed is not None
    assert refreshed.scanner_profile_id is None
    assert refreshed.scanner_profile_snapshot is not None


def test_ops_scanner_profiles_list_visibility_and_sort(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-prof@example.com")
    get_settings.cache_clear()

    user_tok = register_and_login(client, "normie-prof@example.com")
    deny = client.get("/ops/scanner-profiles", headers=auth_headers(user_tok))
    assert deny.status_code == 403

    ops_tok = register_and_login(client, "ops-prof@example.com")
    ok = client.get("/ops/scanner-profiles", headers=auth_headers(ops_tok))
    assert ok.status_code == 200
    rows = ok.json()["items"]
    assert rows == sorted(rows, key=_profiles_sort_key)
