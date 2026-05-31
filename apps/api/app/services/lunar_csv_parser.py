from __future__ import annotations

import csv
import io


def parse_lunar_product_csv(content: bytes | str) -> list[dict[str, str]]:
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig")
    else:
        text = content
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    rows: list[dict[str, str]] = []
    for row in reader:
        normalized = {str(key).strip(): (value or "").strip() for key, value in row.items() if key}
        if any(normalized.values()):
            rows.append(normalized)
    return rows


def row_product_code(row: dict[str, str]) -> str:
    for key in ("MainIdentifier", "Product Code", "ProductCode", "Code", "ItemCode"):
        if row.get(key):
            return row[key]
    return ""
