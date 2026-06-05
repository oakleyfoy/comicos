"""Surface first DB error during list variant persist (not 25P02 follow-on)."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlmodel import Session

from app.db.session import get_engine
from app.services.external_catalog.locg_browser import parse_list_variant_rows
from app.services.external_catalog.sync_service import (
    ensure_locg_source,
    format_db_exception,
    upsert_locg_list_variant_rows,
)


def main() -> int:
    html_path = ROOT.parent.parent / "data/locg_browser_capture/2026-06-10/list_page.html"
    if not html_path.is_file():
        print(json.dumps({"error": "list_page.html missing"}))
        return 1
    html = html_path.read_text(encoding="utf-8")
    rows = parse_list_variant_rows(html, page_date=date(2026, 6, 10))
    with Session(get_engine()) as session:
        ensure_locg_source(session)
        stats = upsert_locg_list_variant_rows(
            session,
            rows,
            list_html=html,
            page_date=date(2026, 6, 10),
        )
    out = {
        "variant_upsert_success": stats.variant_upsert_success,
        "variant_upsert_failure": stats.variant_upsert_failure,
        "first_variant_failure": stats.first_variant_failure,
        "first_variant_error": stats.first_variant_error,
        "persisted": stats.persisted,
        "found": stats.found,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
