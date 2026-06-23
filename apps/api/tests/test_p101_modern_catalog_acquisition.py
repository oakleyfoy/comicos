"""P101 modern catalog acquisition helpers."""

from __future__ import annotations

from app.services.p101_modern_catalog_acquisition_service import (
    build_p101_runbook_plan,
    is_p101_modern_universe_volume,
)
from app.models.catalog_p97 import ComicVineVolumeUniverse


def test_is_p101_modern_universe_volume() -> None:
    row = ComicVineVolumeUniverse(
        volume_id=1,
        name="Superman",
        publisher="DC Comics",
        start_year=2016,
        count_of_issues=52,
    )
    assert is_p101_modern_universe_volume(row) is True
    old = ComicVineVolumeUniverse(
        volume_id=2,
        name="Superman",
        publisher="DC Comics",
        start_year=1987,
        count_of_issues=100,
    )
    assert is_p101_modern_universe_volume(old) is False


def test_runbook_plan_includes_dry_run_before_live() -> None:
    plan = build_p101_runbook_plan(api_root=r"C:\comic-os-p41-feed\apps\api")
    text = "\n".join(plan.powershell_commands)
    assert "apps\\apps\\api" not in text
    assert "queue-preview" in text
    assert "--dry-run" in text
    assert "p97_import_volume_issue_queue.py" in text
    assert "2009" in text or "2009" in str(plan.year_min)
