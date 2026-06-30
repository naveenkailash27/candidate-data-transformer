from __future__ import annotations

import hashlib
from datetime import date

from ..adapters.base import SourceRecord
from ..confidence.scorer import agreement_confidence, overall_confidence
from ..models import (
    CanonicalProfile,
    Education,
    Experience,
    Links,
    Location,
    Method,
    Provenance,
    Skill,
    UnmatchedSkill,
)
from ..normalize.country import to_iso3166
from ..normalize.dates import is_present, normalize_month
from ..normalize.phone import normalize_phone
from ..normalize.skills import canonical_skill
from .match import cluster_records

TIERS = {
    "contact": {"csv": 2, "ats": 2, "github": 1, "resume": 1, "linkedin": 1},
    "skill": {"github": 2, "resume": 1, "linkedin": 1, "csv": 1, "ats": 1},
    "education": {"linkedin": 2, "resume": 2, "csv": 1, "github": 1, "ats": 1},
    "default": {"csv": 1, "ats": 1, "github": 1, "resume": 1, "linkedin": 1},
}


def _tier(source: str, category: str) -> int:
    return TIERS.get(category, TIERS["default"]).get(source, 0)


def _collect(cluster: list[SourceRecord], field: str) -> list[tuple[str, object]]:
    return [(r.source, r.fields[field].value) for r in cluster if field in r.fields]


def _pick_scalar(items: list[tuple[str, object]], category: str):
    groups: dict[str, dict] = {}
    for source, value in items:
        if value is None or str(value).strip() == "":
            continue
        key = str(value).strip().lower()
        g = groups.setdefault(key, {"value": value, "sources": set(), "tier": 0})
        g["sources"].add(source)
        g["tier"] = max(g["tier"], _tier(source, category))
    if not groups:
        return None, 0.0, None, []
    conflict = len(groups) > 1
    winner = max(groups.values(), key=lambda g: (len(g["sources"]), g["tier"], str(g["value"]).lower()))
    n = len(winner["sources"])
    conf = agreement_confidence(n, conflict)
    if conflict:
        method = Method.MERGED_CONFLICT_RESOLVED.value
    elif n > 1:
        method = Method.MERGED_AGREEMENT.value
    else:
        method = Method.DIRECT_MAPPING.value
    return winner["value"], conf, method, sorted(winner["sources"])


def _merge_emails(cluster: list[SourceRecord]):
    out: list[str] = []
    sources: set[str] = set()
    for r in cluster:
        fv = r.fields.get("emails")
        if not fv:
            continue
        sources.add(r.source)
        for e in fv.value:
            el = e.strip().lower()
            if el and el not in out:
                out.append(el)
    return sorted(out), sorted(sources)


def _merge_phones(cluster: list[SourceRecord], country: str | None):
    out: list[str] = []
    sources: set[str] = set()
    for r in cluster:
        fv = r.fields.get("phones")
        if not fv:
            continue
        sources.add(r.source)
        for p in fv.value:
            n = normalize_phone(p, country)
            if n and n not in out:
                out.append(n)
    return out, sorted(sources)


def _merge_location(cluster: list[SourceRecord]):
    items = [(r.source, r.fields["location"].value) for r in cluster if "location" in r.fields]
    if not items:
        return Location(), 0.0, []

    def sub(key: str):
        return _pick_scalar([(s, (v.get(key) if v else None)) for s, v in items], "contact")[0]

    country_raw = sub("country")
    location = Location(city=sub("city"), region=sub("region"), country=to_iso3166(country_raw) if country_raw else None)
    sources = sorted({s for s, _ in items})
    return location, agreement_confidence(len(sources), False), sources


def _merge_links(cluster: list[SourceRecord]):
    links = Links()
    sources: set[str] = set()
    for r in cluster:
        fv = r.fields.get("links")
        if not fv:
            continue
        sources.add(r.source)
        d = fv.value
        links.github = links.github or d.get("github")
        links.linkedin = links.linkedin or d.get("linkedin")
        links.portfolio = links.portfolio or d.get("portfolio")
        for o in d.get("other", []) or []:
            if o and o not in links.other:
                links.other.append(o)
    return links, sorted(sources)


def _merge_skills(cluster: list[SourceRecord]):
    matched: dict[str, set[str]] = {}
    unmatched: dict[str, dict] = {}
    for r in cluster:
        fv = r.fields.get("skills")
        if not fv:
            continue
        for raw in fv.value:
            canon = canonical_skill(raw)
            if canon:
                matched.setdefault(canon, set()).add(r.source)
            else:
                key = str(raw).strip().lower()
                ent = unmatched.setdefault(key, {"raw_text": str(raw).strip(), "sources": set()})
                ent["sources"].add(r.source)

    skills = []
    for name in sorted(matched):
        srcs = sorted(matched[name])
        conf = agreement_confidence(len(srcs), False)
        method = Method.MERGED_AGREEMENT.value if len(srcs) > 1 else Method.NORMALIZED.value
        skills.append(Skill(name=name, confidence=conf, sources=srcs, method=method))

    unmatched_skills = []
    for key in sorted(unmatched):
        ent = unmatched[key]
        srcs = sorted(ent["sources"])
        unmatched_skills.append(
            UnmatchedSkill(raw_text=ent["raw_text"], sources=srcs, confidence=round(agreement_confidence(len(srcs), False) * 0.6, 2))
        )
    return skills, unmatched_skills


def _merge_experience(cluster: list[SourceRecord]):
    raw: list[dict] = []
    sources: set[str] = set()
    for r in cluster:
        fv = r.fields.get("experience")
        if not fv:
            continue
        sources.add(r.source)
        raw.extend(fv.value)

    merged: list[dict] = []
    for e in raw:
        company = e.get("company") or None
        title = e.get("title") or None
        start = normalize_month(e.get("start")) if e.get("start") else None
        end_raw = e.get("end")
        ongoing = bool(e.get("ongoing")) or is_present(end_raw)
        end = None if (end_raw is None or is_present(end_raw)) else normalize_month(end_raw)

        target = None
        for m in merged:
            if company and m["company"] and company.lower() == m["company"].lower():
                if not title or not m["title"] or title.lower() == m["title"].lower():
                    target = m
                    break
        if target:
            target["title"] = target["title"] or title
            target["start"] = target["start"] or start
            target["end"] = target["end"] or end
            target["ongoing"] = target["ongoing"] or ongoing
            target["summary"] = target["summary"] or e.get("summary")
        else:
            merged.append({"company": company, "title": title, "start": start, "end": end, "ongoing": ongoing, "summary": e.get("summary")})

    return [Experience(**m) for m in merged], sorted(sources)


def _merge_education(cluster: list[SourceRecord]):
    raw: list[dict] = []
    sources: set[str] = set()
    for r in cluster:
        fv = r.fields.get("education")
        if not fv:
            continue
        sources.add(r.source)
        raw.extend(fv.value)

    out: list[Education] = []
    seen: set[tuple] = set()
    for e in raw:
        inst = e.get("institution")
        key = (str(inst).lower() if inst else "", str(e.get("degree") or "").lower(), e.get("end_year"))
        if key in seen:
            continue
        seen.add(key)
        out.append(Education(institution=inst, degree=e.get("degree"), field=e.get("field"), end_year=e.get("end_year")))
    return out, sorted(sources)


def _years_experience(experiences: list[Experience], reference: date):
    ref_ord = reference.year * 12 + reference.month
    intervals: list[tuple[int, int]] = []
    malformed = False
    for e in experiences:
        if not e.start:
            continue
        sy, sm = (int(x) for x in e.start.split("-"))
        start = sy * 12 + sm
        if e.end:
            ey, em = (int(x) for x in e.end.split("-"))
            end = ey * 12 + em
        elif e.ongoing:
            end = ref_ord
        else:
            continue
        if end < start:
            malformed = True
            continue
        intervals.append((start, end))

    if not intervals:
        return None, malformed
    intervals.sort()
    spans = [list(intervals[0])]
    for start, end in intervals[1:]:
        if start <= spans[-1][1]:
            spans[-1][1] = max(spans[-1][1], end)
        else:
            spans.append([start, end])
    months = sum(end - start for start, end in spans)
    return round(months / 12, 1), malformed


def _candidate_id(emails: list[str], name: str | None, cluster: list[SourceRecord]) -> str:
    basis = emails[0] if emails else (name or "")
    if not basis:
        basis = "|".join(sorted(r.record_id for r in cluster))
    return "c_" + hashlib.sha1(basis.lower().encode("utf-8")).hexdigest()[:8]


def build_profile(cluster: list[SourceRecord], reference: date | None = None) -> CanonicalProfile:
    reference = reference or date.today()
    prov: list[Provenance] = []
    fconf: dict[str, float] = {}
    present: set[str] = set()

    name, name_conf, name_method, name_src = _pick_scalar(_collect(cluster, "full_name"), "contact")
    emails, email_src = _merge_emails(cluster)
    location, loc_conf, loc_src = _merge_location(cluster)
    phones, phone_src = _merge_phones(cluster, location.country)
    links, link_src = _merge_links(cluster)
    headline, head_conf, head_method, head_src = _pick_scalar(_collect(cluster, "headline"), "default")
    skills, unmatched_skills = _merge_skills(cluster)
    experience, exp_src = _merge_experience(cluster)
    education, edu_src = _merge_education(cluster)
    years, malformed = _years_experience(experience, reference)

    def add(field: str, sources: list[str], method: str, conf: float):
        present.add(field)
        fconf[field] = conf
        if sources:
            prov.append(Provenance(field=field, source=sorted(set(sources)), method=method))

    if name is not None:
        add("full_name", name_src, name_method, name_conf)
    if emails:
        method = Method.MERGED_AGREEMENT.value if len(email_src) > 1 else Method.DIRECT_MAPPING.value
        add("emails", email_src, method, agreement_confidence(len(email_src), False))
    if phones:
        add("phones", phone_src, Method.NORMALIZED.value, agreement_confidence(len(phone_src), False))
    if location.city or location.region or location.country:
        method = Method.MERGED_AGREEMENT.value if len(loc_src) > 1 else Method.DIRECT_MAPPING.value
        add("location", loc_src, method, loc_conf)
    if links.github or links.linkedin or links.portfolio or links.other:
        add("links", link_src, Method.DIRECT_MAPPING.value, 0.8)
    if headline is not None:
        add("headline", head_src, head_method, head_conf)
    if skills:
        skill_sources = sorted({s for sk in skills for s in sk.sources})
        avg = round(sum(s.confidence for s in skills) / len(skills), 2)
        cross_source = any(len(sk.sources) > 1 for sk in skills)
        method = Method.MERGED_AGREEMENT.value if cross_source else Method.NORMALIZED.value
        add("skills", skill_sources, method, avg)
    if experience:
        add("experience", exp_src, Method.DIRECT_MAPPING.value, agreement_confidence(len(exp_src), False))
    if education:
        add("education", edu_src, Method.DIRECT_MAPPING.value, agreement_confidence(len(edu_src), False))
    if years is not None:
        method = Method.FLAGGED_MALFORMED.value if malformed else Method.INTERVAL_MERGE.value
        add("years_experience", exp_src, method, 0.6 if malformed else 0.8)

    return CanonicalProfile(
        candidate_id=_candidate_id(emails, name, cluster),
        full_name=name,
        emails=emails,
        phones=phones,
        location=location,
        links=links,
        headline=headline,
        years_experience=years,
        skills=skills,
        unmatched_skills=unmatched_skills,
        experience=experience,
        education=education,
        provenance=prov,
        overall_confidence=overall_confidence(fconf, present),
    )


def merge_records(records: list[SourceRecord], reference: date | None = None) -> list[CanonicalProfile]:
    profiles = [build_profile(c, reference) for c in cluster_records(records)]
    profiles.sort(key=lambda p: p.candidate_id)
    return profiles
