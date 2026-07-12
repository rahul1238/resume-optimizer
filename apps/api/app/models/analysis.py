from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    owner_uid: str
    resume_id: str
    job_description: str
    job_title: str | None
    company_name: str | None
    provider: str
    model: str
    status: Literal["completed"]
    result: dict[str, object]
    created_at: datetime | None = None
