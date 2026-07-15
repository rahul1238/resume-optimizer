from typing import Protocol

from app.ai.schemas import ResumeAnalysisResult, ResumeImprovementResult


class AIProviderError(Exception):
    status_code = 503
    code = "ai_provider_unavailable"
    message = "The analysis service is temporarily unavailable."

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class AIProviderConfigurationError(AIProviderError):
    code = "ai_provider_not_configured"
    message = "The analysis service is not configured."


class AIProviderQuotaError(AIProviderError):
    status_code = 429
    code = "ai_provider_quota_exceeded"
    message = "Gemini's available model quota has been reached. Try again later."


class AIProvider(Protocol):
    name: str
    model: str

    def analyze_resume(
        self,
        resume_text: str,
        job_description: str,
        job_title: str | None,
        company_name: str | None,
    ) -> ResumeAnalysisResult: ...

    def improve_resume(
        self,
        resume_text: str,
        job_description: str,
        job_title: str | None,
        company_name: str | None,
        current_result: ResumeImprovementResult | None = None,
        feedback: list[str] | None = None,
    ) -> ResumeImprovementResult: ...
