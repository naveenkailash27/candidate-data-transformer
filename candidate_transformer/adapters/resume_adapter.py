from __future__ import annotations

import re
from pathlib import Path

from ..models import Method
from .base import ExtractionFailure, FieldValue, SourceRecord

SOURCE = "resume"
_RE = Method.REGEX_EXTRACTION.value

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")
_DEGREE = re.compile(r"\b(Ph\.?\s?D|B\.?\s?Sc|M\.?\s?Sc|B\.?\s?S|M\.?\s?S|B\.?\s?A|M\.?\s?A|B\.?\s?Tech|M\.?\s?Tech|Bachelor[a-z']*|Master[a-z']*|MBA)\b", re.I)
_INSTITUTION = re.compile(r"\b(University|College|Institute|School|Academy)\b|\bUC\b", re.I)

_MONTH = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_DATE = rf"(?:{_MONTH}\s+)?(?:19|20)\d{{2}}"
_RANGE = re.compile(rf"({_DATE})\s*(?:-|–|—|to)\s*({_DATE}|Present|Current|Now)", re.I)

_HEADERS = {
    "experience": {"experience", "work experience", "employment", "professional experience"},
    "education": {"education", "academic background"},
    "skills": {"skills", "technical skills", "technologies"},
}


def _pdf_text(path: Path) -> str:
    import pdfplumber

    parts = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def extract_resume(path: str | Path) -> SourceRecord | ExtractionFailure:
    p = Path(path)
    suffix = p.suffix.lower()
    try:
        if suffix == ".pdf":
            text = _pdf_text(p)
        elif suffix == ".txt":
            text = p.read_text(encoding="utf-8", errors="ignore")
        else:
            return ExtractionFailure(SOURCE, str(path), f"unsupported resume type: {suffix}")
    except FileNotFoundError:
        return ExtractionFailure(SOURCE, str(path), "file not found")
    except Exception as exc:
        return ExtractionFailure(SOURCE, str(path), f"unparseable: {exc}")

    if not text.strip():
        return ExtractionFailure(SOURCE, str(path), "no extractable text (image-only or empty)")

    return _parse(text, p)


def _section_of(line: str) -> str | None:
    key = line.strip().lower().rstrip(":")
    for name, aliases in _HEADERS.items():
        if key in aliases:
            return name
    return None


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        section = _section_of(line)
        if section:
            current = section
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return sections


def _parse_experience(lines: list[str]) -> list[dict]:
    roles: list[dict] = []
    for line in lines:
        m = _RANGE.search(line)
        if not m:
            if roles and line.strip():
                roles[-1]["summary"] = (roles[-1].get("summary") or "") + (" " if roles[-1].get("summary") else "") + line.strip()
            continue
        start, end = m.group(1), m.group(2)
        ongoing = end.lower() in {"present", "current", "now"}
        head = line[: m.start()].strip(" ,-–—|\t")
        title, company = None, None
        if head:
            parts = re.split(r"\s+at\s+|,|\||–|—|-", head, maxsplit=1)
            title = parts[0].strip() or None
            if len(parts) > 1:
                company = parts[1].strip(" ,-–—|") or None
        roles.append({"company": company, "title": title, "start": start, "end": None if ongoing else end, "ongoing": ongoing})
    return roles


def _parse_education(lines: list[str]) -> list[dict]:
    out: list[dict] = []
    for line in lines:
        if not line.strip():
            continue
        year_m = _YEAR.search(line)
        end_year = int(year_m.group(0)) if year_m else None
        parts = [p.strip() for p in line.split(",") if p.strip()]
        institution = next((p for p in parts if _INSTITUTION.search(p)), None)

        deg_m = _DEGREE.search(line)
        degree = deg_m.group(0).strip() if deg_m else None

        field = None
        if degree:
            deg_part = next((p for p in parts if degree in p), None)
            if deg_part:
                field = re.sub(re.escape(degree), "", deg_part, count=1).strip(" .,-") or None
        if field is None:
            for p in parts:
                if p == institution or (p.isdigit() and len(p) == 4) or (degree and degree in p):
                    continue
                field = p
                break

        out.append({"institution": institution, "degree": degree, "field": field, "end_year": end_year})
    return out


def _parse(text: str, path: Path) -> SourceRecord:
    lines = [ln.rstrip() for ln in text.splitlines()]
    nonempty = [ln for ln in lines if ln.strip()]
    sections = _split_sections(lines)

    fields: dict[str, FieldValue] = {}

    emails = sorted({e.lower() for e in _EMAIL.findall(text)})
    if emails:
        fields["emails"] = FieldValue(emails, _RE)

    phones = [m.group(0).strip() for m in _PHONE.finditer(text)]
    if phones:
        fields["phones"] = FieldValue(phones, _RE)

    if nonempty:
        first = nonempty[0].strip()
        if "@" not in first and not _section_of(first):
            fields["full_name"] = FieldValue(first, _RE)

    if "skills" in sections:
        raw = " ".join(sections["skills"])
        skills = [s.strip() for s in re.split(r"[,;|]", raw) if s.strip()]
        if skills:
            fields["skills"] = FieldValue(skills, _RE)

    if "experience" in sections:
        roles = _parse_experience(sections["experience"])
        if roles:
            fields["experience"] = FieldValue(roles, _RE)

    if "education" in sections:
        edu = _parse_education(sections["education"])
        if edu:
            fields["education"] = FieldValue(edu, _RE)

    return SourceRecord(SOURCE, f"resume:{path.name}", fields, raw={"text": text})
