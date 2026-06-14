from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = API_ROOT / "scripts" / "p97_import_comicvine_catalog.py"


def test_import_issues_exit_when_phase_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    sys.path.insert(0, str(API_ROOT / "scripts"))
    import p97_import_comicvine_catalog as cli

    monkeypatch.setattr(
        cli,
        "ComicVineCatalogImporter",
        lambda **_: MagicMock(
            initialize_or_explain=lambda: None,
            run_bulk_import=lambda *a, **k: MagicMock(
                volume_job_id=1,
                imported_series=0,
                skipped_non_matching_publisher=0,
                failures=[],
                issue_job_id=None,
                issue_import_ran=False,
                issue_import_volumes_attempted=0,
                created_issues=0,
                updated_issues=0,
                cover_images_created=0,
                cover_images_skipped=0,
                cover_images_skipped_no_url=0,
                publisher_distribution={},
            ),
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["p97_import_comicvine_catalog.py", "--import-issues", "--limit", "1"],
    )
    assert cli.main() == 3


def test_help_lists_import_issues() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--import-issues" in result.stdout


@pytest.mark.integration
def test_spawn_smoke_import_issues() -> None:
    import os

    if not os.environ.get("COMICVINE_API_KEY") and not (API_ROOT / ".env").exists():
        pytest.skip("COMICVINE_API_KEY not configured")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--series-name",
            "Spawn",
            "--limit",
            "1",
            "--import-issues",
            "--sleep-seconds",
            "1",
        ],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert "import_issues" in result.stdout
    assert "issue_job_id=" in result.stdout
    created = updated = 0
    for line in result.stdout.splitlines():
        if line.startswith("issues_created="):
            created = int(line.split("=", 1)[1])
        if line.startswith("issues_updated="):
            updated = int(line.split("=", 1)[1])
    assert created + updated >= 1
