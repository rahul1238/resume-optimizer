import re
from dataclasses import dataclass
from typing import Literal

from app.services.resume_service import ResumeService


@dataclass(frozen=True)
class ATSCheck:
    check_id: str
    label: str
    status: Literal["pass", "warning", "fail"]
    detail: str
    weight: int


@dataclass(frozen=True)
class ATSScan:
    score: int
    checks: list[ATSCheck]
    recommendations: list[str]


class ATSScanService:
    section_patterns = {
        "experience": r"(?im)^\s*(?:professional |work )?experience\s*:?[ \t]*$",
        "education": r"(?im)^\s*education\s*:?[ \t]*$",
        "skills": r"(?im)^\s*(?:technical )?skills\s*:?[ \t]*$",
    }

    @classmethod
    def scan(cls, owner_uid: str, resume_id: str) -> ATSScan:
        resume = ResumeService.get(owner_uid, resume_id)
        text = resume.text.strip()
        word_count = len(re.findall(r"\b[\w+#.-]+\b", text))
        checks = [
            cls._binary_check(
                "parseable_text",
                "Machine-readable text",
                len(text) >= 300,
                "The resume contains enough extractable text for ATS parsing.",
                "Very little text was extracted. Avoid scanned or image-only resumes.",
                20,
            ),
            cls._binary_check(
                "email",
                "Email address",
                bool(re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", text)),
                "An email address is machine-readable.",
                "Add a professional email address as plain text.",
                10,
            ),
            cls._binary_check(
                "phone",
                "Phone number",
                bool(re.search(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)", text)),
                "A phone number is machine-readable.",
                "Add a phone number as text rather than an icon or image.",
                8,
            ),
            cls._binary_check(
                "professional_links",
                "Professional links",
                bool(re.search(r"(?:https?://|linkedin\.com|github\.com)", text, re.I)),
                "At least one professional profile link was detected.",
                "Add complete LinkedIn, GitHub, or portfolio URLs when relevant.",
                7,
                warning=True,
            ),
        ]
        for name, pattern, weight in (
            ("experience", cls.section_patterns["experience"], 12),
            ("education", cls.section_patterns["education"], 10),
            ("skills", cls.section_patterns["skills"], 10),
        ):
            checks.append(
                cls._binary_check(
                    f"section_{name}",
                    f"{name.title()} section",
                    bool(re.search(pattern, text)),
                    f"A standard {name} heading was detected.",
                    f"Use a conventional '{name.title()}' section heading.",
                    weight,
                )
            )
        checks.extend(
            [
                cls._binary_check(
                    "achievement_bullets",
                    "Scannable bullet points",
                    len(re.findall(r"(?m)^\s*[-*•]\s+", text)) >= 3,
                    "The resume uses scannable achievement bullets.",
                    "Use concise bullets for experience and project achievements.",
                    8,
                    warning=True,
                ),
                cls._binary_check(
                    "dated_experience",
                    "Employment dates",
                    bool(
                        re.search(
                            r"\b(?:19|20)\d{2}\b|\b(?:present|current)\b",
                            text,
                            re.I,
                        )
                    ),
                    "A machine-readable date or current-role marker was detected.",
                    "Add plain-text dates to experience and education entries.",
                    7,
                ),
                ATSCheck(
                    "content_length",
                    "Resume length",
                    "pass" if 250 <= word_count <= 1_200 else "warning",
                    (
                        f"The resume contains {word_count} words, within a "
                        "practical ATS range."
                        if 250 <= word_count <= 1_200
                        else f"The resume contains {word_count} words. Keep the "
                        "base resume complete and tailor exported versions for "
                        "relevance."
                    ),
                    8,
                ),
            ]
        )
        possible = sum(check.weight for check in checks)
        earned = sum(
            check.weight
            if check.status == "pass"
            else check.weight * 0.5
            if check.status == "warning"
            else 0
            for check in checks
        )
        return ATSScan(
            score=round(earned / possible * 100),
            checks=checks,
            recommendations=[
                check.detail for check in checks if check.status != "pass"
            ],
        )

    @staticmethod
    def _binary_check(
        check_id: str,
        label: str,
        passed: bool,
        success: str,
        failure: str,
        weight: int,
        *,
        warning: bool = False,
    ) -> ATSCheck:
        return ATSCheck(
            check_id=check_id,
            label=label,
            status="pass" if passed else "warning" if warning else "fail",
            detail=success if passed else failure,
            weight=weight,
        )
