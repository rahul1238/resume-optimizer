from types import SimpleNamespace

import pytest
from google.genai import errors

from app.ai.gemini import GeminiProvider
from app.ai.provider import AIProviderError
from app.ai.schemas import ResumeAnalysisResult
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
