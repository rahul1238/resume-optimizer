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


class TailoringDecision(BaseModel):
    decision_id: str = Field(default="", max_length=80)
    content_type: Literal["skill", "experience_bullet", "project", "employment"]
    source_text: str = Field(min_length=1, max_length=1500)
    action: Literal["include", "condense", "omit"]
    relevance: Literal["required", "recommended", "supporting", "irrelevant"]
    reason: str = Field(min_length=1, max_length=500)
    matched_requirements: list[str] = Field(default_factory=list, max_length=5)


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
    tailoring_decisions: list[TailoringDecision] = Field(
        default_factory=list,
        max_length=50,
    )


# Keep Gemini's response schema compact. Stable IDs, review statuses, and the
# structured document are deterministic server concerns and are added later.
class GeminiResumeChange(BaseModel):
    change_type: Literal["summary", "bullet", "skill", "section"]
    target_section: str
    original: str
    suggested: str
    reason: str
    evidence: list[str]
    confidence: float
    requires_confirmation: bool


class GeminiClarificationQuestion(BaseModel):
    requirement: str
    question: str


class GeminiTailoringDecision(BaseModel):
    content_type: Literal["skill", "experience_bullet", "project", "employment"]
    source_text: str
    action: Literal["include", "condense", "omit"]
    relevance: Literal["required", "recommended", "supporting", "irrelevant"]
    reason: str
    matched_requirements: list[str]


class GeminiResumeImprovementResult(BaseModel):
    optimized_resume_draft: str
    suggested_summary: str
    summary_reason: str
    bullet_rewrites: list[BulletRewrite]
    skills_to_emphasize: list[str]
    ats_recommendations: list[str]
    integrity_notes: list[str]
    change_set: list[GeminiResumeChange]
    clarification_questions: list[GeminiClarificationQuestion]
    tailoring_decisions: list[GeminiTailoringDecision]

    def to_domain(self) -> ResumeImprovementResult:
        return ResumeImprovementResult(
            optimized_resume_draft=self.optimized_resume_draft,
            suggested_summary=self.suggested_summary,
            summary_reason=self.summary_reason,
            bullet_rewrites=self.bullet_rewrites[:8],
            skills_to_emphasize=self.skills_to_emphasize[:20],
            ats_recommendations=self.ats_recommendations[:10],
            integrity_notes=self.integrity_notes[:10],
            change_set=[
                ResumeChange.model_validate(change.model_dump())
                for change in self.change_set[:30]
            ],
            clarification_questions=[
                ClarificationQuestion.model_validate(question.model_dump())
                for question in self.clarification_questions[:10]
            ],
            tailoring_decisions=[
                TailoringDecision.model_validate(decision.model_dump())
                for decision in self.tailoring_decisions[:50]
            ],
        )
