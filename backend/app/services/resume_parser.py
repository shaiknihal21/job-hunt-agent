from pathlib import Path

from docx import Document
from pypdf import PdfReader


def parse_resume(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _parse_pdf(path)
    if suffix in {".docx", ".doc"}:
        return _parse_docx(path)
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"Unsupported resume format: {suffix}")


def _parse_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


def _parse_docx(path: Path) -> str:
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
