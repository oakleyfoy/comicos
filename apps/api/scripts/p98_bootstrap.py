"""Shared bootstrap for P98 CLI scripts."""

from __future__ import annotations

import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]


def bootstrap_api_path() -> Path:
    if str(API_ROOT) not in sys.path:
        sys.path.insert(0, str(API_ROOT))
    return API_ROOT
