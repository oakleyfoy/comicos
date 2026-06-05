import re
import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

import httpx
from app.services.external_catalog.locg_list_discovery import audit_list_html

base = "https://leagueofcomicgeeks.com/comic/get_comics"
common = {
    "list": "releases",
    "date_type": "week",
    "date": "2026-06-10",
    "date_end": "",
    "series_id": "0",
    "character": "",
    "user": "0",
    "search": "",
    "list_option": "",
}
client = httpx.Client(
    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124"},
    timeout=30,
    follow_redirects=True,
)
for view in ["", "thumbs", "list", "text"]:
    chunks = []
    offset = 0
    for _ in range(20):
        p = dict(common)
        p["list_offset"] = str(offset)
        if view:
            p["view"] = view
        r = client.get(base, params=p)
        if r.status_code != 200:
            print(view or "default", "status", r.status_code, r.text[:200])
            break
        try:
            data = r.json()
        except Exception as exc:
            print(view or "default", "json error", exc)
            break
        html = data.get("list", "") if isinstance(data, dict) else ""
        if not html:
            break
        chunks.append(html)
        n = len(re.findall(r'<li class="issue', html, re.I))
        offset += n
        if n == 0:
            break
    full = "".join(chunks)
    a = audit_list_html(full or "<html></html>", page_url="x")
    print(
        f"view={view or 'default':8} pages={len(chunks):2} "
        f"total={a.total_li_issue_rows:4} parent={a.parent_issue_rows:4} variant={a.variant_rows:4}"
    )
client.close()
