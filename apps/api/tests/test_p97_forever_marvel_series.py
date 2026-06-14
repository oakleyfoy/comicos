from __future__ import annotations

import re
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "scripts" / "p97_overnight_catalog_run.ps1"


def _runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8").replace("`r", "")


def test_marvel_forever_series_queue_list() -> None:
    text = _runner_text()
    match = re.search(
        r"\$MarvelForeverSeriesTargets\s*=\s*@\((.*?)\)\s*\n",
        text,
        re.DOTALL,
    )
    assert match is not None
    names = re.findall(r'"([^"]+)"', match.group(1))
    assert names == [
        "Amazing Spider-Man",
        "Spider-Man",
        "Avengers",
        "Fantastic Four",
        "X-Men",
        "Uncanny X-Men",
        "Wolverine",
        "Incredible Hulk",
        "Captain America",
        "Iron Man",
        "Thor",
        "Daredevil",
        "Doctor Strange",
        "New Mutants",
        "X-Force",
        "Venom",
        "Punisher",
        "Deadpool",
        "Moon Knight",
        "Black Panther",
        "Guardians of the Galaxy",
        "Silver Surfer",
    ]


def test_marvel_zero_issue_streak_constant() -> None:
    text = _runner_text()
    assert "$MarvelForeverPublisherZeroIssueStreakLimit = 3" in text


def test_marvel_series_mode_daemon_branch() -> None:
    text = _runner_text()
    daemon = text.split("function Start-ForeverAcquisitionDaemon", 1)[1].split("\nfunction ", 1)[0]
    assert "Test-MarvelForeverSeriesQueueActive" in daemon
    assert "Invoke-ForeverMarvelSeriesChunk" in daemon
    assert "Invoke-SeriesImport" in text
    assert "-ForeverMarvel" in text


def test_marvel_publisher_streak_updates_after_chunk() -> None:
    text = _runner_text()
    chunk = text.split("function Invoke-ForeverPublisherChunk", 1)[1].split("\nfunction ", 1)[0]
    assert "Update-MarvelForeverPublisherZeroIssueStreak" in chunk


def test_marvel_forever_progress_persisted() -> None:
    text = _runner_text()
    assert "New-MarvelForeverProgressEntry" in text
    assert "marvel_forever" in text
    assert "Enter-MarvelForeverSeriesQueueMode" in text
    assert "Complete-MarvelForeverAcquisition" in text


def test_forever_progress_exports_marvel_series_fields() -> None:
    text = _runner_text()
    block = text.split("function Write-ForeverProgressArtifacts", 1)[1].split("\nfunction ", 1)[0]
    assert "marvel_forever_mode" in block
    assert "marvel_forever_series_queue" in block
