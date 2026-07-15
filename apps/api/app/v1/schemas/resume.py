from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ResumeUploadResponse(BaseModel):
    resume_id: str
    filename: str
    file_type: Literal["pdf", "docx"]
    page_count: int | None
    storage_path: str
    character_count: int
    text: str
    title: str
    tags: list[str]


class ResumeSummaryResponse(BaseModel):
    resume_id: str
    filename: str
    file_type: Literal["pdf", "docx"]
    page_count: int | None
    character_count: int
    created_at: datetime | None
    title: str
    tags: list[str]


class ResumeProfileUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        cleaned = []
        for tag in value:
            normalized = tag.strip().lower()
            if normalized and normalized not in cleaned:
                if len(normalized) > 30:
                    raise ValueError("Tags must be 30 characters or fewer.")
                cleaned.append(normalized)
        return cleaned


class ATSCheckResponse(BaseModel):
    check_id: str
    label: str
    status: Literal["pass", "warning", "fail"]
    detail: str


class ATSScanResponse(BaseModel):
    score: int = Field(ge=0, le=100)
    checks: list[ATSCheckResponse]
    recommendations: list[str]
