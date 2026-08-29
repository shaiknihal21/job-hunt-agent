from app.models.profile import Profile, Resume
from app.services.resume.jd_parser import parse_job_description
from app.services.resume.tech_terms import TECH_TERMS, normalize_term, term_in_text
from app.services.resume.types import CandidateEvidence, ParsedJD


def _extract_resume_terms(resume_text: str) -> list[str]:
    found = []
    for term in TECH_TERMS:
        if term_in_text(term, resume_text):
            found.append(normalize_term(term))
    return sorted(set(found))


def build_candidate_evidence(profile: Profile, master_resume: Resume, parsed_jd: ParsedJD | None = None) -> CandidateEvidence:
    resume_text = master_resume.parsed_text or ""
    profile_skills = [normalize_term(s) for s in (profile.skills or [])]
    resume_terms = _extract_resume_terms(resume_text)

    verified = sorted(set(profile_skills + resume_terms))
    verified_text = "\n".join(filter(None, [resume_text, ", ".join(profile_skills)]))

    return CandidateEvidence(
        name=profile.name,
        role=profile.role,
        profile_skills=profile_skills,
        resume_text=resume_text,
        verified_terms=verified,
        verified_text=verified_text.lower(),
    )
