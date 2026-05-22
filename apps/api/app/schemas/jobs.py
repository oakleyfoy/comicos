from datetime import datetime

from pydantic import BaseModel

from app.schemas.imports import DraftImportRead


class ImportParseJobEnqueueResponse(BaseModel):
    job_id: str
    status: str


class ImportParseJobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    import_id: int | None = None
    import_record: DraftImportRead | None = None
    error: str | None = None
    enqueued_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
