import json
import shutil
from datetime import date
from pathlib import Path

from candidate_transformer.pipeline import run_pipeline
from candidate_transformer.project.config import load_config

SAMPLES = Path(__file__).resolve().parent.parent / "sample_inputs"
REF = date(2026, 6, 30)


class TestDefaultRun:
    def test_produces_three_profiles(self):
        result = run_pipeline(SAMPLES, reference=REF)
        assert len(result.projected) == 3
        assert result.source_failures == []

    def test_default_output_is_full_schema(self):
        result = run_pipeline(SAMPLES, reference=REF)
        jane = next(p for p in result.projected if p["full_name"] == "Jane Doe")
        assert "provenance" in jane
        assert "overall_confidence" in jane


class TestCustomConfigRun:
    def test_custom_config_projects_and_isolates_errors(self):
        cfg = load_config(SAMPLES.parent / "config" / "example_config.json")
        result = run_pipeline(SAMPLES, config=cfg, reference=REF)
        assert len(result.projected) == 2
        assert len(result.projection_errors) == 1
        assert result.projection_errors[0]["full_name"] == "John Smith"
        keys = set(result.projected[0])
        assert keys <= {"full_name", "primary_email", "phone", "country", "skills", "overall_confidence"}


class TestGracefulDegradation:
    def test_wrong_schema_csv_yields_no_phantom(self, tmp_path):
        shutil.copy(SAMPLES / "recruiter.csv", tmp_path / "recruiter.csv")
        (tmp_path / "other.csv").write_text("foo,bar\n1,2\n", encoding="utf-8")
        result = run_pipeline(tmp_path, reference=REF)
        assert len(result.projected) == 3

    def test_unreadable_github_source_recorded(self, tmp_path):
        shutil.copy(SAMPLES / "recruiter.csv", tmp_path / "recruiter.csv")
        (tmp_path / "github_urls.txt").write_text("https://github.com/ghost\n", encoding="utf-8")
        result = run_pipeline(tmp_path, reference=REF)
        assert len(result.source_failures) == 1
        assert len(result.projected) == 3

    def test_empty_inputs_dir(self, tmp_path):
        result = run_pipeline(tmp_path, reference=REF)
        assert result.projected == []
        assert result.source_failures == []


class TestCli:
    def test_cli_writes_output(self, tmp_path):
        from cli import main

        out = tmp_path / "profiles.json"
        rc = main(["--inputs", str(SAMPLES), "--out", str(out), "--reference", "2026-06-30"])
        assert rc == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert len(data) == 3

    def test_cli_bad_config_path_segment(self, tmp_path):
        from cli import main

        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({"fields": [{"path": "x", "from": "phoones[0]", "type": "string"}]}), encoding="utf-8")
        out = tmp_path / "o.json"
        rc = main(["--inputs", str(SAMPLES), "--config", str(bad), "--out", str(out)])
        assert rc == 2


class TestInteractive:
    def _run(self, monkeypatch, answers):
        from cli import main

        it = iter(answers)
        monkeypatch.setattr("builtins.input", lambda *a: next(it))
        return main([])

    def test_interactive_default(self, monkeypatch, capsys):
        rc = self._run(monkeypatch, [str(SAMPLES), "1", "2026-06-30", ""])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"full_name"' in out and '"provenance"' in out

    def test_interactive_load_config_file(self, monkeypatch, capsys):
        rc = self._run(monkeypatch, [str(SAMPLES), "2", "1", "2026-06-30", ""])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"primary_email"' in out
        assert '"provenance"' not in out

    def test_interactive_build_config_subset(self, monkeypatch, capsys):
        # fields: full_name(2) + emails(3); on_missing omit; no provenance; no confidence
        rc = self._run(monkeypatch, [str(SAMPLES), "3", "2,3", "2", "n", "n", "2026-06-30", ""])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"full_name"' in out and '"emails"' in out
        assert '"provenance"' not in out and '"skills"' not in out

    def test_interactive_build_config_toggles(self, monkeypatch, capsys):
        rc = self._run(monkeypatch, [str(SAMPLES), "3", "a", "1", "y", "y", "2026-06-30", ""])
        assert rc == 0
        out = capsys.readouterr().out
        assert '"provenance"' in out and '"overall_confidence"' in out

    def test_interactive_missing_folder(self, monkeypatch):
        rc = self._run(monkeypatch, ["no_such_folder", "1", "", ""])
        assert rc == 1
