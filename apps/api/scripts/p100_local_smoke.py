"""P100 local API smoke (session → upload → detections)."""

from __future__ import annotations

import io
import json
import sys
import uuid

import httpx
from PIL import Image

BASE = "http://127.0.0.1:8000"
EMAIL = f"p100-smoke-{uuid.uuid4().hex[:8]}@example.com"
PASSWORD = "P100SmokeTest!234"


def main() -> int:
    with httpx.Client(base_url=BASE, timeout=120.0) as client:
        reg = client.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
        if reg.status_code not in (200, 201, 400):
            print("register failed", reg.status_code, reg.text)
            return 1
        login = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
        if login.status_code != 200:
            print("login failed", login.status_code, login.text)
            return 1
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        created = client.post("/api/v1/photo-import/sessions", json={"source_device": "smoke"}, headers=headers)
        print("session", created.status_code)
        if created.status_code != 200:
            print(created.text)
            return 1
        sess = created.json()
        tok = sess["session_token"]
        print("token", tok[:12] + "...", "status", sess["status"])

        beat = client.post(f"/api/v1/photo-import/sessions/{tok}/heartbeat", json={"source_device": "mobile-smoke"})
        print("heartbeat", beat.status_code, beat.json().get("status"))

        img = Image.new("RGB", (400, 600), color=(180, 40, 40))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        up = client.post(
            f"/api/v1/photo-import/sessions/{tok}/images",
            files=[("images", ("comic.jpg", buf.getvalue(), "image/jpeg"))],
        )
        print("upload", up.status_code, up.text[:200])
        if up.status_code != 200:
            return 1

        got = client.get(f"/api/v1/photo-import/sessions/{tok}", headers=headers)
        print("counts", got.json().get("uploaded_photo_count"), got.json().get("detected_book_count"))

        dets = client.get(f"/api/v1/photo-import/sessions/{tok}/detections", headers=headers)
        print("detections", dets.status_code, len(dets.json()))
        if dets.status_code != 200 or not dets.json():
            return 1
        det = dets.json()[0]
        print("detection", det.get("id"), "candidates", det.get("candidate_count"), "best", det.get("best_candidate"))

        if det.get("selected_catalog_issue_id"):
            confirm = client.post(
                f"/api/v1/photo-import/sessions/{tok}/confirm",
                headers=headers,
                json={
                    "items": [
                        {
                            "detected_book_id": det["id"],
                            "catalog_issue_id": det["selected_catalog_issue_id"],
                            "quantity": 1,
                        }
                    ]
                },
            )
            print("confirm", confirm.status_code, confirm.text[:200])

        print(json.dumps({"ok": True, "email": EMAIL}, indent=2))
        return 0


if __name__ == "__main__":
    sys.exit(main())
