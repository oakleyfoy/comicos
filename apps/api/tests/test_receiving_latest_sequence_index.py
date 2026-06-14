from __future__ import annotations

from unittest.mock import MagicMock

from app.services.receiving.receiving_service import _latest_sequence_index


def test_latest_sequence_index_treats_zero_as_valid_max() -> None:
    session = MagicMock()
    session.exec.return_value.first.return_value = 0
    assert _latest_sequence_index(session, 99) == 0


def test_latest_sequence_index_empty_session_returns_negative_one() -> None:
    session = MagicMock()
    session.exec.return_value.first.return_value = None
    assert _latest_sequence_index(session, 99) == -1
