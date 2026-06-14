from __future__ import annotations

import re
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "scripts" / "p97_overnight_catalog_run.ps1"


def _runner_text() -> str:
    return RUNNER.read_text(encoding="utf-8").replace("`r", "")


def test_forever_major_publisher_order() -> None:
    text = _runner_text()
    match = re.search(
        r"\$ForeverMajorPublishers\s*=\s*@\((.*?)\)",
        text,
        re.DOTALL,
    )
    assert match is not None
    block = match.group(1)
    names = re.findall(r'"([^"]+)"', block)
    assert names == [
        "Marvel",
        "DC Comics",
        "Image",
        "Dark Horse",
        "IDW",
        "Boom",
    ]


def test_forever_minor_publishers_deferred_list() -> None:
    text = _runner_text()
    for noisy in ("AWA", "Oni", "DSTLRY", "Aftershock", "Mad Cave"):
        assert noisy in text
        assert f'$ForeverMinorPublishers' in text or "$ForeverMinorPublishers" in text
    assert "Get-ForeverPublisherWorkQueue" in text
    assert "Test-AllForeverMajorPublishersComplete" in text


def test_forever_daemon_uses_sequential_select_not_full_rotation() -> None:
    text = _runner_text()
    daemon = text.split("function Start-ForeverAcquisitionDaemon", 1)[1].split("\nfunction ", 1)[0]
    assert "Select-ForeverPublisherToRun" in daemon
    assert "foreach ($publisher in $PublisherTargets)" not in daemon


def test_forever_major_only_default_without_all_publishers_switch() -> None:
    text = _runner_text()
    assert "[switch]$AllPublishers" in text
    assert "$Script:ForeverMajorOnly = -not $AllPublishers" in text


def test_progress_artifacts_export_major_publisher_fields() -> None:
    text = _runner_text()
    block = text.split("function Write-ForeverProgressArtifacts", 1)[1].split("\nfunction ", 1)[0]
    assert "current_major_publisher" in block
    assert "next_major_publisher" in block
    assert "forever_major_only" in block
