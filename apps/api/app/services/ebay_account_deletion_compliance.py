from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.models.ebay_compliance import EbayAccountDeletionAuditLog
from app.schemas.ebay_account_deletion import (
    EbayAccountDeletionAckResponse,
    EbayAccountDeletionChallengeResponse,
)

EVENT_VERIFICATION_CHALLENGE = "verification_challenge"
EVENT_ACCOUNT_DELETION = "account_deletion_notification"
NOOP_ACTION = "acknowledged_no_user_data_retained"


def compute_challenge_response(
    *,
    challenge_code: str,
    verification_token: str,
    endpoint_url: str,
) -> str:
    """eBay Marketplace Account Deletion endpoint verification (SHA-256 hex, UTF-8 concatenation)."""

    digest = hashlib.sha256()
    digest.update(challenge_code.encode("utf-8"))
    digest.update(verification_token.encode("utf-8"))
    digest.update(endpoint_url.encode("utf-8"))
    return digest.hexdigest()


def _settings_or_raise(settings: Settings | None = None) -> Settings:
    resolved = settings or get_settings()
    if not resolved.ebay_account_deletion_compliance_enabled:
        raise HTTPException(status_code=503, detail="eBay account deletion compliance endpoint is disabled.")
    return resolved


def handle_verification_challenge(
    *,
    challenge_code: str,
    settings: Settings | None = None,
) -> EbayAccountDeletionChallengeResponse:
    resolved = _settings_or_raise(settings)
    token = resolved.ebay_account_deletion_verification_token.strip()
    endpoint = resolved.ebay_account_deletion_endpoint_url.strip()
    if not challenge_code.strip():
        raise HTTPException(status_code=400, detail="challenge_code is required.")
    if not token:
        raise HTTPException(
            status_code=503,
            detail="EBAY_ACCOUNT_DELETION_VERIFICATION_TOKEN is not configured.",
        )
    if not endpoint:
        raise HTTPException(
            status_code=503,
            detail="EBAY_ACCOUNT_DELETION_ENDPOINT_URL is not configured.",
        )
    response_hash = compute_challenge_response(
        challenge_code=challenge_code.strip(),
        verification_token=token,
        endpoint_url=endpoint,
    )
    return EbayAccountDeletionChallengeResponse(challengeResponse=response_hash)


def _payload_digest(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


def _extract_notification_id(payload: dict[str, Any]) -> str | None:
    notification = payload.get("notification")
    if not isinstance(notification, dict):
        return None
    notification_id = notification.get("notificationId")
    if notification_id is None:
        return None
    return str(notification_id).strip() or None


def record_compliance_audit(
    session: Session,
    *,
    event_kind: str,
    external_notification_id: str | None = None,
    payload_digest: str | None = None,
) -> EbayAccountDeletionAuditLog:
    row = EbayAccountDeletionAuditLog(
        event_kind=event_kind,
        external_notification_id=external_notification_id,
        payload_digest=payload_digest,
        noop_action=NOOP_ACTION,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def handle_account_deletion_notification(
    session: Session,
    *,
    raw_body: bytes,
    settings: Settings | None = None,
) -> EbayAccountDeletionAckResponse:
    _settings_or_raise(settings)
    digest = _payload_digest(raw_body) if raw_body else None
    notification_id: str | None = None
    if raw_body:
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
            if isinstance(parsed, dict):
                notification_id = _extract_notification_id(parsed)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    record_compliance_audit(
        session,
        event_kind=EVENT_ACCOUNT_DELETION,
        external_notification_id=notification_id,
        payload_digest=digest,
    )
    return EbayAccountDeletionAckResponse()
