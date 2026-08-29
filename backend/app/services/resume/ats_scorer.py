import re

from app.services.resume.gap_analyzer import gaps_missing
from app.services.resume.tech_terms import normalize_term, term_in_text
from app.services.resume.types import ATSBreakdown, CandidateEvidence, GapItem, GapStatus, ParsedJD


def _coverage(terms: list[str], resume_text: str, evidence: CandidateEvidence) -> float:
    if not terms:
        return 100.0
    hits = 0
    for term in terms:
        if term_in_text(term, resume_text) or any(term_in_text(term, v) for v in evidence.verified_terms):
            hits += 1
    return round((hits / len(terms)) * 100, 1)


def _responsibility_alignment(responsibilities: list[str], resume_text: str, evidence: CandidateEvidence) -> float:
    if not responsibilities:
        return 70.0
    combined = resume_text + " " + evidence.verified_text
    hits = 0
    for resp in responsibilities:
        tokens = [normalize_term(t) for t in re.findall(r"[a-zA-Z+#/.-]{3,}", resp.lower())]
        token_hits = sum(1 for token in tokens[:8] if term_in_text(token, combined))
        if token_hits >= 2:
            hits += 1
    return round((hits / len(responsibilities)) * 100, 1)


def _education_alignment(requirements: list[str], resume_text: str) -> float:
    if not requirements:
        return 100.0
    edu_terms = ["bachelor", "master", "phd", "b.tech", "b.e.", "m.tech", "degree", "computer science"]
    resume_lower = resume_text.lower()
    if any(term in resume_lower for term in edu_terms):
        return 100.0
    return 50.0


def _experience_alignment(requirements: list[str], resume_text: str, profile_years: int | None) -> float:
    if not requirements:
        return 80.0
    req_text = " ".join(requirements).lower()
    nums = [int(n) for n in re.findall(r"(\d+)\+?\s*(?:years|yrs)", req_text)]
    if not nums:
        return 75.0
    required_years = max(nums)
    if profile_years is not None:
        return 100.0 if profile_years >= required_years else round((profile_years / required_years) * 100, 1)
    if re.search(r"\b\d+\s*(?:years|yrs)\b", resume_text, re.I):
        return 80.0
    return 60.0


def _role_alignment(job_title: str, target_role: str, resume_text: str) -> float:
    title_lower = job_title.lower()
    role_lower = target_role.lower()
    score = 50.0
    if any(word in title_lower for word in role_lower.split() if len(word) > 3):
        score += 25.0
    if term_in_text(role_lower.split()[0], resume_text):
        score += 25.0
    return min(100.0, score)


def _keyword_coverage(parsed_jd: ParsedJD, resume_text: str, evidence: CandidateEvidence) -> float:
    terms = [kw.term for kw in parsed_jd.keywords]
    return _coverage(terms, resume_text, evidence)


def score_ats_alignment(
    parsed_jd: ParsedJD,
    evidence: CandidateEvidence,
    resume_text: str,
    job_title: str,
    target_role: str,
    profile_years: int | None = None,
) -> ATSBreakdown:
    required_cov = _coverage(parsed_jd.required_skills, resume_text, evidence)
    preferred_cov = _coverage(parsed_jd.preferred_skills, resume_text, evidence)
    resp_align = _responsibility_alignment(parsed_jd.responsibilities, resume_text, evidence)
    edu_align = _education_alignment(parsed_jd.education_requirements, resume_text)
    exp_align = _experience_alignment(parsed_jd.experience_requirements, resume_text, profile_years)
    keyword_cov = _keyword_coverage(parsed_jd, resume_text, evidence)
    role_align = _role_alignment(job_title, target_role, resume_text)

    overall = round(
        required_cov * 0.25
        + preferred_cov * 0.15
        + resp_align * 0.20
        + exp_align * 0.15
        + edu_align * 0.05
        + keyword_cov * 0.10
        + role_align * 0.10,
        1,
    )

    return ATSBreakdown(
        overall=overall,
        required_skill_coverage=required_cov,
        preferred_skill_coverage=preferred_cov,
        responsibility_alignment=resp_align,
        experience_alignment=exp_align,
        education_alignment=edu_align,
        keyword_coverage=keyword_cov,
        role_alignment=role_align,
    )


def score_from_gaps(report: list[GapItem], parsed_jd: ParsedJD) -> float:
    missing = len(gaps_missing(report))
    total = max(len(report), 1)
    return round(max(0.0, 100.0 - (missing / total) * 100), 1)
