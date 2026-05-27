from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import User
from test_inventory import auth_headers, register_and_login


def test_market_api_v1_envelope_and_pagination_on_ingestion_list(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "p39-v1-envelope@example.com")
    resp = client.get("/api/v1/market/market-ingestion/batches", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {"data", "meta"}
    assert "pagination" in body["data"]
    pag = body["data"]["pagination"]
    assert pag["total_count"] == 0
    assert pag["has_next"] is False
    assert pag["limit"] >= 1
    assert pag["next_cursor"] is None
    meta = body["meta"]
    assert meta["snapshot_id"] is None
    assert meta["engine_versions"]["signals"] == "P39-04"
    assert meta["generated_at"].endswith("Z")

    owner_id = int(session.exec(select(User.id).where(User.email == "p39-v1-envelope@example.com")).one())
    assert meta["owner_user_id"] == str(owner_id)


def test_market_api_v1_ops_has_no_generation_endpoints(client: TestClient) -> None:
    token = register_and_login(client, "p39-v1-ops-nogen@example.com")
    paths = (
        "/api/v1/market/ops/market-signals/generate",
        "/api/v1/market/ops/market-opportunities/generate",
        "/api/v1/market/ops/market-portfolio-coupling/generate",
        "/api/v1/market/ops/market-scoring/run",
        "/api/v1/market/ops/market-normalization/run",
        "/api/v1/market/ops/market-ingestion/batch",
    )
    for path in paths:
        r_post = client.post(path, headers=auth_headers(token), json={})
        assert r_post.status_code in (404, 405), path


def test_market_api_v1_error_shape(client: TestClient) -> None:
    token_a = register_and_login(client, "p39-v1-err-shape-a@example.com")
    token_b = register_and_login(client, "p39-v1-err-shape-b@example.com")

    ingest = client.post(
        "/market-ingestion/batch",
        headers=auth_headers(token_a),
        json={
            "batch_source_type": "csv_import",
            "batch_file_name": "w.csv",
            "records": [
                {
                    "external_listing_id": "x1",
                    "source_name": "S",
                    "title": "T",
                    "publisher": "P",
                    "issue_number": "1",
                    "asking_price": "10.00",
                    "currency": "USD",
                }
            ],
        },
    )
    assert ingest.status_code == 201, ingest.text
    batch_id = int(ingest.json()["id"])

    r = client.get(
        f"/api/v1/market/market-ingestion/batches/{batch_id}",
        headers=auth_headers(token_b),
    )
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "HTTP_404"
    assert isinstance(err["message"], str)


def test_market_api_v1_list_is_deterministic_across_replays(
    client: TestClient,
) -> None:
    token = register_and_login(client, "p39-v1-determinism@example.com")
    payload = {
        "batch_source_type": "csv_import",
        "batch_file_name": "d.csv",
        "records": [
            {
                "external_listing_id": "d1",
                "source_name": "S",
                "title": "T",
                "publisher": "P",
                "issue_number": "1",
                "asking_price": "10.00",
                "currency": "USD",
            }
        ],
    }
    first = client.post("/market-ingestion/batch", headers=auth_headers(token), json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/market-ingestion/batch", headers=auth_headers(token), json=payload)
    assert second.status_code == 200, second.text

    a = client.get(
        "/api/v1/market/market-ingestion/batches?limit=10&offset=0",
        headers=auth_headers(token),
    )
    b = client.get(
        "/api/v1/market/market-ingestion/batches?limit=10&offset=0",
        headers=auth_headers(token),
    )
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["data"]["items"] == b.json()["data"]["items"]
