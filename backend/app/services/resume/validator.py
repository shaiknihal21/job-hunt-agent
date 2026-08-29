from app.config import settings
from app.models.profile import Job, Profile
from app.services.resume.gap_analyzer import gaps_missing
from app.services.resume.tech_terms import term_in_text
from app.services.resume.types import ATSBreakdown, CandidateEvidence, GapItem, ParsedJD, TailoredContent


def validate_resume(
    content: TailoredContent,
    evidence: CandidateEvidence,
    parsed_jd: ParsedJD,
    gap_report: list[GapItem],
    ats_after: ATSBreakdown,
    fact_check_passed: bool,
    fact_check_issues: list[str],
    job: Job,
    profile: Profile,
) -> tuple[str, list[str]]:
    errors: list[str] = []

    if not fact_check_passed:
        errors.extend(fact_check_issues)

    for term in gaps_missing(gap_report):
        skill_blob = " ".join(content.skills_reordered + content.experience_bullets).lower()
        if term_in_text(term, skill_blob):
            errors.append(f"Missing skill incorrectly added to resume: {term}")

    if not content.summary.strip():
        errors.append("Professional summary is empty")
    if len(content.skills_reordered) < 3:
        errors.append("Too few skills listed")
    if len(content.experience_bullets) < 1:
        errors.append("No experience bullets generated")

    required_supported = [
        item.term
        for item in gap_report
        if item.term in parsed_jd.required_skills
        and item.status.value in {"MATCHED", "SUPPORTED_BUT_NOT_EMPHASIZED"}
    ]
    skill_blob = " ".join(content.skills_reordered + content.experience_bullets).lower()
    missing_required = [term for term in required_supported if not term_in_text(term, skill_blob)]
    if len(missing_required) > 2:
        errors.append(f"Required supported skills not emphasized: {', '.join(missing_required[:5])}")

    if profile.email and profile.email not in (evidence.resume_text + profile.email):
        pass  # contact may be added at render time

    if len(content.summary.split()) > 120:
        errors.append("Professional summary too long")

    keyword_blob = " ".join(content.skills_reordered + content.experience_bullets).lower()
    repeated = [skill for skill in content.skills_reordered if keyword_blob.count(skill.lower()) > 3]
    if repeated:
        errors.append(f"Possible keyword stuffing: {', '.join(repeated[:3])}")

    if ats_after.overall < settings.auto_apply_min_ats_score:
        errors.append(f"ATS alignment score too low: {ats_after.overall} (need ≥{settings.auto_apply_min_ats_score})")

    if job.title and not any(word.lower() in content.summary.lower() for word in job.title.split()[:3] if len(word) > 3):
        errors.append("Professional summary not aligned to job title")

    status = "application_ready" if not errors else "needs_review"
    return status, errors
