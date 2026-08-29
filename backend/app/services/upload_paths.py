"""Resolve resume file paths — handles Mac paths with spaces and common typos."""

import re
from pathlib import Path


def _unescape_path(raw: str) -> str:
    s = raw.strip().strip("\"'")
    s = re.sub(r"\\(.)", r"\1", s)
    return s


def resolve_upload_path(file_path: str) -> Path:
    """
    Resolve a resume path from user input.
    Falls back to ~/Downloads/*Resume*.pdf when the exact path is wrong.
    """
    raw = _unescape_path(file_path)
    direct = Path(raw).expanduser()
    if direct.is_file():
        return direct.resolve()

    downloads = Path.home() / "Downloads"
    wanted = direct.name.lower()

    if downloads.is_dir():
        docs = [
            *downloads.glob("*.pdf"),
            *downloads.glob("*.docx"),
            *downloads.glob("*.doc"),
            *downloads.glob("*.txt"),
        ]

        # Exact name case-insensitive
        for p in docs:
            if p.name.lower() == wanted:
                return p.resolve()

        # Common typo: My_Resume__4_.pdf → My_Resume (4).pdf
        if "resume" in wanted:
            resume_files = sorted(
                [p for p in docs if "resume" in p.name.lower()],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if resume_files:
                # Prefer (4) if user hinted at 4
                if "4" in wanted:
                    for p in resume_files:
                        if "(4)" in p.name or " 4" in p.name:
                            return p.resolve()
                return resume_files[0].resolve()

    hints: list[str] = []
    if downloads.is_dir():
        hints = [p.name for p in sorted(downloads.glob("*Resume*"), reverse=True)[:5]]

    msg = f"File not found: {direct}"
    if hints:
        msg += f"\n  Did you mean one of these in ~/Downloads?\n  " + "\n  ".join(hints)
    msg += '\n  Use: ./run.sh upload "~/Downloads/Your_Resume.pdf"'
    raise ValueError(msg)
