from typing import Literal

from pydantic import BaseModel, Field


class ResumeLayoutSettings(BaseModel):
    template: Literal["classic", "compact", "technical"] = "classic"
    page_format: Literal["a4", "letter"] = "a4"
    heading_font: Literal["sans", "serif"] = "sans"
    body_font: Literal["sans", "serif"] = "sans"
    heading_size: float = Field(default=11, ge=10, le=15)
    body_size: float = Field(default=10, ge=9.5, le=12)
    name_size: float = Field(default=17, ge=14, le=22)
    line_spacing: float = Field(default=1.2, ge=1.05, le=1.5)
    margin_top: float = Field(default=0.5, ge=0.35, le=1.2)
    margin_right: float = Field(default=0.55, ge=0.35, le=1.2)
    margin_bottom: float = Field(default=0.5, ge=0.35, le=1.2)
    margin_left: float = Field(default=0.55, ge=0.35, le=1.2)
    section_spacing: float = Field(default=7, ge=2, le=16)
    heading_content_spacing: float = Field(default=3.4, ge=1, le=10)
    block_spacing: float = Field(default=2.5, ge=0, le=10)
