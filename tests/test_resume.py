from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

from candidate_transformer.adapters.base import ExtractionFailure, SourceRecord
from candidate_transformer.adapters.resume_adapter import extract_resume
from candidate_transformer.pipeline import run_pipeline

SAMPLES = Path(__file__).resolve().parent.parent / "sample_inputs"
REF = date(2026, 6, 30)

RESUME_TXT = """Jane Doe
jane.doe@gmail.com | +1 415-555-2671 | San Francisco, CA

Experience
Software Engineer, Acme - Mar 2019 - Present
Built distributed services.
Junior Developer, Initech - Jun 2016 - Feb 2019

Education
B.S. Computer Science, UC Berkeley, 2016

Skills
Python, Go, Docker, PostgreSQL, Kubernetes
"""


class TestProseParsing:
    def _rec(self, tmp_path):
        f = tmp_path / "resume.txt"
        f.write_text(RESUME_TXT, encoding="utf-8")
        return extract_resume(f)

    def test_identity(self, tmp_path):
        rec = self._rec(tmp_path)
        assert isinstance(rec, SourceRecord)
        assert rec.fields["full_name"].value == "Jane Doe"
        assert rec.fields["emails"].value == ["jane.doe@gmail.com"]

    def test_skills(self, tmp_path):
        rec = self._rec(tmp_path)
        assert "Python" in rec.fields["skills"].value
        assert "Kubernetes" in rec.fields["skills"].value

    def test_experience_with_dates(self, tmp_path):
        roles = self._rec(tmp_path).fields["experience"].value
        assert roles[0]["company"] == "Acme"
        assert roles[0]["ongoing"] is True
        assert roles[1]["end"] == "Feb 2019"

    def test_education(self, tmp_path):
        edu = self._rec(tmp_path).fields["education"].value[0]
        assert edu["institution"] == "UC Berkeley"
        assert edu["end_year"] == 2016


class TestPdf:
    def test_real_pdf_extracts(self):
        rec = extract_resume(SAMPLES / "resumes" / "jane_doe_resume.pdf")
        assert isinstance(rec, SourceRecord)
        assert rec.fields["emails"].value == ["jane.doe@gmail.com"]

    def test_image_only_pdf_degrades_to_failure(self, tmp_path):
        blank = tmp_path / "scanned.pdf"
        c = canvas.Canvas(str(blank), pagesize=LETTER)
        c.rect(100, 100, 200, 200)
        c.save()
        result = extract_resume(blank)
        assert isinstance(result, ExtractionFailure)
        assert "no extractable text" in result.reason

    def test_unsupported_type(self, tmp_path):
        f = tmp_path / "resume.docx"
        f.write_text("x", encoding="utf-8")
        assert isinstance(extract_resume(f), ExtractionFailure)

    def test_missing_file(self):
        assert isinstance(extract_resume(SAMPLES / "resumes" / "nope.pdf"), ExtractionFailure)


class TestThreeSourceMerge:
    def test_resume_enriches_jane(self):
        profiles = run_pipeline(SAMPLES, reference=REF).profiles
        jane = next(p for p in profiles if p.full_name == "Jane Doe")
        assert jane.years_experience == 9.9
        assert jane.education[0].institution == "UC Berkeley"

    def test_cross_source_skill_agreement_raises_confidence(self):
        profiles = run_pipeline(SAMPLES, reference=REF).profiles
        jane = next(p for p in profiles if p.full_name == "Jane Doe")
        python = next(s for s in jane.skills if s.name == "Python")
        assert set(python.sources) == {"github", "resume"}
        assert python.confidence > 0.7
