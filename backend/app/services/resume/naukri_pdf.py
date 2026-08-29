"""Prepare PDF files for Naukri upload (repair broken PDFs, simple filenames)."""

import shutil
import tempfile
import uuid
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from app.config import RESUMES_DIR


def repair_pdf(src: Path, dest: Path) -> Path:
    """Rewrite PDF to strip broken object references Naukri may reject."""
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        writer.write(f)
    return dest


def prepare_naukri_upload_file(src: Path, profile_name: str = "Resume") -> Path:
    """Copy/repair PDF to temp with a simple name Naukri accepts."""
    safe = "".join(c if c.isalnum() else "" for c in profile_name.split()[0]) or "Resume"
    dest = Path(tempfile.gettempdir()) / f"{safe}_Resume.pdf"
    if src.suffix.lower() != ".pdf":
        raise ValueError(f"Naukri requires PDF, got: {src}")

    try:
        repair_pdf(src, dest)
    except Exception:
        shutil.copy2(src, dest)
    return dest


def naukri_upload_candidates(resume_path: str) -> list[Path]:
    """
    PDF-only, master resume FIRST (user's original upload — most compatible).
    Skip tiny reportlab exports unless no master exists.
    """
    path = Path(resume_path)
    seen: set[str] = set()
    out: list[Path] = []

    def add(p: Path) -> None:
        if not p.is_file() or p.suffix.lower() != ".pdf":
            return
        key = str(p.resolve())
        if key in seen:
            return
        seen.add(key)
        out.append(p)

    # 1. User's master PDF (uploaded via ./run.sh upload) — try this first
    masters = sorted(RESUMES_DIR.glob("master_*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
    for master in masters:
        add(master)
        break

    # 2. Tailored PDF if substantial (>15KB); skip tiny reportlab files when master exists
    tailored = path.with_suffix(".pdf") if path.suffix.lower() != ".pdf" else path
    if not tailored.exists() and path.suffix.lower() == ".docx":
        tailored = path.with_suffix(".pdf")
    if tailored.exists():
        size = tailored.stat().st_size
        if size > 15_000 or not masters:
            add(tailored)

    return out
