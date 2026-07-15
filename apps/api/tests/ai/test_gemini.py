from types import SimpleNamespace

import pytest
from google.genai import errors

from app.ai.gemini import GeminiProvider
from app.ai.provider import AIProviderError, AIProviderQuotaError
from app.ai.schemas import (
    GeminiResumeImprovementResult,
    ResumeAnalysisResult,
)
from app.core.config import settings


def analysis_result() -> ResumeAnalysisResult:
    return ResumeAnalysisResult(
        match_score=80,
        summary="Strong match.",
        strengths=["Python"],
        recommendations=["Add measurable outcomes."],
    )


def provider_with_client(monkeypatch: pytest.MonkeyPatch, generate_content):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "primary-model")
    monkeypatch.setattr(
        settings,
        "gemini_fallback_models",
        ["fallback-one", "fallback-two"],
    )
    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content),
    )
    monkeypatch.setattr("app.ai.gemini.genai.Client", lambda **_kwargs: client)
    return GeminiProvider()


def test_uses_fallback_after_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called_models: list[str] = []

    def generate_content(**kwargs):
        called_models.append(kwargs["model"])
        if kwargs["model"] == "primary-model":
            raise errors.ServerError(
                503,
                {"error": {"code": 503, "status": "UNAVAILABLE"}},
            )
        return SimpleNamespace(parsed=analysis_result(), text=None)

    provider = provider_with_client(monkeypatch, generate_content)
    result = provider.analyze_resume("Resume", "Job description", None, None)

    assert result.match_score == 80
    assert called_models == ["primary-model", "fallback-one"]
    assert provider.model == "fallback-one"

    provider.analyze_resume("Resume", "Another job description", None, None)
    assert called_models[-1] == "fallback-one"


def test_uses_fallback_after_model_quota_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called_models: list[str] = []

    def generate_content(**kwargs):
        called_models.append(kwargs["model"])
        if kwargs["model"] == "primary-model":
            raise errors.ClientError(
                429,
                {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}},
            )
        return SimpleNamespace(parsed=analysis_result(), text=None)

    provider = provider_with_client(monkeypatch, generate_content)
    result = provider.analyze_resume("Resume", "Job description", None, None)

    assert result.match_score == 80
    assert called_models == ["primary-model", "fallback-one"]


def test_reports_quota_after_all_models_are_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def generate_content(**_kwargs):
        raise errors.ClientError(
            429,
            {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED"}},
        )

    provider = provider_with_client(monkeypatch, generate_content)

    with pytest.raises(AIProviderQuotaError):
        provider.analyze_resume("Resume", "Job description", None, None)


def test_does_not_fallback_for_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called_models: list[str] = []

    def generate_content(**kwargs):
        called_models.append(kwargs["model"])
        raise errors.ClientError(
            400,
            {"error": {"code": 400, "status": "INVALID_ARGUMENT"}},
        )

    provider = provider_with_client(monkeypatch, generate_content)

    with pytest.raises(AIProviderError):
        provider.analyze_resume("Resume", "Job description", None, None)
    assert called_models == ["primary-model"]


def test_compact_improvement_schema_converts_to_domain_result() -> None:
    wire = GeminiResumeImprovementResult(
        optimized_resume_draft="Jordan Lee\n\nSUMMARY\nBackend engineer.",
        suggested_summary="Backend engineer.",
        summary_reason="Concise and relevant.",
        bullet_rewrites=[],
        skills_to_emphasize=["Python"],
        ats_recommendations=["Use standard headings."],
        integrity_notes=[],
        change_set=[
            {
                "change_type": "summary",
                "target_section": "Summary",
                "original": "Engineer.",
                "suggested": "Backend engineer.",
                "reason": "Targets the role.",
                "evidence": ["Python"],
                "confidence": 0.9,
                "requires_confirmation": False,
            }
        ],
        clarification_questions=[
            {
                "requirement": "Kubernetes",
                "question": "Have you deployed services to Kubernetes?",
                "target_section": "Experience",
            }
        ],
        tailoring_decisions=[],
    )

    result = wire.to_domain()

    assert result.change_set[0].status == "proposed"
    assert result.change_set[0].change_id == ""
    assert result.structured_resume is None
    assert result.clarification_questions[0].target_section == "Experience"
    assert result.clarification_questions[0].integration_mode is None
