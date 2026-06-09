from datetime import datetime

from pydantic import BaseModel

from app.schemas.imports import DraftImportRead


class GmailConnectStartResponse(BaseModel):
    authorization_url: str


class GmailStatusResponse(BaseModel):
    configured: bool
    connected: bool
    gmail_email: str | None = None
    token_expires_at: datetime | None = None


class GmailDisconnectResponse(BaseModel):
    disconnected: bool


class GmailSyncEnqueueResponse(BaseModel):
    job_id: str
    status: str


class GmailSyncSettingsUpdate(BaseModel):
    auto_sync_enabled: bool


class GmailSyncStatusResponse(BaseModel):
    auto_sync_enabled: bool
    last_sync_started_at: datetime | None = None
    last_sync_completed_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None


class GmailImportedDraftRead(BaseModel):
    external_message_id: str
    imported_at: datetime
    draft_import: DraftImportRead


class GmailImportRemoveResponse(BaseModel):
    draft_import_id: int
    external_message_id: str
    removed: bool = True
