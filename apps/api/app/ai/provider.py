from typing import Protocol

from app.ai.schemas import ResumeAnalysisResult


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
