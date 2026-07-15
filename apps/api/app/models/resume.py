from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class ResumeRecord:
    resume_id: str
    owner_uid: str
    filename: str
    file_type: Literal["pdf", "docx"]
    page_count: int | None
    character_count: int
    original_storage_path: str
    text_storage_path: str
    content_sha256: str | None = None
    title: str = ""
    tags: tuple[str, ...] = ()
    created_at: datetime | None = None
