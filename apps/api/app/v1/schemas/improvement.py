from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.ai.schemas import ResumeImprovementResult


class ImprovementResponse(BaseModel):
    analysis_id: str
    resume_id: str
    provider: str
    model: str
    created_at: datetime | None
    result: ResumeImprovementResult


class ImprovementGenerateRequest(BaseModel):
    current_result: ResumeImprovementResult | None = None
    feedback: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("feedback")
    @classmethod
    def clean_feedback(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if any(len(item) > 1000 for item in cleaned):
            raise ValueError("Each feedback item must be 1000 characters or fewer.")
        return cleaned


class ImprovementSaveRequest(BaseModel):
    result: ResumeImprovementResult
