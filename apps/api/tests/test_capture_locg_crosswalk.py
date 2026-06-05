from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_SCRIPT = API_ROOT / "scripts" / "capture_locg_date_details_browser.py"


def _load_capture_module():
    spec = importlib.util.spec_from_file_location("capture_locg_date_details_browser", CAPTURE_SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_resolve_run_crosswalk_default_skips() -> None:
    mod = _load_capture_module()
    assert mod.resolve_run_crosswalk(run_crosswalk=False, skip_crosswalk=False) is False
    assert mod.resolve_run_crosswalk(run_crosswalk=False, skip_crosswalk=True) is False


def test_resolve_run_crosswalk_run_flag_enables() -> None:
    mod = _load_capture_module()
    assert mod.resolve_run_crosswalk(run_crosswalk=True, skip_crosswalk=False) is True


def test_resolve_run_crosswalk_mutually_exclusive() -> None:
    mod = _load_capture_module()
    with pytest.raises(ValueError, match="cannot use both"):
        mod.resolve_run_crosswalk(run_crosswalk=True, skip_crosswalk=True)


def test_capture_script_guards_crosswalk_behind_run_flag() -> None:
    text = CAPTURE_SCRIPT.read_text(encoding="utf-8")
    assert "if run_crosswalk:" in text
    assert "resolve_run_crosswalk" in text
    assert "--run-crosswalk" in text
    assert "--skip-crosswalk" in text
