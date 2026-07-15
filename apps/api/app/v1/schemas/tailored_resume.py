from datetime import datetime

from pydantic import BaseModel


class TailoredResumeSummaryResponse(BaseModel):
    analysis_id: str
    resume_id: str
    base_resume_title: str
    company_name: str | None
    role_name: str | None
    application_date: str | None
    revision: int
    created_at: datetime | None
    updated_at: datetime | None
