"""Export tailored resume content to PDF (no MS Word required)."""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from app.services.resume.types import TailoredContent


def write_tailored_pdf(profile_name: str, contact_line: str, content: TailoredContent, out_path: Path) -> str:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_path), pagesize=letter)
    width, height = letter
    y = height - inch
    line_h = 14

    def writeln(text: str, *, bold: bool = False, size: int = 11) -> None:
        nonlocal y
        if y < inch:
            c.showPage()
            y = height - inch
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for line in _wrap(text, 95):
            if y < inch:
                c.showPage()
                y = height - inch
            c.drawString(inch, y, line)
            y -= line_h

    writeln(profile_name, bold=True, size=16)
    if contact_line:
        writeln(contact_line, size=10)
    y -= 6

    writeln("Professional Summary", bold=True, size=12)
    writeln(content.summary)
    y -= 4

    writeln("Technical Skills", bold=True, size=12)
    writeln(", ".join(content.skills_reordered))
    y -= 4

    writeln("Professional Experience", bold=True, size=12)
    for bullet in content.experience_bullets:
        writeln(f"• {bullet}")

    if content.projects:
        y -= 4
        writeln("Projects", bold=True, size=12)
        for project in content.projects:
            writeln(f"• {project}")

    c.save()
    return str(out_path)


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        trial = " ".join(current + [word])
        if len(trial) <= width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [""]
