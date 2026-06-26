from app.services.p103_gcd_enrichment_audit_helpers import (
    build_overall_assertion_failures,
    chunk_ids,
    resolve_job_upc_audit_fields,
)


def test_chunk_ids_batches() -> None:
    assert list(chunk_ids(list(range(1200)), 500)) == [
        list(range(0, 500)),
        list(range(500, 1000)),
        list(range(1000, 1200)),
    ]


def test_build_overall_assertion_failures_lists_each_failure() -> None:
    fails = build_overall_assertion_failures(
        report_counts_ok=False,
        report_failures=["written_rows 1 != updated_issues 2"],
        issues_found_in_db=2500,
        expected_updated=2500,
        expected_inserted_upcs=0,
        job_inserted_upc_count=0,
        tracks_job_upc_inserts=True,
        barcode_pass=False,
        barcode_tests=[
            {
                "pass": False,
                "barcode": "123",
                "expected_catalog_issue_id": 1,
                "lookup_issue_id": None,
                "lookup_method": "none",
            }
        ],
        error_count=30,
    )
    assert any("report_counts_ok" in line for line in fails)
    assert any("barcode_lookup_pass" in line for line in fails)
    assert any("error_count" in line for line in fails)
    assert not any("issues_found_in_db mismatch" in line for line in fails)
    assert not any("existing_or_present" in line for line in fails)
    assert not any("pilot_gcd_upc_count" in line for line in fails)


def test_p103_update_only_zero_job_inserts_passes_despite_present_gcd_upcs() -> None:
    """2500 updates, 0 job UPC inserts, many pre-existing GCD UPCs on those issues."""
    fails = build_overall_assertion_failures(
        report_counts_ok=True,
        report_failures=[],
        issues_found_in_db=2500,
        expected_updated=2500,
        expected_inserted_upcs=0,
        job_inserted_upc_count=0,
        tracks_job_upc_inserts=True,
        barcode_pass=True,
        barcode_tests=[],
        error_count=0,
    )
    assert fails == []


def test_job_inserted_upc_count_compared_only_when_tracked() -> None:
    fails = build_overall_assertion_failures(
        report_counts_ok=True,
        report_failures=[],
        issues_found_in_db=10,
        expected_updated=10,
        expected_inserted_upcs=0,
        job_inserted_upc_count=5,
        tracks_job_upc_inserts=True,
        barcode_pass=True,
        barcode_tests=[],
        error_count=0,
    )
    assert any("job_inserted_upc_count mismatch" in line for line in fails)

    fails_untracked = build_overall_assertion_failures(
        report_counts_ok=True,
        report_failures=[],
        issues_found_in_db=10,
        expected_updated=10,
        expected_inserted_upcs=0,
        job_inserted_upc_count=5,
        tracks_job_upc_inserts=False,
        barcode_pass=True,
        barcode_tests=[],
        error_count=0,
    )
    assert fails_untracked == []


def test_resolve_job_upc_audit_fields_uses_rollback_upc_ids() -> None:
    fields = resolve_job_upc_audit_fields(
        {"inserted_upcs": 0, "written_rows": []},
        {"upc_ids": [], "issue_snapshots": [{}]},
    )
    assert fields["tracks_job_upc_inserts"] is True
    assert fields["job_inserted_upc_count"] == 0
    assert fields["expected_inserted_upcs"] == 0
