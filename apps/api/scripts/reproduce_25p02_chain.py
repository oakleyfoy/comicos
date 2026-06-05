"""Reproduce: first DB error then 25P02 if session not rolled back."""

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
    find_locg_issue_by_comic_id,
    format_db_exception,
    upsert_variants,
)
from app.services.external_catalog.locg_live_html import list_variant_row_to_upsert_dict
from app.models.external_catalog import ExternalCatalogVariant


def main() -> int:
    html_path = ROOT.parent.parent / "data/locg_browser_capture/2026-06-10/list_page.html"
    html = html_path.read_text(encoding="utf-8")
    rows = parse_list_variant_rows(html, page_date=date(2026, 6, 10))
    first_db: dict | None = None
    aborted: dict | None = None
    with Session(get_engine()) as session:
        ensure_locg_source(session)
        parent = find_locg_issue_by_comic_id(session, rows[0].parent_comic_id)
        assert parent is not None
        # Force first failure: varchar(64) cover_label overflow via raw dict
        bad = list_variant_row_to_upsert_dict(rows[0])
        bad["cover_label"] = "X" * 80
        try:
            upsert_variants(session, parent, [bad])
        except Exception as exc:
            first_db = format_db_exception(exc)
        try:
            session.exec(
                __import__("sqlmodel").select(ExternalCatalogVariant).limit(1)
            ).first()
        except Exception as exc2:
            aborted = format_db_exception(exc2)
    print(
        json.dumps(
            {"first_actual_db_error": first_db, "second_error_after_no_rollback": aborted},
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
