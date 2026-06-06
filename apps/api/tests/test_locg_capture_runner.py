from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

from app.services.external_catalog.locg_browser import BrowserCaptureCounters
from app.services.external_catalog.locg_capture_runner import resolve_capture_exit_code
from app.services.external_catalog.locg_capture_timing import CaptureTimingAudit
from app.services.external_catalog.sync_service import (
    SYNC_COMPLETE_WITH_WARNINGS,
    SYNC_COMPLETED,
    SYNC_FAILED,
    SYNC_PARTIAL,
)

API_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = API_ROOT / "scripts" / "capture_locg_date_details_browser.py"


def _load_capture_module():
    spec = importlib.util.spec_from_file_location("capture_locg_date_details_browser", CAPTURE_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resolve_exit_code_complete_and_warnings_only() -> None:
    assert (
        resolve_capture_exit_code(
            run_status=SYNC_COMPLETED,
            list_page_loaded=True,
            list_issues_found=10,
            detail_pages_succeeded=10,
            max_issues=None,
        )
        == 0
    )
    assert (
        resolve_capture_exit_code(
            run_status=SYNC_COMPLETE_WITH_WARNINGS,
            list_page_loaded=True,
            list_issues_found=10,
            detail_pages_succeeded=10,
            max_issues=None,
        )
        == 0
    )
    assert (
        resolve_capture_exit_code(
            run_status=SYNC_PARTIAL,
            list_page_loaded=True,
            list_issues_found=10,
            detail_pages_succeeded=10,
            max_issues=None,
        )
        == 1
    )
    assert (
        resolve_capture_exit_code(
            run_status=SYNC_FAILED,
            list_page_loaded=True,
            list_issues_found=10,
            detail_pages_succeeded=10,
            max_issues=None,
            hard_failure=True,
        )
        == 1
    )


def test_capture_script_exits_zero_db_ok_artifact_warnings(monkeypatch, capsys) -> None:
    db_path = API_ROOT / ".locg_capture_runner_test.db"
    if db_path.exists():
        db_path.unlink()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    browser = BrowserCaptureCounters(
        list_page_loaded=True,
        list_issues_found=3,
        detail_pages_succeeded=3,
        list_variants_found=0,
        list_variants_persisted=0,
        post_capture_warnings=["list_page.html: [Errno 22] Invalid argument"],
    )
    audit = CaptureTimingAudit()

    def _fake_capture(**_kwargs):
        return browser, audit

    # Script imports this inside main() from locg_browser (not a script-level symbol).
    monkeypatch.setattr(
        "app.services.external_catalog.locg_browser.run_playwright_capture",
        _fake_capture,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture_locg_date_details_browser.py",
            "--date",
            "2025-01-01",
            "--skip-crosswalk",
        ],
    )

    mod = _load_capture_module()
    code = mod.main()
    out = capsys.readouterr().out
    assert code == 0
    assert "Run status: COMPLETE_WITH_WARNINGS" in out
    assert "--- LoCG capture final summary ---" in out
    assert "Warnings:" in out and "Errno 22" in out
