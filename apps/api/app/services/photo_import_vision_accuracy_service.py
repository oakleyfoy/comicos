"""P100-24/25 vision sandbox accuracy reporting (GPT fields only, no catalog)."""

from __future__ import annotations

from collections import Counter

from sqlmodel import Session, func, select

from app.models.photo_import_vision_read import PhotoImportVisionRead


def _filled_pct(rows: list[PhotoImportVisionRead], attr: str) -> float:
    if not rows:
        return 0.0
    filled = sum(1 for r in rows if getattr(r, attr, None) not in (None, ""))
    return round(100.0 * filled / len(rows), 1)


def build_vision_sandbox_accuracy_report(session: Session) -> dict[str, object]:
    rows = list(
        session.exec(select(PhotoImportVisionRead).order_by(PhotoImportVisionRead.id.desc())).all()
    )
    total_reads = len(rows)
    rated = [r for r in rows if r.is_correct is not None]
    correct_reads = sum(1 for r in rated if r.is_correct is True)
    incorrect_reads = sum(1 for r in rated if r.is_correct is False)
    accuracy_percent = round(100.0 * correct_reads / len(rated), 1) if rated else 0.0

    confidences = [float(r.confidence) for r in rows if r.confidence is not None]
    average_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

    publisher_filled_percent = _filled_pct(rows, "publisher")
    series_filled_percent = _filled_pct(rows, "series")
    issue_number_filled_percent = _filled_pct(rows, "issue_number")

    incorrect = [r for r in rated if r.is_correct is False]
    series_counter: Counter[str] = Counter()
    publisher_counter: Counter[str] = Counter()
    for r in incorrect:
        series_counter[(r.series or "Unknown series").strip()] += 1
        publisher_counter[(r.publisher or "Unknown publisher").strip()] += 1

    top_uncertain_reads = [
        {
            "read_id": r.id,
            "image_id": r.image_id,
            "series": r.series,
            "issue_number": r.issue_number,
            "confidence": r.confidence,
            "possible_alternates": r.possible_alternates,
        }
        for r in sorted(rows, key=lambda x: float(x.confidence or 0.0))[:15]
    ]

    latest_incorrect_reads = [
        {
            "read_id": r.id,
            "image_id": r.image_id,
            "publisher": r.publisher,
            "series": r.series,
            "issue_number": r.issue_number,
            "feedback_notes": r.feedback_notes,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in incorrect[:25]
    ]

    top_failures = latest_incorrect_reads[:25]
    most_misidentified_series = [
        {"series": name, "count": count} for name, count in series_counter.most_common(15)
    ]
    most_misidentified_publishers = [
        {"publisher": name, "count": count} for name, count in publisher_counter.most_common(15)
    ]

    pending_feedback = total_reads - len(rated)

    return {
        "total_reads": total_reads,
        "correct_reads": correct_reads,
        "incorrect_reads": incorrect_reads,
        "pending_feedback": pending_feedback,
        "accuracy_percent": accuracy_percent,
        "publisher_filled_percent": publisher_filled_percent,
        "series_filled_percent": series_filled_percent,
        "issue_number_filled_percent": issue_number_filled_percent,
        "average_confidence": average_confidence,
        "top_uncertain_reads": top_uncertain_reads,
        "latest_incorrect_reads": latest_incorrect_reads,
        "publisher_accuracy": publisher_filled_percent,
        "series_accuracy": series_filled_percent,
        "issue_accuracy": issue_number_filled_percent,
        "top_failures": top_failures,
        "most_misidentified_series": most_misidentified_series,
        "most_misidentified_publishers": most_misidentified_publishers,
    }


def count_vision_reads_for_session(session: Session, *, session_id: int) -> int:
    return int(
        session.exec(
            select(func.count(PhotoImportVisionRead.id)).where(PhotoImportVisionRead.session_id == session_id)
        ).one()
        or 0
    )
