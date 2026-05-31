"""Live recommendation intelligence certification check (P51-05)."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlmodel import Session  # noqa: E402

from app.db.session import get_engine  # noqa: E402
from app.services.recommendation_intelligence_live_gates import assess_live_p51_04_output  # noqa: E402
from app.services.recommendation_intelligence_certification import get_recommendation_intelligence_certification  # noqa: E402
from app.services.recommendation_intelligence_health import get_recommendation_intelligence_health  # noqa: E402
from app.services.recommendation_intelligence_summary import get_recommendation_intelligence_summary  # noqa: E402
from app.services.recommendation_intelligence_validation import validate_recommendation_intelligence  # noqa: E402
from app.services.recommendation_quality_calibration import calibrate_recommendation_quality  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owner-user-id", type=int, default=40)
    args = parser.parse_args()
    owner_user_id = args.owner_user_id

    with Session(get_engine()) as session:
        validation = validate_recommendation_intelligence(session, owner_user_id=owner_user_id)
        health = get_recommendation_intelligence_health(session, owner_user_id=owner_user_id)
        calibration = calibrate_recommendation_quality(session, owner_user_id=owner_user_id)
        summary = get_recommendation_intelligence_summary(session, owner_user_id=owner_user_id)
        certification = get_recommendation_intelligence_certification(session, owner_user_id=owner_user_id)
        live = assess_live_p51_04_output(session, owner_user_id=owner_user_id)

    report = {
        "live_p51_04_output": {
            "live_output_ready": live.live_output_ready,
            "blocking_reasons": list(live.blocking_reasons),
            "latest_issue_score_count": live.latest_issue_score_count,
            "total_v2_score_rows": live.total_v2_score_rows,
            "completed_runs_with_scores": live.completed_runs_with_scores,
        },
        "validation": validation.model_dump(),
        "health": health.model_dump(),
        "calibration": calibration.model_dump(),
        "summary": summary.model_dump(),
        "certification": certification.model_dump(),
    }
    print(json.dumps(report, indent=2, default=str))
    return 0 if certification.platform_certified else 1


if __name__ == "__main__":
    sys.exit(main())
