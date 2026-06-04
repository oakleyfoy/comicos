from pathlib import Path


def test_diagnose_signal_bucket_script_exists() -> None:
    path = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_recommendation_signal_bucket.py"
    source = path.read_text(encoding="utf-8")
    assert "diagnose_title_signal_buckets" in source
    assert "aggregate_bucket_counts" in source
    assert "--top" in source
    assert "--title" in source
    assert "--strict-title" in source
    assert "--include-books" in source
    assert "generate_cross_system_recommendations" not in source
    assert "--perf-audit" in source
    assert "performance" in source
    assert "fetch_stored_recommendation_by_title" in source
    assert "list_latest_cross_system_recommendations" not in source
