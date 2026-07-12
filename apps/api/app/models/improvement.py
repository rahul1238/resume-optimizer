from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ImprovementRecord:
    analysis_id: str
    owner_uid: str
    resume_id: str
    provider: str
    model: str
    result: dict[str, object]
    created_at: datetime | None = None
