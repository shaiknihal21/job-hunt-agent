"""Persist Naukri recruiter screening Q&A for retries and profile learning."""

import hashlib
import re

from sqlalchemy.orm import Session

from app.models.profile import ApplicationAnswer


def _fingerprint(question: str) -> str:
    normalized = re.sub(r"\s+", " ", question.lower().strip())
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


def save_screening_log(db: Session, profile_id: int, log: list[str]) -> None:
    """Parse chatbot log entries and upsert ApplicationAnswer rows."""
    for entry in log:
        question, answer = _parse_entry(entry)
        if not question or not answer:
            continue
        fp = _fingerprint(question)
        existing = (
            db.query(ApplicationAnswer)
            .filter(
                ApplicationAnswer.profile_id == profile_id,
                ApplicationAnswer.question_fingerprint == fp,
            )
            .first()
        )
        if existing:
            existing.answer_text = answer
            existing.question_text = question
        else:
            db.add(
                ApplicationAnswer(
                    profile_id=profile_id,
                    question_fingerprint=fp,
                    question_text=question,
                    answer_text=answer,
                )
            )


def _parse_entry(entry: str) -> tuple[str | None, str | None]:
    if "→" in entry:
        left, answer = entry.split("→", 1)
        question = left.replace("Q:", "").strip()
        return question, answer.strip()
    if entry.startswith("default years"):
        parts = entry.split("→", 1)
        if len(parts) == 2:
            return "years of experience", parts[1].strip()
    if entry.startswith("uploaded:"):
        return None, None
    return None, None
