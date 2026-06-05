from __future__ import annotations

from datetime import date
from pathlib import Path

from app.services.external_catalog.locg_spreadsheet_certification import (
    SPREADSHEET_EXPECTED_COUNT,
    _normalize_title,
    certify_against_spreadsheet,
    extract_list_row_titles,
    extract_parent_issue_titles,
    spreadsheet_paths_for_date,
)


def test_normalize_title_strips_variant_noise() -> None:
    assert _normalize_title("Absolute Catwoman #1  Cover A") == _normalize_title(
        "absolute catwoman #1 cover a"
    )


def test_extract_parent_issue_titles_only_parent_rows() -> None:
    html = """
    <li class="issue" data-parent="0">
      <div class="title color-primary" data-sorting="Alpha #1">
        <a>Alpha #1</a>
      </div>
    </li>
    <li class="issue variant" data-parent="99">
      <div class="title" data-sorting="Alpha #1 Variant B">
        <a>Alpha #1 <span class="variant-name"> Variant B</span></a>
      </div>
    </li>
    """
    parents = extract_parent_issue_titles(html)
    assert parents == ["Alpha #1"]


def test_extract_list_row_titles_from_fixture_snippet() -> None:
    html = """
    <ul id="comic-list-issues">
    <li class="issue" data-comic="1" data-parent="0">
      <div class="title"><a href="/comic/1/foo">Alpha #1</a></div>
    </li>
    <li class="issue variant" data-comic="2" data-parent="1">
      <div class="title"><a href="/comic/1/foo?variant=2">Alpha #1 <span class="variant-name"> Variant B</span></a></div>
    </li>
    </ul>
    """
    titles = extract_list_row_titles(html)
    assert "Alpha #1" in titles
    assert len(titles) == 2


def test_certify_fails_without_spreadsheet(tmp_path: Path) -> None:
    html = "<ul><li class=\"issue\" data-parent=\"0\"><div class=\"title\"><a>X #1</a></div></li></ul>"
    result = certify_against_spreadsheet(
        html=html,
        page_date=date(2026, 6, 10),
        audit_total_li=230,
        audit_parent=10,
        audit_variant=220,
        audit_other=0,
        list_variants_persisted=100,
        spreadsheet_path=tmp_path / "missing.xlsx",
        repo_root=tmp_path,
    )
    assert not result.passed
    assert result.spreadsheet_expected_count == SPREADSHEET_EXPECTED_COUNT


def test_spreadsheet_path_candidates_include_6_10_26() -> None:
    paths = spreadsheet_paths_for_date(date(2026, 6, 10), repo_root=Path("C:/comic-os-p41-feed"))
    assert any("6-10-26.xlsx" in str(p) for p in paths)
