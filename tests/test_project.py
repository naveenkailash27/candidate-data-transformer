import pytest

from candidate_transformer.models import CanonicalProfile, Links, Location, Skill
from candidate_transformer.project.config import load_config
from candidate_transformer.project.projector import (
    ConfigError,
    ProjectionError,
    project_profile,
)
from candidate_transformer.project.validator import ValidationError


def _profile(**overrides):
    base = dict(
        candidate_id="c_1",
        full_name="Jane Doe",
        emails=["jane.doe@gmail.com"],
        phones=["+14155552671"],
        location=Location(city="San Francisco", region="CA", country="US"),
        links=Links(github="https://github.com/janedoe"),
        skills=[
            Skill(name="Python", confidence=0.9, sources=["github"], method="normalized"),
            Skill(name="Go", confidence=0.7, sources=["github"], method="normalized"),
        ],
        overall_confidence=0.79,
    )
    base.update(overrides)
    return CanonicalProfile(**base)


class TestRenameAndSubset:
    def test_rename_from_index(self):
        cfg = load_config({"fields": [
            {"path": "full_name", "type": "string", "required": True},
            {"path": "primary_email", "from": "emails[0]", "type": "string", "required": True},
        ]})
        out = project_profile(_profile(), cfg)
        assert out == {"full_name": "Jane Doe", "primary_email": "jane.doe@gmail.com"}

    def test_nested_path(self):
        cfg = load_config({"fields": [{"path": "country", "from": "location.country", "type": "string"}]})
        assert project_profile(_profile(), cfg) == {"country": "US"}

    def test_array_map(self):
        cfg = load_config({"fields": [{"path": "skills", "from": "skills[].name", "type": "string[]"}]})
        assert project_profile(_profile(), cfg) == {"skills": ["Python", "Go"]}


class TestNormalizeOverride:
    def test_phone_normalize_idempotent(self):
        cfg = load_config({"fields": [{"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"}]})
        assert project_profile(_profile(), cfg) == {"phone": "+14155552671"}

    def test_skill_canonical_normalize(self):
        cfg = load_config({"fields": [{"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"}]})
        assert project_profile(_profile(), cfg) == {"skills": ["Python", "Go"]}


class TestOnMissing:
    def test_null(self):
        cfg = load_config({"fields": [{"path": "phone", "from": "phones[0]", "type": "string"}], "on_missing": "null"})
        assert project_profile(_profile(phones=[]), cfg) == {"phone": None}

    def test_omit(self):
        cfg = load_config({"fields": [{"path": "phone", "from": "phones[0]", "type": "string"}], "on_missing": "omit"})
        assert project_profile(_profile(phones=[]), cfg) == {}

    def test_error(self):
        cfg = load_config({"fields": [{"path": "phone", "from": "phones[0]", "type": "string"}], "on_missing": "error"})
        with pytest.raises(ProjectionError):
            project_profile(_profile(phones=[]), cfg)

    def test_required_missing_always_errors(self):
        cfg = load_config({"fields": [{"path": "primary_email", "from": "emails[0]", "type": "string", "required": True}], "on_missing": "null"})
        with pytest.raises(ProjectionError):
            project_profile(_profile(emails=[]), cfg)


class TestPathErrors:
    def test_unknown_field_is_config_error(self):
        cfg = load_config({"fields": [{"path": "x", "from": "phoones[0]", "type": "string"}]})
        with pytest.raises(ConfigError):
            project_profile(_profile(), cfg)

    def test_malformed_segment_is_config_error(self):
        cfg = load_config({"fields": [{"path": "x", "from": "emails[[0]", "type": "string"}]})
        with pytest.raises(ConfigError):
            project_profile(_profile(), cfg)

    def test_unknown_normalizer_is_config_error(self):
        cfg = load_config({"fields": [{"path": "phone", "from": "phones[0]", "type": "string", "normalize": "nope"}]})
        with pytest.raises(ConfigError):
            project_profile(_profile(), cfg)


class TestToggles:
    def test_include_confidence(self):
        cfg = load_config({"fields": [{"path": "full_name", "type": "string"}], "include_confidence": True})
        out = project_profile(_profile(), cfg)
        assert out["overall_confidence"] == 0.79

    def test_include_provenance(self):
        cfg = load_config({"fields": [{"path": "full_name", "type": "string"}], "include_provenance": True})
        out = project_profile(_profile(), cfg)
        assert "provenance" in out


class TestValidation:
    def test_type_mismatch_rejected(self):
        cfg = load_config({"fields": [{"path": "full_name", "from": "emails", "type": "string"}]})
        with pytest.raises(ValidationError):
            project_profile(_profile(), cfg)

    def test_example_config_file_loads(self):
        cfg = load_config("config/example_config.json")
        out = project_profile(_profile(), cfg)
        assert out["primary_email"] == "jane.doe@gmail.com"
        assert out["skills"] == ["Python", "Go"]
        assert out["overall_confidence"] == 0.79
