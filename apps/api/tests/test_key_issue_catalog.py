from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.key_issue_catalog import CANONICAL_KEY_ISSUE_CATALOG


def test_key_issue_catalog_contains_required_examples(client: TestClient) -> None:
    keys = {(entry.series_name, entry.issue_number, entry.key_issue_type) for entry in CANONICAL_KEY_ISSUE_CATALOG}
    assert ("Amazing Fantasy", "15", "FIRST_APPEARANCE") in keys
    assert ("Spawn", "1", "FIRST_APPEARANCE") in keys
    assert ("TMNT", "300", "MILESTONE_NUMBERING") in keys
    assert len(CANONICAL_KEY_ISSUE_CATALOG) >= 10
