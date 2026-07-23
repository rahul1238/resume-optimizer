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
    metric_pattern = re.compile(
        r"(?<![\w])\d[\d,]*(?:\.\d+)?"
        r"(?:\s*[-–—]\s*\d[\d,]*(?:\.\d+)?)?"
        r"\s*(?:%|[KMBkmb]\+?|\+)?"
    )
    named_term_pattern = re.compile(
        r"\b(?:[A-Z]{2,}[A-Za-z0-9]*|[A-Z][a-z]+[A-Z][A-Za-z0-9]*"
        r"|[A-Z][a-z]{2,})\b"
    )

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

        proposed_bullets: list[str] = []
        preserved_original = False
        for index, bullet in enumerate(optimized.bullets):
            proposed = f"- {bullet.text.strip()}"
            if mode == "rewrite" and (
                bullet.source_indices != [index]
                or not cls._rewrite_preserves_evidence(
                    source_bullets[index],
                    proposed,
                    candidate_skills,
                )
            ):
                proposed = cls._format_bullet(source_bullets[index])
                preserved_original = True
            proposed_bullets.append(proposed)
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
            evidence_text = " ".join(
                source_bullets[index]
                for index in optimized.bullets[suggestion.bullet_index].source_indices
            )
            if all(cls._contains_skill(evidence_text, skill) for skill in skills):
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
            rationale=(
                f"{optimized.rationale} Some bullets were kept unchanged because "
                "the rewrite did not preserve their source facts exactly."
                if preserved_original
                else optimized.rationale
            ),
        )

    @classmethod
    def _rewrite_preserves_evidence(
        cls,
        source: str,
        proposed: str,
        candidate_skills: list[str],
    ) -> bool:
        source_metrics = {
            cls._normalize_evidence(item)
            for item in cls.metric_pattern.findall(source)
            if item.strip()
        }
        proposed_metrics = {
            cls._normalize_evidence(item)
            for item in cls.metric_pattern.findall(proposed)
            if item.strip()
        }
        if not source_metrics.issubset(proposed_metrics):
            return False

        named_terms = cls.named_term_pattern.findall(
            cls.bullet_pattern.sub("", source, count=1)
        )
        if named_terms:
            named_terms = named_terms[1:]
        normalized_proposal = AnalysisService._normalize_match_text(proposed)
        if any(
            not AnalysisService._contains_keyword(normalized_proposal, term)
            for term in named_terms
        ):
            return False

        return all(
            not cls._contains_skill(source, skill)
            or cls._contains_skill(proposed, skill)
            for skill in candidate_skills
        )

    @staticmethod
    def _normalize_evidence(value: str) -> str:
        return re.sub(r"\s+", "", value).replace("–", "-").replace("—", "-").casefold()

    @classmethod
    def _contains_skill(cls, text: str, skill: str) -> bool:
        normalized_text = AnalysisService._normalize_match_text(text)
        aliases = {skill}
        words = re.findall(r"[A-Za-z0-9]+", skill)
        if len(words) > 1:
            acronym = "".join(word[0] for word in words if word).upper()
            if len(acronym) >= 2:
                aliases.add(acronym)
            core_words = [
                word
                for word in words
                if word.casefold()
                not in {
                    "architecture",
                    "development",
                    "engineering",
                    "framework",
                    "platform",
                }
            ]
            if len(core_words) >= 2:
                aliases.add(" ".join(core_words))
        return any(
            AnalysisService._contains_keyword(normalized_text, alias)
            for alias in aliases
        )

    @classmethod
    def _format_bullet(cls, value: str) -> str:
        return f"- {cls.bullet_pattern.sub('', value, count=1).strip()}"

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
