from __future__ import annotations

from app.services.lunar_change_detection import (
    LunarFileSnapshot,
    calculate_file_checksum,
    detect_changed_file,
    detect_new_file,
    evaluate_import_decision,
)


def test_calculate_file_checksum_stable() -> None:
    content = b"same-bytes"
    assert calculate_file_checksum(content) == calculate_file_checksum(content)
    assert calculate_file_checksum(content) != calculate_file_checksum(b"other")


def test_detect_new_file_when_no_previous() -> None:
    snapshot = LunarFileSnapshot("a.csv", "2026-06", "abc", b"x", "https://example.test/a.csv")
    assert detect_new_file(last_file_name="", last_file_period="", snapshot=snapshot) is True


def test_detect_changed_file() -> None:
    snapshot = LunarFileSnapshot("a.csv", "2026-06", "new-checksum", b"x", "https://example.test/a.csv")
    assert detect_changed_file(last_checksum="old-checksum", snapshot=snapshot) is True
    assert detect_changed_file(last_checksum="new-checksum", snapshot=snapshot) is False


def test_evaluate_import_decision_skip_unchanged() -> None:
    from unittest.mock import Mock

    snapshot = LunarFileSnapshot("a.csv", "2026-06", "same", b"x", "https://example.test/a.csv")
    config = Mock(
        last_imported_file_name="a.csv",
        last_imported_file_period="2026-06",
        last_imported_checksum="same",
        last_imported_at=None,
    )
    decision = evaluate_import_decision(None, owner_user_id=1, snapshot=snapshot, config=config)
    assert decision.should_import is False
    assert decision.reason == "UNCHANGED"


def test_evaluate_import_decision_import_changed() -> None:
    from unittest.mock import Mock

    snapshot = LunarFileSnapshot("a.csv", "2026-06", "changed", b"x", "https://example.test/a.csv")
    config = Mock(
        last_imported_file_name="a.csv",
        last_imported_file_period="2026-06",
        last_imported_checksum="same",
        last_imported_at=None,
    )
    decision = evaluate_import_decision(None, owner_user_id=1, snapshot=snapshot, config=config)
    assert decision.should_import is True
    assert decision.reason == "CHANGED_FILE"
