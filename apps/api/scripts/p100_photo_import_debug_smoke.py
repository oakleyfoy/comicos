"""P100-12 local debug smoke: upload image and print detection/candidate diagnostics."""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
import uuid
from pathlib import Path

import httpx
from PIL import Image

BASE = "http://127.0.0.1:8000"


def _register_login(client: httpx.Client) -> str:
    email = f"p100-debug-{uuid.uuid4().hex[:8]}@example.com"
    password = "P100DebugTest!234"
    reg = client.post("/auth/register", json={"email": email, "password": password})
    if reg.status_code not in (200, 201, 400):
        raise RuntimeError(f"register failed: {reg.status_code} {reg.text}")
    login = client.post("/auth/login", json={"email": email, "password": password})
    if login.status_code != 200:
        raise RuntimeError(f"login failed: {login.status_code} {login.text}")
    return login.json()["access_token"]


def _load_image_bytes(path: Path | None) -> tuple[bytes, str]:
    if path and path.is_file():
        return path.read_bytes(), path.name
    img = Image.new("RGB", (800, 600), color=(120, 80, 40))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue(), "synthetic.jpg"


def main() -> int:
    parser = argparse.ArgumentParser(description="P100 photo import debug smoke")
    parser.add_argument("--image", type=str, default="", help="Path to test photo")
    parser.add_argument("--database-url", type=str, default="", help="Optional DATABASE_URL override for local runs")
    parser.add_argument("--base-url", type=str, default=BASE, help="API base URL")
    args = parser.parse_args()

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    image_path = Path(args.image) if args.image else None
    image_bytes, filename = _load_image_bytes(image_path)

    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=180.0) as client:
        token = _register_login(client)
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post("/api/v1/photo-import/sessions", json={"source_device": "debug-smoke"}, headers=headers)
        if created.status_code != 200:
            print("session create failed", created.status_code, created.text)
            return 1
        sess = created.json()
        session_token = sess["session_token"]
        print("session", session_token[:16] + "...", sess["status"])

        up = client.post(
            f"/api/v1/photo-import/sessions/{session_token}/images",
            files=[("images", (filename, image_bytes, "image/jpeg"))],
        )
        if up.status_code != 200:
            print("upload failed", up.status_code, up.text)
            return 1
        print("upload ok", up.json()[0]["status"])

        for _ in range(30):
            dets = client.get(f"/api/v1/photo-import/sessions/{session_token}/detections", headers=headers)
            if dets.status_code == 200 and dets.json():
                break
            time.sleep(1)
        else:
            print("timeout waiting for detections")
            return 1

        detections = dets.json()
        print(f"detections: {len(detections)}")
        failed = False
        for det in detections:
            print("\n--- detection", det["id"], "---")
            print(
                "AI:",
                det.get("ai_publisher"),
                det.get("ai_series"),
                "#",
                det.get("ai_issue_number") or det.get("ai_visible_issue_text"),
                f"conf={det.get('ai_confidence')}",
            )
            if det.get("ai_uncertainty_reason"):
                print("uncertainty:", det["ai_uncertainty_reason"])

            dbg = client.get(f"/api/v1/photo-import/detections/{det['id']}/candidates", headers=headers)
            if dbg.status_code != 200:
                print("candidates debug failed", dbg.status_code, dbg.text)
                failed = True
                continue
            payload = dbg.json()
            cands = payload.get("candidates") or []
            debug = payload.get("debug") or {}
            print("candidate_count", debug.get("candidate_count"), "terms", debug.get("search_terms_used"))
            for c in cands[:3]:
                print(
                    f"  rank {c['rank']}: {c['publisher']} {c['series']} #{c['issue_number']} "
                    f"score={c['match_score']} on={c.get('matched_on')} reason={c.get('match_reason')}"
                )
            series_text = (det.get("ai_series") or det.get("ai_visible_title_text") or "").strip()
            if series_text and len(cands) == 0:
                print("FAIL: series guess present but zero candidates")
                failed = True

        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
