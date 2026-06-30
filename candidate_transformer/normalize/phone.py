from __future__ import annotations

import phonenumbers


def normalize_phone(raw: object, country: str | None = None) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    region = country.upper() if country else None
    for region_try in ([region] if region else []) + [None]:
        try:
            num = phonenumbers.parse(text, region_try)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(num):
            return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
    return None
