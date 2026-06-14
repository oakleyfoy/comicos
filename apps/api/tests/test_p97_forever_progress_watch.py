from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from p97_forever_progress_watch import format_dashboard  # noqa: E402


def test_format_dashboard_includes_key_sections() -> None:
    doc = {
        "mode": "forever",
        "updated_at": "2026-06-14T12:00:00Z",
        "runtime_seconds": 13320,
        "status": "RUNNING",
        "issues_now": 24418,
        "issues_added_this_run": 1286,
        "goal_150k_progress_pct": 16.3,
        "goal_150k_remaining": 125582,
        "goal_200k_progress_pct": 12.2,
        "goal_200k_remaining": 175582,
        "current_publisher": "Marvel",
        "current_offset": 4300,
        "current_chunk_limit": 100,
        "chunks_completed_this_run": 43,
        "current_sleep_seconds": 7,
        "sleep_floor": 7,
        "last_420_at": "2026-06-14T16:53:24.5000931Z",
        "minutes_since_last_420": 42.5,
        "last_chunk_result": {"created": 72, "updated": 211, "skipped": 228, "failed": 0},
        "publisher_progress": {
            "Marvel": {"offset": 4300, "chunks": 43, "created": 1290, "updated": 4021, "420s": 3, "status": "ACTIVE"},
        },
    }
    text = format_dashboard(doc)
    assert "P97 Forever Catalog Acquisition" in text
    assert "Marvel" in text
    assert "150k progress" in text
    assert "created=72" in text
    assert "Sleep floor:" in text
    assert "Minutes since 420:" in text
