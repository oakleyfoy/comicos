"""Check Lunar monthly imports and optionally import 0426/0526 CSV files (no scoring changes)."""



from __future__ import annotations



import argparse

import json

import os

import re

import subprocess

import sys

from pathlib import Path



ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))



# PARTIAL = normalize had row-level skips; catalog import + refresh still completed.

FINISHED_LUNAR_STATUSES = frozenset({"COMPLETED", "PARTIAL"})



IMPORT_MONTHS = ("2026-04", "2026-05")



TARGETS = (

    {

        "needle_title": "YOUNGBLOOD #1 (2025) TREASURY EDITION",

        "series": "youngblood",

        "title_fragments": ("treasury", "youngblood"),

    },

    {

        "needle_title": "BADROCK #1 CVR A SETH DAMOOSE",

        "series": "badrock",

        "title_fragments": ("badrock", "cvr a", "damoose"),

    },

    {

        "needle_title": "BADROCK #1 CVR B ROB LIEFELD VAR",

        "series": "badrock",

        "title_fragments": ("badrock", "cvr b", "liefeld"),

    },

)



MONTH_FILES = {

    "2026-04": "Lunar_Product_Data_0426.csv",

    "2026-05": "Lunar_Product_Data_0526.csv",

    "2026-06": "Lunar_Product_Data_0626.csv",

}





def _db_host(url: str) -> str:

    m = re.search(r"@([^:/]+)", url)

    return m.group(1).lower() if m else ""





def _find_csv(csv_dir: str | None, file_name: str) -> Path | None:

    candidates: list[Path] = []

    if csv_dir:

        candidates.append(Path(csv_dir) / file_name)

    candidates.extend(

        [

            Path(file_name),

            Path.home() / "Downloads" / file_name,

            Path(ROOT) / "data" / "lunar" / file_name,

        ]

    )

    for c in candidates:

        if c.is_file():

            return c

    return None





def _run_matches_period(run: object, period: str) -> bool:

    file_period = (getattr(run, "file_period", None) or "").strip()

    file_name = getattr(run, "file_name", None) or ""

    if file_period == period:

        return True

    if MONTH_FILES.get(period, "") in file_name:

        return True

    if len(period) >= 7:

        token = f"{period[5:7]}{period[2:4]}"

        if token in file_name:

            return True

    return False





def _period_has_finished_import(period_runs: list) -> bool:

    return any((r.status or "") in FINISHED_LUNAR_STATUSES for r in period_runs)





def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument("--email", required=True)

    parser.add_argument("--production", action="store_true")

    parser.add_argument(

        "--import-missing",

        action="store_true",

        help="Import months with no finished run (COMPLETED or PARTIAL)",

    )

    parser.add_argument(

        "--force",

        action="store_true",

        help="Re-import months even when a finished PARTIAL/COMPLETED run exists",

    )

    parser.add_argument("--csv-dir", default=None, help="Directory containing Lunar_Product_Data_*.csv")

    parser.add_argument("--diagnose", action="store_true", help="Run signal bucket diagnostics after import")

    args = parser.parse_args()



    database_url = os.environ.get("DATABASE_URL", "").strip()

    if not database_url:

        print("error: DATABASE_URL required", file=sys.stderr)

        return 1

    if args.production and _db_host(database_url) in {"localhost", "127.0.0.1"}:

        print("error: production mode requires non-localhost DATABASE_URL", file=sys.stderr)

        return 1



    if ROOT not in sys.path:

        sys.path.insert(0, ROOT)

    scripts_dir = os.path.join(ROOT, "scripts")

    if scripts_dir not in sys.path:

        sys.path.insert(0, scripts_dir)



    from sqlalchemy import func

    from sqlmodel import Session, select



    from app.db.session import get_engine

    from app.models.lunar_feed import LunarFeedRun

    from app.models.release_intelligence import ReleaseIssue, ReleaseSeries, ReleaseVariant

    from app.services.lunar_feed_import import import_lunar_csv_bytes

    from owner_lookup import resolve_owner_user_id



    report: dict = {"lunar_runs_by_period": [], "catalog_matches": [], "imports": []}



    with Session(get_engine()) as session:

        owner_user_id = resolve_owner_user_id(session, args.email)



        runs = list(

            session.exec(

                select(LunarFeedRun)

                .where(LunarFeedRun.owner_user_id == owner_user_id)

                .order_by(LunarFeedRun.created_at.desc())

            ).all()

        )

        for period in ("2026-04", "2026-05", "2026-06"):

            period_runs = [r for r in runs if _run_matches_period(r, period)]

            finished = [r for r in period_runs if (r.status or "") in FINISHED_LUNAR_STATUSES]

            report["lunar_runs_by_period"].append(

                {

                    "file_period": period,

                    "run_count": len(period_runs),

                    "finished_runs": len(finished),

                    "completed_runs": sum(1 for r in period_runs if r.status == "COMPLETED"),

                    "partial_runs": sum(1 for r in period_runs if r.status == "PARTIAL"),

                    "month_coverage_satisfied": len(finished) > 0,

                    "latest": [

                        {

                            "id": r.id,

                            "file_name": r.file_name,

                            "file_period": r.file_period,

                            "status": r.status,

                            "records_processed": r.records_processed,

                            "created_at": r.created_at.isoformat() if r.created_at else None,

                        }

                        for r in period_runs[:3]

                    ],

                }

            )



        for target in TARGETS:

            frags = target["title_fragments"]

            stmt = (

                select(ReleaseIssue, ReleaseSeries)

                .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)

                .where(ReleaseIssue.owner_user_id == owner_user_id)

                .where(func.lower(ReleaseSeries.series_name).contains(target["series"]))

            )

            hits = []

            for issue, series in session.exec(stmt).all():

                title_l = (issue.title or "").lower()

                if all(f in title_l or f in (series.series_name or "").lower() for f in frags[:2]):

                    variants = list(

                        session.exec(

                            select(ReleaseVariant).where(ReleaseVariant.issue_id == issue.id)

                        ).all()

                    )

                    hits.append(

                        {

                            "issue_id": issue.id,

                            "series_name": series.series_name,

                            "issue_number": issue.issue_number,

                            "issue_title": issue.title,

                            "release_uuid": issue.release_uuid,

                            "foc_date": issue.foc_date.isoformat() if issue.foc_date else None,

                            "variant_count": len(variants),

                            "variant_names": [v.variant_name for v in variants[:8]],

                        }

                    )

            report["catalog_matches"].append(

                {"target": target["needle_title"], "found_count": len(hits), "rows": hits[:10]}

            )



        if args.import_missing:

            for period in IMPORT_MONTHS:

                fname = MONTH_FILES[period]

                period_info = next(x for x in report["lunar_runs_by_period"] if x["file_period"] == period)

                period_runs = [r for r in runs if _run_matches_period(r, period)]

                if _period_has_finished_import(period_runs) and not args.force:

                    latest_status = period_runs[0].status if period_runs else None

                    report["imports"].append(

                        {

                            "period": period,

                            "skipped": True,

                            "reason": (

                                f"Month already has finished import (status={latest_status}); "

                                "use --force to re-import"

                            ),

                        }

                    )

                    continue

                csv_path = _find_csv(args.csv_dir, fname)

                if csv_path is None:

                    report["imports"].append(

                        {"period": period, "skipped": True, "reason": f"CSV not found: {fname}"}

                    )

                    continue

                content = csv_path.read_bytes()

                summary = import_lunar_csv_bytes(

                    session,

                    owner_user_id=owner_user_id,

                    file_name=csv_path.name,

                    content_bytes=content,

                    file_period=period,

                    source_type="UPLOAD",

                    source_url=f"file://{csv_path}",

                )

                report["imports"].append(

                    {

                        "period": period,

                        "file": str(csv_path),

                        "status": summary.status,

                        "records_processed": summary.records_processed,

                        "errors": len(summary.errors or []),

                        "forced": bool(args.force),

                    }

                )



            session.expire_all()

            report["catalog_matches_after_import"] = []

            for target in TARGETS:

                frags = target["title_fragments"]

                stmt = (

                    select(ReleaseIssue, ReleaseSeries)

                    .join(ReleaseSeries, ReleaseIssue.series_id == ReleaseSeries.id)

                    .where(ReleaseIssue.owner_user_id == owner_user_id)

                    .where(func.lower(ReleaseSeries.series_name).contains(target["series"]))

                )

                count = 0

                for issue, series in session.exec(stmt).all():

                    title_l = (issue.title or "").lower()

                    if all(f in title_l or f in (series.series_name or "").lower() for f in frags[:2]):

                        count += 1

                report["catalog_matches_after_import"].append(

                    {"target": target["needle_title"], "found_count": count}

                )



    print(json.dumps(report, indent=2))



    if args.diagnose:

        base_cmd = [sys.executable, os.path.join(ROOT, "scripts", "diagnose_recommendation_signal_bucket.py")]

        if args.production:

            base_cmd.append("--production")

        diag = subprocess.run(

            [*base_cmd, "--email", args.email, "--title", "Youngblood"],

            capture_output=True,

            text=True,

            env=os.environ.copy(),

            cwd=ROOT,

        )

        bad = subprocess.run(

            [*base_cmd, "--email", args.email, "--title", "Badrock"],

            capture_output=True,

            text=True,

            env=os.environ.copy(),

            cwd=ROOT,

        )

        print("\n--- diagnose Youngblood ---\n", diag.stdout or diag.stderr)

        print("\n--- diagnose Badrock ---\n", bad.stdout or bad.stderr)



    return 0





if __name__ == "__main__":

    raise SystemExit(main())


