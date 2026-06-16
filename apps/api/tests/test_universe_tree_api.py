from __future__ import annotations

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from decimal import Decimal

from app.models.acquisition import Acquisition
from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries
from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue, UniversePublisher, UniverseVariant, UniverseVolume
from app.models import User
from app.services.universe.universe_issue_service import build_issue_shells_from_catalog, upsert_issue_shell
from app.services.universe.universe_publisher_service import build_publishers_from_discovered_volumes
from app.services.universe.universe_volume_service import build_volumes_from_discovered_universe
from test_inventory import auth_headers, register_and_login


def _seed_cv_universe(session: Session) -> None:
    session.add(
        ComicVineVolumeUniverse(
            volume_id=88001,
            name="Amazing Spider-Man",
            publisher="Marvel",
            start_year=1963,
            count_of_issues=900,
        )
    )
    session.add(
        ComicVineVolumeUniverse(
            volume_id=88002,
            name="Batman",
            publisher="DC Comics",
            start_year=1940,
            count_of_issues=800,
        )
    )
    session.commit()


def test_universe_publishers_build_and_list(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p98-pub@test.com")
    _seed_cv_universe(session)
    stats = build_publishers_from_discovered_volumes(session)
    assert stats["publishers"] >= 2
    resp = client.get("/api/v1/universe/publishers", headers=auth_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    names = {row["name"] for row in body["items"]}
    assert "Marvel" in names
    assert "DC Comics" in names


def test_universe_volumes_hierarchy(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p98-vol@test.com")
    _seed_cv_universe(session)
    build_publishers_from_discovered_volumes(session)
    build_volumes_from_discovered_universe(session)
    marvel = session.exec(select(UniversePublisher).where(UniversePublisher.name == "Marvel")).first()
    assert marvel is not None
    resp = client.get(
        f"/api/v1/universe/publishers/{marvel.id}/volumes",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    titles = {row["name"] for row in resp.json()["items"]}
    assert "Amazing Spider-Man" in titles


def test_universe_issue_and_variant_shells(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p98-iss@test.com")
    _seed_cv_universe(session)
    build_publishers_from_discovered_volumes(session)
    build_volumes_from_discovered_universe(session)
    volume = session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88002)
    ).first()
    assert volume is not None
    upsert_issue_shell(session, volume=volume, issue_number="497", issue_title=None)
    session.commit()
    issue = session.exec(
        select(UniverseIssue).where(
            UniverseIssue.volume_id == int(volume.id or 0),
            UniverseIssue.issue_number == "497",
        )
    ).first()
    assert issue is not None
    variant = session.exec(select(UniverseVariant).where(UniverseVariant.issue_id == issue.id)).first()
    assert variant is not None
    assert variant.variant_type == "UNKNOWN"

    resp = client.get(
        f"/api/v1/universe/volumes/{volume.id}/issues",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert any(row["issue_number"] == "497" for row in resp.json()["items"])

    vresp = client.get(
        f"/api/v1/universe/issues/{issue.id}/variants",
        headers=auth_headers(token),
    )
    assert vresp.status_code == 200
    assert len(vresp.json()["items"]) >= 1


def test_universe_tree_search(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p98-search@test.com")
    _seed_cv_universe(session)
    build_publishers_from_discovered_volumes(session)
    build_volumes_from_discovered_universe(session)
    resp = client.get("/api/v1/universe/search?q=Batman", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.json()["total_count"] >= 1


def test_universe_acquisition_placeholder(client: TestClient, session: Session) -> None:
    token = register_and_login(client, "p98-acq@test.com")
    _seed_cv_universe(session)
    build_publishers_from_discovered_volumes(session)
    build_volumes_from_discovered_universe(session)
    publisher = CatalogPublisher(name="Marvel", normalized_name="marvel")
    session.add(publisher)
    session.flush()
    series = CatalogSeries(
        publisher_id=publisher.id,
        name="Amazing Spider-Man",
        normalized_name="amazing spider man",
        start_year=1963,
        external_source_ids={"COMICVINE": {"88001": True}},
    )
    session.add(series)
    session.flush()
    session.add(
        CatalogIssue(
            series_id=int(series.id),
            publisher_id=int(publisher.id),
            issue_number="347",
            normalized_issue_number="347",
            title="Smoke and Mirrors",
        )
    )
    session.commit()
    build_issue_shells_from_catalog(session)

    volume = session.exec(select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == 88001)).first()
    issue = session.exec(
        select(UniverseIssue).where(
            UniverseIssue.volume_id == int(volume.id or 0),
            UniverseIssue.normalized_issue_number == "347",
        )
    ).first()
    variant = session.exec(select(UniverseVariant).where(UniverseVariant.issue_id == issue.id)).first()

    user_id = int(session.exec(select(User).where(User.email == "p98-acq@test.com")).one().id or 0)
    acq = Acquisition(
        user_id=user_id,
        acquisition_type="LCS",
        seller_name="Test",
        total_paid=Decimal("10.00"),
        shipping_paid=Decimal("0"),
        tax_paid=Decimal("0"),
        status="OPEN",
    )
    session.add(acq)
    session.commit()

    resp = client.post(
        f"/api/v1/universe/acquisitions/{acq.id}/placeholders",
        headers=auth_headers(token),
        json={"universe_variant_id": int(variant.id or 0), "quantity": 1},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["created_count"] == 1
