from __future__ import annotations

_ALIASES = {
    "us": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US",
    "united states": "US", "united states of america": "US", "america": "US",
    "uk": "GB", "u.k.": "GB", "united kingdom": "GB", "great britain": "GB",
    "england": "GB", "scotland": "GB", "wales": "GB",
    "india": "IN", "bharat": "IN",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE", "deutschland": "DE",
    "france": "FR",
    "spain": "ES", "espana": "ES",
    "italy": "IT",
    "netherlands": "NL", "holland": "NL",
    "ireland": "IE",
    "singapore": "SG",
    "china": "CN",
    "japan": "JP",
    "brazil": "BR", "brasil": "BR",
    "mexico": "MX",
    "south korea": "KR", "korea": "KR",
    "switzerland": "CH",
    "sweden": "SE",
    "poland": "PL",
    "israel": "IL",
    "united arab emirates": "AE", "uae": "AE",
}

_KNOWN_CODES = set(_ALIASES.values())


def to_iso3166(raw: object) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if len(text) == 2 and text.upper() in _KNOWN_CODES:
        return text.upper()
    return _ALIASES.get(text.lower())
