"""P99 pending queue batch executor tests."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import P97VolumeIssueImportQueue  # noqa: E402
from app.services.p99_pending_queue_batch_executor_service import (  # noqa: E402
    APPLY_ALLOWED_BATCH_KEYS,
    assert_apply_allowed,
    build_batch_volume_plan,
    normalize_batch_key,
    resolve_queue_rows_for_plan,
)

TOP_FIXTURE = [
    {
        "rank": 1,
        "comicvine_volume_id": 42285,
        "volume": "Teenage Mutant Ninja Turtles",
        "publisher": "IDW Publishing",
        "shell_gap": 150,
        "estimated_import_value": 150,
    }
]


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_normalize_batch_key() -> None:
    assert normalize_batch_key("1") == "1"
    assert normalize_batch_key("group1") == "group1"


def test_apply_group1_allowed() -> None:
    assert "group1" in APPLY_ALLOWED_BATCH_KEYS
    assert_apply_allowed("group1", apply=True)


def test_apply_batch_2_blocked() -> None:
    with pytest.raises(ValueError):
        assert_apply_allowed("2", apply=True)


def test_max_volumes_caps_plan(session: Session, tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    top_path = tmp_path / "top.json"
    top_path.write_text(json.dumps(TOP_FIXTURE), encoding="utf-8")
    batches_path = tmp_path / "batches.json"
    batches_path.write_text(
        json.dumps([{"batch_id": "batch_1", "label": "Top 25", "shells_affected": 150}]),
        encoding="utf-8",
    )
    plan = build_batch_volume_plan(
        session,
        "1",
        top_volumes_path=top_path,
        batches_path=batches_path,
        max_volumes=1,
    )
    assert plan.volumes_selected == 1


def test_skip_non_pending_row(session: Session, tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    top_path = tmp_path / "top.json"
    top_path.write_text(json.dumps(TOP_FIXTURE), encoding="utf-8")
    batches_path = tmp_path / "batches.json"
    batches_path.write_text(
        json.dumps([{"batch_id": "batch_1", "label": "Top 25", "shells_affected": 150}]),
        encoding="utf-8",
    )
    session.add(
        P97VolumeIssueImportQueue(
            comicvine_volume_id=42285,
            name="Teenage Mutant Ninja Turtles",
            publisher="IDW Publishing",
            status="complete",
            missing_issue_count=150,
            created_at=now,
            updated_at=now,
        )
    )
    session.commit()
    plan = build_batch_volume_plan(
        session,
        "1",
        top_volumes_path=top_path,
        batches_path=batches_path,
    )
    ready, skipped = resolve_queue_rows_for_plan(session, plan)
    assert ready == []
    assert len(skipped) == 1
    assert skipped[0].reason == "status_complete"
