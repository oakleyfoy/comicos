from __future__ import annotations

from dataclasses import dataclass

INDUSTRY_PUBLISHER_REGISTRY: tuple[tuple[str, str, int], ...] = (
    ("MARVEL", "Marvel", 10),
    ("DC", "DC", 20),
    ("IMAGE", "Image", 30),
    ("BOOM", "Boom", 40),
    ("DARK_HORSE", "Dark Horse", 50),
    ("IDW", "IDW", 60),
    ("DYNAMITE", "Dynamite", 70),
    ("MAD_CAVE", "Mad Cave", 80),
    ("ONI", "Oni", 90),
    ("MASSIVE", "Massive", 100),
)


@dataclass(frozen=True)
class IndustryPublisherSeedDefinition:
    publisher_code: str
    publisher_name: str
    scan_priority: int
