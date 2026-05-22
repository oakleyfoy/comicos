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
