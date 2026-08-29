import re

from app.services.resume.tech_terms import normalize_term, term_in_text
from app.services.resume.types import CandidateEvidence, TailoredContent


def _extract_metrics(text: str) -> set[str]:
    return set(re.findall(r"\b\d+(?:\.\d+)?%|\b\d+x\b|\$\d+", text.lower()))


def _extract_companies(text: str) -> set[str]:
    return set(re.findall(r"\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2}\b", text))


def verify_tailored_content(content: TailoredContent, evidence: CandidateEvidence) -> tuple[bool, list[str]]:
    issues: list[str] = []
    master_text = evidence.resume_text.lower()
    verified = evidence.verified_text

    for skill in content.skills_reordered:
        norm = normalize_term(skill)
        if not (term_in_text(norm, master_text) or term_in_text(norm, verified) or any(term_in_text(norm, s) for s in evidence.profile_skills)):
            issues.append(f"Skill not verified in candidate evidence: {skill}")

    combined_output = " ".join(content.experience_bullets + content.projects + [content.summary]).lower()
    master_metrics = _extract_metrics(evidence.resume_text)
    output_metrics = _extract_metrics(combined_output)
    invented_metrics = output_metrics - master_metrics
    if invented_metrics:
        issues.append(f"Invented metrics detected: {', '.join(sorted(invented_metrics))}")

    master_companies = _extract_companies(evidence.resume_text)
    output_companies = _extract_companies(" ".join(content.experience_bullets + content.projects))
    invented_companies = {c for c in output_companies if c not in master_companies and len(c) > 4}
    common_words = {"Python", "Java", "Machine", "Learning", "Software", "Engineer", "Developer", "Senior", "Junior"}
    invented_companies -= common_words
    if invented_companies:
        issues.append(f"Possible invented employers/entities: {', '.join(sorted(invented_companies))}")

    return len(issues) == 0, issues
