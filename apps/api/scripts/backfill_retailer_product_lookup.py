"""Backfill retailer product lookup data onto draft imports."""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _normalize_database_url_env() -> None:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgresql://"):
        os.environ["DATABASE_URL"] = "postgresql+pg8000://" + url[len("postgresql://") :]


_normalize_database_url_env()

from sqlmodel import Session, select

from app.db.session import get_engine
from app.models import DraftImport, User
from app.schemas.ai import ParseOrderResponse
from app.services.retailer_lookup import enrich_item_with_midtown_lookup


def _filtered_drafts(session: Session, *, email: str | None, draft_id: int | None, limit: int) -> list[DraftImport]:
    stmt = select(DraftImport).order_by(DraftImport.created_at.desc(), DraftImport.id.desc())
    if draft_id is not None:
        stmt = stmt.where(DraftImport.id == draft_id)
    elif email:
        user = session.exec(select(User).where(User.email == email)).first()
        if user is None or user.id is None:
            raise SystemExit(f"User not found: {email}")
        stmt = stmt.where(DraftImport.user_id == user.id)
    return session.exec(stmt.limit(max(1, limit))).all()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email")
    parser.add_argument("--draft-id", type=int)
    parser.add_argument("--retailer", default="midtown")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    if args.retailer.casefold() != "midtown":
        raise SystemExit("Only --retailer midtown is currently supported.")

    engine = get_engine()
    stats = Counter()
    examples: list[str] = []

    with Session(engine) as session:
        drafts = _filtered_drafts(session, email=args.email, draft_id=args.draft_id, limit=args.limit)
        for draft in drafts:
            parsed = ParseOrderResponse.model_validate(draft.parsed_payload_json)
            changed = False
            for index, item in enumerate(parsed.items):
                item_dict = item.model_dump(mode="json")
                if parsed.retailer:
                    item_dict["retailer"] = parsed.retailer
                stats["scanned"] += 1
                updates = enrich_item_with_midtown_lookup(item_dict, force=args.force)
                status = updates.get("retailer_lookup_status")
                enrichment = updates.get("retailer_lookup_enrichment") or {}
                selected = enrichment.get("selected_candidate") if isinstance(enrichment, dict) else None
                if status == "matched":
                    stats["matched"] += 1
                elif status == "possible_match":
                    stats["possible_match"] += 1
                else:
                    stats["no_match"] += 1

                if updates and any(item_dict.get(key) != value for key, value in updates.items()):
                    changed = True
                    parsed.items[index] = item.model_copy(update=updates)
                if isinstance(selected, dict) and len(examples) < 10:
                    examples.append(
                        " | ".join(
                            [
                                draft.raw_text[:50].replace("\n", " "),
                                str(selected.get("product_title") or ""),
                                str(selected.get("product_url") or ""),
                                str(selected.get("image_url") or ""),
                                str(enrichment.get("score") or ""),
                            ]
                        )
                    )

            if changed:
                stats["updated"] += 1
                if not args.dry_run:
                    draft.parsed_payload_json = parsed.model_dump(mode="json")
                    session.add(draft)
        if not args.dry_run:
            session.commit()

    print(f"scanned={stats['scanned']} attempted_lookup={stats['scanned']} matched={stats['matched']} possible_match={stats['possible_match']} no_match={stats['no_match']} updated={stats['updated']} errors={stats['errors']}")
    if examples:
        print("examples:")
        for example in examples:
            print(f"  - {example}")


if __name__ == "__main__":
    main()
