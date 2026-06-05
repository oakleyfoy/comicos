from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.external_catalog.locg_spreadsheet_certification import (
    _normalize_title,
    extract_list_row_titles,
    extract_parent_issue_titles,
    load_spreadsheet_titles,
)
import re
import zipfile
import xml.etree.ElementTree as ET
from app.services.external_catalog.locg_spreadsheet_certification import _NS, _xlsx_cell_value, _xlsx_shared_strings

xlsx = Path(ROOT).parent.parent / "data/locg_browser_capture/2026-06-10/6-10-26.xlsx"
html_path = Path(ROOT).parent.parent / "data/locg_browser_capture/2026-06-10/list_page.html"
html = html_path.read_text(encoding="utf-8")

print("=== XLSX first 3 rows all columns ===")
with zipfile.ZipFile(xlsx) as zf:
    shared = _xlsx_shared_strings(zf)
    root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    for i, row in enumerate(root.findall(".//m:sheetData/m:row", _NS)[:4]):
        vals = [_xlsx_cell_value(c, shared) for c in row.findall("m:c", _NS)]
        print(i, vals)

sheet = load_spreadsheet_titles(xlsx)
disc = extract_list_row_titles(html)
parents = extract_parent_issue_titles(html)

print("\n=== Title source (LoCG) ===")
print("Uses data-sorting on each <li.issue> block (full release line, not URL slug).")
print("Parent rows: data-parent=\"0\". Variant rows: longer data-sorting with variant/cover text.")

print("\n=== First 20 spreadsheet normalized ===")
for t in sheet[:20]:
    print(_normalize_title(t))

print("\n=== First 20 LoCG parent-issue normalized (data-parent=0) ===")
for t in parents[:20]:
    print(_normalize_title(t), "| raw:", t[:70])

print("\n=== First 20 LoCG all-row normalized (incl. variants) ===")
for t in disc[:20]:
    print(_normalize_title(t), "| raw:", t[:70])

print("\n=== Unique normalized discovered count ===", len({_normalize_title(t) for t in disc}))

# data-sorting attribute
sorting = []
for block in re.finditer(r'<li class="issue[^>]*>.*?</li>', html, re.I | re.S):
    m = re.search(r'data-sorting="([^"]*)"', block.group(0), re.I)
    if m:
        sorting.append(m.group(1).strip())
print("\n=== First 20 data-sorting normalized ===")
for t in sorting[:20]:
    print(_normalize_title(t))

# overlap test with sorting
sn = {_normalize_title(t): t for t in sheet if _normalize_title(t)}
dn = {_normalize_title(t): t for t in sorting if _normalize_title(t)}
print("\nmatch sorting vs sheet:", len(sn.keys() & dn.keys()), "of", len(sn))
