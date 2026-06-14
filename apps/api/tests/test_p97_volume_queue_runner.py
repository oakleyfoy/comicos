from __future__ import annotations

import os
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

API_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(API_ROOT), str(API_ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import app.models  # noqa: F401,E402

from app.models.catalog_p97 import P97ComicVineRequestLedger, P97ComicVineVolumeQueue  # noqa: E402
from app.services.p97_volume_queue_service import (  # noqa: E402
    apply_import_result,
    issues_per_api_request,
    select_next_pending,
)
import p97_run_volume_queue as runner  # noqa: E402


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _fake_stats(*, created=0, updated=0, images=0, api_requests=0, throttled=False, failures=None):
    return types.SimpleNamespace(
        volume_id=None,
        created_issues=created,
        updated_issues=updated,
        cover_images_created=images,
        api_requests_used=api_requests,
        throttled=throttled,
        failures=failures or [],
    )


class _FakeImporter:
    def __init__(self, stats_by_volume=None, default_stats=None):
        self.stats_by_volume = stats_by_volume or {}
        self.default_stats = default_stats or _fake_stats(created=5, api_requests=2)
        self.calls: list[int] = []

    def initialize_or_explain(self):
        return None

    def import_single_volume(self, session, *, comicvine_volume_id, import_issues=False):
        self.calls.append(int(comicvine_volume_id))
        return self.stats_by_volume.get(int(comicvine_volume_id), self.default_stats)


def _seed_pending(session, volume_id, *, priority=100, status="pending"):
    row = P97ComicVineVolumeQueue(
        comicvine_volume_id=volume_id,
        series_name=f"Series {volume_id}",
        priority=priority,
        status=status,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


# --- command composition (exact volume only) ------------------------------

def test_build_volume_import_command_is_exact_volume_only() -> None:
    cmd = runner.build_volume_import_command(87154, import_issues=True)
    assert cmd == [
        "python",
        "scripts/p97_import_comicvine_catalog.py",
        "--volume-id",
        "87154",
        "--import-issues",
    ]
    joined = " ".join(cmd)
    assert "--publisher" not in joined
    assert "--series-name" not in joined
    assert "--offset" not in joined
    assert "--strict-publisher" not in joined


# --- lock file ------------------------------------------------------------

def test_lock_acquire_blocks_foreign_live_pid(tmp_path: Path, monkeypatch) -> None:
    lock = tmp_path / "volume_queue_runner.lock"
    lock.write_text("424242", encoding="utf-8")
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: pid == 424242)
    assert runner.acquire_runner_lock(lock) is False


def test_lock_acquire_replaces_stale_dead_pid(tmp_path: Path, monkeypatch) -> None:
    lock = tmp_path / "volume_queue_runner.lock"
    lock.write_text("424242", encoding="utf-8")
    monkeypatch.setattr(runner, "_pid_alive", lambda pid: False)
    assert runner.acquire_runner_lock(lock) is True
    assert runner.read_lock_pid(lock) == os.getpid()
    runner.release_runner_lock(lock)
    assert not lock.exists()


# --- imported rows are not retried ----------------------------------------

def test_imported_rows_not_selected(session: Session) -> None:
    imported = _seed_pending(session, 111, status="imported")
    pending = _seed_pending(session, 222, status="pending")
    selected = select_next_pending(session)
    assert selected is not None
    assert selected.comicvine_volume_id == 222
    assert imported.status == "imported"


def test_run_skips_imported_volume(session: Session, monkeypatch) -> None:
    monkeypatch.setattr(runner, "write_progress_artifact", lambda *a, **k: None)
    _seed_pending(session, 111, status="imported")
    _seed_pending(session, 222, status="pending")
    fake = _FakeImporter(default_stats=_fake_stats(created=3, api_requests=1))
    monkeypatch.setattr(runner, "ComicVineCatalogImporter", lambda *a, **k: fake)

    runner.run_queue(
        session,
        max_requests_per_hour=120,
        min_seconds_between_requests=0,
        pause_hours_on_420=4,
        limit=10,
        watch=False,
        dry_run=False,
        reprocess=False,
        sleep_fn=lambda *_: None,
    )
    assert fake.calls == [222]
    imported = session.exec(
        select(P97ComicVineVolumeQueue).where(P97ComicVineVolumeQueue.comicvine_volume_id == 111)
    ).first()
    assert imported.status == "imported"


# --- successful run records ledger + marks imported -----------------------

def test_run_imports_pending_and_records_requests(session: Session, monkeypatch) -> None:
    monkeypatch.setattr(runner, "write_progress_artifact", lambda *a, **k: None)
    _seed_pending(session, 87154)
    fake = _FakeImporter(default_stats=_fake_stats(created=10, updated=2, images=4, api_requests=3))
    monkeypatch.setattr(runner, "ComicVineCatalogImporter", lambda *a, **k: fake)

    result = runner.run_queue(
        session,
        max_requests_per_hour=120,
        min_seconds_between_requests=0,
        pause_hours_on_420=4,
        limit=1,
        watch=False,
        dry_run=False,
        reprocess=False,
        sleep_fn=lambda *_: None,
    )
    assert fake.calls == [87154]
    row = session.exec(
        select(P97ComicVineVolumeQueue).where(P97ComicVineVolumeQueue.comicvine_volume_id == 87154)
    ).first()
    assert row.status == "imported"
    assert row.issues_created == 10
    assert row.api_requests_used == 3
    # 3 real requests recorded in the ledger, none of them a 420.
    ledger = session.exec(select(P97ComicVineRequestLedger)).all()
    assert len(ledger) == 3
    assert all(not entry.was_420 for entry in ledger)
    assert result["issues_created_run"] == 10


# --- 420 pauses the queue and never retries immediately -------------------

def test_run_420_pauses_and_marks_throttled(session: Session, monkeypatch) -> None:
    monkeypatch.setattr(runner, "write_progress_artifact", lambda *a, **k: None)
    _seed_pending(session, 87154)
    fake = _FakeImporter(
        default_stats=_fake_stats(created=0, api_requests=2, throttled=True, failures=["ComicVine HTTP 420"])
    )
    monkeypatch.setattr(runner, "ComicVineCatalogImporter", lambda *a, **k: fake)

    sleeps: list[float] = []
    result = runner.run_queue(
        session,
        max_requests_per_hour=120,
        min_seconds_between_requests=0,
        pause_hours_on_420=4,
        limit=10,
        watch=False,
        dry_run=False,
        reprocess=False,
        sleep_fn=lambda s: sleeps.append(s),
    )
    row = session.exec(
        select(P97ComicVineVolumeQueue).where(P97ComicVineVolumeQueue.comicvine_volume_id == 87154)
    ).first()
    assert row.status == "throttled"
    # exactly one volume attempted; no immediate retry burst.
    assert fake.calls == [87154]
    ledger = session.exec(select(P97ComicVineRequestLedger)).all()
    assert any(entry.was_420 for entry in ledger)
    assert result["status"] == "paused_420"


# --- issues per API request -----------------------------------------------

def test_issues_per_api_request_calculation() -> None:
    assert issues_per_api_request(0, 0) == 0.0
    assert issues_per_api_request(10, 0) == 0.0
    assert issues_per_api_request(30, 3) == 10.0
    assert issues_per_api_request(5, 2) == 2.5
