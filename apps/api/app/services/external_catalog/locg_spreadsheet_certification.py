"""Optional match against shop/distributor spreadsheets — not LoCG capture PASS/FAIL."""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

SPREADSHEET_EXPECTED_COUNT = 234
PASS_MIN_TOTAL_LI_ROWS = 230
PASS_MIN_MATCH_PERCENT = 99.0

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


@dataclass
class SpreadsheetCertificationResult:
    passed: bool = False
    spreadsheet_path: str | None = None
    spreadsheet_expected_count: int = SPREADSHEET_EXPECTED_COUNT
    spreadsheet_title_count: int = 0
    discovered_title_count: int = 0
    matched_count: int = 0
    match_percent: float = 0.0
    missing_from_discovery: list[str] = field(default_factory=list)
    extra_in_discovery: list[str] = field(default_factory=list)
    list_variants_persisted: int | None = None
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "spreadsheet_path": self.spreadsheet_path,
            "spreadsheet_expected_count": self.spreadsheet_expected_count,
            "spreadsheet_title_count": self.spreadsheet_title_count,
            "discovered_title_count": self.discovered_title_count,
            "matched_count": self.matched_count,
            "match_percent": self.match_percent,
            "missing_from_discovery": self.missing_from_discovery,
            "extra_in_discovery": self.extra_in_discovery[:50],
            "list_variants_persisted": self.list_variants_persisted,
            "failure_reasons": self.failure_reasons,
        }


def spreadsheet_paths_for_date(page_date: date, repo_root: Path | None = None) -> list[Path]:
    root = repo_root or Path(__file__).resolve().parents[5]
    iso = page_date.isoformat()
    mm, dd, yy = f"{page_date.month:02d}", f"{page_date.day:02d}", str(page_date.year)[2:]
    names = [
        f"{mm}-{dd}-{yy}.xlsx",
        f"6-10-26.xlsx",
        f"{page_date.month}-{page_date.day}-{yy}.xlsx",
    ]
    dirs = [
        root / "data" / "locg_browser_capture" / iso,
        root / "data" / "locg_browser_capture",
        root,
    ]
    out: list[Path] = []
    for d in dirs:
        for name in names:
            p = d / name
            if p not in out:
                out.append(p)
    return out


def resolve_spreadsheet_path(page_date: date, repo_root: Path | None = None) -> Path | None:
    for path in spreadsheet_paths_for_date(page_date, repo_root=repo_root):
        if path.is_file():
            return path
    return None


def _normalize_title(title: str) -> str:
    import html as html_module
    import unicodedata

    t = html_module.unescape(title or "")
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("…", "...").replace("–", "-").replace("—", "-")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()
    t = re.sub(r"[^a-z0-9#]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _title_from_issue_block(block: str) -> str | None:
    """Prefer data-sorting (full release line); fallback to visible title link text."""
    sort_m = re.search(r'data-sorting="([^"]*)"', block, re.IGNORECASE)
    if sort_m:
        title = sort_m.group(1).strip()
        if title:
            return title
    match = re.search(
        r'<div class="title[^"]*"[^>]*>\s*<a[^>]*>(.*?)</a>',
        block,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None
    raw = match.group(1)
    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", raw)).strip()
    return title or None


def extract_parent_issue_titles(html: str) -> list[str]:
    """Titles from parent rows only (data-parent=\"0\"), using data-sorting when present."""
    titles: list[str] = []
    parent_li = re.compile(
        r'<li[^>]*\bissue\b[^>]*\bdata-parent="0"[^>]*>.*?</li>',
        re.IGNORECASE | re.DOTALL,
    )
    for block in parent_li.finditer(html):
        title = _title_from_issue_block(block.group(0))
        if title:
            titles.append(title)
    return titles


def extract_list_row_titles(html: str) -> list[str]:
    titles: list[str] = []
    li_pattern = re.compile(
        r"<li[^>]*\bissue\b[^>]*>.*?</li>",
        re.IGNORECASE | re.DOTALL,
    )
    for block in li_pattern.finditer(html):
        title = _title_from_issue_block(block.group(0))
        if title:
            titles.append(title)
    if not titles:
        for sort_m in re.finditer(r'data-sorting="([^"]+)"', html, re.IGNORECASE):
            title = sort_m.group(1).strip()
            if title and "/comic/" not in title:
                titles.append(title)
    return titles


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        data = zf.read("xl/sharedStrings.xml")
    except KeyError:
        return []
    root = ET.fromstring(data)
    strings: list[str] = []
    for si in root.findall(".//m:si", _NS):
        parts = [t.text or "" for t in si.findall(".//m:t", _NS)]
        strings.append("".join(parts).strip())
    return strings


def _xlsx_cell_value(cell: ET.Element, shared: list[str]) -> str:
    cell_type = cell.get("t")
    value_el = cell.find("m:v", _NS)
    if value_el is None or value_el.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared[int(value_el.text)].strip()
        except (IndexError, ValueError):
            return ""
    return value_el.text.strip()


def load_spreadsheet_titles(path: Path) -> list[str]:
    titles: list[str] = []
    with zipfile.ZipFile(path) as zf:
        shared = _xlsx_shared_strings(zf)
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in zf.namelist():
            for name in zf.namelist():
                if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                    sheet_name = name
                    break
        root = ET.fromstring(zf.read(sheet_name))
        rows = root.findall(".//m:sheetData/m:row", _NS)
        title_col = 0
        data_start = 0

        def _row_values(row_el: ET.Element) -> list[str]:
            cells = row_el.findall("m:c", _NS)
            values: list[str] = []
            for cell in cells:
                ref = cell.get("r", "")
                col = re.match(r"([A-Z]+)", ref)
                col_idx = 0
                if col:
                    letters = col.group(1)
                    for ch in letters:
                        col_idx = col_idx * 26 + (ord(ch) - ord("A") + 1)
                    col_idx -= 1
                while len(values) <= col_idx:
                    values.append("")
                values[col_idx] = _xlsx_cell_value(cell, shared)
            return values

        if rows:
            first = _row_values(rows[0])
            header_like = any(
                (v or "").strip().lower() in {"title", "name", "issue", "series", "product", "description"}
                for v in first
            )
            if header_like:
                data_start = 1
                for idx, name in enumerate((v or "").strip().lower() for v in first):
                    if name in {"title", "name", "issue", "series", "product", "description"}:
                        title_col = idx
                        break

        for row in rows[data_start:]:
            values = _row_values(row)
            if title_col < len(values):
                title = values[title_col].strip()
                if title and title.lower() not in {"title", "name"}:
                    titles.append(title)
    return titles


def certify_against_spreadsheet(
    *,
    html: str,
    page_date: date,
    audit_total_li: int,
    audit_parent: int,
    audit_variant: int,
    audit_other: int,
    list_variants_persisted: int | None,
    spreadsheet_path: Path | None = None,
    repo_root: Path | None = None,
) -> SpreadsheetCertificationResult:
    from app.services.external_catalog.locg_list_discovery import (
        validate_discovery_reconciliation,
    )
    from app.services.external_catalog.locg_list_discovery import ListDiscoveryAudit

    result = SpreadsheetCertificationResult(list_variants_persisted=list_variants_persisted)
    path = spreadsheet_path or resolve_spreadsheet_path(page_date, repo_root=repo_root)
    if path is None:
        result.failure_reasons.append(
            "spreadsheet not found (expected 6-10-26.xlsx under data/locg_browser_capture/2026-06-10/)"
        )
        result.passed = False
        return result
    result.spreadsheet_path = str(path)

    try:
        sheet_titles = load_spreadsheet_titles(path)
    except Exception as exc:  # noqa: BLE001
        result.failure_reasons.append(f"spreadsheet read failed: {exc}")
        return result

    result.spreadsheet_title_count = len(sheet_titles)
    discovered_all = extract_list_row_titles(html)
    discovered_parents = extract_parent_issue_titles(html)
    result.discovered_title_count = len(discovered_parents) or len(discovered_all)

    sheet_norm = {_normalize_title(t): t for t in sheet_titles if _normalize_title(t)}
    disc_norm = {_normalize_title(t): t for t in discovered_all if _normalize_title(t)}
    parent_norm = {_normalize_title(t): t for t in discovered_parents if _normalize_title(t)}

    disc_keys = set(disc_norm.keys()) | set(parent_norm.keys())
    matched_keys: set[str] = set()
    for key in sheet_norm.keys():
        if key in disc_keys:
            matched_keys.add(key)
            continue
        if key in parent_norm:
            matched_keys.add(key)
            continue
        prefix = key + " "
        if any(dk.startswith(prefix) for dk in disc_keys):
            matched_keys.add(key)
            continue
        if any(key in dk for dk in disc_keys if len(key) >= 10):
            matched_keys.add(key)
    result.matched_count = len(matched_keys)
    if sheet_norm:
        result.match_percent = round(100.0 * result.matched_count / len(sheet_norm), 2)
    elif sheet_titles:
        result.match_percent = 0.0
    else:
        result.match_percent = 0.0

    for key, original in sorted(sheet_norm.items()):
        if key not in disc_norm:
            result.missing_from_discovery.append(original)
    for key, original in sorted(disc_norm.items()):
        if key not in sheet_norm:
            result.extra_in_discovery.append(original)

    recon_audit = ListDiscoveryAudit(
        total_li_issue_rows=audit_total_li,
        parent_issue_rows=audit_parent,
        variant_rows=audit_variant,
        other_release_rows=audit_other,
        total_release_rows_reconciled=audit_parent + audit_variant + audit_other,
    )
    try:
        validate_discovery_reconciliation(recon_audit)
    except RuntimeError as exc:
        result.failure_reasons.append(str(exc))

    if audit_total_li < PASS_MIN_TOTAL_LI_ROWS:
        result.failure_reasons.append(
            f"total_li_issue_rows {audit_total_li} < {PASS_MIN_TOTAL_LI_ROWS}"
        )
    if result.match_percent < PASS_MIN_MATCH_PERCENT:
        result.failure_reasons.append(
            f"spreadsheet match {result.match_percent}% < {PASS_MIN_MATCH_PERCENT}%"
        )
    if list_variants_persisted is None:
        result.failure_reasons.append("list_variants_persisted not recorded")
    elif list_variants_persisted < 1 and audit_variant > 0:
        result.failure_reasons.append("list_variants_persisted is zero but variant rows exist")

    result.passed = len(result.failure_reasons) == 0
    return result


def save_certification_report(result: SpreadsheetCertificationResult, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        __import__("json").dumps(result.to_dict(), indent=2),
        encoding="utf-8",
    )


def print_certification_summary(result: SpreadsheetCertificationResult) -> None:
    print("\n--- Spreadsheet certification (6-10-26) ---", flush=True)
    print(f"Spreadsheet: {result.spreadsheet_path}", flush=True)
    print(f"Expected count: {result.spreadsheet_expected_count}", flush=True)
    print(f"Spreadsheet titles loaded: {result.spreadsheet_title_count}", flush=True)
    print(f"Discovered list titles: {result.discovered_title_count}", flush=True)
    print(f"Matched: {result.matched_count} ({result.match_percent}%)", flush=True)
    print(f"list_variants_persisted: {result.list_variants_persisted}", flush=True)
    print(f"PASS: {result.passed}", flush=True)
    if result.failure_reasons:
        print("Failure reasons:", flush=True)
        for reason in result.failure_reasons:
            print(f"  - {reason}", flush=True)
    if result.missing_from_discovery and result.match_percent < PASS_MIN_MATCH_PERCENT:
        print("Missing titles (spreadsheet not in discovery):", flush=True)
        for title in result.missing_from_discovery[:100]:
            print(f"  - {title}", flush=True)
        if len(result.missing_from_discovery) > 100:
            print(f"  ... and {len(result.missing_from_discovery) - 100} more", flush=True)
