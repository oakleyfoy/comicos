"""P104 cover hydration audit CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p97_bootstrap import bootstrap_api_path

bootstrap_api_path()

from sqlmodel import Session, select  # noqa: E402

from app.models.catalog_cover_assets import (  # noqa: E402
    CatalogCoverAsset,
    COVER_ASSET_STATUS_COMPLETE,
)
from app.services.p104_cover_hydration_service import asset_status_counts, verify_asset_files  # noqa: E402
from p97_db import get_p97_engine, resolve_p97_database_url  # noqa: E402

DEFAULT_OUT = Path("data/p104/cover_hydration_audit.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="P104 cover hydration audit")
    parser.add_argument("--sample", type=int, default=10)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    engine = get_p97_engine(resolve_p97_database_url(args.database_url))
    failures: list[str] = []
    with Session(engine) as session:
        counts = asset_status_counts(session)
        complete_rows = session.exec(
            select(CatalogCoverAsset)
            .where(CatalogCoverAsset.status == COVER_ASSET_STATUS_COMPLETE)
            .order_by(CatalogCoverAsset.id.desc())
            .limit(args.sample)
        ).all()
        samples: list[dict] = []
        for asset in complete_rows:
            files_ok, missing = verify_asset_files(asset)
            hashes_ok = bool(
                asset.perceptual_hash and asset.average_hash and asset.difference_hash and asset.color_histogram
            )
            ok = files_ok and hashes_ok
            if not ok:
                failures.append(
                    f"asset_id={asset.id} files_ok={files_ok} missing={missing} hashes_ok={hashes_ok}"
                )
            samples.append(
                {
                    "asset_id": asset.id,
                    "catalog_issue_id": asset.catalog_issue_id,
                    "source": asset.source,
                    "files_ok": files_ok,
                    "missing_paths": missing,
                    "hashes_ok": hashes_ok,
                    "pass": ok,
                }
            )

    payload = {
        "queue_counts": counts,
        "sample_size": len(samples),
        "sample_passed": sum(1 for s in samples if s["pass"]),
        "failures": failures,
        "samples": samples,
        "overall_pass": not failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if payload["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
