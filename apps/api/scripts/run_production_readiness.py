"""Run P57-06 production readiness check (HTTP against local API or in-process TestClient)."""

from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import urllib.error
import urllib.request

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.security import create_access_token, token_expiration_utc
from app.db.session import get_engine
from app.main import app
from app.models import User
from app.security.session_manager import build_device_label, create_session, detect_device_type


def _issue_token(session: Session, user: User) -> str:
    assert user.id is not None
    token = create_access_token(subject=str(user.id))
    create_session(
        session,
        user_id=int(user.id),
        raw_token=token,
        expires_at=token_expiration_utc(token),
        device_label=build_device_label("run-production-readiness"),
        device_type=detect_device_type("run-production-readiness"),
        ip_address="127.0.0.1",
        user_agent="run-production-readiness",
    )
    return token


def _post_live(base_url: str, token: str) -> tuple[int, dict]:
    url = base_url.rstrip("/") + "/api/v1/production-readiness/run"
    req = urllib.request.Request(
        url,
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return resp.status, json.loads(resp.read().decode())


def main() -> int:
    parser = argparse.ArgumentParser(description="POST /api/v1/production-readiness/run")
    parser.add_argument("--owner-user-id", type=int, default=40)
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="Live API base URL; use --in-process to skip HTTP",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Call route via TestClient (current code; use if server is not restarted)",
    )
    args = parser.parse_args()

    with Session(get_engine()) as session:
        user = session.get(User, args.owner_user_id)
        if user is None:
            print(f"User {args.owner_user_id} not found", file=sys.stderr)
            return 2
        token = _issue_token(session, user)
        session.commit()
        owner_email = user.email

    if args.in_process:
        client = TestClient(app)
        resp = client.post(
            "/api/v1/production-readiness/run",
            headers={"Authorization": f"Bearer {token}"},
        )
        status = resp.status_code
        if status != 200:
            print(resp.text, file=sys.stderr)
            return 1
        body = resp.json()
    else:
        try:
            status, body = _post_live(args.base_url, token)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()
            if exc.code == 404 and "Not Found" in detail:
                print(
                    "Live API returned 404 (route missing). Restart uvicorn from this repo or pass --in-process.",
                    file=sys.stderr,
                )
            print(f"HTTP {exc.code}: {detail}", file=sys.stderr)
            return 1
        if status != 200:
            print(json.dumps(body, indent=2), file=sys.stderr)
            return 1

    validation = body["data"]["validation"]
    run = validation["run"]
    print(f"owner_email={owner_email}")
    print(f"readiness_score={run['readiness_score']}")
    print(f"go_live_result={run['go_live_result']}")
    print(f"health_status={run['health_status']}")
    report = run.get("report") or {}
    print("domain_scores=" + json.dumps(report.get("domain_scores"), indent=2))
    recs = validation.get("recommendations") or []
    print(f"recommendations_count={len(recs)}")
    for row in recs[:10]:
        title = row.get("title") or row.get("code") or "?"
        msg = (row.get("message") or "")[:160]
        print(f"  - {title}: {msg}")
    return 0 if run["go_live_result"] == "GO_LIVE_APPROVED" else 1


if __name__ == "__main__":
    sys.exit(main())
