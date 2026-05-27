from __future__ import annotations

from sqlmodel import Session, col, select
from fastapi.testclient import TestClient

from app.models import (
    MarketAcquisitionCandidate,
    MarketAcquisitionIngestionEvent,
    MarketAcquisitionNormalizedCandidate,
    MarketAcquisitionNormalizationEvent,
    MarketAcquisitionNormalizationIssue,
    User,
)
from app.services import market_normalization as norm_svc
from test_inventory import auth_headers, register_and_login


def _ingestion_payload() -> dict[str, object]:
    return {
        "batch_source_type": "csv_import",
        "batch_file_name": "batch.csv",
        "records": [
            {
                "title": "The Amazing Spider-Man",
                "publisher": "Marvel Comics",
                "issue_number": "#12",
                "variant": "Cover A",
                "condition_raw": "VF/NM",
                "asking_price": "25.99",
                "currency": "USD",
                "external_fmv_estimate": "30.00",
            },
            {
                "title": "BATMAN YEAR ONE VARIANT ZZZ",
                "publisher": "DC Comics",
                "issue_number": "1/A 2/B",
                "variant": "Unknown Variant XYZ",
                "condition_raw": "weird_grade",
                "asking_price": "40.00",
                "currency": "usd",
                "external_fmv_estimate": "12.34",
            },
        ],
    }


def test_market_normalization_deterministic_outputs_and_stable_canonical_keys(
    client: TestClient,
    session: Session,
) -> None:
    _tok = register_and_login(client, "ma-norm-stable@example.com")
    ingest = client.post("/market-ingestion/batch", headers=auth_headers(_tok), json=_ingestion_payload())
    assert ingest.status_code == 201, ingest.text
    batch_id = int(ingest.json()["id"])

    cand = session.exec(
        select(MarketAcquisitionCandidate).where(MarketAcquisitionCandidate.ingestion_batch_id == batch_id),
    ).all()
    spider = next(c for c in cand if "Spider" in (c.title or ""))
    out1 = norm_svc.deterministic_normalize_candidate(spider)
    out2 = norm_svc.deterministic_normalize_candidate(spider)
    assert out1["canonical_key"] == out2["canonical_key"]
    assert out1["canonical_publisher"] == "Marvel"
    assert out1["canonical_issue_number"] == "12"
    assert out1["canonical_variant"] == "A"
    assert out1["normalized_condition_band"] == "VF"
    assert out1["normalization_status"] == "SUCCESS"
    assert not (out1["normalization_flags_json"] or {}).get("missing_publisher")

    first = norm_svc.compute_canonical_key(
        canonical_title=out1["canonical_title"],
        canonical_publisher=out1["canonical_publisher"],
        canonical_issue_number=out1["canonical_issue_number"],
        canonical_variant=out1["canonical_variant"],
    )
    second = norm_svc.compute_canonical_key(
        canonical_title=out1["canonical_title"],
        canonical_publisher=out1["canonical_publisher"],
        canonical_issue_number=out1["canonical_issue_number"],
        canonical_variant=out1["canonical_variant"],
    )
    assert first == second == out1["canonical_key"]


def test_market_normalization_replay_events_and_issues(
    client: TestClient,
    session: Session,
) -> None:
    token_a = register_and_login(client, "ma-norm-replay-a@example.com")
    token_b = register_and_login(client, "ma-norm-replay-b@example.com")

    ingest = client.post("/market-ingestion/batch", headers=auth_headers(token_a), json=_ingestion_payload())
    assert ingest.status_code == 201, ingest.text
    batch_id = int(ingest.json()["id"])

    run1 = client.post(
        "/market-normalization/run",
        headers=auth_headers(token_a),
        json={"ingestion_batch_id": batch_id},
    )
    assert run1.status_code == 201, run1.text
    run_id = int(run1.json()["id"])
    evt1_n = len(run1.json()["events"])

    run2 = client.post(
        "/market-normalization/run",
        headers=auth_headers(token_a),
        json={"ingestion_batch_id": batch_id},
    )
    assert run2.status_code == 200, run2.text
    assert int(run2.json()["id"]) == run_id
    evt2_n = len(run2.json()["events"])
    assert evt2_n == evt1_n

    issues = session.exec(select(MarketAcquisitionNormalizationIssue)).all()
    issue_types = {i.issue_type for i in issues}
    assert "VARIANT_CONFLICT" in issue_types
    assert "CONDITION_PARSE_ERROR" in issue_types

    ingestion_count_before = len(
        session.exec(
            select(MarketAcquisitionIngestionEvent).where(
                MarketAcquisitionIngestionEvent.ingestion_batch_id == batch_id,
            ),
        ).all(),
    )

    other_run = client.post(
        "/market-normalization/run",
        headers=auth_headers(token_b),
        json={"ingestion_batch_id": batch_id},
    )
    assert other_run.status_code == 404, other_run.text

    ingestion_count_after = len(
        session.exec(
            select(MarketAcquisitionIngestionEvent).where(
                MarketAcquisitionIngestionEvent.ingestion_batch_id == batch_id,
            ),
        ).all(),
    )
    assert ingestion_count_after == ingestion_count_before

    cand_filter = client.get(
        "/market-normalization/candidates",
        headers=auth_headers(token_a),
        params={"publisher": "Marvel"},
    )
    assert cand_filter.status_code == 200, cand_filter.text
    items = cand_filter.json()["items"]
    assert len(items) == 1
    assert items[0]["canonical_publisher"] == "Marvel"

    norms = session.exec(select(MarketAcquisitionNormalizedCandidate)).all()
    assert len(norms) == 2


def test_market_normalization_owner_ops_runs_visibility(
    client: TestClient,
    session: Session,
) -> None:
    token_a = register_and_login(client, "ma-norm-owner-a@example.com")
    owner_a = int(session.exec(select(User.id).where(User.email == "ma-norm-owner-a@example.com")).one())

    ingest = client.post("/market-ingestion/batch", headers=auth_headers(token_a), json=_ingestion_payload())
    assert ingest.status_code == 201, ingest.text
    batch_id = int(ingest.json()["id"])

    run = client.post(
        "/market-normalization/run",
        headers=auth_headers(token_a),
        json={"ingestion_batch_id": batch_id},
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]

    ops_runs = client.get(f"/ops/market-normalization/runs?owner_user_id={owner_a}", headers=auth_headers(token_a))
    assert ops_runs.status_code == 200, ops_runs.text
    ids = [int(r["id"]) for r in ops_runs.json()["items"]]
    assert int(run_id) in ids

    ops_detail = client.get(f"/ops/market-normalization/runs/{run_id}", headers=auth_headers(token_a))
    assert ops_detail.status_code == 200, ops_detail.text

    norm_events_before = session.exec(select(MarketAcquisitionNormalizationEvent)).all()
    evt_count_before = len(norm_events_before)

    rerun = client.post(
        "/market-normalization/run",
        headers=auth_headers(token_a),
        json={"ingestion_batch_id": batch_id},
    )
    assert rerun.status_code == 200

    evt_count_after = len(session.exec(select(MarketAcquisitionNormalizationEvent)).all())
    assert evt_count_after == evt_count_before


def test_market_normalization_run_checksum_stable_for_ordered_candidates(
    client: TestClient,
    session: Session,
) -> None:
    tok = register_and_login(client, "ma-norm-chk@example.com")
    r = client.post("/market-ingestion/batch", headers=auth_headers(tok), json=_ingestion_payload())
    assert r.status_code == 201, r.text
    batch_id = int(r.json()["id"])
    cand_rows = list(
        session.exec(
            select(MarketAcquisitionCandidate)
            .where(MarketAcquisitionCandidate.ingestion_batch_id == batch_id)
            .order_by(col(MarketAcquisitionCandidate.id)),
        ).all(),
    )
    chk1 = norm_svc.compute_run_checksum(cand_rows)
    chk2 = norm_svc.compute_run_checksum(cand_rows)
    assert chk1 == chk2


def test_parse_optional_money_invalid_string() -> None:
    price, invalid = norm_svc._parse_optional_money("$xYz")
    assert price is None
    assert invalid is True

