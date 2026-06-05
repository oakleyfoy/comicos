from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "scripts" / "verify_cross_system_owner.py"


def test_verify_script_help_lists_rebuild_flag() -> None:
    script = _script_path()
    proc = subprocess.run(
        [sys.executable, str(script), "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(script.parent.parent),
    )
    assert proc.returncode == 0
    assert "--rebuild" in proc.stdout
    assert "--production" in proc.stdout


def test_verify_script_module_has_read_only_default() -> None:
    script = _script_path()
    source = script.read_text(encoding="utf-8")
    assert "generate_cross_system_recommendations" in source
    assert "if args.rebuild:" in source
    assert "read_only" in source
    assert "build_recommendation_ranking_audit" in source
    assert "RECOMMENDATION_PIPELINE_EPOCH" in source
    assert "spread_verification" in source
    assert "recompute_candidates" in source
    assert "candidate_score_trace" in source
    assert '_stage_start("unified_recommendations")' in source
    assert '_stage_end("cross_system_recommendations"' in source
    assert "stage_elapsed_seconds" in source
