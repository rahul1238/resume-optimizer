from pydantic import BaseModel, Field


class ResumeAnalysisResult(BaseModel):
    match_score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1, max_length=1200)
    strengths: list[str] = Field(min_length=1, max_length=10)
    gaps: list[str] = Field(default_factory=list, max_length=10)
    matched_keywords: list[str] = Field(default_factory=list, max_length=30)
    missing_keywords: list[str] = Field(default_factory=list, max_length=30)
    recommendations: list[str] = Field(min_length=1, max_length=10)


class BulletRewrite(BaseModel):
    original: str = Field(min_length=1, max_length=1000)
    suggested: str = Field(min_length=1, max_length=1200)
    reason: str = Field(min_length=1, max_length=500)


class ResumeImprovementResult(BaseModel):
    optimized_resume_draft: str = Field(default="", max_length=50_000)
    suggested_summary: str = Field(min_length=1, max_length=1500)
    summary_reason: str = Field(min_length=1, max_length=500)
    bullet_rewrites: list[BulletRewrite] = Field(default_factory=list, max_length=8)
    skills_to_emphasize: list[str] = Field(default_factory=list, max_length=20)
    ats_recommendations: list[str] = Field(min_length=1, max_length=10)
    integrity_notes: list[str] = Field(default_factory=list, max_length=10)
