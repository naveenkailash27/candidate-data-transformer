from candidate_transformer.normalize.country import to_iso3166
from candidate_transformer.normalize.dates import is_present, normalize_month
from candidate_transformer.normalize.phone import normalize_phone
from candidate_transformer.normalize.registry import get_normalizer
from candidate_transformer.normalize.skills import canonical_skill


class TestPhone:
    def test_e164_with_region(self):
        assert normalize_phone("(415) 555-2671", country="US") == "+14155552671"

    def test_e164_with_plus_prefix_no_region(self):
        assert normalize_phone("+1 415 555 2671") == "+14155552671"

    def test_no_country_signal_returns_none(self):
        assert normalize_phone("415-555-2671") is None

    def test_garbage_returns_none(self):
        assert normalize_phone("not a phone") is None

    def test_empty_returns_none(self):
        assert normalize_phone("") is None
        assert normalize_phone(None) is None


class TestDates:
    def test_full_month(self):
        assert normalize_month("March 2019") == "2019-03"

    def test_iso_like(self):
        assert normalize_month("2019-03-15") == "2019-03"

    def test_year_only_anchors_january(self):
        assert normalize_month("2019") == "2019-01"

    def test_present_returns_none(self):
        assert normalize_month("Present") is None
        assert is_present("current") is True

    def test_garbage_returns_none(self):
        assert normalize_month("xyz") is None
        assert normalize_month("") is None
        assert normalize_month(None) is None


class TestCountry:
    def test_alias(self):
        assert to_iso3166("United States") == "US"
        assert to_iso3166("usa") == "US"
        assert to_iso3166("India") == "IN"

    def test_alpha2_passthrough(self):
        assert to_iso3166("us") == "US"
        assert to_iso3166("GB") == "GB"

    def test_unknown_returns_none(self):
        assert to_iso3166("Atlantis") is None
        assert to_iso3166("") is None
        assert to_iso3166(None) is None


class TestSkills:
    def test_canonical_passthrough(self):
        assert canonical_skill("Python") == "Python"

    def test_alias_match(self):
        assert canonical_skill("py") == "Python"
        assert canonical_skill("k8s") == "Kubernetes"
        assert canonical_skill("reactjs") == "React"

    def test_case_insensitive(self):
        assert canonical_skill("PYTHON") == "Python"

    def test_unmatched_returns_none(self):
        assert canonical_skill("k8s-ops") is None
        assert canonical_skill("wizardry") is None
        assert canonical_skill("") is None


class TestRegistry:
    def test_lookup_by_name(self):
        assert get_normalizer("E164")("+14155552671") == "+14155552671"
        assert get_normalizer("canonical")("py") == "Python"
        assert get_normalizer("ISO3166")("India") == "IN"
        assert get_normalizer("YYYY-MM")("2020") == "2020-01"

    def test_unknown_normalizer(self):
        assert get_normalizer("nope") is None
