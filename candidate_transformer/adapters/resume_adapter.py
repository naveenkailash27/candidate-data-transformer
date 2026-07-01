from __future__ import annotations

import re
from pathlib import Path

from ..models import Method
from .base import ExtractionFailure, FieldValue, SourceRecord

SOURCE = "resume"
_RE = Method.REGEX_EXTRACTION.value

_CLEAN = str.maketrans({
    "�": "-", "–": "-", "—": "-", "‒": "-", "‐": "-", "‑": "-",
    "•": "-", "●": "-", "▪": "-", "⁃": "-",
    " ": " ", "’": "'", "‘": "'",
})

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_YEAR = re.compile(r"(?:19|20)\d{2}")
_DEGREE = re.compile(r"\b(Ph\.?\s?D|B\.?\s?Sc|M\.?\s?Sc|B\.?\s?E|M\.?\s?E|B\.?\s?S|M\.?\s?S|B\.?\s?A|M\.?\s?A|B\.?\s?Tech|M\.?\s?Tech|Bachelor[a-z']*|Master[a-z']*|MBA)\b", re.I)
_INSTITUTION = re.compile(r"\b(University|College|Institute|School|Academy)\b|\bUC\b", re.I)

_GITHUB_URL = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9-]+", re.I)
_LINKEDIN_URL = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9-]+", re.I)

_DATE = r"(?:\d{1,2}[/-]\d{4}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|(?:19|20)\d{2})"
_RANGE = re.compile(rf"({_DATE})\s*(?:-|to)\s*({_DATE}|Present|Current|Now)", re.I)
_LOCATION_TAIL = re.compile(r"\s+[A-Z][a-zA-Z.]+,\s*[A-Z][a-zA-Z.]+\s*$")
_CATEGORY = re.compile(r"\s[-:]\s")
_BULLET = re.compile(r"^[•●\-\*]")

_HEADERS = {
    "experience": {"experience", "work experience", "employment", "professional experience", "work history"},
    "education": {"education", "academic background", "academic qualifications"},
    "skills": {"skills", "technical skills", "technologies", "technical proficiencies", "core competencies"},
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

    return _parse(text.translate(_CLEAN), p)


def _known_section(line: str) -> str | None:
    key = line.strip().lower().rstrip(":")
    for name, aliases in _HEADERS.items():
        if key in aliases:
            return name
    return None


def _is_header(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 40 or len(s.split()) > 5:
        return False
    if s.endswith(":"):
        return True
    return s == s.upper() and any(c.isalpha() for c in s) and not any(c.isdigit() for c in s)


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        known = _known_section(line)
        if known:
            current = known
            sections.setdefault(current, [])
        elif _is_header(line):
            current = None
        elif current:
            sections[current].append(line)
    return sections


def _strip_category(token: str) -> str:
    parts = _CATEGORY.split(token)
    return parts[-1].strip() if len(parts) > 1 else token


def _parse_skills(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        text = line.strip().replace("(", ", ").replace(")", ", ")
        if not text:
            continue
        tokens = [t.strip(" .") for t in re.split(r"[,;|]", text) if t.strip(" .")]
        if tokens:
            tokens[0] = _strip_category(tokens[0]).strip(" .")
        for tok in tokens:
            if tok and len(tok) <= 35 and len(tok.split()) <= 5:
                out.append(tok)
    return out


def _clean_role_text(text: str) -> str:
    return _LOCATION_TAIL.sub("", text).strip(" ,-|")


def _parse_experience(lines: list[str]) -> list[dict]:
    roles: list[dict] = []
    awaiting_title = None
    for line in lines:
        s = line.strip()
        if not s:
            continue
        m = _RANGE.search(s)
        if m:
            start, end = m.group(1), m.group(2)
            ongoing = end.lower() in {"present", "current", "now"}
            head = s[: m.start()].strip(" ,-|\t")
            title = company = None
            if head:
                if re.search(r",| at ", head):
                    parts = re.split(r"\s+at\s+|,", head, maxsplit=1)
                    title = parts[0].strip() or None
                    company = parts[1].strip(" ,-|") if len(parts) > 1 else None
                else:
                    company = head
            roles.append({"company": company, "title": title, "start": start, "end": None if ongoing else end, "ongoing": ongoing, "summary": None})
            awaiting_title = len(roles) - 1 if title is None else None
            continue

        if awaiting_title is not None and not _BULLET.match(s):
            roles[awaiting_title]["title"] = _clean_role_text(s) or None
            awaiting_title = None
            continue

        if roles:
            frag = s.lstrip("•●-* ").strip()
            roles[-1]["summary"] = (roles[-1]["summary"] + " " + frag) if roles[-1]["summary"] else frag
    return roles


def _parse_education(lines: list[str]) -> list[dict]:
    out: list[dict] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        years = [int(y) for y in _YEAR.findall(s)]
        end_year = max(years) if years else None
        parts = [p.strip() for p in re.split(r"[,|]", s) if p.strip()]
        institution = next((p for p in parts if _INSTITUTION.search(p)), None)
        deg_m = _DEGREE.search(s)
        degree = deg_m.group(0).strip() if deg_m else None
        if not institution and not degree:
            continue
        field = None
        if deg_m:
            deg_part = next((p for p in parts if degree in p), "")
            remainder = deg_part.replace(degree, "", 1)
            field = re.split(r"(?:19|20)\d{2}|\||\s[-]\s", remainder)[0].strip(" .,-") or None
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
        if "@" not in first and _known_section(first) is None:
            fields["full_name"] = FieldValue(first, _RE)

    links: dict = {}
    gh = _GITHUB_URL.search(text)
    li = _LINKEDIN_URL.search(text)
    if gh:
        links["github"] = gh.group(0)
    if li:
        links["linkedin"] = li.group(0)
    if links:
        fields["links"] = FieldValue(links, _RE)

    if "skills" in sections:
        skills = _parse_skills(sections["skills"])
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
