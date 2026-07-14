from app.ai.schemas import ResumeAnalysisResult
from app.services.analysis_service import AnalysisService


def analysis_result() -> ResumeAnalysisResult:
    return ResumeAnalysisResult(
        match_score=60,
        summary="Partial match.",
        strengths=["Python"],
        matched_keywords=["Python", "REST APIs", "C++", ".NET"],
        missing_keywords=["Kubernetes", "Node.js"],
        recommendations=["Add supported job keywords."],
    )


def test_keyword_coverage_matches_phrases_and_technical_terms() -> None:
    score, covered, missing = AnalysisService.keyword_coverage(
        analysis_result(),
        "Built REST APIs with Python, C++, .NET, and Node.js.",
    )

    assert score == 83
    assert covered == ["Python", "REST APIs", "C++", ".NET", "Node.js"]
    assert missing == ["Kubernetes"]


def test_keyword_coverage_does_not_match_substrings() -> None:
    result = ResumeAnalysisResult(
        match_score=20,
        summary="Weak match.",
        strengths=["Communication"],
        missing_keywords=["Go"],
        recommendations=["Add supported skills."],
    )

    score, covered, missing = AnalysisService.keyword_coverage(
        result,
        "Coordinated Google Cloud migrations.",
    )

    assert score == 0
    assert covered == []
    assert missing == ["Go"]
