from __future__ import annotations

import json
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlmodel import Session, select

from app.models import ComicIssue, ComicTitle, MetadataAlias, Publisher, Variant
from app.services.metadata_enrichment import normalize_issue_number, normalize_publisher_name, normalize_series_title_with_aliases


@dataclass(frozen=True)
class CanonicalComicRow:
    canonical_comic_id: int
    publisher: str
    imprint: str | None
    title: str
    normalized_title: str
    issue_number: str
    normalized_issue_number: str
    volume: str | None
    publication_date: date | None
    variant_description: str | None
    upc: str | None
    legacy_aliases: tuple[str, ...]
    title_synonyms: tuple[str, ...]


@dataclass(frozen=True)
class CanonicalComicDatasetSnapshot:
    dataset_version: str
    rows: tuple[CanonicalComicRow, ...]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, date):
        return value.isoformat()
    return value


def _hash_payload(payload: Any) -> str:
    raw = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_text_key(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "")
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("/", " ")
    normalized = normalized.replace("-", " ")
    normalized = re.sub(r"(?<=[A-Za-z])1(?=[A-Za-z])", "i", normalized)
    normalized = re.sub(r"(?<=[A-Za-z])0(?=[A-Za-z])", "o", normalized)
    normalized = re.sub(r"[^A-Za-z0-9 ]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def _variant_description(variant: Variant | None) -> str | None:
    if variant is None:
        return None
    parts = [variant.cover_name, variant.printing, variant.ratio, variant.variant_type]
    rendered = " / ".join(part.strip() for part in parts if part and part.strip())
    return rendered or None


def _alias_map(session: Session, *, alias_type: str) -> dict[str, list[str]]:
    rows = session.exec(
        select(MetadataAlias)
        .where(MetadataAlias.alias_type == alias_type, MetadataAlias.is_active.is_(True))
        .order_by(MetadataAlias.canonical_value.asc(), MetadataAlias.alias_value.asc(), MetadataAlias.id.asc())
    ).all()
    out: dict[str, list[str]] = {}
    for row in rows:
        key = row.canonical_value.strip()
        alias = row.alias_value.strip()
        if not key or not alias:
            continue
        out.setdefault(key, [])
        if alias not in out[key]:
            out[key].append(alias)
    return out


def _row_signature(row: CanonicalComicRow) -> dict[str, Any]:
    return {
        "canonical_comic_id": row.canonical_comic_id,
        "publisher": row.publisher,
        "imprint": row.imprint,
        "title": row.title,
        "normalized_title": row.normalized_title,
        "issue_number": row.issue_number,
        "normalized_issue_number": row.normalized_issue_number,
        "volume": row.volume,
        "publication_date": row.publication_date.isoformat() if row.publication_date else None,
        "variant_description": row.variant_description,
        "upc": row.upc,
        "legacy_aliases": list(row.legacy_aliases),
        "title_synonyms": list(row.title_synonyms),
    }


def load_canonical_comic_dataset(session: Session) -> CanonicalComicDatasetSnapshot:
    title_aliases = _alias_map(session, alias_type="series")
    publisher_aliases = _alias_map(session, alias_type="publisher")
    issues = session.exec(select(ComicIssue).order_by(ComicIssue.id.asc())).all()
    titles = {row.id: row for row in session.exec(select(ComicTitle).order_by(ComicTitle.id.asc())).all() if row.id is not None}
    publishers = {row.id: row for row in session.exec(select(Publisher).order_by(Publisher.id.asc())).all() if row.id is not None}
    variants = session.exec(select(Variant).order_by(Variant.comic_issue_id.asc(), Variant.id.asc())).all()
    variant_by_issue: dict[int, Variant] = {}
    for row in variants:
        if row.comic_issue_id not in variant_by_issue:
            variant_by_issue[row.comic_issue_id] = row

    dataset_rows: list[CanonicalComicRow] = []
    for issue in issues:
        title = titles.get(issue.comic_title_id)
        if title is None:
            continue
        publisher = publishers.get(title.publisher_id)
        if publisher is None:
            continue
        canonical_title = normalize_series_title_with_aliases(title.name, session=session).canonical_value or title.name
        canonical_publisher = normalize_publisher_name(publisher.name, session=session).canonical_value or publisher.name
        normalized_title = _normalize_text_key(canonical_title)
        normalized_issue = normalize_issue_number(issue.issue_number).canonical_value or issue.issue_number
        dataset_rows.append(
            CanonicalComicRow(
                canonical_comic_id=int(issue.id or 0),
                publisher=canonical_publisher,
                imprint=None,
                title=canonical_title,
                normalized_title=normalized_title,
                issue_number=issue.issue_number,
                normalized_issue_number=normalized_issue,
                volume=None,
                publication_date=issue.release_date or issue.cover_date,
                variant_description=_variant_description(variant_by_issue.get(int(issue.id or 0))),
                upc=None,
                legacy_aliases=tuple(sorted(publisher_aliases.get(canonical_publisher, []))),
                title_synonyms=tuple(sorted(title_aliases.get(canonical_title, []))),
            )
        )

    ordered_rows = tuple(
        sorted(
            dataset_rows,
            key=lambda row: (
                row.publisher.lower(),
                row.title.lower(),
                row.normalized_issue_number.upper(),
                row.variant_description or "",
                row.canonical_comic_id,
            ),
        )
    )
    dataset_version = _hash_payload([_row_signature(row) for row in ordered_rows])
    return CanonicalComicDatasetSnapshot(dataset_version=dataset_version, rows=ordered_rows)


def query_canonical_comics(
    snapshot: CanonicalComicDatasetSnapshot,
    *,
    title_key: str | None = None,
    issue_key: str | None = None,
    publisher_key: str | None = None,
) -> list[CanonicalComicRow]:
    title_key = _normalize_text_key(title_key)
    issue_key = (issue_key or "").strip().upper()
    publisher_key = _normalize_text_key(publisher_key)
    rows: list[CanonicalComicRow] = []
    for row in snapshot.rows:
        title_match = not title_key or title_key in {row.normalized_title, *(_normalize_text_key(alias) for alias in row.title_synonyms)}
        issue_match = not issue_key or issue_key == row.normalized_issue_number.upper()
        publisher_terms = {row.publisher, *row.legacy_aliases}
        publisher_match = not publisher_key or publisher_key in {_normalize_text_key(value) for value in publisher_terms}
        if title_match or (issue_match and publisher_match):
            rows.append(row)
    return rows
