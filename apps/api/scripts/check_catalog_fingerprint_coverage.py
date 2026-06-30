"""One-off: is a catalog issue in the fingerprint index?"""
from __future__ import annotations

import sys

from sqlmodel import Session, create_engine, select, func

from app.core.config import get_settings
from app.models.catalog_master import CatalogImage, CatalogImageFingerprint, CatalogIssue, CatalogSeries, CatalogUpc, CatalogPublisher


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    barcode = sys.argv[1] if len(sys.argv) > 1 else "75960620629200111"
    series_q = sys.argv[2] if len(sys.argv) > 2 else "Amazing Spider-Man"
    issue_num = sys.argv[3] if len(sys.argv) > 3 else "122"

    with Session(engine) as session:
        total_fp = session.exec(select(func.count()).select_from(CatalogImageFingerprint)).one()
        print(f"catalog_image_fingerprint rows (all): {total_fp}")

        upc_rows = session.exec(
            select(CatalogUpc, CatalogIssue, CatalogSeries)
            .join(CatalogIssue, CatalogUpc.issue_id == CatalogIssue.id)
            .join(CatalogSeries, CatalogIssue.series_id == CatalogSeries.id)
            .where(CatalogUpc.normalized_upc == barcode)
        ).all()
        print(f"\nCatalogUpc exact match for {barcode}: {len(upc_rows)}")
        for upc, issue, series in upc_rows[:5]:
            fp = session.exec(
                select(func.count())
                .select_from(CatalogImageFingerprint)
                .where(CatalogImageFingerprint.issue_id == issue.id)
            ).one()
            imgs = session.exec(
                select(func.count()).select_from(CatalogImage).where(CatalogImage.issue_id == issue.id)
            ).one()
            print(
                f"  issue_id={issue.id} {series.name} #{issue.issue_number} "
                f"catalog_images={imgs} fingerprint_rows={fp}"
            )

        pub = session.exec(
            select(CatalogSeries, CatalogIssue, CatalogPublisher)
            .join(CatalogIssue, CatalogIssue.series_id == CatalogSeries.id)
            .join(CatalogPublisher, CatalogSeries.publisher_id == CatalogPublisher.id)
            .where(CatalogSeries.name.ilike(f"%{series_q}%"))  # type: ignore[attr-defined]
            .where(CatalogIssue.normalized_issue_number == issue_num.replace("#", ""))
        ).all()
        print(f"\nSeries match '{series_q}' #{issue_num}: {len(pub)} catalog issues")
        for series, issue, publisher in pub[:10]:
            fp = session.exec(
                select(func.count())
                .select_from(CatalogImageFingerprint)
                .where(CatalogImageFingerprint.issue_id == issue.id)
            ).one()
            imgs = session.exec(
                select(CatalogImage)
                .where(CatalogImage.issue_id == issue.id)
                .where(CatalogImage.image_type == "cover")
            ).all()
            ready = sum(1 for im in imgs if im.download_status == "ready" and im.local_path)
            print(
                f"  issue_id={issue.id} {publisher.name} | {series.name} #{issue.issue_number} "
                f"covers_ready={ready}/{len(imgs)} fingerprint_rows={fp}"
            )


if __name__ == "__main__":
    main()
