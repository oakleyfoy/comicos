from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import CanonicalCreator, CanonicalSeries, InventoryCopy, MetadataAudit
from app.services.metadata_reenrichment import re_enrich_draft_import, re_enrich_inventory_copy


def register_and_login(client: TestClient, email: str) -> str:
    client.post("/auth/register", json={"email": email, "password": "supersecret123"})
    response = client.post("/auth/login", json={"email": email, "password": "supersecret123"})
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_manual_import_payload(
    *,
    publisher: str = "Marvel",
    title: str = "Amazing Spider-Man",
    writers: list[str] | None = None,
    release_date: str | None = None,
) -> dict:
    return {
        "raw_text": f"{publisher} {title} import",
        "retailer": "Midtown",
        "order_date": "2026-05-21",
        "source_type": "manual_draft",
        "shipping_amount": "0.00",
        "tax_amount": "0.00",
        "items": [
            {
                "publisher": publisher,
                "title": title,
                "release_date": release_date,
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "writers": writers,
                "quantity": 1,
                "raw_item_price": "4.99",
            }
        ],
        "warnings": [],
        "confidence_score": 1.0,
    }


def build_order_payload(
    *,
    publisher: str = "Marvel",
    title: str = "Amazing Spider-Man",
    release_date: str | None = None,
) -> dict:
    return {
        "retailer": "Midtown",
        "order_date": "2026-05-21",
        "source_type": "manual",
        "shipping_amount": 0.00,
        "tax_amount": 0.00,
        "items": [
            {
                "publisher": publisher,
                "title": title,
                "release_date": release_date,
                "issue_number": "1",
                "cover_name": "Cover A",
                "printing": None,
                "ratio": None,
                "variant_type": None,
                "cover_artist": None,
                "quantity": 1,
                "raw_item_price": 4.99,
            }
        ],
    }


def test_metadata_alias_crud_creates_audit_rows(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-audit@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-audit@example.com")

    created = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Marvel Comics",
            "canonical_value": "Marvel",
            "alias_type": "publisher",
        },
        headers=auth_headers(token),
    )
    assert created.status_code == 201

    updated = client.patch(
        f"/ops/metadata-aliases/{created.json()['id']}",
        json={"canonical_value": "Marvel Entertainment"},
        headers=auth_headers(token),
    )
    assert updated.status_code == 200

    deactivated = client.post(
        f"/ops/metadata-aliases/{created.json()['id']}/deactivate",
        headers=auth_headers(token),
    )
    assert deactivated.status_code == 200

    actions = [
        audit.action
        for audit in session.exec(
            select(MetadataAudit)
            .where(MetadataAudit.entity_type == "metadata_alias")
            .order_by(MetadataAudit.id.asc())
        ).all()
    ]
    assert actions == ["alias_created", "alias_updated", "alias_deactivated"]


def test_canonical_series_and_creator_creation_write_audits_without_breaking_flow(
    client: TestClient,
    session: Session,
) -> None:
    token = register_and_login(client, "audit-flow@example.com")

    create_import = client.post(
        "/imports/manual",
        json=build_manual_import_payload(writers=["Joshua Cassara"]),
        headers=auth_headers(token),
    )
    assert create_import.status_code == 201

    confirm = client.post(
        f"/imports/{create_import.json()['id']}/confirm",
        headers=auth_headers(token),
    )
    assert confirm.status_code == 200

    creator_audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "canonical_creator")
    ).all()
    series_audits = session.exec(
        select(MetadataAudit).where(MetadataAudit.entity_type == "canonical_series")
    ).all()
    assert creator_audits
    assert series_audits
    assert session.exec(select(CanonicalCreator)).all()
    assert session.exec(select(CanonicalSeries)).all()


def test_ops_can_enqueue_reenrichment_for_draft_and_record_audit(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-queue@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-queue@example.com")

    created = client.post(
        "/imports/manual",
        json=build_manual_import_payload(writers=["Joshua Cassara"]),
        headers=auth_headers(token),
    )
    assert created.status_code == 201

    fake_job = type("FakeJob", (), {"id": "metadata-reenrich-draft_item-1"})()
    monkeypatch.setattr(
        "app.services.background_jobs.enqueue_metadata_reenrich_job",
        lambda **kwargs: fake_job,
    )

    response = client.post(
        f"/ops/imports/{created.json()['id']}/re-enrich?reason=alias-refresh",
        headers=auth_headers(token),
    )
    assert response.status_code == 202
    assert response.json()["job_id"] == fake_job.id

    queued = session.exec(
        select(MetadataAudit)
        .where(
            MetadataAudit.entity_type == "draft_item",
            MetadataAudit.entity_id == created.json()["id"],
            MetadataAudit.action == "re_enrichment_queued",
        )
        .order_by(MetadataAudit.id.desc())
    ).first()
    assert queued is not None
    assert queued.reason == "alias-refresh"


def test_reenrich_draft_import_preserves_raw_values_and_updates_canonical_fields(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-draft-reenrich@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-draft-reenrich@example.com")

    created = client.post(
        "/imports/manual",
        json=build_manual_import_payload(writers=["Joshua Cassara"]),
        headers=auth_headers(token),
    )
    assert created.status_code == 201
    import_id = created.json()["id"]

    alias_response = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Joshua Cassara",
            "canonical_value": "Josh Cassara",
            "alias_type": "creator",
        },
        headers=auth_headers(token),
    )
    assert alias_response.status_code == 201

    re_enriched = re_enrich_draft_import(
        session,
        draft_import_id=import_id,
        actor_user_id=1,
        reason="creator alias changed",
    )
    item = re_enriched.parsed_payload_json["items"][0]
    assert item["raw_writers"] == ["Joshua Cassara"]
    assert item["writers"] == ["Josh Cassara"]
    assert item["canonical_writers"] == ["Josh Cassara"]


def test_reenrich_inventory_copy_updates_only_enrichment_owned_fields(
    client: TestClient,
    session: Session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPS_ADMIN_EMAILS", "ops-inventory-reenrich@example.com")
    get_settings.cache_clear()
    token = register_and_login(client, "ops-inventory-reenrich@example.com")

    created_order = client.post(
        "/orders",
        json=build_order_payload(
            publisher="Marvel Comics",
            title="Amazing Spider-Man",
            release_date="2025-01-15",
        ),
        headers=auth_headers(token),
    )
    assert created_order.status_code == 201

    copy = session.exec(select(InventoryCopy)).one()
    copy.current_fmv = Decimal("25.00")
    copy.hold_status = "sell"
    copy.grade_status = "graded"
    session.add(copy)
    session.commit()

    alias_response = client.post(
        "/ops/metadata-aliases",
        json={
            "alias_value": "Marvel Comics",
            "canonical_value": "Marvel",
            "alias_type": "publisher",
        },
        headers=auth_headers(token),
    )
    assert alias_response.status_code == 201

    before_variant_id = copy.variant_id
    before_order_item_id = copy.order_item_id
    re_enriched = re_enrich_inventory_copy(
        session,
        inventory_copy_id=copy.id,
        actor_user_id=1,
        reason="publisher alias changed",
    )

    assert re_enriched.variant_id == before_variant_id
    assert re_enriched.order_item_id == before_order_item_id
    assert re_enriched.current_fmv == Decimal("25.00")
    assert re_enriched.hold_status == "sell"
    assert re_enriched.grade_status == "graded"
    assert re_enriched.metadata_identity_key.startswith("Marvel|Amazing Spider-Man|1|")

    audit = session.exec(
        select(MetadataAudit)
        .where(
            MetadataAudit.entity_type == "inventory_copy",
            MetadataAudit.entity_id == copy.id,
            MetadataAudit.action == "re_enriched",
        )
        .order_by(MetadataAudit.id.desc())
    ).first()
    assert audit is not None
    assert audit.before_snapshot["current_fmv"] == "25.00"
    assert audit.after_snapshot["current_fmv"] == "25.00"
