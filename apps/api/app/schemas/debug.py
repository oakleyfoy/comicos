from datetime import datetime

from pydantic import BaseModel


class RuntimeDebugResponse(BaseModel):
    app_name: str
    environment: str
    database_url_safe: str
    redis_url_safe: str
    pid: int
    cwd: str
    started_at: datetime
    git_commit: str | None


class BuildInfoFeatureFlags(BaseModel):
    full_cover_followup_enabled: bool
    mobile_capture_enabled: bool
    suppress_unsafe_fingerprint_enabled: bool


class BuildInfoResponse(BaseModel):
    service: str
    git_sha: str | None
    build_time: str
    process_started_at: str
    server_time: str
    runtime: str
    environment: str
    feature_flags: BuildInfoFeatureFlags
