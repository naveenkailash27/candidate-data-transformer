from __future__ import annotations

import re

from rapidfuzz import fuzz

from ..adapters.base import SourceRecord
from ..normalize.phone import normalize_phone

_GITHUB_HANDLE = re.compile(r"github\.com/([A-Za-z0-9-]+)", re.I)

NAME_THRESHOLD = 90
TITLE_THRESHOLD = 85


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def _emails(r: SourceRecord) -> list[str]:
    fv = r.fields.get("emails")
    return [e.strip().lower() for e in fv.value if e.strip()] if fv else []


def _phones(r: SourceRecord) -> list[str]:
    fv = r.fields.get("phones")
    if not fv:
        return []
    return [n for n in (normalize_phone(p) for p in fv.value) if n]


def _name(r: SourceRecord) -> str | None:
    fv = r.fields.get("full_name")
    return fv.value if fv else None


def _company(r: SourceRecord) -> str | None:
    fv = r.fields.get("experience")
    if fv and fv.value:
        return (fv.value[0].get("company") or "").strip().lower() or None
    return None


def _title(r: SourceRecord) -> str | None:
    fv = r.fields.get("experience")
    if fv and fv.value:
        return (fv.value[0].get("title") or "").strip().lower() or None
    return None


def _github(r: SourceRecord) -> str | None:
    fv = r.fields.get("links")
    if fv:
        m = _GITHUB_HANDLE.search(fv.value.get("github") or "")
        if m:
            return m.group(1).lower()
    return None


def _corroborates(a: SourceRecord, b: SourceRecord) -> bool:
    ca, cb = _company(a), _company(b)
    if ca and cb and ca == cb:
        return True
    ta, tb = _title(a), _title(b)
    if ta and tb and fuzz.token_sort_ratio(ta, tb) >= TITLE_THRESHOLD:
        return True
    return False


def cluster_records(records: list[SourceRecord]) -> list[list[SourceRecord]]:
    n = len(records)
    uf = _UnionFind(n)

    buckets: dict[tuple, list[int]] = {}
    for i, r in enumerate(records):
        for e in _emails(r):
            buckets.setdefault(("email", e), []).append(i)
        for p in _phones(r):
            buckets.setdefault(("phone", p), []).append(i)
        g = _github(r)
        if g:
            buckets.setdefault(("github", g), []).append(i)
    for idxs in buckets.values():
        for j in idxs[1:]:
            uf.union(idxs[0], j)

    blocks: dict[str, list[int]] = {}
    for i, r in enumerate(records):
        nm = _name(r)
        if nm and nm.strip():
            blocks.setdefault(nm.strip().lower().split()[0], []).append(i)
    for idxs in blocks.values():
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                i, j = idxs[a], idxs[b]
                if uf.find(i) == uf.find(j) or records[i].source == records[j].source:
                    continue
                if fuzz.token_sort_ratio(_name(records[i]), _name(records[j])) >= NAME_THRESHOLD and _corroborates(records[i], records[j]):
                    uf.union(i, j)

    groups: dict[int, list[SourceRecord]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(records[i])
    return list(groups.values())
