from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KeyIssueCatalogEntry:
    series_name: str
    issue_number: str
    publisher: str
    key_issue_type: str
    classification: str
    importance_score: float
    confidence_score: float
    title_hint: str = ""


CANONICAL_KEY_ISSUE_CATALOG: tuple[KeyIssueCatalogEntry, ...] = (
    KeyIssueCatalogEntry("Amazing Fantasy", "15", "Marvel", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 99.0, 0.98),
    KeyIssueCatalogEntry("Teenage Mutant Ninja Turtles", "1", "Mirage", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 96.0, 0.95),
    KeyIssueCatalogEntry("TMNT", "1", "IDW", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 94.0, 0.92),
    KeyIssueCatalogEntry("Spawn", "1", "Image", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 95.0, 0.94),
    KeyIssueCatalogEntry("Batman", "404", "DC", "ORIGIN", "ORIGIN", 92.0, 0.93),
    KeyIssueCatalogEntry("Batman", "608", "DC", "MAJOR_STATUS_CHANGE", "MAJOR_STATUS_CHANGE", 90.0, 0.91, title_hint="Under the Hood"),
    KeyIssueCatalogEntry("The Walking Dead", "1", "Image", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 94.0, 0.93),
    KeyIssueCatalogEntry("Invincible", "1", "Image", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 93.0, 0.92),
    KeyIssueCatalogEntry("Ultimate Spider-Man", "1", "Marvel", "UNIVERSE_LAUNCH", "UNIVERSE_LAUNCH", 91.0, 0.9),
    KeyIssueCatalogEntry("Transformers", "1", "Marvel", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 88.0, 0.89),
    KeyIssueCatalogEntry("GI Joe", "1", "Marvel", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 86.0, 0.88),
    KeyIssueCatalogEntry("GI Joe", "25", "Marvel", "MILESTONE_NUMBERING", "MILESTONE_NUMBERING", 84.0, 0.87),
    KeyIssueCatalogEntry("Detective Comics", "27", "DC", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 100.0, 0.99),
    KeyIssueCatalogEntry("Action Comics", "1", "DC", "FIRST_APPEARANCE", "FIRST_APPEARANCE", 100.0, 0.99),
    KeyIssueCatalogEntry("Teenage Mutant Ninja Turtles", "300", "IDW", "MILESTONE_NUMBERING", "MILESTONE_NUMBERING", 89.0, 0.9),
    KeyIssueCatalogEntry("TMNT", "300", "IDW", "MILESTONE_NUMBERING", "MILESTONE_NUMBERING", 89.0, 0.9),
)

MILESTONE_ISSUE_NUMBERS = frozenset({"25", "50", "75", "100", "150", "200", "250", "300", "400", "500", "1000"})
