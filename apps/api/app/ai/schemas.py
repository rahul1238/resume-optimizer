from typing import Literal

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


class StructuredResumeSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=80)
    heading: str = Field(min_length=1, max_length=120)
    items: list[str] = Field(default_factory=list, max_length=100)


class StructuredResumeDocument(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    header: list[str] = Field(default_factory=list, max_length=20)
    sections: list[StructuredResumeSection] = Field(default_factory=list, max_length=30)


class ResumeChange(BaseModel):
    change_id: str = Field(default="", max_length=80)
    change_type: Literal["summary", "bullet", "skill", "section"]
    status: Literal["proposed", "accepted", "rejected"] = "proposed"
    target_section: str = Field(default="", max_length=120)
    original: str = Field(default="", max_length=1500)
    suggested: str = Field(min_length=1, max_length=1500)
    reason: str = Field(min_length=1, max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=5)
    confidence: float = Field(default=0.8, ge=0, le=1)
    requires_confirmation: bool = False


class ClarificationQuestion(BaseModel):
    question_id: str = Field(default="", max_length=80)
    requirement: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=500)
    status: Literal["unanswered", "answered", "skipped"] = "unanswered"
    answer: str = Field(default="", max_length=1000)


class ResumeImprovementResult(BaseModel):
    optimized_resume_draft: str = Field(default="", max_length=50_000)
    suggested_summary: str = Field(min_length=1, max_length=1500)
    summary_reason: str = Field(min_length=1, max_length=500)
    bullet_rewrites: list[BulletRewrite] = Field(default_factory=list, max_length=8)
    skills_to_emphasize: list[str] = Field(default_factory=list, max_length=20)
    ats_recommendations: list[str] = Field(min_length=1, max_length=10)
    integrity_notes: list[str] = Field(default_factory=list, max_length=10)
    structured_resume: StructuredResumeDocument | None = None
    change_set: list[ResumeChange] = Field(default_factory=list, max_length=30)
    clarification_questions: list[ClarificationQuestion] = Field(
        default_factory=list,
        max_length=10,
    )
