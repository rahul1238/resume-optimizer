from pydantic import BaseModel, Field


class ResumeAnalysisResult(BaseModel):
    match_score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=1200)
    strengths: list[str] = Field(min_length=1, max_length=10)
    gaps: list[str] = Field(default_factory=list, max_length=10)
    matched_keywords: list[str] = Field(default_factory=list, max_length=30)
    missing_keywords: list[str] = Field(default_factory=list, max_length=30)
    recommendations: list[str] = Field(min_length=1, max_length=10)
