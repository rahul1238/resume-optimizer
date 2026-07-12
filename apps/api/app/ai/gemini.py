import logging

from google import genai
from google.genai import errors, types

from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
)
from app.ai.schemas import ResumeAnalysisResult, ResumeImprovementResult
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise AIProviderConfigurationError()
        self.model = settings.gemini_model
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=settings.gemini_timeout_seconds * 1000
            ),
        )

    def analyze_resume(
        self,
        resume_text: str,
        job_description: str,
        job_title: str | None,
        company_name: str | None,
    ) -> ResumeAnalysisResult:
        context = "\n".join(
            value
            for value in (
                f"Job title: {job_title}" if job_title else None,
                f"Company: {company_name}" if company_name else None,
            )
            if value
        )
        prompt = f"""You are a precise resume-to-job matching evaluator.
Evaluate only evidence present in the resume and job description. Do not invent
experience or qualifications. Score overall alignment from 0 to 100. Keywords
must be meaningful skills, tools, qualifications, or domain terms. Give concise,
actionable recommendations that do not encourage dishonest claims.

{context}

JOB DESCRIPTION
---
{job_description}
---

RESUME
---
{resume_text}
---
"""
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=ResumeAnalysisResult,
                ),
            )
            if isinstance(response.parsed, ResumeAnalysisResult):
                return response.parsed
            if response.text:
                return ResumeAnalysisResult.model_validate_json(response.text)
        except (errors.APIError, ValueError) as error:
            logger.exception("Gemini resume analysis failed")
            raise AIProviderError() from error

        raise AIProviderError("The analysis service returned an empty response.")

    def improve_resume(
        self,
        resume_text: str,
        job_description: str,
        job_title: str | None,
        company_name: str | None,
        current_result: ResumeImprovementResult | None = None,
        feedback: list[str] | None = None,
    ) -> ResumeImprovementResult:
        context = "\n".join(
            value
            for value in (
                f"Job title: {job_title}" if job_title else None,
                f"Company: {company_name}" if company_name else None,
            )
            if value
        )
        revision_context = ""
        if current_result:
            revision_context += (
                "\nCURRENT IMPROVEMENT DRAFT\n---\n"
                f"{current_result.model_dump_json()}\n---\n"
            )
        if feedback:
            revision_context += (
                "\nUSER EDITING FEEDBACK\n---\n"
                + "\n".join(f"- {item}" for item in feedback)
                + "\n---\n"
            )

        prompt = f"""You are an ethical resume editor. Improve the resume for the
target job using only facts already supported by the resume. Never invent skills,
metrics, employers, responsibilities, dates, or qualifications. Preserve the
candidate's meaning. Rewrite up to eight weak experience bullets when identifiable.
Skills to emphasize must already appear in the resume. Put any requested job skill
that is unsupported by the resume in integrity_notes instead of adding it. When a
current draft and user feedback are provided, revise the draft according to those
editing preferences, but treat them as preferences rather than factual evidence.
Also produce optimized_resume_draft as a complete, plain-text resume ready for
editing. Preserve all useful factual content and recognizable section structure.
Do not include markdown code fences or commentary inside the draft.

{context}

JOB DESCRIPTION
---
{job_description}
---

RESUME
---
{resume_text}
---
{revision_context}
"""
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=ResumeImprovementResult,
                ),
            )
            if isinstance(response.parsed, ResumeImprovementResult):
                return response.parsed
            if response.text:
                return ResumeImprovementResult.model_validate_json(response.text)
        except (errors.APIError, ValueError) as error:
            logger.exception("Gemini resume improvement failed")
            raise AIProviderError() from error

        raise AIProviderError("The improvement service returned an empty response.")
