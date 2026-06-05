"""P65 Collector Experience feature flags."""

from __future__ import annotations

from app.core.config import get_settings


def p65_collector_workspace_enabled() -> bool:
    return bool(get_settings().p65_collector_workspace_enabled)


def p65_llm_narration_enabled() -> bool:
    return bool(get_settings().p65_llm_narration_enabled)


def p65_automation_enabled() -> bool:
    return bool(get_settings().p65_automation_enabled)


def p65_notification_center_enabled() -> bool:
    return bool(get_settings().p65_notification_center_enabled)
