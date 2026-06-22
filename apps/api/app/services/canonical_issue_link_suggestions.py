from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlmodel import Session, select

from app.models import (
    CanonicalIssueLinkSuggestion,
    CanonicalSeries,
    CatalogIssue,
    CatalogPublisher,
    ComicIssue,
    ComicTitle,
    CoverImage,
    CoverImageBarcodeCandidate,
    CoverImageLinkDecision,
    CoverImageOcrCandidate,
    InventoryCopy,
    Publisher,
    User,
    Variant,
)
from app.services.catalog_registry_rows import load_catalog_registry_issue_rows
from app.services.inventory_canonical_spine import (
    apply_inventory_spine_joins,
    issue_number_expr,
    publisher_expr,
    title_expr,
)
from app.services.legacy_spine_availability import legacy_comic_issue_table_exists
from sqlalchemy import func
from app.schemas.canonical_issue_link_suggestions import (
    CanonicalIssueLinkSuggestionRead,
    CanonicalIssueSuggestionGenerateResponse,
    CanonicalIssueSuggestionOpsListResponse,
    CanonicalIssueSuggestionReviewActionResponse,
)
from app.services.cover_images import (
    _barcode_facts_for_cover,
    _selected_ocr_candidates_for_matching,
    get_cover_entity_for_processing_by_ops_or_404,
    get_cover_entity_for_processing_by_owner,
)
from app.services.cover_link_decisions import active_cover_link_decisions_for_pairs, cover_link_pair_key, owner_can_access_cover
from app.services.cover_relationship_graph import build_cover_relationship_graph
from app.services.duplicate_scan_intelligence import duplicate_scan_candidates_for_cover_owner, duplicate_scan_candidates_for_ops
from app.services.metadata_audits import record_metadata_audit
from app.services.metadata_enrichment import (
    build_metadata_identity_components,
    build_metadata_identity_key,
    normalize_issue_number,
    normalize_publisher_name,
    normalize_series_title_with_aliases,
)
from app.services.variant_family_intelligence import variant_family_candidates_for_cover_owner, variant_family_candidates_for_ops

CONFIDENCE_VERSION = "canonical-issue-suggestion-v1"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IssueRegistryRow:
    canonical_issue_id: int
    canonical_series_id: int | None
    canonical_publisher_id: int | None
    title: str
    publisher: str
    issue_number: str


@dataclass
class SuggestionSpec:
    cover_image_id: int
    inventory_copy_id: int | None
    canonical_issue_id: int | None
    canonical_series_id: int | None
    canonical_publisher_id: int | None
    suggested_metadata_identity_key: str | None
    suggestion_type: str
    confidence_bucket: str
    deterministic_score: float
    evidence_json: dict[str, object]
    suppression_reason: str | None = None


def _bucket_for_score(score: float) -> str:
    if score >= 0.95:
        return "very_high"
    if score >= 0.82:
        return "high"
    if score >= 0.65:
        return "medium"
    if score >= 0.45:
        return "low"
    return "very_low"


def _normalize_review_reason(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _reviewer_email_map(session: Session, reviewer_ids: set[int]) -> dict[int, str]:
    if not reviewer_ids:
        return {}
    rows = session.exec(select(User).where(User.id.in_(sorted(reviewer_ids)))).all()
    return {row.id: row.email for row in rows if row.id is not None}


def _serialize_suggestion(
    session: Session,
    row: CanonicalIssueLinkSuggestion,
    *,
    reviewer_emails: dict[int, str] | None = None,
) -> CanonicalIssueLinkSuggestionRead:
    if row.id is None:
        raise ValueError("suggestion row must be flushed before serialization")
    emails = reviewer_emails or _reviewer_email_map(
        session, {row.reviewed_by_user_id} if row.reviewed_by_user_id is not None else set()
    )
    return CanonicalIssueLinkSuggestionRead(
        id=row.id,
        cover_image_id=row.cover_image_id,
        inventory_copy_id=row.inventory_copy_id,
        canonical_issue_id=row.canonical_issue_id,
        canonical_series_id=row.canonical_series_id,
        canonical_publisher_id=row.canonical_publisher_id,
        suggested_metadata_identity_key=row.suggested_metadata_identity_key,
        suggestion_type=row.suggestion_type,  # type: ignore[arg-type]
        confidence_bucket=row.confidence_bucket,  # type: ignore[arg-type]
        deterministic_score=row.deterministic_score,
        confidence_version=row.confidence_version,
        evidence_json=dict(row.evidence_json or {}),
        suppression_reason=row.suppression_reason,
        review_state=row.review_state,  # type: ignore[arg-type]
        reviewed_by_user_id=row.reviewed_by_user_id,
        reviewed_by_email=emails.get(row.reviewed_by_user_id) if row.reviewed_by_user_id is not None else None,
        reviewed_at=row.reviewed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _load_issue_registry_rows(
    session: Session,
    *,
    title: str | None = None,
    issue_number: str | None = None,
    publisher: str | None = None,
) -> list[IssueRegistryRow]:
    catalog_rows = load_catalog_registry_issue_rows(
        session, series=title, issue_number=issue_number, publisher=publisher
    )
    if catalog_rows:
        return [
            IssueRegistryRow(
                canonical_issue_id=row.catalog_issue_id,
                canonical_series_id=row.catalog_series_id,
                canonical_publisher_id=None,
                title=row.series,
                publisher=row.publisher,
                issue_number=row.issue_number,
            )
            for row in catalog_rows
        ]
    if not legacy_comic_issue_table_exists(session):
        return []
    stmt = (
        select(
            ComicIssue.id,
            CanonicalSeries.id,
            Publisher.id,
            ComicTitle.name,
            Publisher.name,
            ComicIssue.issue_number,
        )
        .join(ComicTitle, ComicIssue.comic_title_id == ComicTitle.id)
        .join(Publisher, ComicTitle.publisher_id == Publisher.id)
        .join(
            CanonicalSeries,
            (CanonicalSeries.canonical_title == ComicTitle.name)
            & (CanonicalSeries.canonical_publisher == Publisher.name),
            isouter=True,
        )
    )
    if title is not None:
        stmt = stmt.where(ComicTitle.name == title)
    if issue_number is not None:
        stmt = stmt.where(ComicIssue.issue_number == issue_number)
    if publisher is not None:
        stmt = stmt.where(Publisher.name == publisher)
    stmt = stmt.order_by(Publisher.name.asc(), ComicTitle.name.asc(), ComicIssue.issue_number.asc(), ComicIssue.id.asc())
    rows = session.exec(stmt).all()
    return [
        IssueRegistryRow(
            canonical_issue_id=int(issue_id),
            canonical_series_id=int(series_id) if series_id is not None else None,
            canonical_publisher_id=int(publisher_id) if publisher_id is not None else None,
            title=str(title_name),
            publisher=str(publisher_name),
            issue_number=str(issue_num),
        )
        for issue_id, series_id, publisher_id, title_name, publisher_name, issue_num in rows
    ]


def _load_inventory_issue_context(
    session: Session,
    *,
    inventory_copy_id: int,
) -> IssueRegistryRow | None:
    row = session.exec(
        apply_inventory_spine_joins(
            select(
                CatalogIssue.id,
                InventoryCopy.canonical_series_id,
                CatalogPublisher.id,
                title_expr(),
                publisher_expr(),
                issue_number_expr(),
            ).select_from(InventoryCopy)
        ).where(InventoryCopy.id == inventory_copy_id)
    ).first()
    if row is None:
        return None
    issue_id, series_id, publisher_id, title_name, publisher_name, issue_num = row
    return IssueRegistryRow(
        canonical_issue_id=int(issue_id),
        canonical_series_id=int(series_id) if series_id is not None else None,
        canonical_publisher_id=int(publisher_id),
        title=str(title_name),
        publisher=str(publisher_name),
        issue_number=str(issue_num),
    )


def _load_cover_ocr_context(session: Session, *, cover_image_id: int) -> dict[str, dict[str, object]] | None:
    rows = session.exec(
        select(CoverImageOcrCandidate)
        .where(CoverImageOcrCandidate.cover_image_id == cover_image_id)
        .order_by(CoverImageOcrCandidate.id.asc())
    ).all()
    return _selected_ocr_candidates_for_matching(list(rows)).get(cover_image_id)


def _load_cover_barcode_context(session: Session, *, cover_image_id: int) -> dict[str, object] | None:
    rows = session.exec(
        select(CoverImageBarcodeCandidate)
        .where(CoverImageBarcodeCandidate.cover_image_id == cover_image_id)
        .order_by(CoverImageBarcodeCandidate.id.asc())
    ).all()
    return _barcode_facts_for_cover(list(rows)).get(cover_image_id)


def _normalized_cover_biblio_from_ocr(
    session: Session,
    *,
    cover: CoverImage,
) -> tuple[str | None, str | None, str | None]:
    ocr = _load_cover_ocr_context(session, cover_image_id=int(cover.id))
    if not ocr:
        return None, None, None

    title_raw = ocr.get("title", {}).get("normalized")
    issue_raw = ocr.get("issue_number", {}).get("normalized")
    publisher_raw = ocr.get("publisher", {}).get("normalized")
    title = normalize_series_title_with_aliases(str(title_raw) if title_raw else None, session=session).canonical_value
    issue = normalize_issue_number(str(issue_raw) if issue_raw else None).canonical_value
    publisher = normalize_publisher_name(str(publisher_raw) if publisher_raw else None, session=session).canonical_value
    return title, issue, publisher


def _identity_key_for_cover(session: Session, *, cover: CoverImage) -> str | None:
    if cover.inventory_copy_id is not None:
        inv = session.get(InventoryCopy, int(cover.inventory_copy_id))
        if inv is not None and inv.metadata_identity_key:
            return inv.metadata_identity_key
    title, issue, publisher = _normalized_cover_biblio_from_ocr(session, cover=cover)
    if not title or not issue:
        return None
    components = build_metadata_identity_components(
        publisher=publisher,
        series_title=title,
        issue_number=issue,
        variant=None,
    )
    return build_metadata_identity_key(components)


def _same_identity_issue_row_for_cover(session: Session, *, cover: CoverImage) -> IssueRegistryRow | None:
    if cover.inventory_copy_id is None:
        return None
    inv = session.get(InventoryCopy, int(cover.inventory_copy_id))
    if inv is None or not inv.metadata_identity_key:
        return None
    return _load_inventory_issue_context(session, inventory_copy_id=int(inv.id))


def _peer_cover_issue_contexts(session: Session, *, cover_ids: set[int]) -> dict[int, IssueRegistryRow]:
    out: dict[int, IssueRegistryRow] = {}
    if not cover_ids:
        return out
    rows = session.exec(select(CoverImage).where(CoverImage.id.in_(sorted(cover_ids)))).all()
    for row in rows:
        if row.id is None or row.inventory_copy_id is None:
            continue
        ctx = _load_inventory_issue_context(session, inventory_copy_id=int(row.inventory_copy_id))
        if ctx is not None:
            out[int(row.id)] = ctx
    return out


def _score_contextual(count: int, *, base: float) -> float:
    return round(min(0.95, base + min(0.18, 0.06 * max(0, count - 1))), 4)


def _existing_rows_for_cover(session: Session, *, cover_image_id: int) -> list[CanonicalIssueLinkSuggestion]:
    return session.exec(
        select(CanonicalIssueLinkSuggestion)
        .where(CanonicalIssueLinkSuggestion.cover_image_id == cover_image_id)
        .order_by(CanonicalIssueLinkSuggestion.id.asc())
    ).all()


def _signature_for_spec(spec: SuggestionSpec) -> tuple[int, int | None, str | None, str, str]:
    return (
        spec.cover_image_id,
        spec.canonical_issue_id,
        spec.suggested_metadata_identity_key,
        spec.suggestion_type,
        CONFIDENCE_VERSION,
    )


def _signature_for_row(row: CanonicalIssueLinkSuggestion) -> tuple[int, int | None, str | None, str, str]:
    return (
        row.cover_image_id,
        row.canonical_issue_id,
        row.suggested_metadata_identity_key,
        row.suggestion_type,
        row.confidence_version,
    )


def _dedupe_specs(specs: list[SuggestionSpec]) -> list[SuggestionSpec]:
    by_sig: dict[tuple[int, int | None, str | None, str, str], SuggestionSpec] = {}
    for spec in specs:
        sig = _signature_for_spec(spec)
        incumbent = by_sig.get(sig)
        if incumbent is None or spec.deterministic_score > incumbent.deterministic_score:
            by_sig[sig] = spec
    return sorted(
        by_sig.values(),
        key=lambda item: (-item.deterministic_score, item.suggestion_type, item.canonical_issue_id or -1, item.suggested_metadata_identity_key or ""),
    )


def _build_suggestion_specs(
    session: Session,
    *,
    cover: CoverImage,
    current_user: User | None,
) -> list[SuggestionSpec]:
    if cover.id is None:
        return []
    cover_id = int(cover.id)
    inventory_copy_id = int(cover.inventory_copy_id) if cover.inventory_copy_id is not None else None
    specs: list[SuggestionSpec] = []

    identity_key = _identity_key_for_cover(session, cover=cover)
    barcode_ctx = _load_cover_barcode_context(session, cover_image_id=cover_id) or {}
    shared_barcode_values = sorted(set(barcode_ctx.get("approved_barcodes", set()))) if isinstance(barcode_ctx.get("approved_barcodes"), set) else []

    exact_issue = _same_identity_issue_row_for_cover(session, cover=cover)
    if identity_key and exact_issue is not None:
        score = 0.98
        specs.append(
            SuggestionSpec(
                cover_image_id=cover_id,
                inventory_copy_id=inventory_copy_id,
                canonical_issue_id=exact_issue.canonical_issue_id,
                canonical_series_id=exact_issue.canonical_series_id,
                canonical_publisher_id=exact_issue.canonical_publisher_id,
                suggested_metadata_identity_key=identity_key,
                suggestion_type="exact_identity_key",
                confidence_bucket=_bucket_for_score(score),
                deterministic_score=score,
                evidence_json={
                    "source": "inventory_metadata_identity_key",
                    "metadata_identity_key": identity_key,
                    "title": exact_issue.title,
                    "publisher": exact_issue.publisher,
                    "issue_number": exact_issue.issue_number,
                    "supporting_shared_upcs": shared_barcode_values,
                },
            )
        )

    title, issue, publisher = _normalized_cover_biblio_from_ocr(session, cover=cover)
    if title and issue and publisher:
        exact_rows = _load_issue_registry_rows(session, title=title, issue_number=issue, publisher=publisher)
        for row in exact_rows[:3]:
            score = 0.9 + (0.02 if shared_barcode_values else 0.0)
            specs.append(
                SuggestionSpec(
                    cover_image_id=cover_id,
                    inventory_copy_id=inventory_copy_id,
                    canonical_issue_id=row.canonical_issue_id,
                    canonical_series_id=row.canonical_series_id,
                    canonical_publisher_id=row.canonical_publisher_id,
                    suggested_metadata_identity_key=identity_key,
                    suggestion_type="normalized_title_issue_publisher",
                    confidence_bucket=_bucket_for_score(score),
                    deterministic_score=round(score, 4),
                    evidence_json={
                        "normalized_title": title,
                        "normalized_issue_number": issue,
                        "normalized_publisher": publisher,
                        "supporting_shared_upcs": shared_barcode_values,
                    },
                )
            )

    if title and issue:
        title_issue_rows = _load_issue_registry_rows(session, title=title, issue_number=issue, publisher=None)
        if title_issue_rows:
            row = title_issue_rows[0]
            score = 0.68 + (0.01 if shared_barcode_values else 0.0)
            specs.append(
                SuggestionSpec(
                    cover_image_id=cover_id,
                    inventory_copy_id=inventory_copy_id,
                    canonical_issue_id=row.canonical_issue_id,
                    canonical_series_id=row.canonical_series_id,
                    canonical_publisher_id=row.canonical_publisher_id,
                    suggested_metadata_identity_key=identity_key,
                    suggestion_type="normalized_title_issue",
                    confidence_bucket=_bucket_for_score(score),
                    deterministic_score=round(score, 4),
                    evidence_json={
                        "normalized_title": title,
                        "normalized_issue_number": issue,
                        "publisher_missing_or_weaker": True,
                        "supporting_shared_upcs": shared_barcode_values,
                    },
                )
            )

    graph = build_cover_relationship_graph(session, center_cover_image_id=cover_id, current_user=current_user)
    relationship_peers: set[int] = set()
    for edge in graph.edges:
        if edge.decision_type == "rejected_link" or edge.relationship_type == "unrelated":
            continue
        if edge.relationship_type == "duplicate_scan":
            continue
        peer_id = (
            edge.candidate_cover_image_id if edge.source_cover_image_id == cover_id else edge.source_cover_image_id
        )
        relationship_peers.add(int(peer_id))
    relationship_issue_map = _peer_cover_issue_contexts(session, cover_ids=relationship_peers)
    rel_counts: dict[int, tuple[IssueRegistryRow, int]] = {}
    for ctx in relationship_issue_map.values():
        current = rel_counts.get(ctx.canonical_issue_id)
        rel_counts[ctx.canonical_issue_id] = (ctx, 1 if current is None else current[1] + 1)
    for ctx, count in sorted(rel_counts.values(), key=lambda item: (-item[1], item[0].canonical_issue_id)):
        score = _score_contextual(count, base=0.61)
        specs.append(
            SuggestionSpec(
                cover_image_id=cover_id,
                inventory_copy_id=inventory_copy_id,
                canonical_issue_id=ctx.canonical_issue_id,
                canonical_series_id=ctx.canonical_series_id,
                canonical_publisher_id=ctx.canonical_publisher_id,
                suggested_metadata_identity_key=identity_key,
                suggestion_type="relationship_context",
                confidence_bucket=_bucket_for_score(score),
                deterministic_score=score,
                evidence_json={
                    "peer_cover_ids": sorted(relationship_issue_map.keys()),
                    "supporting_peer_count": count,
                    "title": ctx.title,
                    "publisher": ctx.publisher,
                    "issue_number": ctx.issue_number,
                },
            )
        )

    if current_user is None:
        vf = variant_family_candidates_for_ops(session, cover_image_id=cover_id)
        dup = duplicate_scan_candidates_for_ops(session, cover_image_id=cover_id)
    else:
        vf = variant_family_candidates_for_cover_owner(session, cover_image_id=cover_id, current_user=current_user)
        dup = duplicate_scan_candidates_for_cover_owner(session, cover_image_id=cover_id, current_user=current_user)

    vf_issue_map = _peer_cover_issue_contexts(
        session, cover_ids={int(peer.peer_cover_image_id) for peer in vf.variant_peers}
    )
    vf_counts: dict[int, tuple[IssueRegistryRow, int]] = {}
    for ctx in vf_issue_map.values():
        current = vf_counts.get(ctx.canonical_issue_id)
        vf_counts[ctx.canonical_issue_id] = (ctx, 1 if current is None else current[1] + 1)
    for ctx, count in sorted(vf_counts.values(), key=lambda item: (-item[1], item[0].canonical_issue_id)):
        score = _score_contextual(count, base=0.64)
        specs.append(
            SuggestionSpec(
                cover_image_id=cover_id,
                inventory_copy_id=inventory_copy_id,
                canonical_issue_id=ctx.canonical_issue_id,
                canonical_series_id=ctx.canonical_series_id,
                canonical_publisher_id=ctx.canonical_publisher_id,
                suggested_metadata_identity_key=identity_key,
                suggestion_type="variant_family_context",
                confidence_bucket=_bucket_for_score(score),
                deterministic_score=score,
                evidence_json={
                    "peer_cover_ids": sorted(vf_issue_map.keys()),
                    "supporting_peer_count": count,
                    "touching_cluster_count": len(vf.touching_clusters),
                    "title": ctx.title,
                    "publisher": ctx.publisher,
                    "issue_number": ctx.issue_number,
                },
            )
        )

    dup_issue_map = _peer_cover_issue_contexts(
        session, cover_ids={int(peer.peer_cover_image_id) for peer in dup.duplicate_peers}
    )
    dup_counts: dict[int, tuple[IssueRegistryRow, int]] = {}
    for ctx in dup_issue_map.values():
        current = dup_counts.get(ctx.canonical_issue_id)
        dup_counts[ctx.canonical_issue_id] = (ctx, 1 if current is None else current[1] + 1)
    for ctx, count in sorted(dup_counts.values(), key=lambda item: (-item[1], item[0].canonical_issue_id)):
        score = _score_contextual(count, base=0.56)
        specs.append(
            SuggestionSpec(
                cover_image_id=cover_id,
                inventory_copy_id=inventory_copy_id,
                canonical_issue_id=ctx.canonical_issue_id,
                canonical_series_id=ctx.canonical_series_id,
                canonical_publisher_id=ctx.canonical_publisher_id,
                suggested_metadata_identity_key=identity_key,
                suggestion_type="duplicate_scan_context",
                confidence_bucket=_bucket_for_score(score),
                deterministic_score=score,
                evidence_json={
                    "peer_cover_ids": sorted(dup_issue_map.keys()),
                    "supporting_peer_count": count,
                    "touching_cluster_count": len(dup.touching_clusters),
                    "title": ctx.title,
                    "publisher": ctx.publisher,
                    "issue_number": ctx.issue_number,
                    "review_only_context": True,
                },
            )
        )

    return _dedupe_specs(specs)


def _upsert_generated_suggestions(
    session: Session,
    *,
    cover: CoverImage,
    specs: list[SuggestionSpec],
    actor_user_id: int | None,
) -> list[CanonicalIssueLinkSuggestion]:
    cover_id = int(cover.id)
    existing = _existing_rows_for_cover(session, cover_image_id=cover_id)
    existing_by_sig = {_signature_for_row(row): row for row in existing}
    now = utc_now()
    out_rows: list[CanonicalIssueLinkSuggestion] = []

    for spec in specs:
        sig = _signature_for_spec(spec)
        row = existing_by_sig.get(sig)
        if row is None:
            row = CanonicalIssueLinkSuggestion(
                cover_image_id=cover_id,
                inventory_copy_id=spec.inventory_copy_id,
                canonical_issue_id=spec.canonical_issue_id,
                canonical_series_id=spec.canonical_series_id,
                canonical_publisher_id=spec.canonical_publisher_id,
                suggested_metadata_identity_key=spec.suggested_metadata_identity_key,
                suggestion_type=spec.suggestion_type,
                confidence_bucket=spec.confidence_bucket,
                deterministic_score=spec.deterministic_score,
                confidence_version=CONFIDENCE_VERSION,
                evidence_json=spec.evidence_json,
                suppression_reason=spec.suppression_reason,
                review_state="pending",
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="canonical_issue_link_suggestion",
                entity_id=int(row.id),
                action="canonical_issue_link_suggestion_created",
                after_snapshot=row,
                actor_user_id=actor_user_id,
            )
        else:
            row.inventory_copy_id = spec.inventory_copy_id
            row.canonical_issue_id = spec.canonical_issue_id
            row.canonical_series_id = spec.canonical_series_id
            row.canonical_publisher_id = spec.canonical_publisher_id
            row.suggested_metadata_identity_key = spec.suggested_metadata_identity_key
            row.confidence_bucket = spec.confidence_bucket
            row.deterministic_score = spec.deterministic_score
            row.evidence_json = spec.evidence_json
            row.suppression_reason = spec.suppression_reason
            row.updated_at = now
            session.add(row)
            session.flush()
            record_metadata_audit(
                session,
                entity_type="canonical_issue_link_suggestion",
                entity_id=int(row.id),
                action="canonical_issue_link_suggestion_regenerated",
                after_snapshot=row,
                actor_user_id=actor_user_id,
            )
        out_rows.append(row)

    session.commit()
    for row in out_rows:
        session.refresh(row)
    return sorted(out_rows, key=lambda item: (-item.deterministic_score, item.id or -1))


def _suggestion_row_or_404(session: Session, suggestion_id: int) -> CanonicalIssueLinkSuggestion:
    row = session.get(CanonicalIssueLinkSuggestion, suggestion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Canonical issue link suggestion not found")
    return row


def _require_owner_access_to_suggestion(session: Session, *, row: CanonicalIssueLinkSuggestion, current_user: User) -> None:
    cover = session.get(CoverImage, row.cover_image_id)
    if cover is None or not owner_can_access_cover(session, cover=cover, current_user=current_user):
        raise HTTPException(status_code=404, detail="Canonical issue link suggestion not found")


def _set_review_state(
    session: Session,
    *,
    row: CanonicalIssueLinkSuggestion,
    review_state: str,
    reviewer: User,
    reason: str | None,
) -> CanonicalIssueLinkSuggestion:
    now = utc_now()
    row.review_state = review_state
    row.reviewed_by_user_id = reviewer.id
    row.reviewed_at = now
    row.updated_at = now
    if review_state in {"rejected", "ignored"}:
        row.suppression_reason = _normalize_review_reason(reason) or review_state
    session.add(row)
    session.flush()
    record_metadata_audit(
        session,
        entity_type="canonical_issue_link_suggestion",
        entity_id=int(row.id),
        action=f"canonical_issue_link_suggestion_{review_state}",
        after_snapshot=row,
        reason=_normalize_review_reason(reason),
        actor_user_id=reviewer.id,
    )
    session.commit()
    session.refresh(row)
    return row


def generate_canonical_issue_suggestions_for_owner(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User,
) -> CanonicalIssueSuggestionGenerateResponse:
    cover = get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    specs = _build_suggestion_specs(session, cover=cover, current_user=current_user)
    rows = _upsert_generated_suggestions(
        session,
        cover=cover,
        specs=specs,
        actor_user_id=current_user.id,
    )
    emails = _reviewer_email_map(session, {row.reviewed_by_user_id for row in rows if row.reviewed_by_user_id is not None})
    return CanonicalIssueSuggestionGenerateResponse(
        cover_image_id=int(cover.id),
        suggestion_count=len(rows),
        suggestions=[_serialize_suggestion(session, row, reviewer_emails=emails) for row in rows],
    )


def generate_canonical_issue_suggestions_for_ops(
    session: Session,
    *,
    cover_image_id: int,
    reviewer: User,
) -> CanonicalIssueSuggestionGenerateResponse:
    cover = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    specs = _build_suggestion_specs(session, cover=cover, current_user=None)
    rows = _upsert_generated_suggestions(
        session,
        cover=cover,
        specs=specs,
        actor_user_id=reviewer.id,
    )
    emails = _reviewer_email_map(session, {row.reviewed_by_user_id for row in rows if row.reviewed_by_user_id is not None})
    return CanonicalIssueSuggestionGenerateResponse(
        cover_image_id=int(cover.id),
        suggestion_count=len(rows),
        suggestions=[_serialize_suggestion(session, row, reviewer_emails=emails) for row in rows],
    )


def list_canonical_issue_suggestions_for_cover_owner(
    session: Session,
    *,
    cover_image_id: int,
    current_user: User,
) -> list[CanonicalIssueLinkSuggestionRead]:
    cover = get_cover_entity_for_processing_by_owner(
        session,
        current_user=current_user,
        cover_image_id=cover_image_id,
    )
    rows = _existing_rows_for_cover(session, cover_image_id=int(cover.id))
    rows.sort(key=lambda item: (-item.deterministic_score, item.id or -1))
    emails = _reviewer_email_map(session, {row.reviewed_by_user_id for row in rows if row.reviewed_by_user_id is not None})
    return [_serialize_suggestion(session, row, reviewer_emails=emails) for row in rows]


def list_canonical_issue_suggestions_for_cover_ops(
    session: Session,
    *,
    cover_image_id: int,
) -> list[CanonicalIssueLinkSuggestionRead]:
    cover = get_cover_entity_for_processing_by_ops_or_404(session, cover_image_id=cover_image_id)
    rows = _existing_rows_for_cover(session, cover_image_id=int(cover.id))
    rows.sort(key=lambda item: (-item.deterministic_score, item.id or -1))
    emails = _reviewer_email_map(session, {row.reviewed_by_user_id for row in rows if row.reviewed_by_user_id is not None})
    return [_serialize_suggestion(session, row, reviewer_emails=emails) for row in rows]


def approve_canonical_issue_suggestion_for_owner(
    session: Session,
    *,
    suggestion_id: int,
    current_user: User,
    reason: str | None,
) -> CanonicalIssueSuggestionReviewActionResponse:
    row = _suggestion_row_or_404(session, suggestion_id)
    _require_owner_access_to_suggestion(session, row=row, current_user=current_user)
    updated = _set_review_state(session, row=row, review_state="approved", reviewer=current_user, reason=reason)
    return CanonicalIssueSuggestionReviewActionResponse(suggestion=_serialize_suggestion(session, updated))


def reject_canonical_issue_suggestion_for_owner(
    session: Session,
    *,
    suggestion_id: int,
    current_user: User,
    reason: str | None,
) -> CanonicalIssueSuggestionReviewActionResponse:
    row = _suggestion_row_or_404(session, suggestion_id)
    _require_owner_access_to_suggestion(session, row=row, current_user=current_user)
    updated = _set_review_state(session, row=row, review_state="rejected", reviewer=current_user, reason=reason)
    return CanonicalIssueSuggestionReviewActionResponse(suggestion=_serialize_suggestion(session, updated))


def ignore_canonical_issue_suggestion_for_owner(
    session: Session,
    *,
    suggestion_id: int,
    current_user: User,
    reason: str | None,
) -> CanonicalIssueSuggestionReviewActionResponse:
    row = _suggestion_row_or_404(session, suggestion_id)
    _require_owner_access_to_suggestion(session, row=row, current_user=current_user)
    updated = _set_review_state(session, row=row, review_state="ignored", reviewer=current_user, reason=reason)
    return CanonicalIssueSuggestionReviewActionResponse(suggestion=_serialize_suggestion(session, updated))


def approve_canonical_issue_suggestion_for_ops(
    session: Session,
    *,
    suggestion_id: int,
    reviewer: User,
    reason: str | None,
) -> CanonicalIssueSuggestionReviewActionResponse:
    row = _suggestion_row_or_404(session, suggestion_id)
    updated = _set_review_state(session, row=row, review_state="approved", reviewer=reviewer, reason=reason)
    return CanonicalIssueSuggestionReviewActionResponse(suggestion=_serialize_suggestion(session, updated))


def reject_canonical_issue_suggestion_for_ops(
    session: Session,
    *,
    suggestion_id: int,
    reviewer: User,
    reason: str | None,
) -> CanonicalIssueSuggestionReviewActionResponse:
    row = _suggestion_row_or_404(session, suggestion_id)
    updated = _set_review_state(session, row=row, review_state="rejected", reviewer=reviewer, reason=reason)
    return CanonicalIssueSuggestionReviewActionResponse(suggestion=_serialize_suggestion(session, updated))


def ignore_canonical_issue_suggestion_for_ops(
    session: Session,
    *,
    suggestion_id: int,
    reviewer: User,
    reason: str | None,
) -> CanonicalIssueSuggestionReviewActionResponse:
    row = _suggestion_row_or_404(session, suggestion_id)
    updated = _set_review_state(session, row=row, review_state="ignored", reviewer=reviewer, reason=reason)
    return CanonicalIssueSuggestionReviewActionResponse(suggestion=_serialize_suggestion(session, updated))


def list_canonical_issue_suggestions_for_ops(
    session: Session,
    *,
    review_state: str = "all",
    confidence_bucket: str = "all",
    suggestion_type: str = "all",
) -> CanonicalIssueSuggestionOpsListResponse:
    stmt = select(CanonicalIssueLinkSuggestion).order_by(
        CanonicalIssueLinkSuggestion.deterministic_score.desc(),
        CanonicalIssueLinkSuggestion.id.asc(),
    )
    if review_state != "all":
        stmt = stmt.where(CanonicalIssueLinkSuggestion.review_state == review_state)
    if confidence_bucket != "all":
        stmt = stmt.where(CanonicalIssueLinkSuggestion.confidence_bucket == confidence_bucket)
    if suggestion_type != "all":
        stmt = stmt.where(CanonicalIssueLinkSuggestion.suggestion_type == suggestion_type)
    rows = session.exec(stmt).all()
    emails = _reviewer_email_map(session, {row.reviewed_by_user_id for row in rows if row.reviewed_by_user_id is not None})
    return CanonicalIssueSuggestionOpsListResponse(
        suggestions=[_serialize_suggestion(session, row, reviewer_emails=emails) for row in rows],
        review_state=review_state,  # type: ignore[arg-type]
        confidence_bucket=confidence_bucket,  # type: ignore[arg-type]
        suggestion_type=suggestion_type,  # type: ignore[arg-type]
    )
