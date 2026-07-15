from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ImprovementRecord:
    analysis_id: str
    owner_uid: str
    resume_id: str
    provider: str
    model: str
    result: dict[str, object]
    company_name: str | None = None
    role_name: str | None = None
    application_date: str | None = None
    layout_settings: dict[str, Any] | None = None
    revision: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None
