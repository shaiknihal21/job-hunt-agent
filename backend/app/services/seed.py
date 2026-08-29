from datetime import datetime

from sqlalchemy.orm import Session

from app.config import TARGET_ROLES, settings
from app.models.profile import Profile


DEFAULT_PROFILE = {
    "name": "Your Name",
    "role": "AI / Software / Data Engineer",
    "email": None,
    "phone": None,
    "location": "Hyderabad",
    "work_authorization": "India",
    "skills": [
        "Python",
        "LangChain",
        "LangGraph",
        "RAG",
        "LLMs",
        "FastAPI",
        "PyTorch",
        "Machine Learning",
        "SQL",
        "Apache Spark",
        "Airflow",
        "ETL",
        "AWS",
        "Docker",
        "Data Pipelines",
        "Software Engineering",
    ],
    "target_roles": TARGET_ROLES,
    "preferred_locations": [
        "Hyderabad", "Remote", "WFH", "Bangalore", "Pune",
        "Chennai", "Mumbai", "Delhi", "Noida", "Pan India",
    ],
    "salary_expectations": {"min_lpa": 0, "currency": "INR"},
    "links": {"linkedin": "", "github": ""},
    "application_defaults": {
        "notice_period_days": 30,
        "current_ctc": None,
        "expected_ctc": None,
        "years_experience": 1,
    },
    "custom_answers": {
        "retrieval augmented generation": "1",
        "rag": "1",
        "llm": "1",
        "langchain": "1",
        "python": "1",
        "machine learning": "1",
        "generative ai": "1",
    },
}


def seed_profile(db: Session) -> Profile:
    existing = db.query(Profile).first()
    if existing:
        return sync_fresher_profile(existing, db)

    profile = Profile(**DEFAULT_PROFILE)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def sync_fresher_profile(profile: Profile, db: Session) -> Profile:
    """Keep profile aligned with fresher settings."""
    defaults = dict(profile.application_defaults or {})
    if defaults.get("years_experience") is None:
        defaults["years_experience"] = settings.candidate_years_experience
        profile.application_defaults = defaults
    preferred = profile.preferred_locations or []
    for loc in DEFAULT_PROFILE["preferred_locations"]:
        if loc not in preferred:
            preferred.append(loc)
    profile.preferred_locations = preferred
    salary = dict(profile.salary_expectations or {})
    if salary.get("min_lpa") is None:
        salary["min_lpa"] = settings.min_salary_lpa
    if not salary.get("currency"):
        salary["currency"] = "INR"
    profile.salary_expectations = salary
    db.commit()
    db.refresh(profile)
    return profile


def get_or_create_profile(db: Session) -> Profile:
    profile = db.query(Profile).first()
    if profile:
        return sync_fresher_profile(profile, db)
    return seed_profile(db)
