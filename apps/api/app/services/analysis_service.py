from __future__ import annotations

import re
import unicodedata
from uuid import uuid4

from app.ai.factory import get_ai_provider
from app.ai.schemas import ResumeAnalysisResult
from app.models.analysis import AnalysisRecord
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.improvement_repository import ImprovementRepository
from app.repositories.resume_repository import ResumeRepository
from app.services.resume_storage_service import ResumeStorageService


class AnalysisService:
    technical_aliases = {
        "c++": "cplusplus",
        "c#": "csharp",
        ".net": "dotnet",
        "node.js": "nodejs",
    }

    @staticmethod
    def list(owner_uid: str, resume_id: str | None = None) -> list[AnalysisRecord]:
        return AnalysisRepository.list_owned(owner_uid, resume_id)

    @staticmethod
    def get(owner_uid: str, analysis_id: str) -> AnalysisRecord:
        return AnalysisRepository.get_owned(analysis_id, owner_uid)

    @staticmethod
    def delete(owner_uid: str, analysis_id: str) -> None:
        AnalysisRepository.get_owned(analysis_id, owner_uid)
        ImprovementRepository.delete(analysis_id)
        AnalysisRepository.delete(analysis_id)

    @staticmethod
    def coverage(
        owner_uid: str,
        analysis_id: str,
        draft: str,
    ) -> tuple[int, list[str], list[str]]:
        record = AnalysisRepository.get_owned(analysis_id, owner_uid)
        result = ResumeAnalysisResult.model_validate(record.result)
        return AnalysisService.keyword_coverage(result, draft)

    @staticmethod
    def keyword_coverage(
        result: ResumeAnalysisResult,
        draft: str,
    ) -> tuple[int, list[str], list[str]]:
        keywords = list(
            dict.fromkeys([*result.matched_keywords, *result.missing_keywords])
        )
        normalized_draft = AnalysisService._normalize_match_text(draft)
        covered = [
            keyword
            for keyword in keywords
            if AnalysisService._contains_keyword(normalized_draft, keyword)
        ]
        missing = [keyword for keyword in keywords if keyword not in covered]
        score = round(len(covered) / len(keywords) * 100) if keywords else 100
        return score, covered, missing

    @staticmethod
    def _contains_keyword(normalized_draft: str, keyword: str) -> bool:
        normalized_keyword = AnalysisService._normalize_match_text(keyword)
        if not normalized_keyword:
            return False
        return f" {normalized_keyword} " in f" {normalized_draft} "

    @staticmethod
    def _normalize_match_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKC", value).casefold()
        for source, replacement in AnalysisService.technical_aliases.items():
            normalized = normalized.replace(source, replacement)
        return re.sub(r"[^a-z0-9]+", " ", normalized).strip()

    @staticmethod
    def analyze(
        owner_uid: str,
        resume_id: str,
        job_description: str,
        job_title: str | None,
        company_name: str | None,
    ) -> tuple[str, str, str, ResumeAnalysisResult]:
        resume = ResumeRepository.get_owned(resume_id, owner_uid)
        resume_text = ResumeStorageService.read_text(resume.text_storage_path)
        provider = get_ai_provider()
        result = provider.analyze_resume(
            resume_text=resume_text,
            job_description=job_description,
            job_title=job_title,
            company_name=company_name,
        )
        analysis_id = str(uuid4())
        AnalysisRepository.create(
            AnalysisRecord(
                analysis_id=analysis_id,
                owner_uid=owner_uid,
                resume_id=resume_id,
                job_description=job_description,
                job_title=job_title,
                company_name=company_name,
                provider=provider.name,
                model=provider.model,
                status="completed",
                result=result.model_dump(),
            )
        )
        return analysis_id, provider.name, provider.model, result
