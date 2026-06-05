from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.external_catalog.locg_spreadsheet_certification import (
    load_spreadsheet_titles,
    extract_list_row_titles,
    _normalize_title,
)

html_path = ROOT.parent.parent / "data/locg_browser_capture/2026-06-10/list_page.html"
xlsx = ROOT.parent.parent / "data/locg_browser_capture/2026-06-10/6-10-26.xlsx"
html = html_path.read_text(encoding="utf-8")
sheet = load_spreadsheet_titles(xlsx)
disc = extract_list_row_titles(html)
parents = []
for m in re.finditer(r'<li class="issue[^"]*"[^>]*data-parent="0"[^>]*>.*?</li>', html, re.I | re.S):
    sm = re.search(r'data-sorting="([^"]*)"', m.group(0), re.I)
    if sm:
        parents.append(sm.group(1).strip())
sn = {_normalize_title(t) for t in sheet}
pn = {_normalize_title(t) for t in parents}
dn = {_normalize_title(t) for t in disc}
print("sheet", len(sheet), "parents", len(parents), "disc", len(disc))
print("exact parent match", len(sn & pn))
print("exact any-row match", len(sn & dn))
# prefix: sheet norm in any disc norm
prefix = sum(1 for s in sn if any(s in d or d.startswith(s) for d in dn))
print("prefix/substring hits", prefix)
for t in sheet[:8]:
    n = _normalize_title(t)
    if n in dn:
        print("exact", t)
    else:
        hits = [d for d in dn if n in d or d.startswith(n)]
        print(t, "hits", len(hits), list(hits)[:1])
