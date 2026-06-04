"""Owner email -> user id resolution for production scripts."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from owner_lookup import resolve_owner_user_id, unwrap_user_row, user_id_from_object


def test_user_id_from_orm_like() -> None:
    assert user_id_from_object(SimpleNamespace(id=42)) == 42


def test_user_id_from_mapping_row() -> None:
    class _Row:
        def __getitem__(self, key: str):
            return {"id": 7}[key]

    assert user_id_from_object(_Row()) == 7


def test_unwrap_user_scalar_tuple() -> None:
    assert unwrap_user_row((SimpleNamespace(id=3),)) is not None
    assert user_id_from_object(unwrap_user_row((SimpleNamespace(id=3),))) == 3


def test_resolve_owner_user_id_integration(client) -> None:
    from sqlmodel import Session, select

    from app.db.session import get_engine
    from app.models import User

    with Session(get_engine()) as session:
        user_row = session.exec(select(User).limit(1)).one_or_none()
        user = unwrap_user_row(user_row)
        if user is None:
            return
        email = getattr(user, "email", None)
        expected = user_id_from_object(user)
        if not email or expected is None:
            return
        assert resolve_owner_user_id(session, email) == expected
