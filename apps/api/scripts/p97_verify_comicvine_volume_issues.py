"""Verify catalog issues imported for a ComicVine volume id."""

from __future__ import annotations

import argparse
import re

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session, select  # noqa: E402

from app.models.catalog_master import CatalogImage, CatalogIssue, CatalogSeries  # noqa: E402
from app.services.comicvine_catalog_importer import comicvine_volume_id_for_series  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402


def _comicvine_issue_id(issue: CatalogIssue) -> str | None:
    ext = (issue.external_source_ids or {}).get("COMICVINE")
    if not isinstance(ext, dict) or not ext:
        return None
    key = next(iter(ext.keys()), None)
    return str(key) if key is not None else None


def _issue_sort_key(issue: CatalogIssue) -> tuple:
    num = issue.normalized_issue_number or issue.issue_number or ""
    parts = re.split(r"(\d+)", num)
    key: list = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return tuple(key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify ComicVine volume issues in catalog")
    parser.add_argument("--volume-id", type=int, required=True)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    volume_key = str(int(args.volume_id))
    engine = get_p97_engine(resolve_p97_database_url(args.database_url))

    with Session(engine) as session:
        series = next(
            (
                row
                for row in session.exec(select(CatalogSeries)).all()
                if comicvine_volume_id_for_series(row) == volume_key
            ),
            None,
        )
        if series is None:
            print(f"No catalog_series linked to ComicVine volume {volume_key}")
            return 1

        issues = list(
            session.exec(select(CatalogIssue).where(CatalogIssue.series_id == int(series.id or 0))).all()
        )
        issues.sort(key=_issue_sort_key)

        print(f"ComicVine volume: {volume_key}")
        print(f"catalog_series_id: {series.id}  name: {series.name}")
        print(f"issue_count: {len(issues)}")
        print("")
        print(
            f"{'issue#':<8} {'cv_issue_id':<22} {'cover_date':<12} {'store_date':<12} "
            f"{'release_date':<12} image_url"
        )
        print("-" * 120)
        for issue in issues:
            images = session.exec(
                select(CatalogImage).where(CatalogImage.issue_id == int(issue.id or 0))
            ).all()
            urls = [img.source_url for img in images if img.source_url]
            image_preview = urls[0] if urls else ""
            print(
                f"{issue.issue_number:<8} "
                f"{(_comicvine_issue_id(issue) or ''):<22} "
                f"{str(issue.cover_date or ''):<12} "
                f"{str(issue.store_date or ''):<12} "
                f"{str(issue.release_date or ''):<12} "
                f"{image_preview}"
            )
            for extra in urls[1:3]:
                print(f"{'':8} {'':22} {'':12} {'':12} {'':12} {extra}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
