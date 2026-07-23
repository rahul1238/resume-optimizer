import re
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from app.ai.factory import get_ai_provider
from app.ai.provider import AIProviderError
from app.ai.schemas import ResumeAnalysisResult
from app.repositories.analysis_repository import AnalysisRepository
from app.services.analysis_service import AnalysisService
from app.services.improvement_service import ImprovementService


class BulletOptimizationError(AIProviderError):
    status_code = 409
    code = "bullet_optimization_invalid"


@dataclass(frozen=True)
class SkillIntegrationProposal:
    suggestion_id: str
    bullet_index: int
    skills: list[str]
    suggested_bullet: str
    reason: str


@dataclass(frozen=True)
class BulletOptimizationProposal:
    proposal_id: str
    section_id: str
    group_index: int
    entry_label: str
    item_indices: list[int]
    original_bullets: list[str]
    proposed_bullets: list[str]
    target_count: int
    mode: Literal["prioritize", "consolidate", "expand", "rewrite"]
    protected_keywords: list[str]
    lost_keywords: list[str]
    rationale: str
    skill_integrations: list[SkillIntegrationProposal] = field(default_factory=list)

    @property
    def can_apply(self) -> bool:
        return not self.lost_keywords


class BulletOptimizationService:
    bullet_pattern = re.compile(r"^\s*[-*•]\s+")

    @classmethod
    def propose(
        cls,
        owner_uid: str,
        analysis_id: str,
        section_id: str,
        group_index: int,
        target_count: int,
        mode: Literal["prioritize", "consolidate", "expand", "rewrite"],
    ) -> BulletOptimizationProposal:
        improvement = ImprovementService.get(owner_uid, analysis_id)
        result = ImprovementService.result(improvement)
        document = result.structured_resume
        if document is None:
            raise BulletOptimizationError(
                "The tailored resume has no structured content."
            )
        section = next(
            (item for item in document.sections if item.section_id == section_id),
            None,
        )
        if section is None or not cls._is_supported_section(section.heading):
            raise BulletOptimizationError(
                "Choose an experience or project bullet group."
            )
        groups = cls.groups(section.items)
        if group_index < 0 or group_index >= len(groups):
            raise BulletOptimizationError("The selected bullet group no longer exists.")
        entry_label, item_indices, source_bullets = groups[group_index]
        if target_count == len(source_bullets) and mode != "rewrite":
            raise BulletOptimizationError(
                "Choose a different bullet count to create a proposal."
            )
        if mode == "rewrite" and target_count != len(source_bullets):
            raise BulletOptimizationError(
                "JD rewriting keeps the current bullet count."
            )

        analysis = AnalysisRepository.get_owned(analysis_id, owner_uid)
        analysis_result = ResumeAnalysisResult.model_validate(analysis.result)
        source_text = "\n".join(source_bullets)
        protected_keywords = [
            keyword
            for keyword in dict.fromkeys(
                [
                    *analysis_result.matched_keywords,
                    *analysis_result.missing_keywords,
                ]
            )
            if AnalysisService._contains_keyword(
                AnalysisService._normalize_match_text(source_text),
                keyword,
            )
        ]
        provider = get_ai_provider()
        candidate_skills = cls._candidate_skills(document)
        optimized = provider.optimize_bullets(
            source_bullets=source_bullets,
            target_count=target_count,
            mode=mode,
            job_description=analysis.job_description,
            protected_keywords=protected_keywords,
            candidate_skills=candidate_skills,
        )
        if len(optimized.bullets) != target_count:
            raise AIProviderError("The bullet service returned an unexpected count.")
        for bullet in optimized.bullets:
            if any(
                index < 0 or index >= len(source_bullets)
                for index in bullet.source_indices
            ):
                raise AIProviderError(
                    "The bullet service returned invalid evidence links."
                )

        proposed_bullets = [f"- {bullet.text.strip()}" for bullet in optimized.bullets]
        proposed_text = "\n".join(proposed_bullets)
        normalized_proposal = AnalysisService._normalize_match_text(proposed_text)
        lost_keywords = [
            keyword
            for keyword in protected_keywords
            if not AnalysisService._contains_keyword(normalized_proposal, keyword)
        ]
        verified_skills = {skill.casefold(): skill for skill in candidate_skills}
        skill_integrations: list[SkillIntegrationProposal] = []
        seen_bullet_indices: set[int] = set()
        for suggestion in optimized.skill_integrations if mode == "rewrite" else []:
            if (
                suggestion.bullet_index >= len(proposed_bullets)
                or suggestion.bullet_index in seen_bullet_indices
            ):
                continue
            skills = [
                verified_skills[skill.casefold()]
                for skill in suggestion.skills
                if skill.casefold() in verified_skills
            ]
            if not skills:
                continue
            seen_bullet_indices.add(suggestion.bullet_index)
            skill_integrations.append(
                SkillIntegrationProposal(
                    suggestion_id=str(uuid4()),
                    bullet_index=suggestion.bullet_index,
                    skills=list(dict.fromkeys(skills)),
                    suggested_bullet=f"- {suggestion.suggested_text.strip()}",
                    reason=suggestion.reason.strip(),
                )
            )
        return BulletOptimizationProposal(
            proposal_id=str(uuid4()),
            section_id=section_id,
            group_index=group_index,
            entry_label=entry_label,
            item_indices=item_indices,
            original_bullets=source_bullets,
            proposed_bullets=proposed_bullets,
            target_count=target_count,
            mode=mode,
            protected_keywords=protected_keywords,
            lost_keywords=lost_keywords,
            skill_integrations=skill_integrations,
            rationale=optimized.rationale,
        )

    @staticmethod
    def _candidate_skills(document) -> list[str]:
        skills: list[str] = []
        for section in document.sections:
            if "skill" not in section.heading.casefold():
                continue
            for item in section.items:
                value = re.sub(r"^[^:]{1,40}:\s*", "", item)
                skills.extend(
                    part.strip()
                    for part in re.split(r"[,|;/]", value)
                    if part.strip() and len(part.strip()) <= 50
                )
        return list(dict.fromkeys(skills))[:40]

    @classmethod
    def groups(cls, items: list[str]) -> list[tuple[str, list[int], list[str]]]:
        groups: list[tuple[str, list[int], list[str]]] = []
        pending_header: list[str] = []
        index = 0
        while index < len(items):
            if not cls.bullet_pattern.match(items[index]):
                pending_header.append(items[index])
                index += 1
                continue
            label = pending_header[0] if pending_header else "Entry"
            indices: list[int] = []
            bullets: list[str] = []
            while index < len(items) and cls.bullet_pattern.match(items[index]):
                indices.append(index)
                bullets.append(items[index])
                index += 1
            groups.append((label, indices, bullets))
            pending_header = []
        return groups

    @staticmethod
    def _is_supported_section(heading: str) -> bool:
        normalized = heading.casefold()
        return "experience" in normalized or "project" in normalized
