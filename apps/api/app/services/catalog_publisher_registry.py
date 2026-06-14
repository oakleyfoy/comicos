from __future__ import annotations

from app.services.catalog_ingestion_service import normalize_series_name

PRIMARY_US_PUBLISHERS = frozenset(
    {
        "Marvel",
        "DC Comics",
        "Image",
        "Dark Horse",
        "BOOM! Studios",
        "IDW Publishing",
        "Dynamite Entertainment",
        "Valiant Entertainment",
        "Skybound",
        "Titan Comics",
        "Oni Press",
        "AfterShock Comics",
        "AWA Studios",
        "Mad Cave Studios",
        "DSTLRY",
    }
)

INTERNATIONAL_LICENSE_PUBLISHERS = frozenset(
    {
        "Panini Comics",
        "Panini Verlag",
        "Delcourt",
        "Abril",
        "Planeta DeAgostini",
        "Planeta",
        "Egmont Comics",
        "Hjemmet",
        "Saldapress",
        "Cross Cult",
        "Mandragora",
        "JuniorPress BV",
        "Europe Comics",
        "Kodansha",
        "Shogakukan",
    }
)

INTERNATIONAL_PUBLISHER_SUBSTRINGS = (
    "panini",
    "delcourt",
    "abril",
    "planeta",
    "egmont",
    "hjemmet",
    "cross cult",
    "saldapress",
)


def _normalized_publisher(name: str) -> str:
    return normalize_series_name(name or "")


def _matches_catalog_name(actual: str, canonical: str) -> bool:
    act = _normalized_publisher(actual)
    can = _normalized_publisher(canonical)
    if not act or not can:
        return False
    if act == can:
        return True
    if act.startswith(f"{can} "):
        return True
    if can.startswith(f"{act} "):
        return True
    if act.startswith(can) and len(act) > len(can) and not act[len(can)].isalnum():
        return True
    return False


def _matches_any(name: str, candidates: frozenset[str]) -> bool:
    return any(_matches_catalog_name(name, candidate) for candidate in candidates)


def is_primary_us_publisher(publisher: str | None) -> bool:
    return _matches_any(publisher or "", PRIMARY_US_PUBLISHERS)


def is_international_publisher(publisher: str | None) -> bool:
    if is_international_license_publisher(publisher):
        return True
    lowered = (publisher or "").lower()
    return any(token in lowered for token in INTERNATIONAL_PUBLISHER_SUBSTRINGS)


def is_international_license_publisher(publisher: str | None) -> bool:
    return _matches_any(publisher or "", INTERNATIONAL_LICENSE_PUBLISHERS)


def publisher_quality_score(publisher: str | None) -> int:
    if is_primary_us_publisher(publisher):
        return 100
    if is_international_publisher(publisher):
        return 0
    return 50
