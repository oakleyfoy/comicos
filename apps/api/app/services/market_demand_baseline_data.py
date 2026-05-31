from __future__ import annotations

# Deterministic P51-03 market demand baselines (no external APIs).
# Tuple: entity_type, entity_name, demand_score, liquidity, long_term, volatility
MARKET_DEMAND_BASELINES: tuple[tuple[str, str, float, float, float, float], ...] = (
    ("FRANCHISE", "Batman", 94.0, 88.0, 92.0, 35.0),
    ("FRANCHISE", "Spider-Man", 93.0, 90.0, 91.0, 38.0),
    ("FRANCHISE", "Teenage Mutant Ninja Turtles", 86.0, 82.0, 85.0, 42.0),
    ("FRANCHISE", "TMNT", 86.0, 82.0, 85.0, 42.0),
    ("FRANCHISE", "Invincible", 78.0, 72.0, 80.0, 55.0),
    ("FRANCHISE", "Transformers", 84.0, 80.0, 83.0, 45.0),
    ("FRANCHISE", "G.I. Joe", 80.0, 76.0, 79.0, 48.0),
    ("FRANCHISE", "GI Joe", 80.0, 76.0, 79.0, 48.0),
    ("CHARACTER", "Venom", 88.0, 85.0, 86.0, 50.0),
    ("CHARACTER", "Wolverine", 90.0, 87.0, 89.0, 44.0),
    ("CHARACTER", "Deadpool", 89.0, 88.0, 85.0, 52.0),
    ("FRANCHISE", "X-Men", 91.0, 86.0, 90.0, 46.0),
    ("FRANCHISE", "Spawn", 83.0, 78.0, 82.0, 58.0),
    ("FRANCHISE", "Star Wars", 87.0, 84.0, 86.0, 40.0),
    ("FRANCHISE", "Power Rangers", 75.0, 70.0, 74.0, 50.0),
    ("FRANCHISE", "Gargoyles", 72.0, 68.0, 73.0, 48.0),
    ("CHARACTER", "Vampirella", 70.0, 65.0, 71.0, 55.0),
    ("CHARACTER", "Red Sonja", 69.0, 64.0, 70.0, 54.0),
    ("SERIES", "Image Comics creator-owned launches", 82.0, 75.0, 84.0, 62.0),
    ("FRANCHISE", "DC major heroes", 88.0, 85.0, 87.0, 38.0),
    ("FRANCHISE", "Marvel major heroes", 90.0, 87.0, 89.0, 40.0),
    ("VARIANT", "Affordable ratio variants", 76.0, 80.0, 72.0, 65.0),
    ("KEY_ISSUE_TYPE", "First appearances", 92.0, 78.0, 94.0, 45.0),
)
