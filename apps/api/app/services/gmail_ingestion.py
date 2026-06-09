import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib import error, parse, request

from fastapi import HTTPException
from jwt import InvalidTokenError
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.security import (
    create_oauth_state_token,
    decode_oauth_state_token,
    decrypt_secret_value,
    encrypt_secret_value,
)
from app.models import DraftImport, GmailAccount, GmailImportRecord, User
from app.schemas.ai import ParseOrderResponse
from app.schemas.gmail import (
    GmailImportedDraftRead,
    GmailImportRemoveResponse,
    GmailStatusResponse,
    GmailSyncStatusResponse,
)
from app.services.ai_order_parser import AiOrderParserError, parse_order_draft_from_text
from app.services.imports import (
    draft_import_cover_image_counts,
    get_import_for_user_or_404,
    serialize_import,
    utc_now,
)
from app.services.ops_events import classify_failure_message, record_ops_event

LOGGER = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
GMAIL_MESSAGE_DETAIL_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}"
GMAIL_PROVIDER = "gmail"
GMAIL_SYNC_JOB_TYPE = "gmail_sync"
GMAIL_OAUTH_SCOPES = (
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.readonly",
)
GMAIL_LOOKBACK_DAYS = 30
GMAIL_MAX_MESSAGES = 20
SUPPORTED_SENDER_DOMAINS = {
    "eBay": ("ebay.com",),
    "Whatnot": ("whatnot.com",),
    "Midtown Comics": ("midtowncomics.com",),
    "DCBS": ("dcbservice.com",),
    "Third Eye": ("thirdeyecomics.com",),
}
FORWARDED_HEADER_PATTERN = re.compile(
    r"^(from|subject|sender|reply-to):\s*(.+)$",
    re.IGNORECASE,
)
MAX_SYNC_ERROR_LENGTH = 280


class GmailIntegrationError(Exception):
    pass


class GmailIntegrationNotConfiguredError(GmailIntegrationError):
    pass


class GmailNotConnectedError(GmailIntegrationError):
    pass


@dataclass
class GmailReceiptMessage:
    external_message_id: str
    provider_name: str
    subject: str
    sender: str
    received_at: datetime
    body_text: str


def gmail_integration_is_configured() -> bool:
    settings = get_settings()
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
    )


def ensure_gmail_integration_configured() -> None:
    if not gmail_integration_is_configured():
        raise GmailIntegrationNotConfiguredError("Gmail integration is not configured.")


def build_gmail_connect_authorization_url(
    current_user: User,
    *,
    redirect_origin: str | None,
    redirect_path: str,
) -> str:
    ensure_gmail_integration_configured()
    settings = get_settings()
    state = create_oauth_state_token(
        user_id=current_user.id,
        provider=GMAIL_PROVIDER,
        redirect_origin=redirect_origin,
        redirect_path=redirect_path,
    )
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{parse.urlencode(params)}"


def decode_gmail_connect_state(state: str) -> dict:
    try:
        payload = decode_oauth_state_token(state)
    except InvalidTokenError as exc:
        raise HTTPException(status_code=400, detail="Invalid Gmail OAuth state.") from exc

    if payload.get("provider") != GMAIL_PROVIDER:
        raise HTTPException(status_code=400, detail="Invalid Gmail OAuth state.")

    try:
        payload["user_id"] = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Gmail OAuth state.") from exc

    return payload


def _decode_base64url(value: str | None) -> str:
    if not value:
        return ""
    padding = "=" * (-len(value) % 4)
    raw = base64.urlsafe_b64decode(value + padding)
    return raw.decode("utf-8", errors="ignore")


def _humanize_google_oauth_error(message: str) -> str:
    normalized = message.strip().lower()
    if "invalid_grant" in normalized:
        return (
            "Gmail authorization expired or was revoked. "
            "Open Gmail Receipt Drafts and use Connect Gmail again."
        )
    return message.strip()


def _extract_error_message(exc: error.HTTPError) -> str:
    try:
        payload = json.loads(exc.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return f"Gmail request failed with status {exc.code}."

    if isinstance(payload, dict):
        detail = payload.get("error")
        if isinstance(detail, dict):
            message = detail.get("message")
            if isinstance(message, str) and message.strip():
                return _humanize_google_oauth_error(message)
        if isinstance(detail, str) and detail.strip():
            return _humanize_google_oauth_error(detail)
        error_description = payload.get("error_description")
        if isinstance(error_description, str) and error_description.strip():
            return _humanize_google_oauth_error(error_description)

    return f"Gmail request failed with status {exc.code}."


def _json_request(
    url: str,
    *,
    method: str = "GET",
    data: dict | None = None,
    headers: dict[str, str] | None = None,
) -> dict:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")

    req = request.Request(url, method=method, data=body, headers=request_headers)
    try:
        with request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise GmailIntegrationError(_extract_error_message(exc)) from exc
    except (error.URLError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise GmailIntegrationError("Unable to reach Gmail right now.") from exc


def exchange_gmail_oauth_code(code: str) -> dict:
    ensure_gmail_integration_configured()
    settings = get_settings()
    return _json_request(
        GOOGLE_TOKEN_URL,
        method="POST",
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
    )


def refresh_gmail_access_token(refresh_token: str) -> dict:
    ensure_gmail_integration_configured()
    settings = get_settings()
    return _json_request(
        GOOGLE_TOKEN_URL,
        method="POST",
        data={
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )


def fetch_google_userinfo(access_token: str) -> dict:
    return _json_request(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )


def get_gmail_account_for_user(session: Session, current_user: User) -> GmailAccount | None:
    return session.exec(
        select(GmailAccount).where(GmailAccount.user_id == current_user.id)
    ).first()


def list_auto_sync_enabled_accounts(session: Session) -> list[GmailAccount]:
    return session.exec(
        select(GmailAccount).where(GmailAccount.auto_sync_enabled.is_(True))
    ).all()


def build_gmail_sync_status(account: GmailAccount | None) -> GmailSyncStatusResponse:
    if account is None:
        return GmailSyncStatusResponse(auto_sync_enabled=False)

    return GmailSyncStatusResponse(
        auto_sync_enabled=account.auto_sync_enabled,
        last_sync_started_at=account.last_sync_started_at,
        last_sync_completed_at=account.last_sync_completed_at,
        last_sync_status=account.last_sync_status,
        last_sync_error=account.last_sync_error,
    )


def get_gmail_sync_status_for_user(
    session: Session,
    current_user: User,
) -> GmailSyncStatusResponse:
    account = get_gmail_account_for_user(session, current_user)
    return build_gmail_sync_status(account)


def update_gmail_sync_settings_for_user(
    session: Session,
    *,
    current_user: User,
    auto_sync_enabled: bool,
) -> GmailSyncStatusResponse:
    account = get_gmail_account_for_user(session, current_user)
    if account is None or account.access_token_encrypted is None:
        raise GmailNotConnectedError("Connect a Gmail account before enabling auto sync.")

    account.auto_sync_enabled = auto_sync_enabled
    account.updated_at = utc_now()
    session.add(account)
    session.commit()
    session.refresh(account)
    return build_gmail_sync_status(account)


def _truncate_sync_error(message: str) -> str:
    normalized = " ".join(message.split())
    if len(normalized) <= MAX_SYNC_ERROR_LENGTH:
        return normalized
    return normalized[: MAX_SYNC_ERROR_LENGTH - 3] + "..."


def mark_gmail_sync_started(session: Session, account: GmailAccount) -> None:
    account.last_sync_started_at = utc_now()
    account.last_sync_status = "started"
    account.last_sync_error = None
    account.updated_at = utc_now()
    session.add(account)
    session.commit()
    session.refresh(account)


def mark_gmail_sync_success(session: Session, account: GmailAccount) -> None:
    account.last_sync_completed_at = utc_now()
    account.last_sync_status = "success"
    account.last_sync_error = None
    account.updated_at = utc_now()
    session.add(account)
    session.commit()
    session.refresh(account)


def mark_gmail_sync_failed(session: Session, account: GmailAccount, error_message: str) -> None:
    account.last_sync_completed_at = utc_now()
    account.last_sync_status = "failed"
    account.last_sync_error = _truncate_sync_error(error_message)
    account.updated_at = utc_now()
    session.add(account)
    session.commit()
    session.refresh(account)


def store_gmail_account_tokens(
    session: Session,
    *,
    current_user: User,
    gmail_email: str,
    google_subject_id: str,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
) -> GmailAccount:
    account = get_gmail_account_for_user(session, current_user)
    now = utc_now()
    token_expires_at = now + timedelta(seconds=expires_in or 3600)

    if account is None:
        account = GmailAccount(
            user_id=current_user.id,
            gmail_email=gmail_email,
            google_subject_id=google_subject_id,
            created_at=now,
            updated_at=now,
        )

    account.gmail_email = gmail_email
    account.google_subject_id = google_subject_id
    account.access_token_encrypted = encrypt_secret_value(access_token)
    if refresh_token:
        account.refresh_token_encrypted = encrypt_secret_value(refresh_token)
    account.token_expires_at = token_expires_at
    account.updated_at = now

    session.add(account)
    session.commit()
    session.refresh(account)
    return account


def connect_gmail_account_for_user(
    session: Session,
    *,
    current_user: User,
    code: str,
) -> GmailAccount:
    token_payload = exchange_gmail_oauth_code(code)
    access_token = token_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailIntegrationError("Google OAuth did not return an access token.")

    userinfo = fetch_google_userinfo(access_token)
    gmail_email = userinfo.get("email")
    google_subject_id = userinfo.get("sub")
    if not isinstance(gmail_email, str) or not isinstance(google_subject_id, str):
        raise GmailIntegrationError("Google OAuth did not return account identity.")

    refresh_token = token_payload.get("refresh_token")
    expires_in = token_payload.get("expires_in")
    return store_gmail_account_tokens(
        session,
        current_user=current_user,
        gmail_email=gmail_email,
        google_subject_id=google_subject_id,
        access_token=access_token,
        refresh_token=refresh_token if isinstance(refresh_token, str) else None,
        expires_in=expires_in if isinstance(expires_in, int) else None,
    )


def get_gmail_status_for_user(session: Session, current_user: User) -> GmailStatusResponse:
    account = get_gmail_account_for_user(session, current_user)
    configured = gmail_integration_is_configured()
    connected = bool(configured and account and account.access_token_encrypted)
    return GmailStatusResponse(
        configured=configured,
        connected=connected,
        gmail_email=account.gmail_email if connected and account else None,
        token_expires_at=account.token_expires_at if connected and account else None,
    )


def disconnect_gmail_for_user(session: Session, current_user: User) -> None:
    account = get_gmail_account_for_user(session, current_user)
    if account is None:
        return

    account.access_token_encrypted = None
    account.refresh_token_encrypted = None
    account.token_expires_at = None
    account.auto_sync_enabled = False
    account.updated_at = utc_now()
    session.add(account)
    session.commit()


def _get_valid_access_token(session: Session, account: GmailAccount) -> str:
    if account.access_token_encrypted is None:
        raise GmailNotConnectedError("Connect a Gmail account before syncing receipts.")

    if (
        account.token_expires_at is None
        or account.token_expires_at > datetime.now(timezone.utc) + timedelta(minutes=1)
    ):
        return decrypt_secret_value(account.access_token_encrypted)

    if account.refresh_token_encrypted is None:
        raise GmailNotConnectedError("Reconnect Gmail before syncing receipts.")

    try:
        refresh_payload = refresh_gmail_access_token(
            decrypt_secret_value(account.refresh_token_encrypted)
        )
    except GmailIntegrationError as exc:
        if "invalid_grant" in str(exc).lower() or "authorization expired" in str(exc).lower():
            account.access_token_encrypted = None
            account.refresh_token_encrypted = None
            account.token_expires_at = None
            account.auto_sync_enabled = False
            account.last_sync_error = str(exc)[:MAX_SYNC_ERROR_LENGTH]
            account.updated_at = utc_now()
            session.add(account)
            session.commit()
            raise GmailNotConnectedError(str(exc)) from exc
        raise

    access_token = refresh_payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise GmailIntegrationError("Google refresh did not return an access token.")

    expires_in = refresh_payload.get("expires_in")
    account.access_token_encrypted = encrypt_secret_value(access_token)
    account.token_expires_at = utc_now() + timedelta(seconds=expires_in or 3600)
    account.updated_at = utc_now()
    session.add(account)
    session.commit()
    session.refresh(account)
    return access_token


def _gmail_api_get(access_token: str, url: str) -> dict:
    return _json_request(url, headers={"Authorization": f"Bearer {access_token}"})


def _supported_sender_query() -> str:
    senders = [
        f"from:{domain}"
        for domains in SUPPORTED_SENDER_DOMAINS.values()
        for domain in domains
    ]
    provider_terms = [
        f'"{provider_name}"' if " " in provider_name else provider_name
        for provider_name in SUPPORTED_SENDER_DOMAINS
    ]
    return (
        f"newer_than:{GMAIL_LOOKBACK_DAYS}d "
        f"(({' OR '.join(senders)}) OR ({' OR '.join(provider_terms)}))"
    )


def _is_supported_sender(sender: str) -> bool:
    sender_lower = sender.lower()
    return any(
        domain in sender_lower
        for domains in SUPPORTED_SENDER_DOMAINS.values()
        for domain in domains
    )


def _extract_forwarded_header_values(text: str) -> list[str]:
    forwarded_values: list[str] = []
    for line in text.splitlines():
        match = FORWARDED_HEADER_PATTERN.match(line.strip())
        if match:
            forwarded_values.append(match.group(2).strip())
    return forwarded_values


def _detect_supported_provider(*texts: str) -> str | None:
    normalized_texts = [text.lower() for text in texts if text.strip()]
    for provider_name, domains in SUPPORTED_SENDER_DOMAINS.items():
        provider_name_lower = provider_name.lower()
        if any(
            provider_name_lower in text
            or any(domain in text for domain in domains)
            for text in normalized_texts
        ):
            return provider_name
    return None


def _header_value(headers: list[dict], name: str) -> str:
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            value = header.get("value")
            return value if isinstance(value, str) else ""
    return ""


def _extract_body_text(payload: dict) -> str:
    mime_type = payload.get("mimeType")
    body = payload.get("body") or {}
    body_data = body.get("data")

    if mime_type == "text/plain" and isinstance(body_data, str):
        return _decode_base64url(body_data)

    parts = payload.get("parts") or []
    if isinstance(parts, list):
        for part in parts:
            text = _extract_body_text(part)
            if text.strip():
                return text

    if isinstance(body_data, str):
        return _decode_base64url(body_data)

    return ""


def _parse_received_at(message: dict, headers: list[dict]) -> datetime:
    internal_date = message.get("internalDate")
    if isinstance(internal_date, str) and internal_date.isdigit():
        return datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)

    date_header = _header_value(headers, "Date")
    if date_header:
        parsed = parsedate_to_datetime(date_header)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    return utc_now()


def list_recent_supported_receipt_emails(
    session: Session,
    account: GmailAccount,
) -> list[GmailReceiptMessage]:
    access_token = _get_valid_access_token(session, account)
    query = parse.urlencode({"q": _supported_sender_query(), "maxResults": GMAIL_MAX_MESSAGES})
    listing = _gmail_api_get(access_token, f"{GMAIL_MESSAGES_URL}?{query}")

    messages: list[GmailReceiptMessage] = []
    for message in listing.get("messages", []):
        message_id = message.get("id")
        if not isinstance(message_id, str):
            continue

        details = _gmail_api_get(
            access_token,
            GMAIL_MESSAGE_DETAIL_URL.format(message_id=message_id) + "?format=full",
        )
        payload = details.get("payload") or {}
        headers = payload.get("headers") or []
        subject = _header_value(headers, "Subject")
        sender = _header_value(headers, "From")
        snippet = str(details.get("snippet") or "").strip()

        body_text = _extract_body_text(payload).strip() or snippet
        if not body_text:
            continue

        provider_name = _detect_supported_provider(
            sender,
            subject,
            snippet,
            body_text,
            *_extract_forwarded_header_values(snippet),
            *_extract_forwarded_header_values(body_text),
        )
        if provider_name is None:
            record_ops_event(
                event_type="unsupported_provider_skip",
                status="skipped",
                user_id=account.user_id,
                gmail_account_id=account.id,
                external_message_id=message_id,
                message="Gmail message did not match a supported provider",
                details={
                    "subject": subject,
                    "sender": sender,
                },
            )
            continue

        messages.append(
            GmailReceiptMessage(
                external_message_id=message_id,
                provider_name=provider_name,
                subject=subject,
                sender=sender,
                received_at=_parse_received_at(details, headers),
                body_text=body_text,
            )
        )

    return messages


def _gmail_warning(message: GmailReceiptMessage) -> str:
    subject = message.subject or "No subject"
    received_at = message.received_at.astimezone(timezone.utc).isoformat()
    return (
        f'Imported from Gmail email "{subject}" from {message.sender} at {received_at}. '
        f"Recognized provider: {message.provider_name}."
    )


def _create_gmail_draft_import(
    session: Session,
    *,
    current_user: User,
    message: GmailReceiptMessage,
) -> DraftImport:
    parsed = parse_order_draft_from_text(message.body_text)
    warning = _gmail_warning(message)
    parsed = ParseOrderResponse.model_validate(
        parsed.model_copy(
            update={
                "source_type": "gmail_draft",
                "warnings": [*parsed.warnings, warning],
            }
        )
    )

    timestamp = utc_now()
    draft_import = DraftImport(
        user_id=current_user.id,
        raw_text=message.body_text,
        parsed_payload_json=parsed.model_dump(mode="json"),
        confidence_score=parsed.confidence_score,
        status="draft",
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(draft_import)
    session.flush()
    return draft_import


def sync_gmail_receipts_for_user(session: Session, current_user: User) -> dict[str, int]:
    ensure_gmail_integration_configured()
    account = get_gmail_account_for_user(session, current_user)
    if account is None or account.access_token_encrypted is None:
        raise GmailNotConnectedError("Connect a Gmail account before syncing receipts.")

    messages = list_recent_supported_receipt_emails(session, account)
    created_count = 0
    duplicate_count = 0

    for message in messages:
        existing_record = session.exec(
            select(GmailImportRecord).where(
                GmailImportRecord.external_message_id == message.external_message_id
            )
        ).first()
        if existing_record is not None:
            duplicate_count += 1
            record_ops_event(
                event_type="duplicate_skip",
                status="skipped",
                user_id=current_user.id,
                gmail_account_id=account.id,
                draft_import_id=existing_record.draft_import_id,
                external_message_id=message.external_message_id,
                message="Skipped duplicate Gmail import",
                details={
                    "original_imported_at": existing_record.imported_at,
                    "provider_name": message.provider_name,
                },
            )
            continue

        try:
            draft_import = _create_gmail_draft_import(
                session,
                current_user=current_user,
                message=message,
            )
        except AiOrderParserError as exc:
            LOGGER.exception(
                "Skipping Gmail message %s after parser failure",
                message.external_message_id,
            )
            session.rollback()
            failure_message = str(exc)
            record_ops_event(
                event_type="parser_failure",
                status="failed",
                user_id=current_user.id,
                gmail_account_id=account.id,
                external_message_id=message.external_message_id,
                message=failure_message,
                details={
                    "failure_type": classify_failure_message(failure_message),
                    "provider_name": message.provider_name,
                    "subject": message.subject,
                    "sender": message.sender,
                    "error": failure_message,
                },
            )
            continue

        session.add(
            GmailImportRecord(
                gmail_account_id=account.id,
                external_message_id=message.external_message_id,
                draft_import_id=draft_import.id,
                imported_at=utc_now(),
            )
        )
        session.commit()
        created_count += 1

    return {
        "processed_messages": len(messages),
        "created_draft_imports": created_count,
        "skipped_duplicates": duplicate_count,
    }


def serialize_gmail_import_drafts(
    session: Session,
    current_user: User,
    *,
    limit: int = 50,
) -> list[GmailImportedDraftRead]:
    records = session.exec(
        select(GmailImportRecord, DraftImport)
        .join(DraftImport, DraftImport.id == GmailImportRecord.draft_import_id)
        .where(DraftImport.user_id == current_user.id)
        .order_by(
            GmailImportRecord.imported_at.desc(),
            DraftImport.created_at.desc(),
            GmailImportRecord.id.desc(),
        )
        .limit(limit)
    ).all()
    draft_ids = [
        draft_import.id for _, draft_import in records if draft_import.id is not None
    ]
    cover_counts = draft_import_cover_image_counts(session, draft_ids)

    def cover_count_for(draft_import: DraftImport) -> int:
        if draft_import.id is None:
            return 0
        return cover_counts.get(draft_import.id, 0)

    return [
        GmailImportedDraftRead(
            external_message_id=record.external_message_id,
            imported_at=record.imported_at,
            draft_import=serialize_import(
                session,
                draft_import,
                prefetch_cover_images=False,
                cover_image_count=cover_count_for(draft_import),
                enrich_metadata=False,
                enrich_lifecycle=False,
            ),
        )
        for record, draft_import in records
    ]


def remove_gmail_import_for_user(
    session: Session,
    current_user: User,
    draft_import_id: int,
) -> GmailImportRemoveResponse:
    draft_import = get_import_for_user_or_404(session, current_user, draft_import_id)
    if draft_import.status == "confirmed":
        raise HTTPException(
            status_code=409,
            detail="Confirmed imports cannot be removed from Gmail receipts.",
        )

    gmail_record = session.exec(
        select(GmailImportRecord).where(GmailImportRecord.draft_import_id == draft_import_id)
    ).first()
    if gmail_record is None:
        raise HTTPException(status_code=404, detail="Gmail import record not found for this draft.")

    account = session.exec(
        select(GmailAccount).where(
            GmailAccount.id == gmail_record.gmail_account_id,
            GmailAccount.user_id == current_user.id,
        )
    ).first()
    if account is None:
        raise HTTPException(status_code=404, detail="Gmail import record not found for this draft.")

    external_message_id = gmail_record.external_message_id
    session.delete(gmail_record)
    draft_import.status = "discarded"
    draft_import.updated_at = utc_now()
    session.add(draft_import)
    session.commit()

    record_ops_event(
        event_type="gmail_import_removed",
        status="success",
        user_id=current_user.id,
        gmail_account_id=account.id,
        draft_import_id=draft_import_id,
        external_message_id=external_message_id,
        message="Removed Gmail receipt import and discarded draft.",
    )

    return GmailImportRemoveResponse(
        draft_import_id=draft_import_id,
        external_message_id=external_message_id,
        removed=True,
    )
