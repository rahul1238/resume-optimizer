from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import ResumeAnalysisResult
from app.core.config import settings


class AnalysisCreateRequest(BaseModel):
    resume_id: str = Field(min_length=1, max_length=100)
    job_description: str = Field(
        min_length=100,
        max_length=settings.max_job_description_characters,
    )
    job_title: str | None = Field(default=None, max_length=200)
    company_name: str | None = Field(default=None, max_length=200)

    @field_validator(
        "resume_id", "job_description", "job_title", "company_name", mode="before"
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AnalysisCreateResponse(BaseModel):
    analysis_id: str
    resume_id: str
    status: str
    provider: str
    model: str
    result: ResumeAnalysisResult
