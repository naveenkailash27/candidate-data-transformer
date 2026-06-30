from datetime import date
from pathlib import Path

from candidate_transformer.adapters.csv_adapter import extract_csv
from candidate_transformer.adapters.github_adapter import extract_github
from candidate_transformer.merge.merge import build_profile, merge_records
from candidate_transformer.models import Experience

SAMPLES = Path(__file__).resolve().parent.parent / "sample_inputs"
GH = SAMPLES / "github"
REF = date(2026, 6, 30)


def _all_records():
    records = list(extract_csv(SAMPLES / "recruiter.csv"))
    for url in (SAMPLES / "github_urls.txt").read_text().split():
        records.append(extract_github(url, GH))
    return records


def _by_name(profiles, name):
    return next(p for p in profiles if p.full_name == name)


class TestClustering:
    def test_three_candidates(self):
        profiles = merge_records(_all_records(), reference=REF)
        assert len(profiles) == 3

    def test_jane_and_john_not_over_merged(self):
        profiles = merge_records(_all_records(), reference=REF)
        names = sorted(p.full_name for p in profiles)
        assert names == ["Jane Doe", "John Smith", "Priya Patel"]


class TestEmailTierMerge:
    def test_jane_merged_by_email(self):
        jane = _by_name(merge_records(_all_records(), reference=REF), "Jane Doe")
        assert jane.emails == ["jane.doe@gmail.com"]

    def test_cross_source_phone_resolution(self):
        jane = _by_name(merge_records(_all_records(), reference=REF), "Jane Doe")
        assert jane.phones == ["+14155552671"]
        assert jane.location.country == "US"

    def test_jane_skills_canonicalized(self):
        jane = _by_name(merge_records(_all_records(), reference=REF), "Jane Doe")
        names = [s.name for s in jane.skills]
        assert "Kubernetes" in names
        assert jane.unmatched_skills == []


class TestFuzzyTierMerge:
    def test_john_merged_by_name_and_company(self):
        john = _by_name(merge_records(_all_records(), reference=REF), "John Smith")
        assert john.phones == ["+442079460958"]
        assert john.location.country == "GB"

    def test_john_unmatched_skill_preserved(self):
        john = _by_name(merge_records(_all_records(), reference=REF), "John Smith")
        raws = [u.raw_text for u in john.unmatched_skills]
        assert "wizardry" in raws


class TestGracefulNull:
    def test_priya_bad_phone_is_null(self):
        priya = _by_name(merge_records(_all_records(), reference=REF), "Priya Patel")
        assert priya.phones == []
        assert priya.emails == ["priya.patel@outlook.com"]

    def test_years_experience_null_without_dates(self):
        for p in merge_records(_all_records(), reference=REF):
            assert p.years_experience is None


class TestIntervalMerge:
    def test_overlapping_roles_not_double_counted(self):
        from candidate_transformer.merge.merge import _years_experience

        exp = [
            Experience(company="A", start="2019-01", end="2023-01"),
            Experience(company="B", start="2020-01", end="2021-01"),
        ]
        years, malformed = _years_experience(exp, REF)
        assert years == 4.0
        assert malformed is False

    def test_ongoing_uses_reference(self):
        from candidate_transformer.merge.merge import _years_experience

        exp = [Experience(company="A", start="2024-06", end=None, ongoing=True)]
        years, _ = _years_experience(exp, REF)
        assert years == 2.0

    def test_malformed_range_flagged(self):
        from candidate_transformer.merge.merge import _years_experience

        exp = [Experience(company="A", start="2023-01", end="2020-01")]
        years, malformed = _years_experience(exp, REF)
        assert malformed is True
        assert years is None


class TestConfidenceAndId:
    def test_deterministic_id(self):
        p1 = merge_records(_all_records(), reference=REF)
        p2 = merge_records(_all_records(), reference=REF)
        assert [p.candidate_id for p in p1] == [p.candidate_id for p in p2]

    def test_overall_confidence_in_range(self):
        for p in merge_records(_all_records(), reference=REF):
            assert 0.0 <= p.overall_confidence <= 1.0
