"""Natural-language command parser for the job hunt agent."""

import re
import shlex
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import settings
from app.services.llm import get_groq_llm


class ChatCommand(BaseModel):
    action: Literal["scan", "pending", "approve", "skip", "apply", "status", "upload", "auto", "help", "unknown"]
    job_id: int | None = Field(default=None, description="Numeric job ID (approve/skip) or application ID (apply)")
    company_hint: str | None = Field(default=None, description="Company or role keyword to match a job")
    file_path: str | None = Field(default=None, description="Resume file path for upload action")
    reply: str = Field(description="Brief friendly response to show the user")


def _get_llm():
    return get_groq_llm(temperature=0.1)


def parse_command(user_text: str, context: str = "") -> ChatCommand:
    text = user_text.strip()
    text_lower = text.lower()

    # Raw file path pasted (Mac: /Users/... or ~/...)
    if _looks_like_file_path(text):
        return ChatCommand(action="upload", file_path=text, reply="")

    # Fast path — no LLM needed
    if text_lower in {"help", "?", "commands"}:
        return ChatCommand(action="help", reply="Here are the commands you can use.")
    if text_lower in {"auto", "run auto", "auto apply", "apply automatically"}:
        return ChatCommand(
            action="auto",
            reply=f"Running auto cycle (all sources, score≥{settings.auto_apply_min_score})...",
        )
    if text_lower in {"scan", "find jobs", "search", "discover"}:
        return ChatCommand(action="scan", reply="Scanning job boards for new matches...")
    if text_lower in {"pending", "queue", "approvals", "show pending"}:
        return ChatCommand(action="pending", reply="Here are jobs waiting for your approval.")
    if text_lower in {"status", "report", "stats"}:
        return ChatCommand(action="status", reply="Here's your weekly job hunt summary.")

    llm = _get_llm()
    if not llm:
        return _parse_heuristic(user_text)

    structured = llm.with_structured_output(ChatCommand)
    try:
        return structured.invoke([
            SystemMessage(content="""You parse commands for a personal job hunting agent.
Map user intent to one action:
- scan: find/discover/search jobs
- pending: show approval queue
- approve: approve a job (extract job_id or company_hint — this is a JOB id)
- skip: skip/reject a job
- apply: submit an approved application (job_id field = APPLICATION id, not job id)
- status: weekly stats/report
- upload: upload resume (extract full file_path including spaces)
- auto: autonomous discover+apply cycle
- help: user asks what you can do
- unknown: unclear intent

Examples:
"find AI engineer jobs" -> scan
"approve the Microsoft role" -> approve, company_hint=Microsoft
"skip #12" -> skip, job_id=12
"submit application 3" -> apply, job_id=3
"upload ~/My Resume (4).pdf" -> upload, file_path=~/My Resume (4).pdf"""),
            HumanMessage(content=f"Context:\n{context}\n\nUser: {user_text}"),
        ])
    except Exception:
        return _parse_heuristic(user_text)


def _looks_like_file_path(text: str) -> bool:
    t = text.strip().strip("\"'")
    if t.startswith(("/", "~")):
        return any(t.lower().endswith(ext) for ext in (".pdf", ".docx", ".doc", ".txt"))
    return False


def _extract_file_path(user_text: str) -> str | None:
    text = user_text.strip()
    if "upload" in text.lower():
        rest = re.split(r"\bupload\b", text, maxsplit=1, flags=re.IGNORECASE)[-1].strip()
        if rest:
            if rest[0] in "\"'" and rest[-1] == rest[0]:
                return rest[1:-1]
            return rest.strip("\"'")
    try:
        parts = shlex.split(text)
        for p in parts:
            if any(p.lower().endswith(ext) for ext in (".pdf", ".docx", ".doc", ".txt")):
                return p
    except ValueError:
        pass
    if text.startswith(("/", "~")) or ".pdf" in text.lower() or ".docx" in text.lower():
        return text
    parts = user_text.split()
    return next((p for p in parts if "." in p and "/" in p), None) or next((p for p in parts if "." in p), None)


def _parse_heuristic(user_text: str) -> ChatCommand:
    text = user_text.lower()

    if any(w in text for w in ("scan", "find", "search", "discover")):
        return ChatCommand(action="scan", reply="Scanning for jobs...")
    if any(w in text for w in ("pending", "queue", "approval")):
        return ChatCommand(action="pending", reply="Showing pending jobs...")
    if any(w in text for w in ("status", "report", "stats", "summary")):
        return ChatCommand(action="status", reply="Here's your status...")
    if "upload" in text or text.endswith((".pdf", ".docx", ".doc", ".txt")):
        path = _extract_file_path(user_text)
        return ChatCommand(action="upload", file_path=path, reply="Uploading resume...")
    if "approve" in text:
        job_id = _extract_id(text)
        hint = _extract_hint(text, "approve")
        return ChatCommand(action="approve", job_id=job_id, company_hint=hint, reply="Approving job...")
    if "skip" in text or "reject" in text:
        job_id = _extract_id(text)
        hint = _extract_hint(text, "skip")
        return ChatCommand(action="skip", job_id=job_id, company_hint=hint, reply="Skipping job...")
    if any(w in text for w in ("apply", "submit")):
        job_id = _extract_id(text)
        return ChatCommand(action="apply", job_id=job_id, reply="Submitting application...")

    return ChatCommand(action="unknown", reply="Try: scan, pending, approve #5, apply #3, status, upload resume.pdf")


def _extract_id(text: str) -> int | None:
    for token in text.replace("#", " ").split():
        if token.isdigit():
            return int(token)
    return None


def _extract_hint(text: str, verb: str) -> str | None:
    parts = text.split(verb, 1)
    if len(parts) < 2:
        return None
    hint = parts[1].strip(" .#0123456789")
    return hint or None
