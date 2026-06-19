"""P100-24 vision sandbox accuracy reporting."""

from __future__ import annotations

from collections import Counter

from sqlmodel import Session, func, select

from app.models.photo_import_vision_read import PhotoImportVisionRead


def build_vision_sandbox_accuracy_report(session: Session) -> dict[str, object]:
    rows = list(session.exec(select(PhotoImportVisionRead)).all())
    total_reads = len(rows)
    rated = [r for r in rows if r.is_correct is not None]
    correct_reads = sum(1 for r in rated if r.is_correct is True)
    incorrect_reads = sum(1 for r in rated if r.is_correct is False)
    accuracy_percent = round(100.0 * correct_reads / len(rated), 1) if rated else 0.0

    def field_rate(field: str) -> float:
        """Share of rated reads marked correct (proxy until per-field feedback exists)."""
        return accuracy_percent

    incorrect = [r for r in rated if r.is_correct is False]
    series_counter: Counter[str] = Counter()
    publisher_counter: Counter[str] = Counter()
    failure_rows: list[dict[str, object]] = []
    for r in incorrect:
        series_key = (r.series or "Unknown series").strip()
        pub_key = (r.publisher or "Unknown publisher").strip()
        series_counter[series_key] += 1
        publisher_counter[pub_key] += 1
        failure_rows.append(
            {
                "read_id": r.id,
                "image_id": r.image_id,
                "publisher": r.publisher,
                "series": r.series,
                "issue_number": r.issue_number,
                "feedback_notes": r.feedback_notes,
            }
        )

    top_failures = failure_rows[:25]
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
        "publisher_accuracy": field_rate("publisher"),
        "series_accuracy": field_rate("series"),
        "issue_accuracy": field_rate("issue"),
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
