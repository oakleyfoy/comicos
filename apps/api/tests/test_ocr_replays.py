from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlmodel import Session, select

from app.models import CoverImageOcrResult, InventoryCopy, MetadataAudit, OcrReplayItem
from app.tasks.jobs import run_cover_image_ocr_job, run_cover_image_process_job


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_order_basic(client: TestClient, token: str) -> dict:
    payload = {
        "retailer": "Whatnot",
        "order_date": "2026-05-19",
        "source_type": "manual",
        "shipping_amount": 0,
        "tax_amount": 0,
        "items": [
            {
                "title": "Invincible",
                "publisher": "Image",
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 5.0,
            }
        ],
    }
    response = client.post("/orders", json=payload, headers=auth_headers(token))
    assert response.status_code == 201
    return response.json()


def make_png_bytes(
    *,
    size: tuple[int, int] = (1400, 900),
    color: tuple[int, int, int] = (30, 120, 200),
) -> bytes:
    image = Image.new("RGB", size, color=color)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _inventory_copy_id_for_new_order(client: TestClient, token: str) -> int:
    created = create_order_basic(client, token)
    order_detail = client.get(f"/orders/{created['order_id']}", headers=auth_headers(token))
    return order_detail.json()["items"][0]["inventory_copy_ids"][0]


def _upload_inventory_cover(client: TestClient, token: str, inventory_copy_id: int, body: bytes) -> int:
    response = client.post(
        f"/inventory/{inventory_copy_id}/cover-images",
        headers=auth_headers(token),
        files={"file": ("scan.png", body, "image/png")},
        data={"source_type": "upload"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _make_cover_ready(client: TestClient, session: Session, token: str) -> tuple[int, int, int]:
    inventory_copy_id = _inventory_copy_id_for_new_order(client, token)
    cover_id = _upload_inventory_cover(client, token, inventory_copy_id, make_png_bytes())
    inv = session.get(InventoryCopy, inventory_copy_id)
    assert inv is not None
    result = run_cover_image_process_job(cover_id, inv.user_id)
    assert result["processing_status"] == "processed"
    return inventory_copy_id, cover_id, inv.user_id


def _stub_ocr_enqueue(monkeypatch, cover_id: int) -> None:
    fake_job = type("FakeJob", (), {"id": f"cover-image-ocr-{cover_id}"})()
    monkeypatch.setattr("app.services.background_jobs.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr("app.tasks.queue.fetch_job_by_id", lambda job_id: None)
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_cover_image_ocr_job",
        lambda **kwargs: fake_job,
    )


def _run_ocr_for_cover(
    client: TestClient,
    session: Session,
    token: str,
    cover_id: int,
    user_id: int,
    monkeypatch,
    *,
    raw_text: str,
) -> int:
    _stub_ocr_enqueue(monkeypatch, cover_id)
    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", lambda path: raw_text)
    monkeypatch.setattr("app.services.cover_images.get_tesseract_engine_version", lambda: "tesseract-replay")
    enqueue = client.post(f"/cover-images/{cover_id}/run-ocr", headers=auth_headers(token))
    assert enqueue.status_code == 202
    ocr_result_id = enqueue.json()["ocr_result_id"]
    assert ocr_result_id is not None
    result = run_cover_image_ocr_job(cover_id, user_id, ocr_result_id)
    assert result["processing_status"] == "processed"
    session.expire_all()
    return ocr_result_id


def _bootstrap_full_pipeline_artifacts(
    client: TestClient,
    session: Session,
    token: str,
    cover_id: int,
    user_id: int,
    monkeypatch,
) -> None:
    _run_ocr_for_cover(
        client,
        session,
        token,
        cover_id,
        user_id,
        monkeypatch,
        raw_text="SPAWN #1 IMAGE\nUPC 123456789012",
    )
    assert client.post(
        f"/cover-images/{cover_id}/extract-ocr-candidates",
        headers=auth_headers(token),
    ).status_code == 200
    assert client.post(
        f"/cover-images/{cover_id}/extract-barcodes",
        headers=auth_headers(token),
    ).status_code == 200
    assert client.post(
        f"/cover-images/{cover_id}/generate-fingerprints",
        headers=auth_headers(token),
    ).status_code == 200
    assert client.post(
        f"/cover-images/{cover_id}/analyze-ocr-quality",
        headers=auth_headers(token),
    ).status_code == 200
    assert client.post(
        f"/cover-images/{cover_id}/reconcile-ocr-metadata",
        headers=auth_headers(token),
    ).status_code == 200


def test_create_ocr_replay_orders_items_and_skips_invalid_ids(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "ocr-replay-create@example.com")
    _inv_a, cover_a, _user_a = _make_cover_ready(client, session, token)
    _inv_b, cover_b, _user_b = _make_cover_ready(client, session, token)

    response = client.post(
        "/ocr-replays",
        headers=auth_headers(token),
        json={"replay_type": "ocr_result", "cover_image_ids": [cover_b, 999999, cover_a, cover_a]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["total_items"] == 2
    assert [item["cover_image_id"] for item in payload["items"]] == [cover_a, cover_b]
    assert payload["status"] == "pending"

    audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_replay_run")).all()
    assert any(a.action == "ocr_replay_run_created" for a in audits)


def test_ocr_replay_detects_unchanged_full_pipeline_without_mutating_history(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ocr-replay-unchanged@example.com")
    inventory_copy_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _bootstrap_full_pipeline_artifacts(client, session, token, cover_id, user_id, monkeypatch)
    before_ocr_ids = [
        row.id
        for row in session.exec(
            select(CoverImageOcrResult)
            .where(CoverImageOcrResult.cover_image_id == cover_id)
            .order_by(CoverImageOcrResult.id.asc())
        ).all()
    ]

    create = client.post(
        "/ocr-replays",
        headers=auth_headers(token),
        json={"replay_type": "full_pipeline", "cover_image_ids": [cover_id]},
    )
    assert create.status_code == 201
    replay_id = create.json()["id"]

    start = client.post(f"/ocr-replays/{replay_id}/start", headers=auth_headers(token))
    assert start.status_code == 200
    payload = start.json()
    assert payload["status"] == "completed"
    assert payload["changed_items"] == 0
    assert payload["unchanged_items"] == 1
    assert payload["items"][0]["status"] == "unchanged"
    assert payload["items"][0]["diff_summary_json"]["status"] == "unchanged"

    session.expire_all()
    after_rows = session.exec(
        select(CoverImageOcrResult)
        .where(CoverImageOcrResult.cover_image_id == cover_id)
        .order_by(CoverImageOcrResult.id.asc())
    ).all()
    assert [row.id for row in after_rows] == before_ocr_ids

    inventory_detail = client.get(f"/inventory/{inventory_copy_id}", headers=auth_headers(token))
    assert inventory_detail.status_code == 200
    assert inventory_detail.json()["cover_images"][0]["id"] == cover_id


def test_ocr_replay_detects_changed_ocr_output(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ocr-replay-changed@example.com")
    _inv_id, cover_id, user_id = _make_cover_ready(client, session, token)
    _run_ocr_for_cover(
        client,
        session,
        token,
        cover_id,
        user_id,
        monkeypatch,
        raw_text="INVINCIBLE #1 IMAGE",
    )

    monkeypatch.setattr(
        "app.services.cover_images._run_tesseract_ocr_on_cover_path",
        lambda path: "INVINCIBLE #2 IMAGE",
    )
    create = client.post(
        "/ocr-replays",
        headers=auth_headers(token),
        json={"replay_type": "ocr_result", "cover_image_ids": [cover_id]},
    )
    replay_id = create.json()["id"]

    start = client.post(f"/ocr-replays/{replay_id}/start", headers=auth_headers(token))
    assert start.status_code == 200
    payload = start.json()
    assert payload["status"] == "completed_with_changes"
    assert payload["changed_items"] == 1
    assert payload["items"][0]["status"] == "changed"
    assert "raw_text" in payload["items"][0]["diff_summary_json"]["changed_fields"]


def test_ocr_replay_isolates_item_failures_and_allows_rerun_without_duplicate_items(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    token = register_and_login(client, "ocr-replay-failure@example.com")
    _inv_a, cover_a, user_a = _make_cover_ready(client, session, token)
    _inv_b, cover_b, user_b = _make_cover_ready(client, session, token)
    assert user_a == user_b
    _run_ocr_for_cover(
        client,
        session,
        token,
        cover_a,
        user_a,
        monkeypatch,
        raw_text="ALPHA #1",
    )
    _run_ocr_for_cover(
        client,
        session,
        token,
        cover_b,
        user_b,
        monkeypatch,
        raw_text="BETA #2",
    )

    outputs = iter(["ALPHA #1", ValueError("synthetic replay failure")])

    def _replay_ocr(path) -> str:
        value = next(outputs)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr("app.services.cover_images._run_tesseract_ocr_on_cover_path", _replay_ocr)

    create = client.post(
        "/ocr-replays",
        headers=auth_headers(token),
        json={"replay_type": "ocr_result", "cover_image_ids": [cover_b, cover_a]},
    )
    replay_id = create.json()["id"]
    assert [item["cover_image_id"] for item in create.json()["items"]] == [cover_a, cover_b]

    start = client.post(f"/ocr-replays/{replay_id}/start", headers=auth_headers(token))
    assert start.status_code == 200
    payload = start.json()
    assert payload["status"] == "completed_with_changes"
    assert payload["unchanged_items"] == 1
    assert payload["failed_items"] == 1
    assert {item["status"] for item in payload["items"]} == {"unchanged", "failed"}
    failed_item = next(item for item in payload["items"] if item["status"] == "failed")
    assert "synthetic replay failure" in failed_item["last_error"]

    rerun = client.post(f"/ocr-replays/{replay_id}/start", headers=auth_headers(token))
    assert rerun.status_code == 200
    session.expire_all()
    items = session.exec(select(OcrReplayItem).where(OcrReplayItem.replay_run_id == replay_id)).all()
    assert len(items) == 2

    item_audits = session.exec(select(MetadataAudit).where(MetadataAudit.entity_type == "ocr_replay_item")).all()
    actions = {audit.action for audit in item_audits}
    assert "ocr_replay_item_unchanged" in actions
    assert "ocr_replay_item_failed" in actions
