"""Audit stored cover-image fields for catalog and scan-backed sources."""

from __future__ import annotations

import os
import sys
from typing import Any

from sqlalchemy import func, or_
from sqlmodel import Session, select

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.db.session import get_engine
from app.models.asset_ledger import CoverImage, CoverImageDerivative
from app.models.external_catalog import ExternalCatalogIssue, ExternalCatalogVariant
from app.models.release_intelligence import ReleaseIssue, ReleaseVariant


def _sample_value(row: Any, field_name: str) -> str | None:
    value = getattr(row, field_name, None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _field_names(model: type[Any]) -> list[str]:
    explicit_fields = {
        "cover_image_url",
        "thumbnail_url",
        "high_resolution_image_url",
        "image_url",
        "storage_path",
    }
    return [
        name
        for name in model.model_fields
        if name in explicit_fields
    ]


def _scalar(value: Any) -> Any:
    if hasattr(value, "_mapping"):
        return value[0]
    if isinstance(value, tuple):
        return value[0]
    return value


def _print_model_summary(session: Session, model: type[Any], *, label: str, sample_limit: int = 3) -> None:
    print(f"\n[{label}]")
    image_fields = _field_names(model)
    if not image_fields:
        print("  image_like_fields: none")
        return

    print(f"  image_like_fields: {', '.join(image_fields)}")
    total_rows = _scalar(session.exec(select(func.count()).select_from(model)).one())
    print(f"  rows: {int(total_rows or 0)}")

    for field_name in image_fields:
        field = getattr(model, field_name)
        count = _scalar(
            session.exec(
            select(func.count())
            .select_from(model)
            .where(field.is_not(None))  # type: ignore[attr-defined]
            .where(field != "")
            ).one()
        )
        print(f"  {field_name}: {int(count or 0)}")

    sample_filters = [
        getattr(model, field_name).is_not(None)  # type: ignore[attr-defined]
        for field_name in image_fields
    ]
    rows = session.exec(select(model).where(or_(*sample_filters)).limit(sample_limit)).all()
    if not rows:
        print("  samples: none")
        return

    print("  samples:")
    for row in rows:
        publisher = _sample_value(row, "publisher")
        title = _sample_value(row, "series_name") or _sample_value(row, "title") or _sample_value(row, "variant_name")
        issue = _sample_value(row, "issue_number")
        preferred_fields = [
            "cover_image_url",
            "thumbnail_url",
            "high_resolution_image_url",
            "image_url",
            "storage_path",
        ]
        first_image = next(
            (
                _sample_value(row, field_name)
                for field_name in preferred_fields + image_fields
                if field_name in image_fields and _sample_value(row, field_name)
            ),
            None,
        )
        bits = [
            f"id={getattr(row, 'id', None)}",
            f"publisher={publisher or '—'}",
            f"title={title or '—'}",
            f"issue={issue or '—'}",
            f"image={first_image or '—'}",
        ]
        print(f"    - {' | '.join(bits)}")


def main() -> None:
    engine = get_engine()
    with Session(engine) as session:
        _print_model_summary(session, ReleaseIssue, label="ReleaseIssue")
        _print_model_summary(session, ReleaseVariant, label="ReleaseVariant")
        _print_model_summary(session, ExternalCatalogIssue, label="ExternalCatalogIssue")
        _print_model_summary(session, ExternalCatalogVariant, label="ExternalCatalogVariant")
        _print_model_summary(session, CoverImage, label="CoverImage")
        _print_model_summary(session, CoverImageDerivative, label="CoverImageDerivative")


if __name__ == "__main__":
    main()
