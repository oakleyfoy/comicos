from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


def _load_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "lunar_production_month_import_check.py"
    spec = importlib.util.spec_from_file_location("lunar_production_month_import_check", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_partial_counts_as_finished() -> None:
    mod = _load_module()
    runs = [
        SimpleNamespace(status="PARTIAL"),
        SimpleNamespace(status="FAILED"),
    ]
    assert mod._period_has_finished_import(runs) is True


def test_run_matches_april_file() -> None:
    mod = _load_module()
    run = SimpleNamespace(file_period="2026-04", file_name="Lunar_Product_Data_0426.csv")
    assert mod._run_matches_period(run, "2026-04") is True


def test_script_documents_force_and_finished() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "lunar_production_month_import_check.py"
    ).read_text(encoding="utf-8")
    assert "FINISHED_LUNAR_STATUSES" in source
    assert '"PARTIAL"' in source or "'PARTIAL'" in source
    assert "--force" in source
    assert "finished_runs" in source
    assert "month_coverage_satisfied" in source
