from __future__ import annotations

from sqlmodel import Session, select
from fastapi.testclient import TestClient

from app.models import (
    MarketAcquisitionCandidate,
    MarketAcquisitionIngestionBatch,
    MarketAcquisitionIngestionEvent,
    MarketAcquisitionRawSource,
    User,
)
from test_inventory import auth_headers, register_and_login


def _payload() -> dict[str, object]:
    return {
        "batch_source_type": "csv_import",
        "batch_file_name": "watchlist.csv",
        "records": [
            {
                "external_listing_id": "L-100",
                "source_name": "Auction House",
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "1",
                "variant": "Cover A",
                "condition_raw": "VF/NM",
                "asking_price": "125.00",
                "currency": "USD",
                "external_fmv_estimate": "150.00",
            },
            {
                "external_source_type": "auction_snapshot",
                "external_listing_id": "L-101",
                "source_name": "Auction House",
                "title": "Saga",
                "publisher": "Image",
                "issue_number": "2",
                "asking_price": "95.00",
                "currency": "USD",
            },
        ],
    }


def test_market_ingestion_replay_safe_checksum_and_raw_hash_stability(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "market-ingestion-replay@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "market-ingestion-replay@example.com")).one())

    first = client.post("/market-ingestion/batch", headers=auth_headers(token), json=_payload())
    assert first.status_code == 201, first.text
    second = client.post("/market-ingestion/batch", headers=auth_headers(token), json=_payload())
    assert second.status_code == 200, second.text
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["batch_checksum"] == second.json()["batch_checksum"]

    batch_rows = list(
        session.exec(
            select(MarketAcquisitionIngestionBatch).where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)
        ).all()
    )
    assert len(batch_rows) == 1
    assert batch_rows[0].successful_records == 2
    assert batch_rows[0].failed_records == 0

    raw_rows = list(
        session.exec(
            select(MarketAcquisitionRawSource).where(MarketAcquisitionRawSource.ingestion_batch_id == int(batch_rows[0].id or 0))
        ).all()
    )
    assert len(raw_rows) == 2
    assert [row.raw_hash for row in raw_rows] == [
        row["metadata_json"]["raw_hash"] for row in first.json()["events"] if row["event_type"] == "RECORD_PARSED"
    ]

    candidate_rows = list(
        session.exec(
            select(MarketAcquisitionCandidate).where(MarketAcquisitionCandidate.ingestion_batch_id == int(batch_rows[0].id or 0))
        ).all()
    )
    assert len(candidate_rows) == 2
    assert all(row.normalized_flag is False for row in candidate_rows)


def test_market_ingestion_append_only_failure_handling_and_raw_preservation(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "market-ingestion-failures@example.com")
    payload = {
        "batch_source_type": "manual_input",
        "records": [
            {"title": "Batman", "issue_number": "1", "asking_price": "50.00"},
            {"issue_number": "2", "asking_price": "10.00"},
            {"title": "Spawn", "asking_price": "abc"},
        ],
    }

    response = client.post("/market-ingestion/batch", headers=auth_headers(token), json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["successful_records"] == 1
    assert body["failed_records"] == 2
    assert body["ingestion_status"] == "COMPLETED"

    raw = client.get(f"/market-ingestion/batches/{body['id']}/raw", headers=auth_headers(token))
    assert raw.status_code == 200, raw.text
    raw_rows = raw.json()["items"]
    assert len(raw_rows) == 3
    assert sum(1 for row in raw_rows if row["processing_status"] == "FAILED") == 2
    assert all("raw_record_json" in row for row in raw_rows)

    event_types = [row["event_type"] for row in body["events"]]
    assert event_types[0] == "BATCH_CREATED"
    assert event_types[-1] == "BATCH_COMPLETED"
    assert event_types.count("RECORD_REJECTED") == 2


def test_market_ingestion_all_failed_batch_marks_failed(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "market-ingestion-all-failed@example.com")
    payload = {
        "batch_source_type": "csv_import",
        "records": [
            {"issue_number": "7"},
            {"title": "Sandman", "asking_price": "bad-number"},
        ],
    }

    response = client.post("/market-ingestion/batch", headers=auth_headers(token), json=payload)
    assert response.status_code == 201, response.text
    assert response.json()["ingestion_status"] == "FAILED"
    assert response.json()["successful_records"] == 0
    assert response.json()["failed_records"] == 2


def test_market_ingestion_owner_ops_separation_and_raw_filters(
    client: TestClient,
    session: Session,
) -> None:
    token_a = register_and_login(client, "market-ingestion-owner-a@example.com")
    token_b = register_and_login(client, "market-ingestion-owner-b@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "market-ingestion-owner-a@example.com")).one())

    created = client.post("/market-ingestion/batch", headers=auth_headers(token_a), json=_payload())
    assert created.status_code == 201, created.text
    batch_id = int(created.json()["id"])

    owner_b_get = client.get(f"/market-ingestion/batches/{batch_id}", headers=auth_headers(token_b))
    assert owner_b_get.status_code == 404, owner_b_get.text

    owner_b_raw = client.get(f"/market-ingestion/batches/{batch_id}/raw", headers=auth_headers(token_b))
    assert owner_b_raw.status_code == 404, owner_b_raw.text

    ops_batches = client.get(f"/ops/market-ingestion/batches?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_batches.status_code == 200, ops_batches.text
    assert ops_batches.json()["total_items"] == 1
    assert all(row["owner_user_id"] == owner_a for row in ops_batches.json()["items"])

    ops_detail = client.get(f"/ops/market-ingestion/batches/{batch_id}", headers=auth_headers(token_a))
    assert ops_detail.status_code == 200, ops_detail.text
    assert ops_detail.json()["owner_user_id"] == owner_a

    ops_raw = client.get(
        f"/ops/market-ingestion/raw?owner_user_id={owner_a}&ingestion_batch_id={batch_id}",
        headers=auth_headers(token_a),
    )
    assert ops_raw.status_code == 200, ops_raw.text
    assert len(ops_raw.json()["items"]) == 2


def test_market_ingestion_duplicate_batch_prevention_keeps_counts_stable(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "market-ingestion-counts@example.com")
    owner_id = int(session.exec(select(User.id).where(User.email == "market-ingestion-counts@example.com")).one())

    first = client.post("/market-ingestion/batch", headers=auth_headers(token), json=_payload())
    assert first.status_code == 201, first.text

    batch_count_before = len(
        list(session.exec(select(MarketAcquisitionIngestionBatch).where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)).all())
    )
    raw_count_before = len(
        list(
            session.exec(
                select(MarketAcquisitionRawSource)
                .join(MarketAcquisitionIngestionBatch, MarketAcquisitionRawSource.ingestion_batch_id == MarketAcquisitionIngestionBatch.id)
                .where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)
            ).all()
        )
    )
    candidate_count_before = len(
        list(
            session.exec(
                select(MarketAcquisitionCandidate)
                .join(MarketAcquisitionIngestionBatch, MarketAcquisitionCandidate.ingestion_batch_id == MarketAcquisitionIngestionBatch.id)
                .where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)
            ).all()
        )
    )
    event_count_before = len(
        list(
            session.exec(
                select(MarketAcquisitionIngestionEvent)
                .join(MarketAcquisitionIngestionBatch, MarketAcquisitionIngestionEvent.ingestion_batch_id == MarketAcquisitionIngestionBatch.id)
                .where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)
            ).all()
        )
    )

    replay = client.post("/market-ingestion/batch", headers=auth_headers(token), json=_payload())
    assert replay.status_code == 200, replay.text

    batch_count_after = len(
        list(session.exec(select(MarketAcquisitionIngestionBatch).where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)).all())
    )
    raw_count_after = len(
        list(
            session.exec(
                select(MarketAcquisitionRawSource)
                .join(MarketAcquisitionIngestionBatch, MarketAcquisitionRawSource.ingestion_batch_id == MarketAcquisitionIngestionBatch.id)
                .where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)
            ).all()
        )
    )
    candidate_count_after = len(
        list(
            session.exec(
                select(MarketAcquisitionCandidate)
                .join(MarketAcquisitionIngestionBatch, MarketAcquisitionCandidate.ingestion_batch_id == MarketAcquisitionIngestionBatch.id)
                .where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)
            ).all()
        )
    )
    event_count_after = len(
        list(
            session.exec(
                select(MarketAcquisitionIngestionEvent)
                .join(MarketAcquisitionIngestionBatch, MarketAcquisitionIngestionEvent.ingestion_batch_id == MarketAcquisitionIngestionBatch.id)
                .where(MarketAcquisitionIngestionBatch.owner_user_id == owner_id)
            ).all()
        )
    )

    assert batch_count_after == batch_count_before == 1
    assert raw_count_after == raw_count_before == 2
    assert candidate_count_after == candidate_count_before == 2
    assert event_count_after == event_count_before
