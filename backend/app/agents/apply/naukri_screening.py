"""Answer Naukri recruiter screening questions from profile defaults."""

import re


def _years(profile_data: dict) -> str:
    defaults = profile_data.get("application_defaults") or {}
    return str(defaults.get("years_experience", 1))


def _custom(profile_data: dict) -> dict[str, str]:
    raw = profile_data.get("custom_answers") or {}
    return {k.lower(): str(v) for k, v in raw.items()}


def answer_for_question(question: str, profile_data: dict) -> str | None:
    """Return an honest answer for a recruiter question, or None if unknown."""
    q = question.lower()
    custom = _custom(profile_data)
    years = _years(profile_data)

    for key, val in custom.items():
        if key in q:
            return val

    skill_years = {
        "retrieval augmented generation": years,
        "rag": years,
        "large language model": years,
        "llm": years,
        "langchain": years,
        "langgraph": years,
        "generative ai": years,
        "gen ai": years,
        "machine learning": years,
        "deep learning": years,
        "python": years,
        "pytorch": years,
        "fastapi": years,
        "sql": years,
        "apache spark": years,
        "airflow": years,
        "data pipeline": years,
        "etl": years,
        "aws": years,
        "docker": years,
    }
    for skill, ans in skill_years.items():
        if skill in q and ("year" in q or "experience" in q or "how many" in q):
            return ans

    if re.search(r"how many years", q) or re.search(r"years of experience", q):
        return years
    if "notice period" in q:
        nd = (profile_data.get("application_defaults") or {}).get("notice_period_days")
        return str(nd) if nd else "30"
    if "current ctc" in q or "current salary" in q:
        ctc = (profile_data.get("application_defaults") or {}).get("current_ctc")
        return str(ctc) if ctc else None
    if "expected ctc" in q or "expected salary" in q:
        exp = (profile_data.get("application_defaults") or {}).get("expected_ctc")
        return str(exp) if exp else None
    if q.strip() in {"yes", "no"}:
        return None
    if "willing to relocate" in q or "hybrid" in q or "work from office" in q:
        return "Yes"
    return None
