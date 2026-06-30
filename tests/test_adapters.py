from pathlib import Path

from candidate_transformer.adapters.base import ExtractionFailure, SourceRecord
from candidate_transformer.adapters.csv_adapter import extract_csv
from candidate_transformer.adapters.github_adapter import extract_github, login_from_url

SAMPLES = Path(__file__).resolve().parent.parent / "sample_inputs"
GH_FIXTURES = SAMPLES / "github"


class TestCsvAdapter:
    def test_parses_all_rows(self):
        records = extract_csv(SAMPLES / "recruiter.csv")
        assert isinstance(records, list)
        assert len(records) == 3

    def test_field_mapping(self):
        jane = extract_csv(SAMPLES / "recruiter.csv")[0]
        assert jane.fields["full_name"].value == "Jane Doe"
        assert jane.fields["emails"].value == ["jane.doe@gmail.com"]
        assert jane.fields["phones"].value == ["(415) 555-2671"]
        assert jane.fields["experience"].value[0]["company"] == "Acme"

    def test_empty_email_omitted(self):
        john = extract_csv(SAMPLES / "recruiter.csv")[1]
        assert "emails" not in john.fields

    def test_missing_file_degrades(self):
        result = extract_csv(SAMPLES / "does_not_exist.csv")
        assert isinstance(result, ExtractionFailure)
        assert result.source == "csv"

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("name,email\n", encoding="utf-8")
        assert extract_csv(f) == []


class TestGithubAdapter:
    def test_login_from_url(self):
        assert login_from_url("https://github.com/janedoe") == "janedoe"
        assert login_from_url("https://github.com/janedoe/") == "janedoe"
        assert login_from_url("") is None

    def test_extract_fields(self):
        rec = extract_github("https://github.com/janedoe", GH_FIXTURES)
        assert isinstance(rec, SourceRecord)
        assert rec.fields["full_name"].value == "Jane Doe"
        assert rec.fields["emails"].value == ["jane.doe@gmail.com"]
        assert rec.fields["location"].value == {"city": "San Francisco", "region": "CA", "country": "US"}
        assert "Python" in rec.fields["skills"].value

    def test_null_email_omitted(self):
        rec = extract_github("https://github.com/jsmith", GH_FIXTURES)
        assert "emails" not in rec.fields

    def test_missing_fixture_degrades(self):
        result = extract_github("https://github.com/ghost", GH_FIXTURES)
        assert isinstance(result, ExtractionFailure)

    def test_malformed_json_degrades(self, tmp_path):
        (tmp_path / "broken.json").write_text("{not valid", encoding="utf-8")
        result = extract_github("https://github.com/broken", tmp_path)
        assert isinstance(result, ExtractionFailure)
        assert "malformed" in result.reason

    def test_bad_url_degrades(self):
        result = extract_github("not a url", GH_FIXTURES)
        assert isinstance(result, ExtractionFailure)
