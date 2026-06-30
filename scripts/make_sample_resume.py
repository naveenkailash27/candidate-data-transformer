from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

LINES = [
    "Jane Doe",
    "jane.doe@gmail.com | +1 415-555-2671 | San Francisco, CA",
    "",
    "Experience",
    "Software Engineer, Acme - Mar 2019 - Present",
    "Built and scaled distributed backend services.",
    "Junior Developer, Initech - Jun 2016 - Feb 2019",
    "Maintained internal tooling and data pipelines.",
    "",
    "Education",
    "B.S. Computer Science, UC Berkeley, 2016",
    "",
    "Skills",
    "Python, Go, Docker, PostgreSQL, Kubernetes",
]


def build(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=LETTER)
    _, height = LETTER
    y = height - 72
    for line in LINES:
        c.drawString(72, y, line)
        y -= 18
    c.save()


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_inputs/resumes/jane_doe_resume.pdf")
    build(target)
    print(f"wrote {target}")
