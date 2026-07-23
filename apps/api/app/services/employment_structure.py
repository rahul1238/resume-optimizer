from __future__ import annotations

import re
from dataclasses import dataclass

_BULLET = re.compile(r"^\s*[-*\u2022]\s+")
_DATE = re.compile(
    r"(?ix)"
    r"(?:\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|"
    r"dec(?:ember)?)\b|\b(?:19|20)\d{2}\b|\b\d{1,2}/\d{2,4}\b|"
    r"\bpresent\b|\bcurrent\b)"
)
_ROLE = re.compile(
    r"(?i)\b(?:engineer|developer|intern|manager|analyst|consultant|specialist|"
    r"associate|architect|administrator|officer|lead|director|designer|"
    r"researcher|support|tester|qa|sde)\b"
)
_ACTION = re.compile(
    r"(?i)^(?:achieved|administered|architected|automated|built|collaborated|"
    r"created|delivered|deployed|designed|developed|drove|enhanced|engineered|"
    r"established|implemented|improved|increased|integrated|launched|led|"
    r"maintained|managed|migrated|optimized|reduced|resolved|scaled|streamlined|"
    r"supported|tested|worked)\b"
)
_WORDS = re.compile(r"[a-z0-9+#]{2,}(?:\.[a-z0-9+#]+)*")


@dataclass(frozen=True)
class EmploymentEntry:
    header: list[str]
    bullets: list[str]

    @property
    def label(self) -> str:
        return self.header[0] if self.header else ""

    @property
    def items(self) -> list[str]:
        return [*self.header, *[f"- {bullet}" for bullet in self.bullets]]


def is_bullet(value: str) -> bool:
    return bool(_BULLET.match(value))


def bullet_text(value: str) -> str:
    return _BULLET.sub("", value).strip()


def parse_employment_entries(items: list[str]) -> list[EmploymentEntry]:
    cleaned = [re.sub(r"\s+", " ", item).strip() for item in items if item.strip()]
    starts = [
        index
        for index, item in enumerate(cleaned)
        if _looks_like_entry_start(cleaned, index, item)
    ]
    if not starts:
        return _parse_marker_groups(cleaned)

    entries: list[EmploymentEntry] = []
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(cleaned)
        entry = _parse_entry(cleaned[start:end])
        if entry.header:
            entries.append(entry)
    return entries


def entry_similarity(left: EmploymentEntry, right: EmploymentEntry) -> float:
    left_tokens = _title_tokens(left.label)
    right_tokens = _title_tokens(right.label)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def bullet_evidence_score(bullet: str, entry: EmploymentEntry) -> float:
    candidate = _tokens(bullet)
    evidence = _tokens(" ".join(entry.bullets))
    if not candidate or not evidence:
        return 0.0
    return len(candidate & evidence) / len(candidate)


def deduplicate_bullets(bullets: list[str]) -> list[str]:
    kept: list[str] = []
    signatures: list[set[str]] = []
    for bullet in bullets:
        normalized = bullet_text(bullet)
        signature = _tokens(normalized)
        if not normalized or any(
            signature
            and existing
            and len(signature & existing) / min(len(signature), len(existing)) >= 0.8
            for existing in signatures
        ):
            continue
        kept.append(normalized)
        signatures.append(signature)
    return kept


def _looks_like_entry_start(items: list[str], index: int, value: str) -> bool:
    if is_bullet(value) or not _ROLE.search(value):
        return False
    window = items[index : min(index + 5, len(items))]
    return any(_DATE.search(item) for item in window)


def _parse_entry(lines: list[str]) -> EmploymentEntry:
    header = [lines[0]]
    content_start = 1
    saw_date = bool(_DATE.search(lines[0]))
    while content_start < len(lines):
        line = lines[content_start]
        if is_bullet(line) or _ACTION.search(line) or len(line) > 70:
            break
        if _DATE.search(line):
            saw_date = True
            header.append(line)
            content_start += 1
            continue
        if saw_date and len(header) <= 4:
            header.append(line)
            content_start += 1
            continue
        break
    return EmploymentEntry(
        header=header,
        bullets=_merge_narrative(lines[content_start:]),
    )


def _merge_narrative(lines: list[str]) -> list[str]:
    bullets: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            bullets.append(" ".join(current).strip())
            current.clear()

    for line in lines:
        if is_bullet(line):
            flush()
            bullets.append(bullet_text(line))
            continue
        if current and current[-1].endswith((".", "!", "?")):
            flush()
        current.append(line)
    flush()
    return deduplicate_bullets(bullets)


def _parse_marker_groups(items: list[str]) -> list[EmploymentEntry]:
    entries: list[EmploymentEntry] = []
    header: list[str] = []
    bullets: list[str] = []
    for item in items:
        if is_bullet(item):
            bullets.append(bullet_text(item))
        elif bullets:
            entries.append(
                EmploymentEntry(header=header, bullets=deduplicate_bullets(bullets))
            )
            header = [item]
            bullets = []
        else:
            header.append(item)
    if header:
        entries.append(
            EmploymentEntry(header=header, bullets=deduplicate_bullets(bullets))
        )
    return entries


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _WORDS.findall(value.casefold())
        if token
        not in {
            "and",
            "for",
            "from",
            "into",
            "the",
            "using",
            "with",
        }
    }


def _title_tokens(value: str) -> set[str]:
    title = re.split(r"\s+(?:[|–—-]|at)\s+", value, maxsplit=1, flags=re.I)[0]
    return _tokens(title)
