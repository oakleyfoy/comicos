from __future__ import annotations

from pathlib import Path


def test_navigation_contract_collector_home_and_groups() -> None:
    root = Path(__file__).resolve().parents[3]
    nav = (root / "apps" / "web" / "src" / "config" / "appNavigation.ts").read_text(encoding="utf-8")
    app = (root / "apps" / "web" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert "/collector-home" in nav
    assert 'path="/collector-home"' in app
    for group in ("Home", "Buy", "Inventory", "Storage", "Grade", "Sell", "Discovery", "Mobile", "Reports", "Settings"):
        assert f'title: "{group}"' in nav
