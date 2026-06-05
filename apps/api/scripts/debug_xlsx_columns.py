import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from app.services.external_catalog.locg_spreadsheet_certification import _NS, _xlsx_cell_value, _xlsx_shared_strings

p = Path(r"C:\comic-os-p41-feed\data\locg_browser_capture\2026-06-10\6-10-26.xlsx")
with zipfile.ZipFile(p) as zf:
    shared = _xlsx_shared_strings(zf)
    root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    for i, row in enumerate(root.findall(".//m:sheetData/m:row", _NS)[:5]):
        vals = [_xlsx_cell_value(c, shared) for c in row.findall("m:c", _NS)]
        print(i, vals)
