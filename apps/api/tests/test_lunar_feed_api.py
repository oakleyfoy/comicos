from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.schemas.lunar_feed import LunarFeedImportSummaryRead
from test_inventory import auth_headers, register_and_login


def test_lunar_feed_api(client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("LUNAR_USERNAME", "store-user")
    monkeypatch.setenv("LUNAR_PASSWORD", "secret-value")
    token = register_and_login(client, "lunar-api@example.com")

    status = client.get("/api/v1/lunar-feed/credential-status", headers=auth_headers(token))
    assert status.status_code == 200
    body = status.json()["data"]
    assert body["credential_available"] is True
    assert "secret-value" not in str(body)
    assert body["username_masked"]

    with patch("app.api.lunar_feed.download_latest_monthly_products_csv") as download_mock:
        download_mock.return_value = type(
            "Downloaded",
            (),
            {
                "file_name": "june.csv",
                "file_period": "2026-06",
                "file_type": "LUNAR_FORMAT",
                "source_url": "https://example.test/june.csv",
                "content_bytes": b"x",
            },
        )()
        download = client.post("/api/v1/lunar-feed/download/latest", headers=auth_headers(token))
        assert download.status_code == 201

    dashboard = client.get("/api/v1/lunar-feed/dashboard", headers=auth_headers(token))
    assert dashboard.status_code == 200

    with patch("app.api.lunar_feed.import_latest_lunar_csv_from_remote") as import_mock:
        import_mock.return_value = LunarFeedImportSummaryRead(
            run_id=1,
            status="COMPLETED",
            source_type="REMOTE",
            file_name="june.csv",
            file_period="2026-06",
            records_processed=1,
            records_created=1,
            records_updated=0,
            records_failed=0,
            foc_alerts_created=0,
            errors=[],
        )
        remote = client.post("/api/v1/lunar-feed/import/latest-remote", headers=auth_headers(token))
        assert remote.status_code == 201

    csv_body = (
        "MainIdentifier,PublisherName,SeriesName,IssueNumber,Title,FOCDate,InStoreDate,CoverPrice\n"
        "A1,Image,Series,1,Series #1,2026-06-01,2026-06-24,4.99\n"
    )
    upload = client.post(
        "/api/v1/lunar-feed/import/upload",
        headers=auth_headers(token),
        files={"file": ("upload.csv", csv_body.encode("utf-8"), "text/csv")},
    )
    assert upload.status_code == 201
    assert upload.json()["data"]["records_processed"] == 1
