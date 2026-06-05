from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"


def _load_script(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_backfill_script_does_not_import_recommendation_rebuild() -> None:
    text = (SCRIPTS / "backfill_locg_calendar.py").read_text(encoding="utf-8")
    assert "rebuild" not in text.lower() or "crosswalk" not in text
    assert "generate_unified" not in text
    assert "cross_system" not in text
    assert "run_spec_recommendations" not in text


def test_sync_script_source() -> None:
    text = (SCRIPTS / "sync_locg_new_weeks.py").read_text(encoding="utf-8")
    assert "sync_new_weeks" in text
    assert "generate_unified" not in text


def test_report_script_source() -> None:
    text = (SCRIPTS / "report_external_catalog_coverage.py").read_text(encoding="utf-8")
    assert "build_coverage_report" in text
    assert "rebuild_external_catalog_crosswalk" in text


def test_browser_capture_script_no_recommendation_rebuild() -> None:
    text = (SCRIPTS / "capture_locg_date_details_browser.py").read_text(encoding="utf-8")
    assert "run_playwright_capture" in text
    assert "compute_recommendation_decision" not in text
    assert "cross_system_recommendation" not in text
