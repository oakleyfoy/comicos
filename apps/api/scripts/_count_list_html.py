import re
from pathlib import Path

h = Path(r"C:\comic-os-p41-feed\data\locg_browser_capture\2026-06-10\list_page.html").read_text(encoding="utf-8")
print("li issue", len(re.findall(r'<li class="issue', h)))
print("parent0", len(re.findall(r'data-parent="0"', h)))
print("variant-collapsed", len(re.findall(r"variant-collapsed", h)))
print("comic href", len(re.findall(r'href="/comic/', h)))
m = re.search(r'data-list-offset="(\d+)"', h)
print("offset", m.group(1) if m else None)
