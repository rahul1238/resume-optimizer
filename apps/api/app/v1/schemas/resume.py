from typing import Literal

from pydantic import BaseModel


class ResumeUploadResponse(BaseModel):
    resume_id: str
    filename: str
    file_type: Literal["pdf", "docx"]
    page_count: int | None
    storage_path: str
    character_count: int
    text: str
