import re
from pathlib import Path

h = Path(r"C:\comic-os-p41-feed\data\locg_browser_capture\2026-06-10\list_page.html").read_text(
    encoding="utf-8"
)
total = len(re.findall(r'<li class="issue', h, re.I))
parent = sum(
    1
    for m in re.finditer(r'<li class="issue[^"]*"[^>]*data-parent="(\d+)"', h, re.I)
    if m.group(1) == "0"
)
variant = sum(
    1
    for m in re.finditer(r'<li class="issue[^"]*"[^>]*data-parent="(\d+)"', h, re.I)
    if m.group(1) != "0"
)
visible = 0
for m in re.finditer(r'<li class="issue([^"]*)"[^>]*data-parent="(\d+)"', h, re.I):
    if "hidden" not in m.group(1):
        visible += 1
print("total_li", total)
print("parent", parent)
print("variant", variant)
print("visible_li_not_hidden", visible)
