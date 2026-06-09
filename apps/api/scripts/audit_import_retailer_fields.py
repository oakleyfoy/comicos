"""Audit retailer fields stored on draft import payloads."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

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


def _bool(value: object) -> str:
    return "yes" if value else "no"


def _item_value(item, key: str) -> str:
    value = item.get(key) if isinstance(item, dict) else getattr(item, key, None)
    if isinstance(value, str):
        return value.strip()
    return "" if value is None else str(value)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    engine = get_engine()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == args.email)).first()
        if user is None or user.id is None:
            raise SystemExit(f"User not found: {args.email}")

        drafts = (
            session.exec(
                select(DraftImport)
                .where(DraftImport.user_id == user.id)
                .order_by(DraftImport.created_at.desc(), DraftImport.id.desc())
                .limit(max(1, args.limit))
            )
            .all()
        )

        print(f"email={args.email} user_id={user.id} drafts={len(drafts)}")
        for draft in drafts:
            parsed = ParseOrderResponse.model_validate(draft.parsed_payload_json)
            print(f"\ndraft_id={draft.id} status={draft.status} retailer={parsed.retailer} order_date={parsed.order_date}")
            for index, item in enumerate(parsed.items):
                print(
                    "  line={line} title={title} retailer={retailer} product_url={product_url} image_url={image_url} "
                    "sku={sku} cover_name={cover_name} issue_number={issue_number} price={price} "
                    "lookup_status={lookup_status} lookup_score={lookup_score} "
                    "raw_title={raw_title} raw_text={raw_text} lookup={lookup}".format(
                        line=index,
                        title=_item_value(item, "title"),
                        retailer=_item_value(item, "retailer") or _item_value(item, "retailer_source"),
                        product_url=_item_value(item, "retailer_product_url"),
                        image_url=_item_value(item, "retailer_cover_url") or _item_value(item, "cover_image_url"),
                        sku=_item_value(item, "retailer_sku"),
                        cover_name=_item_value(item, "cover_name"),
                        issue_number=_item_value(item, "issue_number"),
                        price=_item_value(item, "raw_item_price"),
                        lookup_status=_item_value(item, "retailer_lookup_status"),
                        lookup_score=_item_value(item, "retailer_lookup_score"),
                        raw_title=_item_value(item, "raw_title"),
                        raw_text=(draft.raw_text[:80] + "…") if draft.raw_text and len(draft.raw_text) > 80 else draft.raw_text,
                        lookup="yes" if _item_value(item, "retailer_lookup_enrichment") else "no",
                    )
                )


if __name__ == "__main__":
    main()
