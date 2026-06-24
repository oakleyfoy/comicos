"""Backfill ``catalog_upc`` from a Grand Comics Database (GCD) data dump.

ComicVine does not expose barcodes, but GCD records the printed UPC/EAN on
``gcd_issue.barcode``. This service reads a GCD dump (SQLite file or any SQLAlchemy
URL), maps each barcoded GCD issue to a local ComicOS catalog issue by
publisher/series/issue-number/year, validates the barcode with
:mod:`app.services.barcode_validation_service`, and reports exactly what it would
insert. Dry-run first; ``write=True`` only inserts brand-new ``catalog_upc`` rows.

Safety rules (never weaken existing data):
* User-confirmed ``comic_issue_barcodes`` always win — a barcode already learned from a
  real scan is skipped (never overwritten by GCD).
* An existing ``catalog_upc`` row is never overwritten. Only new barcodes are inserted.
* Mismatched publisher/issue/era are rejected by the shared validation rules.

GCD dumps: https://www.comics.org/download/ (members). Load the dump into SQLite/Postgres
and point ``--gcd-db`` at it. Expected tables: ``gcd_issue`` (number, barcode, key_date,
series_id), ``gcd_series`` (name, year_began, publisher_id), ``gcd_publisher`` (name).
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.models.catalog_master import CatalogIssue, CatalogPublisher, CatalogSeries, CatalogUpc, CatalogVariant
from app.models.intake_queue import ComicIssueBarcode
from app.services.barcode_validation_service import validate_barcode_catalog_match
from app.services.catalog_ingestion_service import (
    normalize_issue_number,
    normalize_series_name,
    normalize_upc,
    series_names_compatible,
    upsert_upc,
)

logger = logging.getLogger(__name__)

FULL_BARCODE_MIN_LEN = 17
MAX_SAMPLES = 40
SAVE_EVERY = 5000
GCD_SOURCE = "GCD"

# Pull digit runs out of a free-text barcode cell (GCD may store "76194134192703921",
# "7 61941 34192 7 03921", "UPC: ...", or several barcodes split by ; or ,).
_DIGIT_RUN = re.compile(r"\d[\d\s-]{6,}\d")


def gcd_engine_from(target: str) -> Engine:
    """Accept a SQLAlchemy URL or a bare file path (treated as SQLite)."""
    if "://" in target:
        return create_engine(target)
    return create_engine(f"sqlite:///{Path(target).as_posix()}")


def extract_barcodes(raw: str | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for chunk in re.split(r"[;,]", str(raw)):
        for run in _DIGIT_RUN.findall(chunk):
            digits = normalize_upc(run)
            if len(digits) >= 8 and digits not in seen:
                seen.add(digits)
                out.append(digits)
    return out


def _year_from_key_date(key_date: str | None, year_began: Any) -> int | None:
    text_val = str(key_date or "").strip()
    if len(text_val) >= 4 and text_val[:4].isdigit():
        year = int(text_val[:4])
        if 1900 <= year <= 2100:
            return year
    try:
        yb = int(year_began)
        if 1900 <= yb <= 2100:
            return yb
    except (TypeError, ValueError):
        pass
    return None


@dataclass
class LocalIssueRef:
    issue_id: int
    publisher: str
    series: str
    issue_number: str
    year: int | None


@dataclass
class _Bucket:
    with_barcode: int = 0
    matched: int = 0
    projected_inserts: int = 0
    conflicts: int = 0
    rejected: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "with_barcode": self.with_barcode,
            "matched": self.matched,
            "projected_inserts": self.projected_inserts,
            "conflicts": self.conflicts,
            "rejected": self.rejected,
        }


@dataclass
class GcdBackfillStats:
    gcd_total_issues: int = 0
    rows_checked: int = 0           # GCD rows with a non-empty barcode field
    rows_with_barcode: int = 0      # rows yielding >=1 usable digit barcode
    matched_local_issues: int = 0   # rows matched to a local issue
    unmatched_rows: int = 0
    projected_inserts: int = 0
    duplicate_conflicts: int = 0
    rejected_validation: int = 0
    skipped_learned: int = 0        # barcode already user-confirmed -> left untouched
    written: int = 0
    by_publisher: dict[str, _Bucket] = field(default_factory=lambda: defaultdict(_Bucket))
    by_year: dict[str, _Bucket] = field(default_factory=lambda: defaultdict(_Bucket))
    samples: list[dict[str, Any]] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k not in ("by_publisher", "by_year", "samples")}
        d["by_publisher"] = {k: v.as_dict() for k, v in self.by_publisher.items()}
        d["by_year"] = {k: v.as_dict() for k, v in self.by_year.items()}
        d["samples"] = self.samples
        return d

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GcdBackfillStats":
        stats = cls()
        for key, value in data.items():
            if key in ("by_publisher", "by_year"):
                target = stats.by_publisher if key == "by_publisher" else stats.by_year
                for name, bucket in (value or {}).items():
                    target[name] = _Bucket(**bucket)
            elif key == "samples":
                stats.samples = list(value or [])
            elif hasattr(stats, key):
                setattr(stats, key, value)
        return stats


@dataclass
class _Resume:
    offset: int
    stats: GcdBackfillStats

    @classmethod
    def load(cls, path: Path | None) -> "_Resume":
        if path is not None and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return cls(offset=int(data.get("offset", 0)), stats=GcdBackfillStats.from_json(data.get("stats", {})))
            except Exception:
                logger.warning("GCD resume file unreadable; starting fresh: %s", path, exc_info=True)
        return cls(offset=0, stats=GcdBackfillStats())

    def save(self, path: Path | None) -> None:
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"offset": self.offset, "stats": self.stats.to_json()}, indent=2), encoding="utf-8")


def build_local_index(session: Session) -> dict[tuple[str, str], list[LocalIssueRef]]:
    """(normalized_series, normalized_issue_number) -> local issues, for fast GCD matching."""
    pubs = {int(pid): name for pid, name in session.exec(select(CatalogPublisher.id, CatalogPublisher.name)).all() if pid is not None}
    series_rows = session.exec(select(CatalogSeries.id, CatalogSeries.name, CatalogSeries.start_year)).all()
    series_meta = {int(sid): (name, start_year) for sid, name, start_year in series_rows if sid is not None}

    index: dict[tuple[str, str], list[LocalIssueRef]] = defaultdict(list)
    rows = session.exec(
        select(
            CatalogIssue.id,
            CatalogIssue.series_id,
            CatalogIssue.publisher_id,
            CatalogIssue.issue_number,
            CatalogIssue.normalized_issue_number,
            CatalogIssue.cover_date,
        )
    ).all()
    for issue_id, series_id, publisher_id, issue_number, norm_issue, cover_date in rows:
        if issue_id is None or series_id is None:
            continue
        series_name, start_year = series_meta.get(int(series_id), ("", None))
        norm_series = normalize_series_name(series_name)
        if not norm_series:
            continue
        year = cover_date.year if cover_date is not None else (int(start_year) if start_year else None)
        index[(norm_series, norm_issue)].append(
            LocalIssueRef(
                issue_id=int(issue_id),
                publisher=pubs.get(int(publisher_id), "") if publisher_id else "",
                series=series_name,
                issue_number=issue_number,
                year=year,
            )
        )
    return index


def _match_local(
    index: dict[tuple[str, str], list[LocalIssueRef]],
    *,
    gcd_publisher: str,
    gcd_series: str,
    gcd_issue_number: str,
    gcd_year: int | None,
) -> LocalIssueRef | None:
    norm_series = normalize_series_name(gcd_series)
    norm_issue = normalize_issue_number(gcd_issue_number)
    if not norm_series or not norm_issue:
        return None
    candidates = list(index.get((norm_series, norm_issue), ()))
    if not candidates:
        # Compatible-name fallback (e.g. "Superman" vs "Superman (2016)") within same issue number.
        for (cand_series, cand_issue), refs in index.items():
            if cand_issue == norm_issue and series_names_compatible(norm_series, cand_series):
                candidates.extend(refs)
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    pub_norm = normalize_series_name(gcd_publisher)

    def score(ref: LocalIssueRef) -> tuple[int, int]:
        pub_ok = 1 if pub_norm and normalize_series_name(ref.publisher) == pub_norm else 0
        if gcd_year is not None and ref.year is not None:
            year_pen = -abs(ref.year - gcd_year)
        else:
            year_pen = -999
        return (pub_ok, year_pen)

    ranked = sorted(candidates, key=score, reverse=True)
    best, second = ranked[0], ranked[1]
    if score(best) == score(second):
        return None  # ambiguous: refuse rather than guess
    return best


def _iter_gcd_rows(gcd: Engine, *, offset: int, batch: int = 5000) -> Iterator[list[dict[str, Any]]]:
    query = text(
        """
        SELECT i.id AS issue_id, i.number AS number, i.barcode AS barcode, i.key_date AS key_date,
               s.name AS series_name, s.year_began AS year_began, p.name AS publisher_name
        FROM gcd_issue i
        JOIN gcd_series s ON s.id = i.series_id
        LEFT JOIN gcd_publisher p ON p.id = s.publisher_id
        WHERE i.barcode IS NOT NULL AND TRIM(i.barcode) <> ''
        ORDER BY i.id
        LIMIT :batch OFFSET :offset
        """
    )
    cur = offset
    while True:
        with gcd.connect() as conn:
            rows = [dict(r._mapping) for r in conn.execute(query, {"batch": batch, "offset": cur})]
        if not rows:
            break
        yield rows
        cur += len(rows)
        if len(rows) < batch:
            break


def _add_sample(stats: GcdBackfillStats, **row: Any) -> None:
    if len(stats.samples) < MAX_SAMPLES:
        stats.samples.append(row)


def run_gcd_backfill(
    session: Session,
    gcd: Engine,
    *,
    write: bool = False,
    limit: int | None = None,
    resume_path: Path | None = None,
) -> GcdBackfillStats:
    state = _Resume.load(resume_path)
    stats = state.stats
    index = build_local_index(session)

    with gcd.connect() as conn:
        stats.gcd_total_issues = int(conn.execute(text("SELECT COUNT(*) FROM gcd_issue")).scalar() or 0)

    processed_this_run = 0
    stop = False
    for batch in _iter_gcd_rows(gcd, offset=state.offset):
        if stop:
            break
        for row in batch:
            if limit is not None and processed_this_run >= limit:
                stop = True
                break
            stats.rows_checked += 1
            processed_this_run += 1
            state.offset += 1

            barcodes = extract_barcodes(row.get("barcode"))
            if not barcodes:
                continue
            stats.rows_with_barcode += 1

            gcd_publisher = str(row.get("publisher_name") or "")
            gcd_series = str(row.get("series_name") or "")
            gcd_number = str(row.get("number") or "")
            year = _year_from_key_date(row.get("key_date"), row.get("year_began"))

            local = _match_local(
                index,
                gcd_publisher=gcd_publisher,
                gcd_series=gcd_series,
                gcd_issue_number=gcd_number,
                gcd_year=year,
            )
            if local is None:
                stats.unmatched_rows += 1
                _add_sample(
                    stats,
                    barcode=barcodes[0],
                    local_issue_id=None,
                    publisher=gcd_publisher,
                    series=gcd_series,
                    issue_number=gcd_number,
                    year=year,
                    validation_status="unmatched",
                )
                continue
            stats.matched_local_issues += 1

            pub_key = local.publisher or gcd_publisher or "Unknown"
            year_key = str(local.year or year or "unknown")
            stats.by_publisher[pub_key].with_barcode += 1
            stats.by_year[year_key].with_barcode += 1
            stats.by_publisher[pub_key].matched += 1
            stats.by_year[year_key].matched += 1

            for bc in barcodes:
                validation = validate_barcode_catalog_match(
                    bc,
                    publisher=local.publisher,
                    issue_number=local.issue_number,
                    year=str(local.year) if local.year is not None else (str(year) if year else None),
                )
                if validation.status != "exact_match":
                    stats.rejected_validation += 1
                    stats.by_publisher[pub_key].rejected += 1
                    stats.by_year[year_key].rejected += 1
                    _add_sample(stats, barcode=bc, local_issue_id=local.issue_id, publisher=local.publisher, series=local.series, issue_number=local.issue_number, year=local.year, validation_status=validation.status)
                    continue

                # Rule: user-confirmed learned mappings always win.
                learned = session.exec(
                    select(ComicIssueBarcode).where(ComicIssueBarcode.normalized_barcode == bc)
                ).first()
                if learned is not None:
                    stats.skipped_learned += 1
                    continue

                existing = session.exec(select(CatalogUpc).where(CatalogUpc.normalized_upc == bc)).first()
                if existing is not None:
                    if existing.issue_id is not None and int(existing.issue_id) != local.issue_id:
                        stats.duplicate_conflicts += 1
                        stats.by_publisher[pub_key].conflicts += 1
                        stats.by_year[year_key].conflicts += 1
                        _add_sample(stats, barcode=bc, local_issue_id=local.issue_id, publisher=local.publisher, series=local.series, issue_number=local.issue_number, year=local.year, validation_status="duplicate_conflict")
                    continue  # never overwrite an existing catalog_upc row

                stats.projected_inserts += 1
                stats.by_publisher[pub_key].projected_inserts += 1
                stats.by_year[year_key].projected_inserts += 1
                _add_sample(stats, barcode=bc, local_issue_id=local.issue_id, publisher=local.publisher, series=local.series, issue_number=local.issue_number, year=local.year, validation_status="exact_match")

                if write:
                    variant = session.exec(
                        select(CatalogVariant).where(CatalogVariant.issue_id == local.issue_id)
                    ).first()
                    upsert_upc(
                        session,
                        raw_upc=bc,
                        issue_id=local.issue_id,
                        variant_id=int(variant.id) if variant is not None and variant.id is not None else None,
                        source=GCD_SOURCE,
                        barcode_type="upc",
                    )
                    stats.written += 1

        if write:
            session.commit()
        if state.offset % SAVE_EVERY < len(batch):
            state.save(resume_path)
            logger.info(
                "GCD backfill progress: checked=%s matched=%s inserts=%s conflicts=%s unmatched=%s",
                stats.rows_checked, stats.matched_local_issues, stats.projected_inserts,
                stats.duplicate_conflicts, stats.unmatched_rows,
            )

    state.save(resume_path)
    return stats
