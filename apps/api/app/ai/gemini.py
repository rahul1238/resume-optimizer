import logging

from google import genai
from google.genai import errors, types

from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderQuotaError,
)
from app.ai.schemas import (
    GeminiResumeImprovementResult,
    ResumeAnalysisResult,
    ResumeImprovementResult,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiProvider:
    name = "gemini"
    fallback_status_codes = {429, 500, 503, 504}

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise AIProviderConfigurationError()
        self.model = settings.gemini_model
        self._models = list(
            dict.fromkeys([settings.gemini_model, *settings.gemini_fallback_models])
        )
        self._client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=settings.gemini_timeout_seconds * 1000
            ),
        )

    def _generate(self, prompt: str, response_schema):
        last_error: errors.APIError | None = None
        for index, model in enumerate(self._models):
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        response_mime_type="application/json",
                        response_schema=response_schema,
                    ),
                )
                self.model = model
                if index > 0:
                    self._models.insert(0, self._models.pop(index))
                return response
            except errors.APIError as error:
                last_error = error
                has_fallback = index < len(self._models) - 1
                if error.code not in self.fallback_status_codes or not has_fallback:
                    raise
                logger.warning(
                    "Gemini model unavailable; trying fallback",
                    extra={
                        "failed_model": model,
                        "fallback_model": self._models[index + 1],
                        "status_code": error.code,
                    },
                )
        if last_error:
            raise last_error
        raise AIProviderError("No Gemini models are configured.")

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
            response = self._generate(prompt, ResumeAnalysisResult)
            if isinstance(response.parsed, ResumeAnalysisResult):
                return response.parsed
            if response.text:
                return ResumeAnalysisResult.model_validate_json(response.text)
        except (errors.APIError, ValueError) as error:
            logger.exception("Gemini resume analysis failed")
            if isinstance(error, errors.APIError) and error.code == 429:
                raise AIProviderQuotaError() from error
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
that is unsupported by the resume in integrity_notes instead of adding it.

Treat RESUME as an immutable master career profile containing everything the
candidate can truthfully claim. Produce a targeted derivative, not another master
resume. First distinguish required job qualifications from recommended ones.
Select skills, projects, and experience bullets only when they support a required
qualification, a recommended qualification, or essential context for the target
role. For example, a backend application should omit unrelated frontend tools
unless the job asks for them or they materially support a selected achievement.
Do not keyword-stuff or retain unrelated content merely because space is available.

Preserve every employer, role, and date range so tailoring cannot create employment
gaps. An irrelevant role may be condensed, but never removed. Prefer the strongest
three to six relevant bullets for a recent role and fewer for older or less relevant
roles. Keep the master resume unchanged; omissions apply only to this tailored draft.
Populate tailoring_decisions for selected and omitted skills, projects, experience
bullets, and employment entries. Identify whether each item serves a required,
recommended, supporting, or irrelevant requirement, and cite the matched job
requirements. Employment decisions must use include or condense, never omit.

For each proposed edit, add one atomic change_set item. Include the exact original
text, the suggested replacement, its target section, a concise reason, and up to
five exact facts from the resume as evidence. Set requires_confirmation to true
when the evidence is indirect or incomplete. Use confidence conservatively.
For an important job requirement that may be relevant but is not supported, create
a clarification_question that asks about the candidate's real experience instead
of adding the requirement. Do not ask about requirements that are clearly
irrelevant. Return structured_resume with the complete draft divided into header
and sections; every structured item must also appear in optimized_resume_draft.

When a current draft and user feedback are provided, revise the draft according
to those editing preferences, but treat them as preferences rather than factual
evidence.
Also produce optimized_resume_draft as a complete, plain-text resume ready for
editing. Preserve all useful factual content and recognizable section structure.
Preserve every supported URL from the resume. Show profile links as ATS-readable
text such as "LinkedIn: https://linkedin.com/in/username" rather than hiding the
destination behind a username, icon, or generic label.
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
            response = self._generate(prompt, GeminiResumeImprovementResult)
            if isinstance(response.parsed, GeminiResumeImprovementResult):
                return response.parsed.to_domain()
            if response.text:
                return GeminiResumeImprovementResult.model_validate_json(
                    response.text
                ).to_domain()
        except (errors.APIError, ValueError) as error:
            logger.exception("Gemini resume improvement failed")
            if isinstance(error, errors.APIError) and error.code == 429:
                raise AIProviderQuotaError() from error
            raise AIProviderError() from error

        raise AIProviderError("The improvement service returned an empty response.")
