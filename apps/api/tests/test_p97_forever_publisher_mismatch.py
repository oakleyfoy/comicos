"""Rules mirrored from Test-ForeverPublisherMismatchOnlyChunk in overnight runner."""

ISSUE_IMPORT_ERROR = "ERROR: --import-issues requested but no issue import phase ran."


def is_publisher_mismatch_only_chunk(
    *,
    throttled: bool,
    imported_series: int,
    accepted_volumes: int,
    issues_created: int,
    issues_updated: int,
    skipped_publisher: int,
    total_candidates_seen: int,
    exit_code: int = 3,
    output_lines: list[str] | None = None,
    failures: int = 0,
) -> bool:
    if throttled:
        return False
    if failures > 0:
        return False
    blob = "\n".join(output_lines or [])
    if "Traceback (most recent call last)" in blob:
        return False
    if imported_series > 0 or accepted_volumes > 0:
        return False
    if issues_created > 0 or issues_updated > 0:
        return False
    mismatch_lines = sum(1 for line in (output_lines or []) if "STRICT_PUBLISHER_MISMATCH" in line)
    skipped = skipped_publisher if skipped_publisher > 0 else mismatch_lines
    seen = total_candidates_seen if total_candidates_seen > 0 else skipped
    if skipped <= 0 or seen <= 0:
        return False
    if exit_code == 3:
        if "STRICT_PUBLISHER_MISMATCH" not in blob:
            return False
        if "no issue import phase ran" not in blob.lower():
            return False
        return True
    if exit_code != 0:
        return False
    return True


def _mismatch_stderr() -> list[str]:
    return [
        "skipped_publisher=100",
        "total_candidates_seen=100",
        "imported_series=0",
        "accepted_volumes=0",
        "issues_created=0",
        "issues_updated=0",
        "INFO comicvine skip volume_id=1 reason=STRICT_PUBLISHER_MISMATCH",
        ISSUE_IMPORT_ERROR,
    ]


def test_mismatch_only_detected_exit_3() -> None:
    assert is_publisher_mismatch_only_chunk(
        exit_code=3,
        throttled=False,
        imported_series=0,
        accepted_volumes=0,
        issues_created=0,
        issues_updated=0,
        skipped_publisher=100,
        total_candidates_seen=100,
        output_lines=_mismatch_stderr(),
    )


def test_mismatch_only_detected_exit_0() -> None:
    assert is_publisher_mismatch_only_chunk(
        exit_code=0,
        throttled=False,
        imported_series=0,
        accepted_volumes=0,
        issues_created=0,
        issues_updated=0,
        skipped_publisher=50,
        total_candidates_seen=50,
    )


def test_exit_3_without_strict_mismatch_string_not_mismatch_only() -> None:
    assert not is_publisher_mismatch_only_chunk(
        exit_code=3,
        throttled=False,
        imported_series=0,
        accepted_volumes=0,
        issues_created=0,
        issues_updated=0,
        skipped_publisher=100,
        total_candidates_seen=100,
        output_lines=[ISSUE_IMPORT_ERROR],
    )


def test_zero_candidates_not_mismatch_only() -> None:
    assert not is_publisher_mismatch_only_chunk(
        exit_code=3,
        throttled=False,
        imported_series=0,
        accepted_volumes=0,
        issues_created=0,
        issues_updated=0,
        skipped_publisher=0,
        total_candidates_seen=0,
        output_lines=[ISSUE_IMPORT_ERROR],
    )


def test_imported_series_not_mismatch_only() -> None:
    assert not is_publisher_mismatch_only_chunk(
        exit_code=0,
        throttled=False,
        imported_series=1,
        accepted_volumes=1,
        issues_created=0,
        issues_updated=0,
        skipped_publisher=0,
        total_candidates_seen=10,
    )


def test_true_api_failure_not_mismatch_only() -> None:
    assert not is_publisher_mismatch_only_chunk(
        exit_code=3,
        throttled=False,
        imported_series=0,
        accepted_volumes=0,
        issues_created=0,
        issues_updated=0,
        skipped_publisher=100,
        total_candidates_seen=100,
        failures=2,
        output_lines=_mismatch_stderr(),
    )
