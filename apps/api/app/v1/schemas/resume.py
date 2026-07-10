from typing import Literal

from pydantic import BaseModel


class ResumeUploadResponse(BaseModel):
    filename: str
    file_type: Literal["pdf", "docx"]
    page_count: int | None
    character_count: int
    text: str
