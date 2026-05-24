"""Thin ops-role checks shared by dashboards and mutations (avoid import cycles)."""

from app.core.config import Settings
from app.models import User


def is_ops_admin_user(current_user: User, settings: Settings) -> bool:
    """Same semantics historically used at ``GET /files/cover-images`` ops fallback."""
    configured_emails = settings.ops_admin_emails
    if configured_emails:
        return current_user.email.lower() in configured_emails
    return settings.app_env.lower() != "production"
