"""ComicVine on-demand volume selection for photo import."""

from __future__ import annotations

from app.services.photo_import_comicvine_ondemand_service import select_comicvine_volume_id


def test_selects_falcon_2017_over_1983() -> None:
    candidates = [
        {"id": 3223, "name": "The Falcon", "start_year": 1983, "publisher": {"name": "Marvel"}, "count_of_issues": 4},
        {"id": 104938, "name": "Falcon", "start_year": 2017, "publisher": {"name": "Marvel"}, "count_of_issues": 8},
    ]
    vid = select_comicvine_volume_id(candidates, series="Falcon", issue_number="1", year=2017)
    assert vid == 104938


def test_rejects_wrong_era_when_gpt_has_year() -> None:
    candidates = [
        {"id": 3223, "name": "The Falcon", "start_year": 1983, "publisher": {"name": "Marvel"}, "count_of_issues": 4},
    ]
    vid = select_comicvine_volume_id(candidates, series="Falcon", issue_number="1", year=2017)
    assert vid is None


def test_falcon_without_the_matches_the_falcon() -> None:
    candidates = [
        {"id": 104938, "name": "Falcon", "start_year": 2017, "publisher": {"name": "Marvel"}, "count_of_issues": 8},
    ]
    vid = select_comicvine_volume_id(candidates, series="The Falcon", issue_number="1", year=2017)
    assert vid == 104938
