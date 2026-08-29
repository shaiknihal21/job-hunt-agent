import json
import re
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.config import (
    EXCLUDED_COMPANIES,
    FRESHER_NEGATIVE_KEYWORDS,
    FRESHER_POSITIVE_KEYWORDS,
    PREFERRED_COMPANIES,
    company_is_blocked,
    is_abroad_location,
    is_excluded_company,
    is_india_location,
    is_preferred_company,
    is_remote_job,
    is_service_company,
    settings,
)
from app.services.llm import get_groq_llm
from app.services.salary import parse_salary_lpa, salary_meets_minimum
from app.models.profile import Job, JobScore, Profile


class ScoreBreakdown(BaseModel):
    score: float = Field(ge=0, le=100)
    skill_match: float = Field(ge=0, le=100)
    experience_match: float = Field(ge=0, le=100)
    location_match: float = Field(ge=0, le=100)
    salary_match: float = Field(ge=0, le=100)
    company_boost: float = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


AI_KEYWORDS = [
    "ai", "artificial intelligence", "gen ai", "generative ai", "genai",
    "machine learning", "ml", "llm", "large language model", "langchain",
    "langgraph", "rag", "retrieval", "pytorch", "tensorflow", "deep learning",
    "nlp", "transformer", "openai", "prompt engineering", "agent", "mcp",
    "vector", "embedding", "fine-tuning", "fine tuning",
    "software engineer", "backend", "full stack", "fullstack",
    "data engineer", "data pipeline", "etl", "spark", "airflow", "dbt",
    "kafka", "sql", "python", "aws", "gcp", "azure",
]


def _get_llm():
    return get_groq_llm(temperature=0.2, max_tokens=2048)


def _keyword_score(text: str, keywords: list[str]) -> float:
    text_lower = text.lower()
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return min(100.0, (hits / len(keywords)) * 100)


def _years_experience(profile: Profile) -> int:
    defaults = profile.application_defaults or {}
    return int(defaults.get("years_experience") or settings.candidate_years_experience)


def _experience_level_score(combined: str, years: int) -> tuple[float, list[str], list[str]]:
    """Score how well a job matches candidate experience level (fresher-friendly)."""
    reasons: list[str] = []
    red_flags: list[str] = []

    if any(k in combined for k in FRESHER_NEGATIVE_KEYWORDS):
        if years <= 2:
            red_flags.append("Senior/experienced role — likely needs more years")
            return 20.0, reasons, red_flags

    if years <= 2:
        if any(k in combined for k in FRESHER_POSITIVE_KEYWORDS):
            reasons.append("Fresher / early-career friendly role")
            return 95.0, reasons, red_flags
        if "senior" in combined and "junior" not in combined:
            red_flags.append("Senior title — review experience requirement")
            return 35.0, reasons, red_flags
        return 70.0, reasons, red_flags

    return 65.0, reasons, red_flags


def _heuristic_score(job: Job, profile: Profile) -> ScoreBreakdown:
    combined = f"{job.title} {job.description or ''} {job.company}".lower()
    years = _years_experience(profile)

    skill_keywords = profile.skills + AI_KEYWORDS
    skill_match = _keyword_score(combined, skill_keywords)

    target_roles = profile.target_roles or []
    role_hits = sum(1 for r in target_roles if r.lower() in combined)
    role_match = min(100.0, (role_hits / max(len(target_roles), 1)) * 100 + _keyword_score(combined, AI_KEYWORDS) * 0.3)
    level_score, level_reasons, level_flags = _experience_level_score(combined, years)
    experience_match = round((role_match * 0.6 + level_score * 0.4), 1)

    preferred_locs = [loc.lower() for loc in (profile.preferred_locations or [])]
    loc_text = (job.location or "").lower()
    desc_text = (job.description or "").lower()

    if is_remote_job(job.location, job.remote, job.description, job.title):
        location_match = 100.0
    elif is_india_location(job.location, job.description):
        location_match = 80.0 if any(loc in loc_text for loc in preferred_locs) else 65.0
    elif is_abroad_location(job.location, job.description):
        location_match = 0.0
    else:
        location_match = 70.0 if job.remote else 50.0

    salary_match = 70.0  # neutral when unknown
    min_lpa = settings.min_salary_lpa
    if profile.salary_expectations and profile.salary_expectations.get("min_lpa"):
        min_lpa = float(profile.salary_expectations["min_lpa"])

    meets = salary_meets_minimum(job.salary_text, min_lpa) if min_lpa > 0 else None
    parsed = parse_salary_lpa(job.salary_text)
    if meets is True:
        salary_match = 95.0
    elif meets is False:
        salary_match = 0.0
    elif parsed is None:
        salary_match = 55.0  # undisclosed — lower score, not auto-rejected

    if is_preferred_company(job.company):
        company_boost = 82.0
    elif is_service_company(job.company):
        company_boost = 10.0
    else:
        company_boost = 80.0  # startups/SMEs — nearly equal to big names

    weighted = (
        skill_match * 0.30
        + experience_match * 0.30
        + location_match * 0.15
        + salary_match * 0.15
        + company_boost * 0.10
    )

    reasons = []
    if skill_match >= 60:
        reasons.append("Strong AI/ML skill alignment")
    if experience_match >= 60:
        reasons.append("Title matches AI / Software / Data Engineer roles")
    reasons.extend(level_reasons)
    if location_match >= 90:
        reasons.append("Remote/WFH eligible")
    elif location_match >= 70:
        reasons.append("India location match")
    if company_boost >= 81:
        reasons.append("Well-known product company")
    elif company_boost >= 75:
        reasons.append("Product/tech company (startup, SaaS, or MNC)")

    red_flags = list(level_flags)
    if settings.filter_excluded_companies and (is_excluded_company(job.company) or is_service_company(job.company)):
        red_flags.append("Service/consulting company — excluded")
    if "intern" in combined and years >= 1:
        pass  # ok for candidates with some experience
    elif "intern" in combined and years == 0:
        red_flags.append("Internship role")
    if experience_match < 30:
        red_flags.append("Weak role title match")
    if is_abroad_location(job.location, job.description) and not is_remote_job(job.location, job.remote, job.description, job.title):
        red_flags.append("Abroad on-site role — only remote/WFH targeted outside India")

    if meets is False and min_lpa > 0:
        red_flags.append(f"Salary below {min_lpa:.0f} LPA minimum")
    elif meets is None and not job.salary_text and min_lpa > 0:
        red_flags.append(f"Salary not listed — verify ≥{min_lpa:.0f} LPA before applying")

    if company_is_blocked(job.company):
        weighted = 0.0
    elif meets is False and min_lpa > 0:
        weighted = 0.0
    elif is_abroad_location(job.location, job.description) and not is_remote_job(
        job.location, job.remote, job.description, job.title
    ):
        weighted = 0.0

    return ScoreBreakdown(
        score=round(weighted, 1),
        skill_match=round(skill_match, 1),
        experience_match=round(experience_match, 1),
        location_match=round(location_match, 1),
        salary_match=round(salary_match, 1),
        company_boost=round(company_boost, 1),
        reasons=reasons or ["Partial match — review manually"],
        red_flags=red_flags,
    )


def _llm_score(job: Job, profile: Profile) -> ScoreBreakdown | None:
    llm = _get_llm()
    if not llm:
        return None

    structured = llm.with_structured_output(ScoreBreakdown)
    years = _years_experience(profile)
    prompt = f"""Score this job for a candidate with {years} year(s) of experience targeting AI/ML/Software/Data Engineer roles.

Candidate profile:
- Role: {profile.role}
- Experience: {years} year(s)
- Skills: {', '.join(profile.skills or [])}
- Target roles: {', '.join(profile.target_roles or [])}
- Location: {profile.location} (India)
- Preferred locations: {', '.join(profile.preferred_locations or [])}

Job:
- Title: {job.title}
- Company: {job.company}
- Location: {job.location}
- Remote: {job.remote}
- Salary: {job.salary_text}
- Description: {(job.description or '')[:3000]}

LOCATION RULE: India on-site/hybrid is fine. Jobs outside India ONLY score well if remote/WFH/online — otherwise score location_match as 0.

EXPERIENCE RULE: Candidate has ~{years} year(s) experience. BOOST entry-level, junior, associate, graduate, 0-2 year roles.
Score 0 or very low for roles requiring 5+ / 8+ / 10+ years, Principal, Staff, Director.

COMPANY RULE: Score 0 for IT services/consulting (TCS, Infosys, Wipro, Accenture, etc.).
All other companies are eligible — startups, SaaS, product firms, tech MNCs.

Score 0-100 using weights: skill 30%, experience/title 30%, location 15%, salary 15%, company type 10%.
BLOCKLIST (score 0): {', '.join(EXCLUDED_COMPANIES)}.
Provide reasons and red_flags."""

    try:
        return structured.invoke([
            SystemMessage(content="You are a job matching expert for AI/ML engineering roles."),
            HumanMessage(content=prompt),
        ])
    except Exception:
        return None


def rank_job(job: Job, profile: Profile, *, use_llm: bool = True) -> ScoreBreakdown:
    if company_is_blocked(job.company):
        return ScoreBreakdown(
            score=0.0,
            skill_match=0.0,
            experience_match=0.0,
            location_match=0.0,
            salary_match=0.0,
            company_boost=0.0,
            reasons=["Excluded: service/consulting company"],
            red_flags=[f"{job.company} is not a product-based MNC"],
        )

    if is_abroad_location(job.location, job.description) and not is_remote_job(
        job.location, job.remote, job.description, job.title
    ):
        return ScoreBreakdown(
            score=0.0,
            skill_match=0.0,
            experience_match=0.0,
            location_match=0.0,
            salary_match=0.0,
            company_boost=0.0,
            reasons=["Excluded: abroad on-site role"],
            red_flags=["Outside India — only remote/WFH targets are targeted"],
        )

    min_lpa = settings.min_salary_lpa
    if profile.salary_expectations and profile.salary_expectations.get("min_lpa"):
        min_lpa = float(profile.salary_expectations["min_lpa"])
    if min_lpa > 0 and salary_meets_minimum(job.salary_text, min_lpa) is False:
        parsed = parse_salary_lpa(job.salary_text)
        lo, hi = parsed if parsed else (0, 0)
        return ScoreBreakdown(
            score=0.0,
            skill_match=0.0,
            experience_match=0.0,
            location_match=0.0,
            salary_match=0.0,
            company_boost=0.0,
            reasons=[f"Salary below {min_lpa:.0f} LPA minimum"],
            red_flags=[f"Listed salary {lo:.0f}–{hi:.0f} LPA — below your {min_lpa:.0f} LPA floor"],
        )

    llm_result = _llm_score(job, profile) if use_llm else None
    heuristic = _heuristic_score(job, profile)

    if llm_result:
        # Blend LLM and heuristic for stability
        blended = ScoreBreakdown(
            score=round(llm_result.score * 0.7 + heuristic.score * 0.3, 1),
            skill_match=round(llm_result.skill_match * 0.7 + heuristic.skill_match * 0.3, 1),
            experience_match=round(llm_result.experience_match * 0.7 + heuristic.experience_match * 0.3, 1),
            location_match=round(llm_result.location_match * 0.7 + heuristic.location_match * 0.3, 1),
            salary_match=round(llm_result.salary_match * 0.7 + heuristic.salary_match * 0.3, 1),
            company_boost=round(llm_result.company_boost * 0.7 + heuristic.company_boost * 0.3, 1),
            reasons=list(dict.fromkeys(llm_result.reasons + heuristic.reasons))[:5],
            red_flags=list(dict.fromkeys(llm_result.red_flags + heuristic.red_flags))[:5],
        )
        return blended
    return heuristic


def rank_jobs_batch(
    jobs: list[Job],
    profile: Profile,
    *,
    llm_top_n: int | None = None,
) -> dict[int, ScoreBreakdown]:
    """Heuristic pass for all jobs; Groq LLM re-rank on top N only."""
    top_n = llm_top_n if llm_top_n is not None else settings.llm_rank_top_n
    breakdowns: dict[int, ScoreBreakdown] = {}

    for job in jobs:
        breakdowns[job.id] = rank_job(job, profile, use_llm=False)

    if top_n <= 0 or not settings.groq_api_key:
        return breakdowns

    ranked = sorted(jobs, key=lambda j: breakdowns[j.id].score, reverse=True)
    for job in ranked[:top_n]:
        breakdowns[job.id] = rank_job(job, profile, use_llm=True)

    return breakdowns


def save_job_score(db, job: Job, breakdown: ScoreBreakdown) -> JobScore:
    existing = job.score
    if existing:
        existing.score = breakdown.score
        existing.skill_match = breakdown.skill_match
        existing.experience_match = breakdown.experience_match
        existing.location_match = breakdown.location_match
        existing.salary_match = breakdown.salary_match
        existing.company_boost = breakdown.company_boost
        existing.reasons = breakdown.reasons
        existing.red_flags = breakdown.red_flags
        db.commit()
        db.refresh(existing)
        return existing

    score = JobScore(
        job_id=job.id,
        score=breakdown.score,
        skill_match=breakdown.skill_match,
        experience_match=breakdown.experience_match,
        location_match=breakdown.location_match,
        salary_match=breakdown.salary_match,
        company_boost=breakdown.company_boost,
        reasons=breakdown.reasons,
        red_flags=breakdown.red_flags,
    )
    db.add(score)
    job.status = "ranked"
    db.commit()
    db.refresh(score)
    return score
