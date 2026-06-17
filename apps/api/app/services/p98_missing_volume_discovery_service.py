"""P98 — Find ComicVine volumes missing from the master universe skeleton.

Publisher-targeted ComicVine volume listing (filter=publisher:…), compared against
``universe_volume.comicvine_volume_id``. Dry-run by default; ``--apply`` inserts
``comicvine_volume_universe`` + ``universe_publisher`` + ``universe_volume`` only
(no issue shells, no P97 queue, no catalog import).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlmodel import Session, select

from app.models.catalog_p97 import ComicVineVolumeUniverse
from app.models.universe import UniverseIssue, UniverseVariant, UniverseVolume
from app.services.comicvine_api_response import payload_results
from app.services.comicvine_catalog_importer import ComicVineThrottleError
from app.services.p97_comicvine_universe_discovery_service import (
    ComicVineEndpointForbiddenError,
    ComicVineUniverseDiscoveryClient,
    upsert_universe_volume,
    volume_row_from_api,
)
from app.services.p98_discovery_integrity_service import comicvine_universe_volume_ids
from app.services.p98_gap_priority_service import score_volume
from app.services.p98_major_publisher_registry import (
    MajorPublisherConfig,
    config_for_comicvine_publisher_name,
    resolve_major_publisher,
)
from app.services.universe.universe_issue_service import VOLUME_STATUS_VOLUME_ONLY
from app.services.universe.universe_publisher_service import upsert_publisher
from app.services.universe.universe_volume_service import upsert_volume

REQUEST_TYPE_LABEL = "p98_missing_volume_discovery"
DEFAULT_PROGRESS_REL = Path("data/p98/missing_volume_discovery_progress.json")
DEFAULT_RESULTS_REL = Path("data/p98/missing_volume_discovery_results.json")
DEFAULT_MISSING_QUEUE_REL = Path("data/p98/missing_major_publisher_volumes.json")

ACTION_INSERT_VOLUME_ONLY = "INSERT_VOLUME_ONLY"
ACTION_DISCOVER_VOLUME = "DISCOVER_VOLUME"


def _api_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_progress_path() -> Path:
    return _api_root() / DEFAULT_PROGRESS_REL


def default_results_path() -> Path:
    return _api_root() / DEFAULT_RESULTS_REL


def default_missing_queue_path() -> Path:
    return _api_root() / DEFAULT_MISSING_QUEUE_REL


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MissingVolumeCandidate:
    publisher: str
    volume: str
    comicvine_volume_id: int
    start_year: int | None
    issue_count: int
    priority_score: int
    reason: str
    recommended_action: str = ACTION_INSERT_VOLUME_ONLY
    in_comicvine_volume_universe: bool = False
    in_universe_volume: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "volume": self.volume,
            "comicvine_volume_id": self.comicvine_volume_id,
            "start_year": self.start_year,
            "issue_count": self.issue_count,
            "priority_score": self.priority_score,
            "reason": self.reason,
            "recommended_action": self.recommended_action,
            "in_comicvine_volume_universe": self.in_comicvine_volume_universe,
            "in_universe_volume": self.in_universe_volume,
        }


@dataclass
class PublisherDiscoveryProgress:
    publisher: str = ""
    comicvine_filter: str = ""
    offset: int = 0
    pages_scanned: int = 0
    volumes_scanned: int = 0
    missing_found: int = 0
    inserted: int = 0
    last_status_code: int | None = None
    last_error: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "comicvine_filter": self.comicvine_filter,
            "offset": self.offset,
            "pages_scanned": self.pages_scanned,
            "volumes_scanned": self.volumes_scanned,
            "missing_found": self.missing_found,
            "inserted": self.inserted,
            "last_status_code": self.last_status_code,
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PublisherDiscoveryProgress:
        if not data:
            return cls()
        return cls(
            publisher=str(data.get("publisher") or ""),
            comicvine_filter=str(data.get("comicvine_filter") or ""),
            offset=int(data.get("offset") or 0),
            pages_scanned=int(data.get("pages_scanned") or 0),
            volumes_scanned=int(data.get("volumes_scanned") or 0),
            missing_found=int(data.get("missing_found") or 0),
            inserted=int(data.get("inserted") or 0),
            last_status_code=data.get("last_status_code"),
            last_error=data.get("last_error"),
            updated_at=data.get("updated_at"),
        )


def load_discovery_progress(path: Path | None = None) -> dict[str, Any]:
    progress_path = path or default_progress_path()
    if not progress_path.is_file():
        return {"publishers": {}}
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {"publishers": {}}
    if not isinstance(data, dict):
        return {"publishers": {}}
    data.setdefault("publishers", {})
    return data


def save_discovery_progress(progress: dict[str, Any], path: Path | None = None) -> None:
    progress_path = path or default_progress_path()
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress["updated_at"] = _utc_now().isoformat()
    progress_path.write_text(json.dumps(progress, indent=2), encoding="utf-8")


def _progress_for_publisher(progress: dict[str, Any], key: str) -> PublisherDiscoveryProgress:
    pub_map = progress.setdefault("publishers", {})
    raw = pub_map.get(key)
    if isinstance(raw, dict):
        return PublisherDiscoveryProgress.from_dict(raw)
    return PublisherDiscoveryProgress()


def _store_progress(progress: dict[str, Any], key: str, row: PublisherDiscoveryProgress) -> None:
    row.updated_at = _utc_now().isoformat()
    progress.setdefault("publishers", {})[key] = row.to_dict()


def universe_comicvine_volume_ids(session: Session) -> set[int]:
    return {int(v) for v in session.exec(select(UniverseVolume.comicvine_volume_id)).all()}


def _priority_for_volume(
    config: MajorPublisherConfig,
    *,
    volume_name: str,
    start_year: int | None,
    issue_count: int,
) -> int:
    pub_norm = config.canonical.lower()
    return score_volume(
        publisher_normalized=pub_norm,
        volume_name=volume_name,
        start_year=start_year,
        missing_issue_count=issue_count,
        issue_count=issue_count,
    )


def _candidate_from_payload(
    config: MajorPublisherConfig,
    parsed: dict[str, Any],
    *,
    reason: str,
    in_comicvine_volume_universe: bool = False,
    in_universe_volume: bool = False,
) -> MissingVolumeCandidate | None:
    cv_pub = parsed.get("publisher")
    matched = config_for_comicvine_publisher_name(str(cv_pub) if cv_pub else None)
    if matched is None or matched.canonical != config.canonical:
        return None
    issue_count = int(parsed.get("count_of_issues") or 0)
    return MissingVolumeCandidate(
        publisher=config.canonical,
        volume=str(parsed["name"]),
        comicvine_volume_id=int(parsed["volume_id"]),
        start_year=parsed.get("start_year"),
        issue_count=issue_count,
        priority_score=_priority_for_volume(
            config,
            volume_name=str(parsed["name"]),
            start_year=parsed.get("start_year"),
            issue_count=issue_count,
        ),
        reason=reason,
        recommended_action=ACTION_INSERT_VOLUME_ONLY,
        in_comicvine_volume_universe=in_comicvine_volume_universe,
        in_universe_volume=in_universe_volume,
    )


def get_volume_expansion_candidates_from_local_db(session: Session) -> list[MissingVolumeCandidate]:
    """Major-publisher rows in comicvine_volume_universe but not universe_volume (no API)."""
    existing = universe_comicvine_volume_ids(session)
    out: list[MissingVolumeCandidate] = []
    for row in session.exec(select(ComicVineVolumeUniverse)).all():
        config = config_for_comicvine_publisher_name(row.publisher)
        if config is None:
            continue
        vid = int(row.volume_id)
        if vid in existing:
            continue
        parsed = {
            "volume_id": vid,
            "name": row.name,
            "publisher": row.publisher,
            "start_year": row.start_year,
            "count_of_issues": row.count_of_issues,
        }
        cand = _candidate_from_payload(
            config,
            parsed,
            reason="LOCAL_CV_UNIVERSE_NOT_IN_P98",
            in_comicvine_volume_universe=True,
            in_universe_volume=False,
        )
        if cand is not None:
            out.append(cand)
    out.sort(key=lambda c: c.priority_score, reverse=True)
    return out


@dataclass
class PublisherMissingVolumeReport:
    publisher: str
    comicvine_volumes_scanned: int = 0
    already_in_comicvine_universe: int = 0
    already_in_universe: int = 0
    in_both_tables: int = 0
    missing_from_p98_only: int = 0
    missing_from_both: int = 0
    missing_from_universe: int = 0
    would_insert: int = 0
    inserted: int = 0
    missing_candidates: list[MissingVolumeCandidate] = field(default_factory=list)
    throttled: bool = False
    stopped: bool = False
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "publisher": self.publisher,
            "comicvine_volumes_scanned": self.comicvine_volumes_scanned,
            "already_in_comicvine_universe": self.already_in_comicvine_universe,
            "already_in_universe": self.already_in_universe,
            "in_both_tables": self.in_both_tables,
            "missing_from_p98_only": self.missing_from_p98_only,
            "missing_from_both": self.missing_from_both,
            "missing_from_universe": self.missing_from_universe,
            "would_insert": self.would_insert,
            "inserted": self.inserted,
            "missing_candidates": [c.as_dict() for c in self.missing_candidates],
            "throttled": self.throttled,
            "stopped": self.stopped,
            "error": self.error,
        }


def apply_missing_volume(
    session: Session,
    candidate: MissingVolumeCandidate,
    parsed: dict[str, Any],
) -> bool:
    """Insert universe + discovered rows. Returns True if universe_volume was created."""
    existing = session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == candidate.comicvine_volume_id)
    ).first()
    if existing is not None:
        return False

    upsert_universe_volume(session, parsed)
    pub = upsert_publisher(session, name=candidate.publisher)
    upsert_volume(
        session,
        publisher=pub,
        comicvine_volume_id=candidate.comicvine_volume_id,
        name=candidate.volume,
        start_year=candidate.start_year,
        count_of_issues=candidate.issue_count or None,
    )
    vol = session.exec(
        select(UniverseVolume).where(UniverseVolume.comicvine_volume_id == candidate.comicvine_volume_id)
    ).first()
    if vol is not None:
        vol.volume_status = VOLUME_STATUS_VOLUME_ONLY
        session.add(vol)
    session.commit()
    return True


def discover_missing_volumes_for_publisher(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    config: MajorPublisherConfig,
    *,
    limit_pages: int = 10,
    limit_volumes: int | None = 500,
    min_issue_count: int = 1,
    apply: bool = False,
    stop_on_throttle: bool = True,
    progress: dict[str, Any] | None = None,
    progress_key: str | None = None,
    resume: bool = True,
) -> PublisherMissingVolumeReport:
    report = PublisherMissingVolumeReport(publisher=config.canonical)
    progress = progress if progress is not None else load_discovery_progress()
    key = progress_key or config.canonical
    prog = _progress_for_publisher(progress, key) if resume else PublisherDiscoveryProgress()
    if resume and prog.publisher == config.canonical and prog.offset > 0:
        start_offset = prog.offset
    else:
        start_offset = 0
        prog = PublisherDiscoveryProgress(publisher=config.canonical)

    existing_ids = universe_comicvine_volume_ids(session)
    cv_universe_ids = comicvine_universe_volume_ids(session)
    missing_cap = int(limit_volumes) if limit_volumes is not None and limit_volumes > 0 else None
    pages_left = max(1, int(limit_pages))
    offset = start_offset

    filter_names = config.expected_comicvine_publisher_names or (config.canonical,)
    filter_name = prog.comicvine_filter or filter_names[0]
    prog.comicvine_filter = filter_name

    page_size = 100
    while pages_left > 0:
        try:
            payload = client.fetch_publisher_volumes_page(
                publisher_filter=filter_name,
                offset=offset,
                limit=page_size,
            )
        except ComicVineThrottleError as exc:
            report.throttled = True
            report.error = str(exc)
            prog.last_error = str(exc)
            if stop_on_throttle:
                report.stopped = True
            break
        except ComicVineEndpointForbiddenError as exc:
            report.error = str(exc)
            report.stopped = True
            prog.last_error = str(exc)
            break
        except Exception as exc:  # noqa: BLE001
            report.error = str(exc)
            prog.last_error = str(exc)
            break

        prog.last_status_code = 200
        pages_left -= 1
        prog.pages_scanned += 1
        rows = payload_results(payload)
        if not rows:
            break

        for row in rows:
            parsed = volume_row_from_api(row)
            if parsed is None:
                continue
            report.comicvine_volumes_scanned += 1
            prog.volumes_scanned += 1
            issue_count = int(parsed.get("count_of_issues") or 0)
            if issue_count < int(min_issue_count):
                continue
            cv_id = int(parsed["volume_id"])
            in_cv = cv_id in cv_universe_ids
            in_p98 = cv_id in existing_ids
            if in_cv:
                report.already_in_comicvine_universe += 1
            if in_p98:
                report.already_in_universe += 1
            if in_cv and in_p98:
                report.in_both_tables += 1
            elif in_cv and not in_p98:
                report.missing_from_p98_only += 1
            elif not in_cv and not in_p98:
                report.missing_from_both += 1
            if cv_id in existing_ids:
                continue
            cand = _candidate_from_payload(
                config,
                parsed,
                reason=f"COMICVINE_NOT_IN_UNIVERSE filter={filter_name}",
                in_comicvine_volume_universe=in_cv,
                in_universe_volume=in_p98,
            )
            if cand is None:
                continue
            report.missing_from_universe += 1
            prog.missing_found += 1
            report.missing_candidates.append(cand)
            report.would_insert += 1
            if apply:
                if apply_missing_volume(session, cand, parsed):
                    existing_ids.add(cv_id)
                    report.inserted += 1
                    prog.inserted += 1
            if missing_cap is not None and len(report.missing_candidates) >= missing_cap:
                report.stopped = True
                break

        offset += len(rows)
        prog.offset = offset
        _store_progress(progress, key, prog)

        if report.stopped or len(rows) < page_size:
            break

    report.missing_candidates.sort(key=lambda c: c.priority_score, reverse=True)
    save_discovery_progress(progress)
    return report


def discover_missing_major_publishers(
    session: Session,
    client: ComicVineUniverseDiscoveryClient,
    *,
    limit_pages: int = 10,
    limit_volumes: int | None = None,
    min_issue_count: int = 1,
    apply: bool = False,
    stop_on_throttle: bool = True,
) -> list[PublisherMissingVolumeReport]:
    from app.services.p98_major_publisher_registry import all_major_publishers

    progress = load_discovery_progress()
    reports: list[PublisherMissingVolumeReport] = []
    for config in all_major_publishers():
        reports.append(
            discover_missing_volumes_for_publisher(
                session,
                client,
                config,
                limit_pages=limit_pages,
                limit_volumes=limit_volumes,
                min_issue_count=min_issue_count,
                apply=apply,
                stop_on_throttle=stop_on_throttle,
                progress=progress,
            )
        )
        if reports[-1].throttled and stop_on_throttle:
            break
    return reports


def save_discovery_results(
    reports: list[PublisherMissingVolumeReport],
    *,
    path: Path | None = None,
) -> None:
    out_path = path or default_results_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": _utc_now().isoformat(),
        "reports": [r.as_dict() for r in reports],
        "all_missing": [
            c.as_dict()
            for r in reports
            for c in r.missing_candidates
        ],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_missing_volume_action_queue(
    session: Session,
    *,
    results_path: Path | None = None,
    include_local_db: bool = True,
) -> list[dict[str, Any]]:
    """Planning queue from last API discovery results and/or local CV universe gap."""
    seen: set[int] = set()
    rows: list[MissingVolumeCandidate] = []

    results_path = results_path or default_results_path()
    if results_path.is_file():
        try:
            data = json.loads(results_path.read_text(encoding="utf-8-sig"))
            for raw in data.get("all_missing") or []:
                cv_id = int(raw.get("comicvine_volume_id") or 0)
                if cv_id <= 0 or cv_id in seen:
                    continue
                seen.add(cv_id)
                rows.append(
                    MissingVolumeCandidate(
                        publisher=str(raw.get("publisher") or ""),
                        volume=str(raw.get("volume") or ""),
                        comicvine_volume_id=cv_id,
                        start_year=raw.get("start_year"),
                        issue_count=int(raw.get("issue_count") or 0),
                        priority_score=int(raw.get("priority_score") or 0),
                        reason=str(raw.get("reason") or ""),
                        recommended_action=str(
                            raw.get("recommended_action") or ACTION_INSERT_VOLUME_ONLY
                        ),
                    )
                )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass

    if include_local_db:
        for cand in get_volume_expansion_candidates_from_local_db(session):
            if cand.comicvine_volume_id in seen:
                continue
            seen.add(cand.comicvine_volume_id)
            cand.recommended_action = ACTION_INSERT_VOLUME_ONLY
            rows.append(cand)

    rows.sort(key=lambda c: c.priority_score, reverse=True)
    return [r.as_dict() for r in rows]


def assert_no_issue_shell_mutations(session: Session, before_issues: int, before_variants: int) -> None:
    from sqlalchemy import func

    issues = int(session.exec(select(func.count()).select_from(UniverseIssue)).one())
    variants = int(session.exec(select(func.count()).select_from(UniverseVariant)).one())
    if issues != before_issues or variants != before_variants:
        raise RuntimeError("P98 missing-volume discovery must not create issue/variant shells")
