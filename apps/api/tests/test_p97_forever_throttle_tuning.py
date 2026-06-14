from __future__ import annotations

import re
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "scripts" / "p97_overnight_catalog_run.ps1"


def test_forever_sleep_floor_is_ten_seconds() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    match = re.search(r"\$ComicVineForeverMinSleepSeconds\s*=\s*(\d+(?:\.\d+)?)", text)
    assert match is not None
    assert float(match.group(1)) == 10.0


def test_forever_disables_sleep_recovery_in_apply() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "function Apply-ComicVineSleepRecovery" in text
    block = text.split("function Apply-ComicVineSleepRecovery", 1)[1].split("function ", 1)[0]
    assert "if ($Forever) { return }" in block.replace("`r", "")


def test_forever_import_has_zero_throttle_retries() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "function Get-ImportThrottleRetryMax" in text
    assert "if ($Forever) { return 0 }" in text.replace("`r", "")


def test_forever_420_at_sleep_floor_skips_global_cooldown() -> None:
    text = RUNNER.read_text(encoding="utf-8")
    assert "function Invoke-ForeverPublisherChunk" in text
    block = text.split("function Invoke-ForeverPublisherChunk", 1)[1].split("\nfunction ", 1)[0]
    normalized = block.replace("`r", "")
    assert "HTTP_420_THROTTLED" in normalized
    assert "Start-Sleep -Seconds $ThrottleSleepSeconds" not in normalized
    assert "no global cooldown" in normalized
