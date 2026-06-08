"""Collector Advisor dashboard status and collector-facing messages."""

from __future__ import annotations

from app.schemas.p90_collector_advisor import P90AdvisorSignalDiagnosticsRead
from app.services.advisor_signal_diagnostics import diagnostics_has_external_signals

ADVISOR_STATUS_NO_SNAPSHOT = "NO_SNAPSHOT"
ADVISOR_STATUS_EMPTY_NO_COLLECTION = "EMPTY_NO_COLLECTION"
ADVISOR_STATUS_EMPTY_NO_SIGNALS = "EMPTY_NO_SIGNALS"
ADVISOR_STATUS_EMPTY_GATHER_FAILED = "EMPTY_GATHER_FAILED"
ADVISOR_STATUS_OK = "OK"

ADVISOR_MESSAGE_NO_SNAPSHOT = (
    "Generate your first Advisor plan to see today's buy, sell, grade, and watch actions."
)
ADVISOR_MESSAGE_EMPTY_NO_COLLECTION = "Import comics to unlock personalized recommendations."
ADVISOR_MESSAGE_EMPTY_NO_SIGNALS = (
    "ComicOS found your collection data, but no ranked actions need attention right now."
)
ADVISOR_MESSAGE_GATHER_FAILED = "ComicOS could not finish building your Advisor plan. Try again."


def advisor_message_for_status(status: str) -> str:
    if status == ADVISOR_STATUS_NO_SNAPSHOT:
        return ADVISOR_MESSAGE_NO_SNAPSHOT
    if status == ADVISOR_STATUS_EMPTY_NO_COLLECTION:
        return ADVISOR_MESSAGE_EMPTY_NO_COLLECTION
    if status == ADVISOR_STATUS_EMPTY_NO_SIGNALS:
        return ADVISOR_MESSAGE_EMPTY_NO_SIGNALS
    if status == ADVISOR_STATUS_EMPTY_GATHER_FAILED:
        return ADVISOR_MESSAGE_GATHER_FAILED
    return ""


def resolve_advisor_dashboard_status(
    *,
    has_snapshot: bool,
    generation_status: str,
    total_actions: int,
    diagnostics: P90AdvisorSignalDiagnosticsRead,
) -> str:
    if not has_snapshot:
        return ADVISOR_STATUS_NO_SNAPSHOT
    if generation_status == "GATHER_FAILED":
        return ADVISOR_STATUS_EMPTY_GATHER_FAILED
    if total_actions > 0:
        return ADVISOR_STATUS_OK
    if diagnostics.inventory_count <= 0 and not diagnostics_has_external_signals(diagnostics):
        return ADVISOR_STATUS_EMPTY_NO_COLLECTION
    return ADVISOR_STATUS_EMPTY_NO_SIGNALS
