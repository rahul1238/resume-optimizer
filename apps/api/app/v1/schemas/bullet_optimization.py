from typing import Literal

from pydantic import BaseModel, Field


class BulletOptimizationRequest(BaseModel):
    section_id: str = Field(min_length=1, max_length=80)
    group_index: int = Field(ge=0, le=50)
    target_count: int = Field(ge=1, le=12)
    mode: Literal["prioritize", "consolidate", "expand", "rewrite"]


class SkillIntegrationResponse(BaseModel):
    suggestion_id: str
    bullet_index: int
    skills: list[str]
    suggested_bullet: str
    reason: str


class BulletOptimizationResponse(BaseModel):
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
    skill_integrations: list[SkillIntegrationResponse]
    rationale: str
    can_apply: bool
