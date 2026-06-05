"""P64 Collector Assistant feature flags."""

from __future__ import annotations

from app.core.config import get_settings


def p64_collector_assistant_enabled() -> bool:
    return bool(get_settings().p64_collector_assistant_enabled)


def p64_llm_narration_enabled() -> bool:
    return bool(get_settings().p64_llm_narration_enabled)
