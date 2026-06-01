"""Compare tracemalloc delta for industry dashboard read vs refresh (local dev)."""
from __future__ import annotations

import sys
import tracemalloc
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import User
from app.services.industry_scanner_dashboard import build_industry_scanner_dashboard


def _measure(label: str, fn) -> float:
    tracemalloc.start()
    fn()
    current, _peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    mb = current / (1024 * 1024)
    print(f"{label}: traced {mb:.2f} MiB")
    return mb


def main() -> None:
    with Session(get_engine()) as session:
        user = session.exec(select(User).order_by(User.id.asc())).first()
        if user is None or user.id is None:
            print("No users in DB — skip memory measure (register locally first).")
            return
        owner_id = int(user.id)

        read_mb = _measure(
            "GET-equivalent refresh=false",
            lambda: build_industry_scanner_dashboard(session, owner_user_id=owner_id, refresh=False),
        )
        refresh_mb = _measure(
            "GET-equivalent refresh=true",
            lambda: build_industry_scanner_dashboard(session, owner_user_id=owner_id, refresh=True),
        )
        print(f"delta (refresh - read): {refresh_mb - read_mb:.2f} MiB")


if __name__ == "__main__":
    main()
